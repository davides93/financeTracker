import type { RevolutSnapshot } from './RevolutInvestments'
import type { Report } from './portfolioReport'

export type Quote = { broker_ticker: string; isin: string; ticker: string; market: string; currency: string; price: number; source: string }
export type QuoteFile = { as_of: string; quotes: Quote[] }
export type Valuation = { as_of: string; total_eur: number; rows: (Quote & { quantity: number; value_eur: number })[]; cash_eur: number; missing: string[]; blockers: string[] }
const day = 86400000
function validDate(value: string) {
  return /^\d{4}-\d{2}-\d{2}$/.test(value) && Number.isFinite(Date.parse(value)) && new Date(value).toISOString().slice(0, 10) === value
}
export function parseQuotes(text: string, today = new Date().toISOString().slice(0, 10)): QuoteFile {
  if (text.length > 500000) throw new Error('File quotazioni troppo grande.')
  const file = JSON.parse(text) as QuoteFile
  if (!file || typeof file.as_of !== 'string' || !validDate(file.as_of) || file.as_of > today || !Array.isArray(file.quotes) || file.quotes.length > 500) throw new Error('Data o elenco quotazioni non valido.')
  const keys = new Set<string>()
  for (const q of file.quotes) {
    if (!q || ['broker_ticker', 'isin', 'ticker', 'market', 'currency', 'source'].some(k => typeof q[k as keyof Quote] !== 'string' || !String(q[k as keyof Quote]).trim() || String(q[k as keyof Quote]).length > 500) || !/^[A-Z]{2}[A-Z0-9]{9}[0-9]$/.test(q.isin) || !/^[A-Z0-9]{4}$/.test(q.market) || q.currency !== 'EUR' || !Number.isFinite(q.price) || q.price <= 0) throw new Error('Quotazione non valida: servono ISIN, ticker, MIC, prezzo positivo e valuta EUR.')
    if (!/^https:\/\//.test(q.source)) throw new Error('Indica una fonte HTTPS verificabile per ogni prezzo.')
    const url = new URL(q.source)
    if (url.username || url.password) throw new Error('La fonte non deve contenere credenziali.')
    const key = `${q.broker_ticker}:${q.currency}`
    if (keys.has(key)) throw new Error('Associazione duplicata per ticker e valuta.')
    keys.add(key)
  }
  return file
}
export function valueRevolut(snapshot: RevolutSnapshot, quotes: QuoteFile, today = new Date().toISOString().slice(0, 10)): Valuation {
  const blockers: string[] = []
  if (quotes.as_of < snapshot.last_transaction.slice(0, 10)) blockers.push('Le quotazioni precedono gli ultimi movimenti.')
  if (Date.parse(today) - Date.parse(quotes.as_of) > 7 * day) blockers.push('Quotazioni più vecchie di sette giorni: aggiornare il file.')
  if (snapshot.warnings.length) blockers.push('Corporate action o variazioni anomale da riconciliare nello storico.')
  const missing: string[] = []
  const rows: Valuation['rows'] = []
  const seen = new Set<string>()
  for (const p of snapshot.positions.filter(p => p.open)) {
    const q = quotes.quotes.find(q => q.broker_ticker === p.broker_ticker && q.currency === p.currency)
    const quantity = Number(p.quantity)
    if (!q || !Number.isFinite(quantity) || quantity <= 0) { missing.push(`${p.broker_ticker} (${p.currency})`); continue }
    const key = `${q.isin}:${q.market}`
    if (seen.has(key)) blockers.push('Più posizioni associate allo stesso ISIN e mercato: riconciliare.')
    seen.add(key)
    rows.push({ ...q, quantity, value_eur: quantity * q.price })
  }
  let cash_eur = 0
  for (const [currency, amount] of Object.entries(snapshot.cash)) {
    const cash = Number(amount)
    if (!Number.isFinite(cash)) blockers.push('Cassa non valida.')
    else if (currency !== 'EUR' && cash !== 0) blockers.push(`Cambio ${currency}/EUR non disponibile.`)
    else if (currency === 'EUR') cash_eur += cash
  }
  if (missing.length) blockers.push('Copertura incompleta delle posizioni.')
  const total_eur = Math.round((cash_eur + rows.reduce((sum, row) => sum + row.value_eur, 0)) * 100) / 100
  if (!Number.isFinite(total_eur) || total_eur < 0) blockers.push('Totale non valido.')
  return { as_of: quotes.as_of, total_eur, rows, cash_eur, missing, blockers }
}
function monthDate(start: Date, months: number) {
  const date = new Date(Date.UTC(start.getUTCFullYear(), start.getUTCMonth() + months, 1))
  const last = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth() + 1, 0)).getUTCDate()
  date.setUTCDate(Math.min(start.getUTCDate(), last))
  return date.toISOString().slice(0, 10)
}
// Same convention as forecasting/scenarios.py: ACT/365.25, contributions at day end.
export function applyValuation(report: Report, value: Valuation): Report {
  if (value.blockers.length || !report.config.accounts.revolut) throw new Error('Valorizzazione incompleta o conto Revolut assente.')
  if (Object.values(report.config.accounts).some(a => a.as_of > value.as_of)) throw new Error('La data delle quotazioni precede un conto nel rapporto.')
  const accounts = { ...report.config.accounts, revolut: { ...report.config.accounts.revolut, initial_eur: value.total_eur, as_of: value.as_of } }
  const start = new Date(value.as_of)
  const end = monthDate(start, 60)
  const checkpoints = new Set(Array.from({ length: 61 }, (_, i) => monthDate(start, i)))
  const events: Record<string, Record<string, number>> = {}
  for (const [key, account] of Object.entries(accounts)) {
    if ([account.initial_eur, account.monthly_eur ?? 0, account.weekly_eur ?? 0].some(n => !Number.isFinite(n) || n < 0)) throw new Error('Saldo o PAC non valido.')
    events[key] = {}
    for (let i = 1; i <= 60; i++) events[key][monthDate(start, i)] = account.monthly_eur ?? 0
    for (let t = +start + 7 * day; t <= Date.parse(end); t += 7 * day) {
      const date = new Date(t).toISOString().slice(0, 10)
      events[key][date] = (events[key][date] ?? 0) + (account.weekly_eur ?? 0)
    }
    for (const [date, amount] of Object.entries(events[key])) if (amount) checkpoints.add(date)
  }
  const results = Object.fromEntries(Object.entries(report.results).map(([name, scenario]) => {
    const balances = Object.fromEntries(Object.entries(accounts).map(([k, a]) => [k, a.initial_eur]))
    const initial = Object.values(balances).reduce((a, b) => a + b, 0)
    let contributed = 0, previous = +start
    for (const key of Object.keys(accounts)) if (!Number.isFinite(scenario.rates[key]) || scenario.rates[key] <= -1) throw new Error('Tasso mancante o non valido.')
    const path = [...checkpoints].sort().map(date => {
      const dt = (Date.parse(date) - previous) / day / 365.25
      for (const key of Object.keys(accounts)) {
        const payment = events[key][date] ?? 0
        balances[key] = balances[key] * (1 + scenario.rates[key]) ** dt + payment
        contributed += payment
      }
      previous = Date.parse(date)
      const total_eur = Object.values(balances).reduce((a, b) => a + b, 0)
      if (!Number.isFinite(total_eur)) throw new Error('Scenario fuori intervallo.')
      return { date, total_eur, capital_without_returns_eur: initial + contributed }
    })
    return [name, { rates: scenario.rates, path, final: path[path.length - 1] }]
  }))
  return { ...report, config: { accounts }, results }
}
