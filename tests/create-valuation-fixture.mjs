// Synthetic offline QA vault, never real statements. Run with Node 22+.
import { writeFile } from 'node:fs/promises'
const today = new Date().toISOString().slice(0, 10)
const snapshot = { first_transaction: today, last_transaction: today, transaction_count: 1, realized_pnl_lots: 0, positions: [{ broker_ticker: 'DEMO', quantity: '2.5', currency: 'EUR', open: true }], cash: { EUR: '100' }, warnings: [], movements: [] }
const point = { date: today, total_eur: 10050, capital_without_returns_eur: 10050 }
const portfolio = { config: { accounts: { directa: { initial_eur: 10000, as_of: today, monthly_eur: 200 }, revolut: { initial_eur: 50, as_of: today, weekly_eur: 50 } } }, results: { invariato: { rates: { directa: 0, revolut: 0 }, path: [point], final: point } }, audit: { snapshot_cash_difference_eur: null } }
const ledger = { accounts: [], movements: [], spaces: [], portfolio, revolutInvestments: snapshot }
const salt = crypto.getRandomValues(new Uint8Array(16)), iv = crypto.getRandomValues(new Uint8Array(12))
const material = await crypto.subtle.importKey('raw', new TextEncoder().encode('orizzonte-demo-only'), 'PBKDF2', false, ['deriveKey'])
const key = await crypto.subtle.deriveKey({ name: 'PBKDF2', salt, iterations: 600000, hash: 'SHA-256' }, material, { name: 'AES-GCM', length: 256 }, false, ['encrypt'])
const data = await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, key, new TextEncoder().encode(JSON.stringify(ledger)))
await writeFile('tests/fixtures/valuation-vault.json', JSON.stringify({ salt: [...salt], iv: [...iv], data: [...new Uint8Array(data)] }))
const quotes = { as_of: today, quotes: [{ broker_ticker: 'DEMO', isin: 'IE0000000000', ticker: 'DEMO', market: 'XETR', currency: 'EUR', price: 40, source: 'https://example.com/synthetic-not-market-data' }] }
await writeFile('tests/fixtures/quotes.json', JSON.stringify(quotes, null, 2))
await writeFile('tests/fixtures/quotes-missing.json', JSON.stringify({ ...quotes, quotes: [] }, null, 2))
console.log('Synthetic fixtures ready; passphrase: orizzonte-demo-only')
