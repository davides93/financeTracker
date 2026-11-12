import { execFile } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { readFile } from 'node:fs/promises'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import type { Plugin } from 'vite'

function localPortfolio(): Plugin {
  const source = new URL('./forecasting/outputs/combined-five-year/scenarios.json', import.meta.url)
  return {
    name: 'local-portfolio',
    configureServer(server) {
      let generating = false
      server.middlewares.use('/api/local-copilot', async (req, res) => {
        const origin = req.headers.origin
        const host = req.headers.host
        if (req.method !== 'POST' || !host?.startsWith('127.0.0.1:') ||
            origin !== `http://${host}` || req.headers['content-type'] !== 'application/json') {
          res.writeHead(403).end()
          return
        }
        if (generating) { res.writeHead(429).end(); return }
        generating = true
        res.setHeader('Cache-Control', 'no-store')
        res.setHeader('Content-Type', 'application/json')
        try {
          const chunks: Buffer[] = []
          let size = 0
          for await (const chunk of req) {
            size += chunk.length
            if (size > 32_768) { res.writeHead(413).end(); return }
            chunks.push(chunk)
          }
          const data = JSON.parse(Buffer.concat(chunks).toString())
          if (typeof data.question !== 'string' || data.question.length > 1000 ||
              typeof data.context !== 'string' || data.context.length > 5000) {
            res.writeHead(400).end()
            return
          }
          const binary = fileURLToPath(new URL('./native/apple/.build/local-copilot', import.meta.url))
          await new Promise<void>(resolve => {
            const child = execFile(binary, { timeout: 30_000, maxBuffer: 65536 }, (error, stdout) => {
              if (error) res.writeHead(503).end(JSON.stringify({ status: 'unavailable' }))
              else res.end(stdout)
              resolve()
            })
            child.stdin?.on('error', () => {})
            child.stdin?.end(JSON.stringify({ question: data.question, context: data.context }))
          })
        } catch {
          res.writeHead(400).end()
        } finally {
          generating = false
        }
      })
      const previewImport = (route: string, module: string, contentType: string, limit: number) => {
        server.middlewares.use(route, async (req, res) => {
          const host = req.headers.host
          if (req.method !== 'POST' || !host?.startsWith('127.0.0.1:') ||
              req.headers.origin !== `http://${host}` || req.headers['content-type'] !== contentType) {
            res.writeHead(403).end()
            return
          }
          res.setHeader('Cache-Control', 'no-store')
          res.setHeader('Content-Type', 'application/json')
          try {
            const chunks: Buffer[] = []
            let size = 0
            for await (const chunk of req) {
              size += chunk.length
              if (size > limit) { res.writeHead(413).end(); return }
              chunks.push(chunk)
            }
            const python = fileURLToPath(new URL('./forecasting/.venv/bin/python', import.meta.url))
            const cwd = fileURLToPath(new URL('.', import.meta.url))
            const child = execFile(python, ['-m', module], { cwd, timeout: 15_000, maxBuffer: 3_000_000 }, (error, output) => {
              if (error) res.writeHead(422).end(JSON.stringify({ error: 'Estratto non valido o motore locale non disponibile.' }))
              else res.end(output)
            })
            child.stdin?.on('error', () => {})
            child.stdin?.end(Buffer.concat(chunks))
          } catch {
            res.writeHead(400).end()
          }
        })
      }
      previewImport('/api/directa-preview', 'forecasting.directa_app', 'text/csv', 2_000_000)
      previewImport('/api/revolut-preview', 'forecasting.revolut_app', 'application/json', 4_000_000)
      server.middlewares.use('/api/portfolio', async (req, res) => {
        if (req.method !== 'GET') {
          res.writeHead(405, { Allow: 'GET' }).end()
          return
        }
        res.setHeader('Cache-Control', 'no-store')
        res.setHeader('Content-Type', 'application/json')
        try {
          res.end(await readFile(source, 'utf8'))
        } catch {
          res.writeHead(503).end(JSON.stringify({ error: 'Rapporto locale non disponibile' }))
        }
      })
    },
  }
}

export default defineConfig({
  plugins: [react(), localPortfolio()],
  server: { host: '127.0.0.1', fs: { deny: ['.env', '.env.*', '*.{crt,pem}', '**/.git/**', '**/forecasting/**'] } },
})
