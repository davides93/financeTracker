import { useState } from 'react'
import type { RevolutSnapshot } from './RevolutInvestments'
import type { Report } from './portfolioReport'
import { applyValuation, parseQuotes, valueRevolut } from './revolutPricing'
import type { Valuation } from './revolutPricing'
export type SavedValuation = { value: Valuation; previousReport: Report; snapshot: RevolutSnapshot; confirmedAt: string }
const eur = (n: number) => new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR' }).format(n)
export function RevolutValuation({ snapshot, report, saved, save }: {
  snapshot?: RevolutSnapshot; report?: Report; saved?: SavedValuation
  save: (report: Report, saved: SavedValuation) => Promise<void>
}) {
  const [preview, setPreview] = useState<{ value: Valuation; snapshot: RevolutSnapshot; report: Report }>()
  const [checked, setChecked] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const stale = preview && (preview.snapshot !== snapshot || preview.report !== report)
  return <article className="panel investment-panel">
    <h2>Valorizza le posizioni Revolut</h2>
    <p>Import offline di quotazioni JSON in EUR. Ogni prezzo deve avere data, ISIN, ticker, mercato MIC e fonte HTTPS. Nessuna richiesta di mercato automatica. Prezzi di oltre sette giorni e anomalie nello storico bloccano la conferma.</p>
    {!snapshot || !report ? <p>Salva prima lo storico Revolut e un rapporto investimenti.</p> : <form onSubmit={event => {
      event.preventDefault()
      const file = new FormData(event.currentTarget).get('quotes')
      setPreview(undefined); setChecked(false); setError(''); setBusy(true)
      void (async () => {
        try {
          if (!(file instanceof File) || !file.size || file.size > 500000) throw new Error('Seleziona un JSON fino a 500 KB.')
          const value = valueRevolut(snapshot, parseQuotes(await file.text()))
          setPreview({ value, snapshot, report })
        } catch (e) { setError(e instanceof Error ? e.message : 'File non valido.') }
        finally { setBusy(false) }
      })()
    }}>
      <label>Quotazioni JSON <input name="quotes" type="file" accept=".json,application/json" required disabled={busy} /></label>
      <button className="connect" disabled={busy}>Anteprima valorizzazione</button>
    </form>}
    {error && <p role="alert">{error}</p>}
    {preview && <>
      <h3>Anteprima · {preview.value.as_of}</h3>
      <p>Copertura {preview.value.rows.length}/{preview.snapshot.positions.filter(p => p.open).length} posizioni · cassa {eur(preview.value.cash_eur)} · {preview.value.blockers.length ? 'Subtotale coperto' : 'Totale'} {eur(preview.value.total_eur)}</p>
      <p>Stima attuale: {eur(preview.report.config.accounts.revolut?.initial_eur ?? 0)}. Confermando, gli scenari ripartono dalla data delle quotazioni per cinque anni, con i PAC e tassi del rapporto. Gli altri conti mantengono le ultime valorizzazioni disponibili.</p>
      <ul>{preview.value.rows.map(row => <li key={`${row.broker_ticker}:${row.currency}`}>{row.broker_ticker} → {row.isin} · {row.ticker} / {row.market} · {row.quantity} × {eur(row.price)} = {eur(row.value_eur)} · <a href={row.source} target="_blank" rel="noreferrer">Fonte dichiarata</a></li>)}</ul>
      {preview.value.missing.length > 0 && <p>Mancanti: {preview.value.missing.join(', ')}</p>}
      <ul>{preview.value.blockers.map((b, i) => <li key={i}>{b}</li>)}</ul>
      {stale && <p role="alert">Storico o rapporto cambiato: genera una nuova anteprima.</p>}
      <label><input type="checkbox" checked={checked} onChange={e => setChecked(e.target.checked)} /> Ho verificato fonti, ISIN, mercato, quantità, cassa e corporate action. Lo storico è completo fino alla data delle quotazioni, con posizioni e cassa iniziali a zero.</label>
      <button className="connect" disabled={busy || !checked || !!stale || !!preview.value.blockers.length} onClick={() => {
        setBusy(true); setError('')
        void (async () => {
          try {
            // Compute only after explicit confirmation; persist report and evidence atomically.
            const next = applyValuation(preview.report, preview.value)
            await save(next, { value: preview.value, previousReport: preview.report, snapshot: preview.snapshot, confirmedAt: new Date().toISOString() })
            setPreview(undefined); setChecked(false)
          } catch (e) { setError(e instanceof Error ? e.message : 'Salvataggio non riuscito.') }
          finally { setBusy(false) }
        })()
      }}>Conferma valorizzazione e ricalcola scenari</button>
      <button className="quiet-button" disabled={busy} onClick={() => setPreview(undefined)}>Scarta valorizzazione</button>
    </>}
    {saved && <details><summary>Ultima valorizzazione confermata · {saved.value.as_of} · {eur(saved.value.total_eur)}</summary>
      <p>Confermata il {saved.confirmedAt}. Stima precedente conservata: {eur(saved.previousReport.config.accounts.revolut.initial_eur)}. L’evidenza si riferisce allo storico presente alla conferma; import successivi richiedono una nuova valorizzazione.</p>
      <ul>{saved.value.rows.map(r => <li key={`${r.broker_ticker}:${r.currency}`}>{r.isin} · {r.market} · {r.quantity} quote · {eur(r.price)} · <a href={r.source} target="_blank" rel="noreferrer">Fonte dichiarata</a></li>)}</ul>
    </details>}
  </article>
}
