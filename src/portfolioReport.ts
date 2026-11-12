type Account = { initial_eur: number; as_of: string; monthly_eur?: number; weekly_eur?: number }
type Point = { total_eur: number; date: string; capital_without_returns_eur: number }
type Scenario = { final: Point; path: Point[]; rates: Record<string, number> }
type DirectaHistory = { valuations: number; from: string; through: string; movements: { date: string; description: string; amount: number }[] }
export type Report = { config: { accounts: Record<string, Account> }; results: Record<string, Scenario>; audit: { snapshot_cash_difference_eur: number | null }; directa_history?: DirectaHistory }

function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('Struttura del rapporto non valida.')
  return value as Record<string, unknown>
}
function number(value: unknown) {
  if (typeof value !== 'number' || !Number.isFinite(value)) throw new Error('Importo o tasso non valido.')
  return value
}
function date(value: unknown) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) throw new Error('Data del rapporto non valida.')
  const timestamp = new Date(value)
  if (!Number.isFinite(+timestamp) || timestamp.toISOString().slice(0, 10) !== value) throw new Error('Data del rapporto non valida.')
  return value
}
function entries(value: unknown, max: number) {
  const items = Object.entries(record(value))
  if (!items.length || items.length > max || items.some(([key]) => !/^[a-z][a-z0-9_-]{0,39}$/.test(key))) {
    throw new Error('Conti o scenari non validi.')
  }
  return items
}
function point(value: unknown): Point {
  const row = record(value)
  return { date: date(row.date), total_eur: number(row.total_eur), capital_without_returns_eur: number(row.capital_without_returns_eur) }
}

export function parsePortfolioReport(text: string): Report {
  if (text.length > 3_000_000) throw new Error('Rapporto troppo grande.')
  const input = record(JSON.parse(text))
  const config = record(input.config)
  if (config.currency !== 'EUR') throw new Error('Il rapporto deve essere in euro.')
  const accounts = Object.fromEntries(entries(config.accounts, 25).map(([key, raw]) => {
    const a = record(raw)
    return [key, {
      initial_eur: number(a.initial_eur), as_of: date(a.as_of),
      monthly_eur: a.monthly_eur === undefined ? undefined : number(a.monthly_eur),
      weekly_eur: a.weekly_eur === undefined ? undefined : number(a.weekly_eur),
    }]
  }))
  const results = Object.fromEntries(entries(input.results, 25).map(([key, raw]) => {
    const scenario = record(raw)
    if (!Array.isArray(scenario.path) || !scenario.path.length || scenario.path.length > 4000) throw new Error('Serie dello scenario non valida.')
    const path = scenario.path.map(point)
    const final = point(scenario.final)
    if (path.some((row, i) => i > 0 && row.date <= path[i - 1].date) ||
        JSON.stringify(path.at(-1)) !== JSON.stringify(final)) throw new Error('Serie dello scenario incoerente.')
    const rates = Object.fromEntries(entries(scenario.rates, 25).map(([account, rate]) => {
      if (!Object.hasOwn(accounts, account)) throw new Error('Tasso associato a un conto sconosciuto.')
      return [account, number(rate)]
    }))
    return [key, { path, final, rates }]
  }))
  const difference = record(input.audit).snapshot_cash_difference_eur
  let directa_history: DirectaHistory | undefined
  if (input.directa_history !== undefined) {
    const history = record(input.directa_history)
    if (!Array.isArray(history.movements) || history.movements.length > 10000) throw new Error('Storico Directa non valido.')
    directa_history = {
      valuations: number(history.valuations), from: date(history.from), through: date(history.through),
      movements: history.movements.map(raw => {
        const movement = record(raw)
        if (typeof movement.description !== 'string' || movement.description.length > 1000) throw new Error('Descrizione non valida.')
        return { date: date(movement.date), description: movement.description, amount: number(movement.amount) }
      }),
    }
  }
  return { config: { accounts }, results, directa_history, audit: { snapshot_cash_difference_eur: difference == null ? null : number(difference) } }
}
