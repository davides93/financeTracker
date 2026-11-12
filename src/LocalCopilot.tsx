import { nativeStorage } from './vaultStorage'
import { useState } from 'react'

export function LocalCopilot({ context }: { context: string }) {
  const [messages, setMessages] = useState<{ question: string; answer: string }[]>([])
  const [busy, setBusy] = useState(false)
  return <article className="panel investment-panel">
    <h2>Copilota locale</h2>
    <p>{nativeStorage ? 'Motore non ancora incluso nel pacchetto nativo. Nessun fallback cloud.' : 'Apple Intelligence · contesto della schermata · prototipo macOS'}</p>
    <div aria-live="polite">{messages.map(({ question, answer }, i) => <div key={i}><p><strong>{question}</strong></p><p>{answer}</p></div>)}</div>
    <form onSubmit={async event => {
      event.preventDefault()
      if (busy) return
      const form = event.currentTarget
      const question = String(new FormData(form).get('question') ?? '').trim()
      if (!question) return
      setBusy(true)
      form.reset()
      let answer: string
      try {
        const response = await fetch('/api/local-copilot', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ question, context: context.slice(0, 5000) }),
        })
        const result = await response.json()
        answer = response.ok && result.status === 'ok' && typeof result.answer === 'string'
          ? result.answer : 'Modello locale non disponibile o contesto troppo grande.'
      } catch {
        answer = 'Motore locale non raggiungibile.'
      } finally {
        setBusy(false)
      }
      setMessages(history => [...history, { question, answer }])
    }}>
      <label>Domanda sui dati della schermata <input name="question" required maxLength={1000} /></label>
      <button className="quiet-button" disabled={busy || nativeStorage}>{busy ? 'Elaborazione…' : 'Chiedi'}</button>
    </form>
  </article>
}
