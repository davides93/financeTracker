import { nativeStorage } from './vaultStorage'
import { LocalCopilot } from './LocalCopilot'
import { useRef, useState } from 'react'
import { parsePortfolioReport } from './portfolioReport'
import type { Report } from './portfolioReport'
import './Portfolio.css'

const eur = new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR' })
const percent = new Intl.NumberFormat('it-IT', { style: 'percent', maximumFractionDigits: 2 })
const date = (iso: string) => iso.split('-').reverse().join('/')
const labels: Record<string, string> = { directa: 'Directa', revolut: 'Revolut', esempio: 'Esempio', avverso: 'Avverso', favorevole: 'Favorevole', invariato: 'Rendimento zero' }

export function Portfolio({ showForecast, report, save }: {
  showForecast: boolean; report?: Report; save: (report: Report) => Promise<void>
}) {
  const [preview, setPreview] = useState<Report>()
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const saving = useRef(false)
  const [selected, setSelected] = useState('esempio')
  async function importReport(read: () => Promise<string>, previewOnly = false) {
    if (saving.current) return
    saving.current = true
    setBusy(true)
    setError('')
    try {
      const next = parsePortfolioReport(await read())
      if (previewOnly) setPreview(next)
      else { await save(next); setPreview(undefined) }
    }
    catch (err) { setError(err instanceof Error ? err.message : 'Importazione non riuscita.') }
    finally { saving.current = false; setBusy(false) }
  }
  const accounts = Object.entries(report?.config.accounts ?? {})
  const scenarioKey = report && Object.hasOwn(report.results, selected) ? selected : Object.keys(report?.results ?? {})[0]
  const scenario = report?.results[scenarioKey]
  const initial = accounts.reduce((sum, [, account]) => sum + account.initial_eur, 0)
  const path = scenario?.path ?? []
  const max = Math.max(1, ...path.map(p => Math.max(p.total_eur, p.capital_without_returns_eur)))
  const line = (key: 'total_eur' | 'capital_without_returns_eur') => path.map((p, i) =>
    `${16 + i * 568 / Math.max(1, path.length - 1)},${186 - p[key] * 166 / max}`
  ).join(' ')

  return <div className="investment">
    <header className="topbar"><div><h1>{showForecast ? 'Previsioni' : 'Portafoglio'}</h1><p>Rapporto salvato nell’archivio privato</p></div></header>
    {!showForecast && <article className="panel investment-panel">
      <h2>Importa rapporto investimenti</h2>
      <p>Carica il rapporto JSON generato dal monitor Directa e Revolut. L’importazione sostituisce il rapporto precedente nell’archivio.</p>
      <form onSubmit={event => {
        event.preventDefault()
        const file = new FormData(event.currentTarget).get('report')
        void importReport(async () => {
          if (!(file instanceof File) || !file.size || file.size > 3_000_000) throw new Error('Seleziona un rapporto JSON fino a 3 MB.')
          return file.text()
        })
      }}>
        <label>Rapporto JSON <input name="report" type="file" accept=".json,application/json" required /></label>
        <button className="connect" disabled={busy}>Salva rapporto</button>
      </form>
      <button className="quiet-button" disabled={busy || nativeStorage} onClick={() => void importReport(async () => {
        const response = await fetch('/api/portfolio')
        if (!response.ok) throw new Error('Rapporto sul server locale indisponibile.')
        return response.text()
      })}>Importa dal monitor locale</button>
    </article>}
    {!showForecast && <article className="panel investment-panel">
      <h2>Importa CSV patrimoniale Directa</h2>{nativeStorage && <p>Motore CSV non ancora incluso nel pacchetto. Puoi importare il rapporto JSON e il backup cifrato dal browser.</p>}
      <p>Usa l’export PatrimonioTotale. L’anteprima aggiorna Directa e usa la stima Revolut e i PAC del monitor locale.</p>
      <form onSubmit={event => {
        event.preventDefault()
        const file = new FormData(event.currentTarget).get('directa')
        setPreview(undefined)
        void importReport(async () => {
          if (!(file instanceof File) || !file.size || file.size > 2_000_000) throw new Error('Seleziona un CSV fino a 2 MB.')
          const response = await fetch('/api/directa-preview', {
            method: 'POST', headers: { 'Content-Type': 'text/csv' }, body: await file.arrayBuffer(),
          })
          if (!response.ok) throw new Error('Verifica il formato PatrimonioTotale e la disponibilità del monitor locale.')
          return response.text()
        }, true)
      }}>
        <label>CSV Directa <input type="file" name="directa" accept=".csv,text/csv" required /></label>
        <button className="connect" disabled={busy || nativeStorage}>Analizza CSV Directa</button>
      </form>
      {preview?.directa_history && <div>
        <p>Anteprima · Directa {eur.format(preview.config.accounts.directa.initial_eur)} al {date(preview.directa_history.through)} · {preview.directa_history.valuations} valorizzazioni · {preview.directa_history.movements.length} movimenti</p>
        <button className="connect" disabled={busy} onClick={() => {
          const payload = { ...preview, config: { ...preview.config, currency: 'EUR' } }
          void importReport(async () => JSON.stringify(payload))
        }}>Conferma aggiornamento Directa</button>
        <button className="quiet-button" disabled={busy} onClick={() => setPreview(undefined)}>Scarta anteprima</button>
      </div>}
    </article>}
    {error && <p role="alert">{error}</p>}
    {!report && <p>Nessun rapporto nell’archivio. Caricalo da Portafoglio.</p>}
    {report && <>
      {!showForecast && <>
        <article className="panel investment-panel"><h2>Patrimonio complessivo</h2><strong className="investment-total">{eur.format(initial)}</strong><p>Somma delle ultime valorizzazioni disponibili, con date diverse.</p></article>
        <div className="investment-accounts">{accounts.map(([key, account]) => <article className="panel investment-panel" key={key}>
          <h2>{labels[key] ?? key}</h2><strong className="investment-total">{eur.format(account.initial_eur)}</strong>
          <p>{key === 'revolut' ? 'Stima' : 'Valorizzazione'} al {date(account.as_of)}</p>
          <p>PAC di {eur.format(account.monthly_eur ?? account.weekly_eur ?? 0)} {account.monthly_eur !== undefined ? 'al mese' : 'alla settimana'}</p>
        </article>)}</div>
        {report.directa_history && <details className="panel investment-panel">
          <summary>Storico Directa · {report.directa_history.movements.length} movimenti</summary>
          <p>Valorizzazioni dal {date(report.directa_history.from)} al {date(report.directa_history.through)}.</p>
          <ul>{report.directa_history.movements.map((m, index) => <li key={index}>{date(m.date)} · {m.description} · {eur.format(m.amount)}</li>)}</ul>
        </details>}
        {report.audit.snapshot_cash_difference_eur !== null && report.audit.snapshot_cash_difference_eur !== 0 && <p>Da riconciliare: {eur.format(report.audit.snapshot_cash_difference_eur)} di differenza di liquidità tra PDF e CSV Directa.</p>}
    </>}
      {scenario && <article className="panel investment-panel">
        <div className="panel-heading"><div><h2>Scenari a cinque anni</h2><p>Ipotesi di rendimento con i PAC configurati</p></div>
          <label>Scenario <select aria-label="Scenario" value={scenarioKey} onChange={event => setSelected(event.target.value)}>{Object.keys(report.results).map(key => <option key={key} value={key}>{labels[key] ?? key}</option>)}</select></label>
        </div>
        <strong className="investment-total">{eur.format(scenario.final.total_eur)}</strong><p>Valore ipotetico al {date(scenario.final.date)} · {Object.entries(scenario.rates).map(([key, rate]) => `${labels[key] ?? key} ${percent.format(rate)} annuo`).join(' · ')}</p>
        <svg viewBox="0 0 600 200" role="img" aria-label="Andamento dello scenario e del capitale con rendimento zero">
          <polyline points={line('capital_without_returns_eur')} fill="none" stroke="#737b89" strokeWidth="2" strokeDasharray="6 4" />
          <polyline points={line('total_eur')} fill="none" stroke="#157463" strokeWidth="3" />
        </svg>
        <p>Linea tratteggiata · Capitale iniziale e versamenti senza rendimento ({eur.format(scenario.final.capital_without_returns_eur)})</p>
        <p>Scenari deterministici prima delle imposte personali. Il modello AI rimane in sperimentazione.</p>
      </article>}
      <LocalCopilot context={JSON.stringify({
        ...(!showForecast && { conti: accounts, totale: initial }),
        scenario: scenarioKey,
        ipotesi: scenario?.rates,
        risultatoIpotetico: scenario?.final,
      })} />
    </>}
  </div>
}
