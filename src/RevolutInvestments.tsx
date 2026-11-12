import { nativeStorage } from './vaultStorage'
import { useRef, useState } from 'react'

export type RevolutSnapshot = {
  first_transaction: string
  last_transaction: string
  transaction_count: number
  realized_pnl_lots: number
  positions: { broker_ticker: string; quantity: string; currency: string; open: boolean }[]
  cash: Record<string, string>
  warnings: { kind: string }[]
  movements: { date: string; type: string; ticker: string; amount: string; currency: string }[]
}

export function RevolutInvestments({ snapshot, save }: {
  snapshot?: RevolutSnapshot; save: (snapshot: RevolutSnapshot) => Promise<void>
}) {
  const [preview, setPreview] = useState<RevolutSnapshot>()
  const [busy, setBusy] = useState(false)
  const pending = useRef(false)
  const [error, setError] = useState('')
  async function run(action: () => Promise<void>) {
    if (pending.current) return
    pending.current = true
    setBusy(true)
    setError('')
    try { await action() }
    catch (failure) { setError(failure instanceof Error ? failure.message : 'Operazione non riuscita.') }
    finally { pending.current = false; setBusy(false) }
  }
  const visible = preview ?? snapshot
  return <article className="panel investment-panel">
    <h2>Importa Revolut Investimenti</h2>{nativeStorage && <p>Motore Trading non ancora incluso nel pacchetto. Ripristina un backup cifrato con lo storico già importato per valorizzarlo offline.</p>}
    <p>Carica l’estratto del conto Trading e il prospetto profitti e perdite dello stesso periodo. Il motore riconcilia le vendite e ricostruisce quantità e cassa assumendo un saldo iniziale a zero.</p>
    <form onSubmit={event => {
      event.preventDefault()
      const form = new FormData(event.currentTarget)
      setPreview(undefined)
      void run(async () => {
        const account = form.get('account')
        const pnl = form.get('pnl')
        if (!(account instanceof File) || !(pnl instanceof File) || !account.size || !pnl.size || account.size + pnl.size > 2_000_000) {
          throw new Error('Seleziona entrambi i CSV, fino a 2 MB complessivi.')
        }
        const response = await fetch('/api/revolut-preview', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ account: await account.text(), pnl: await pnl.text() }),
        })
        if (!response.ok) throw new Error('Verifica il formato degli estratti, la riconciliazione delle vendite e il motore locale.')
        setPreview(await response.json() as RevolutSnapshot)
      })
    }}>
      <label>Estratto Trading CSV <input type="file" name="account" accept=".csv,text/csv" required /></label>
      <label>Profitti e perdite CSV <input type="file" name="pnl" accept=".csv,text/csv" required /></label>
      <button className="connect" disabled={busy || nativeStorage}>Analizza estratti Revolut</button>
    </form>
    {error && <p role="alert">{error}</p>}
    {visible && <>
      <p>{preview ? 'Anteprima' : 'Storico salvato'} · {visible.transaction_count} movimenti · {visible.positions.filter(p => p.open).length} posizioni aperte · {visible.realized_pnl_lots} lotti venduti riconciliati</p>
      <p>Dal {visible.first_transaction.slice(0, 10)} al {visible.last_transaction.slice(0, 10)} · cassa ricostruita {Object.entries(visible.cash).map(([currency, amount]) => `${amount} ${currency}`).join(', ') || '—'}</p>
      {visible.warnings.length > 0 && <p>{visible.warnings.length} variazioni di prezzo anomale da verificare, ad esempio per frazionamenti.</p>}
      <details><summary>Posizioni aperte</summary><ul>{visible.positions.filter(p => p.open).map(p => <li key={`${p.broker_ticker}-${p.currency}`}>{p.broker_ticker} · {p.quantity} quote · {p.currency}</li>)}</ul></details>
      <details><summary>Movimenti Revolut Investimenti</summary><ul>{visible.movements.map((m, i) => <li key={i}>{m.date.slice(0, 10)} · {m.type} {m.ticker} · {m.amount} {m.currency}</li>)}</ul></details>
      <p>Questo import salva lo storico Trading separatamente. Per aggiornare il rapporto e gli scenari usa “Valorizza le posizioni Revolut” e conferma l’anteprima delle quotazioni.</p>
    </>}
    {preview && <>
      <button className="connect" disabled={busy} onClick={() => void run(async () => { await save(preview); setPreview(undefined) })}>Salva storico Revolut</button>
      <button className="quiet-button" disabled={busy} onClick={() => setPreview(undefined)}>Scarta anteprima</button>
    </>}
  </article>
}
