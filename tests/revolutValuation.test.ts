import { test } from 'node:test'
import assert from 'node:assert/strict'
import { parseQuotes, valueRevolut, applyValuation } from '../src/revolutPricing.ts'
const snapshot = { first_transaction: '2026-11-01', last_transaction: '2026-11-05', transaction_count: 1, realized_pnl_lots: 0, positions: [{ broker_ticker: 'DEMO', quantity: '2.5', currency: 'EUR', open: true }], cash: { EUR: '100' }, warnings: [], movements: [] }
const quotes = { as_of: '2026-11-06', quotes: [{ broker_ticker: 'DEMO', isin: 'IE0000000000', ticker: 'DEMO', market: 'XETR', currency: 'EUR', price: 40, source: 'https://example.com/synthetic' }] }
const report = { config: { accounts: { revolut: { initial_eur: 50, as_of: '2026-11-01', weekly_eur: 50 }, directa: { initial_eur: 10000, as_of: '2026-11-01', monthly_eur: 200 } } }, results: { invariato: { rates: { revolut: 0, directa: 0 }, path: [], final: { total_eur: 0, date: '', capital_without_returns_eur: 0 } } }, audit: { snapshot_cash_difference_eur: null } }
test('fractional positions, cash and five-year PAC; preserve source report', () => {
  const value = valueRevolut(snapshot, parseQuotes(JSON.stringify(quotes), '2026-11-06'), '2026-11-06')
  assert.equal(value.total_eur, 200)
  const result = applyValuation(report, value)
  assert.equal(result.results.invariato.final.total_eur, 35200)
  assert.equal(result.results.invariato.final.date, '2031-11-06')
  assert.equal(report.config.accounts.revolut.initial_eur, 50)
})
test('missing, stale, currency and corporate actions block updates', () => {
  for (const [s, q, today] of [
    [snapshot, { ...quotes, quotes: [] }, '2026-11-06'],
    [snapshot, quotes, '2026-11-14'],
    [{ ...snapshot, cash: { USD: '1' } }, quotes, '2026-11-06'],
    [{ ...snapshot, warnings: [{ kind: 'split' }] }, quotes, '2026-11-06'],
    [{ ...snapshot, last_transaction: '2026-11-07' }, quotes, '2026-11-07'],
  ] as const) {
    assert.throws(() => applyValuation(report, valueRevolut(s, q, today)))
  }
})
test('reject future dates, duplicate mappings, bad prices and unsafe sources', () => {
  for (const q of [ { ...quotes, as_of: '2026-11-07' }, { ...quotes, quotes: [...quotes.quotes, ...quotes.quotes] },
    ...[0, -2, null].map(price => ({ ...quotes, quotes: [{ ...quotes.quotes[0], price }] })),
    { ...quotes, quotes: [{ ...quotes.quotes[0], source: 'javascript:alert(1)' }] },
  ]) assert.throws(() => parseQuotes(JSON.stringify(q), '2026-11-06'))
})
test('growth uses ACT/365.25 and rejects missing rates', () => {
  const value = valueRevolut(snapshot, quotes, '2026-11-06')
  const single = { ...report, config: { accounts: { revolut: { initial_eur: 0, as_of: '2026-11-01' } } }, results: { growth: { ...report.results.invariato, rates: { revolut: 0.1 } } } }
  const result = applyValuation(single, value).results.growth
  const years = (Date.parse('2031-11-06') - Date.parse('2026-11-06')) / 86400000 / 365.25
  assert.ok(Math.abs(result.final.total_eur - 200 * 1.1 ** years) < 1e-8)
  assert.throws(() => applyValuation({ ...single, results: { growth: { ...single.results.growth, rates: {} } } }, value))
})
test('matches the Python engine with growth and end-of-month contributions', async () => {
  const { execFileSync } = await import('node:child_process')
  const value = { ...valueRevolut(snapshot, quotes, '2026-11-06'), as_of: '2028-01-31' }
  const base = { ...report, results: { esempio: { ...report.results.invariato, rates: { directa: 0.04, revolut: -0.02 } } } }
  const result = applyValuation(base, value)
  const config = { start_date: value.as_of, years: 5, accounts: result.config.accounts }
  const python = JSON.parse(execFileSync('python3', ['-c', 'import json,sys; from forecasting.scenarios import project; x=json.load(sys.stdin); print(json.dumps(project(x["config"],x["rates"])))'], { input: JSON.stringify({ config, rates: base.results.esempio.rates }), encoding: 'utf8' }))
  assert.equal(result.results.esempio.path.length, python.path.length)
  result.results.esempio.path.forEach((point, i) => {
    assert.equal(point.date, python.path[i].date)
    assert.ok(Math.abs(point.total_eur - python.path[i].total_eur) < 1e-7)
    assert.equal(point.capital_without_returns_eur, python.path[i].capital_without_returns_eur)
  })
})
