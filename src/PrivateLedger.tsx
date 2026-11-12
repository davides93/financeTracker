import { nativeStorage } from './vaultStorage'
import { prepareHistory } from './historyImport'
import { LocalCopilot } from './LocalCopilot'
import { useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { encryptedBackup, hasVault, unlockVault } from './ledgerVault'
import type { Ledger, Movement } from './ledgerVault'
import './PrivateLedger.css'

type Vault = Awaited<ReturnType<typeof unlockVault>>
const money = (cents: number) => new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR' }).format(cents / 100)
const field = (data: FormData, key: string) => String(data.get(key) ?? '').trim()
function cents(value: string) {
  const normalized = value.replace(',', '.')
  if (!/^-?\d{1,9}(\.\d{1,2})?$/.test(normalized)) throw new Error('Inserisci un importo con al massimo due decimali.')
  return Math.round(Number(normalized) * 100)
}

export function PrivateLedger({ page, vault, onUnlock, onLock }: {
  page: string; vault?: Vault; onUnlock: (vault: Vault) => void; onLock: () => void
}) {
  const [busy, setBusy] = useState(false)
  const locked = useRef(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [preview, setPreview] = useState<Awaited<ReturnType<typeof prepareHistory>>>()
  const [from, setFrom] = useState('')
  const [through, setThrough] = useState('')
  const ledger = vault?.ledger
  const accountName = (id: string) => ledger?.accounts.find(a => a.id === id)?.name ?? 'Conto'
  const balance = (id: string, opening: number) => opening + (ledger?.movements ?? []).filter(m => m.account === id).reduce((sum, m) => sum + m.cents, 0)
  const period = (ledger?.movements ?? []).filter(m => (!from || m.date >= from) && (!through || m.date <= through))
  const periodExpenses = period.filter(m => m.kind === 'expense').reduce((sum, m) => sum - m.cents, 0)
  async function run(action: () => Promise<void>) {
    if (locked.current) return
    locked.current = true
    setBusy(true); setError(''); setNotice('')
    try { await action() } catch (err) { setError(err instanceof Error ? err.message : 'Operazione non riuscita') }
    finally { locked.current = false; setBusy(false) }
  }
  function submit(event: FormEvent<HTMLFormElement>, update: (data: FormData, current: Ledger) => Ledger) {
    event.preventDefault()
    if (!vault) return
    const form = event.currentTarget
    const data = new FormData(form)
    void run(async () => {
      const next = update(data, vault.ledger)
      await vault.save(next, vault.ledger)
      onUnlock({ ...vault, ledger: next })
      form.reset()
      setNotice('Salvato nell’archivio privato.')
    })
  }
  return <div className="investment private-ledger">
    <header className="topbar"><div><h1>{page}</h1><p>{nativeStorage ? 'Archivio cifrato nel database locale del dispositivo' : 'Archivio personale cifrato su questo browser'}</p></div>{vault && <button className="quiet-button" disabled={busy} onClick={onLock}>Blocca archivio</button>}</header>
    {error && <p role="alert">{error}</p>}{notice && <p role="status">{notice}</p>}
    {!ledger ? <article className="panel investment-panel">
      <h2>{hasVault() ? 'Sblocca archivio' : 'Crea archivio privato'}</h2>
      <p>Conserva la passphrase. Puoi esportare una copia cifrata dal Profilo. La sincronizzazione automatica è in preparazione.</p>
      <form onSubmit={event => {
        event.preventDefault()
        const form = event.currentTarget
        const data = new FormData(form)
        const password = String(data.get('password') ?? '')
        const backup = data.get('backup')
        form.reset()
        void run(async () => {
          try {
            const file = backup instanceof File && backup.size ? backup : undefined
            if (file && file.size > 10_000_000) throw new Error('Backup troppo grande.')
            onUnlock(await unlockVault(password, file ? await file.text() : undefined))
          }
          catch { throw new Error('Impossibile aprire l’archivio. Controlla passphrase e disponibilità dello spazio del browser.') }
        })
      }}><label>Passphrase<input type="password" name="password" minLength={12} required autoComplete={hasVault() ? 'current-password' : 'new-password'} /></label>{!hasVault() && <label>Ripristina da copia cifrata (facoltativo)<input type="file" name="backup" accept=".json,application/json" /></label>}<button className="connect" disabled={busy}>{hasVault() ? 'Sblocca' : 'Apri o crea archivio'}</button></form>
    </article> : <>
      {(page === 'Conti' || page === 'Panoramica') && <div className="investment-accounts">
        {ledger.accounts.map(a => <article className="panel investment-panel" key={a.id}><h2>{a.name}</h2><strong className="investment-total">{money(balance(a.id, a.opening))}</strong><p>{a.provider} · saldo da movimenti registrati</p></article>)}
        {ledger.accounts.length === 0 && <article className="panel investment-panel"><p>Nessun conto registrato.</p></article>}
      </div>}
      {page === 'Conti' && <article className="panel investment-panel"><h2>Aggiungi conto o carta</h2><form onSubmit={e => submit(e, (d, current) => {
        const name = field(d, 'name')
        if (!name) throw new Error('Inserisci un nome.')
        return { ...current, accounts: [...current.accounts, { id: crypto.randomUUID(), name, provider: field(d, 'provider'), opening: cents(field(d, 'opening')) }] }
      })}>
        <label>Istituto<select name="provider"><option>ING</option><option>Revolut</option><option>American Express</option><option>Altro</option></select></label>
        <label>Nome<input name="name" required maxLength={80} /></label><label>Saldo iniziale in EUR<input name="opening" defaultValue="0" required inputMode="decimal" /></label>
        <button className="connect" disabled={busy}>Salva conto</button></form><p>Registrazione manuale. Il collegamento agli istituti richiede un provider Open Banking configurato.</p></article>}
      {page === 'Conti' && ledger.accounts.length > 0 && <article className="panel investment-panel">
        <h2>Importa storico movimenti</h2>
        <p>CSV in EUR. Usa Data, Descrizione, Importo con segno e Valuta, oppure un estratto Revolut con intestazioni inglesi. Il saldo iniziale deve precedere i movimenti importati.</p>
        <form onSubmit={event => {
          event.preventDefault()
          const data = new FormData(event.currentTarget)
          const file = data.get('history')
          setPreview(undefined)
          void run(async () => {
            if (!(file instanceof File) || !file.size || file.size > 5_000_000) throw new Error('Seleziona un CSV fino a 5 MB.')
            setPreview(await prepareHistory(await file.text(), field(data, 'account'), ledger.movements))
          })
        }}>
          <label>Conto di importazione<select name="account">{ledger.accounts.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}</select></label>
          <label>Estratto CSV<input type="file" name="history" accept=".csv,text/csv" required /></label>
          <button className="connect" disabled={busy}>Analizza estratto</button>
        </form>
        {preview && <div>
          <p>{preview.rows} righe · {preview.movements.length} nuovi movimenti · {preview.duplicates} già presenti · {preview.skipped} non contabilizzati</p>
          {preview.movements.length > 0 && <>
            <p>Destinazione {accountName(preview.movements[0].account)} · dal {preview.movements[0].date} al {preview.movements.at(-1)?.date} · variazione {money(preview.movements.reduce((sum, m) => sum + m.cents, 0))}</p>
            <ul>{preview.movements.slice(0, 8).map(m => <li key={m.id}>{m.date} · {m.label} · {money(m.cents)}</li>)}</ul>
            <button className="connect" disabled={busy} onClick={() => void run(async () => {
              if (!vault) return
              const next = { ...vault.ledger, movements: [...vault.ledger.movements, ...preview.movements] }
              await vault.save(next, vault.ledger)
              onUnlock({ ...vault, ledger: next })
              setPreview(undefined)
              setNotice('Storico salvato nell’archivio privato.')
            })}>Conferma importazione</button>
          </>}
          <button className="quiet-button" disabled={busy} onClick={() => setPreview(undefined)}>Chiudi anteprima</button>
        </div>}
        <p>Verifica la copertura e i saldi con l’estratto originale. I trasferimenti importati richiedono riconciliazione.</p>
      </article>}
      {(page === 'Spese' || page === 'Panoramica') && <article className="panel investment-panel"><h2>Movimenti personali</h2>
        <p>Uscite nel periodo {money(periodExpenses)} · {period.length} movimenti</p>
        <div className="history-filters"><label>Dal <input type="date" value={from} onChange={e => setFrom(e.target.value)} /></label><label>Al <input type="date" value={through} onChange={e => setThrough(e.target.value)} /></label></div>
        {page === 'Spese' && ledger.accounts.length > 0 && <form onSubmit={e => submit(e, (d, current) => {
          const amount = cents(field(d, 'amount'))
          const label = field(d, 'label')
          const kind = field(d, 'kind') as Movement['kind']
          const account = field(d, 'account')
          const date = field(d, 'date')
          if (!label || amount <= 0) throw new Error('Inserisci descrizione e importo positivo.')
          const movement: Movement = { id: crypto.randomUUID(), account, date, label, kind, cents: kind === 'income' ? amount : -amount }
          const movements = [...current.movements, movement]
          if (kind === 'transfer') {
            const target = field(d, 'target')
            if (!target || target === account) throw new Error('Scegli un conto di destinazione diverso.')
            movements.push({ ...movement, id: crypto.randomUUID(), account: target, cents: amount })
          }
          return { ...current, movements }
        })}><label>Conto<select name="account">{ledger.accounts.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}</select></label>
          <label>Tipo<select name="kind"><option value="expense">Spesa</option><option value="income">Entrata</option><option value="transfer">Trasferimento</option></select></label>
          <label>Destinazione per trasferimenti<select name="target"><option value="">Scegli conto</option>{ledger.accounts.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}</select></label>
          <label>Data<input name="date" type="date" required /></label><label>Descrizione<input name="label" required maxLength={120} /></label>
          <label>Importo in EUR<input name="amount" required inputMode="decimal" /></label><button className="connect" disabled={busy}>Registra movimento</button></form>}
        {ledger.movements.length === 0 && <p>Nessun movimento registrato.</p>}
        <ul>{[...period].sort((a,b) => b.date.localeCompare(a.date)).map(m => <li key={m.id}>{m.date} · {m.label} · {accountName(m.account)} · {money(m.cents)}</li>)}</ul>
      </article>}
      {page === 'Condivisi' && <>
        <article className="panel investment-panel"><h2>Spazi condivisi locali</h2><p>Divisione a metà tra due persone. I partecipanti e le spese sono registrati su questo dispositivo.</p>
          <form onSubmit={e => submit(e, (d, current) => {
            const name = field(d, 'name'), member = field(d, 'member')
            if (!name || !member) throw new Error('Inserisci nome dello spazio e partecipante.')
            return { ...current, spaces: [...current.spaces, { id: crypto.randomUUID(), name, member, expenses: [] }] }
          })}><label>Spazio<input name="name" maxLength={80} required /></label><label>Partecipante<input name="member" maxLength={80} required /></label><button className="connect" disabled={busy}>Crea spazio</button></form>
        </article>
        {ledger.spaces.map(space => {
          const net = space.expenses.reduce((sum, expense) => sum + (expense.payer === 'me' ? Math.floor(expense.cents / 2) : -Math.ceil(expense.cents / 2)), 0)
          return <article key={space.id} className="panel investment-panel"><h2>{space.name}</h2><p>{net === 0 ? 'Saldo in pari' : net > 0 ? `${space.member} ti deve ${money(net)}` : `Devi ${money(-net)} a ${space.member}`}</p>
            <form onSubmit={e => submit(e, (d, current) => {
              const amount = cents(field(d, 'amount')), label = field(d, 'label')
              if (!label || amount <= 0) throw new Error('Inserisci descrizione e importo positivo.')
              const payer = field(d, 'payer') === 'me' ? 'me' : 'other'
              return { ...current, spaces: current.spaces.map(s => s.id === space.id ? { ...s, expenses: [...s.expenses, { id: crypto.randomUUID(), label, cents: amount, payer }] } : s) }
            })}><label>Spesa<input name="label" maxLength={120} required /></label><label>Importo in EUR<input name="amount" required inputMode="decimal" /></label><label>Pagato da<select name="payer"><option value="me">Io</option><option value="other">{space.member}</option></select></label><button className="connect" disabled={busy}>Aggiungi spesa</button></form>
            <ul>{space.expenses.map(item => <li key={item.id}>{item.label} · {money(item.cents)} · {item.payer === 'me' ? 'Io' : space.member}</li>)}</ul>
          </article>
        })}
      </>}
      {page !== 'Profilo' && <LocalCopilot context={JSON.stringify(page === 'Condivisi'
        ? { spazi: ledger.spaces }
        : {
          conti: ledger.accounts.map(a => ({ nome: a.name, saldo: money(balance(a.id, a.opening)) })),
          ...(page !== 'Conti' && { periodo: { dal: from || null, al: through || null, numeroMovimenti: period.length, uscite: money(periodExpenses) }, movimentiRecenti: [...period].sort((a,b) => b.date.localeCompare(a.date)).slice(0, 12).map(m => ({ data: m.date, descrizione: m.label, conto: accountName(m.account), importo: money(m.cents), tipo: m.kind })) }),
        })} />}
      {page === 'Profilo' && <article className="panel investment-panel"><h2>Accesso e sincronizzazione</h2><p>Archivio locale sbloccato. Accesso Google, Drive e inviti remoti sono in preparazione.</p>
        <p>Per ripristinare la copia servono il file e la stessa passphrase.</p>
        <button className="quiet-button" disabled={busy} onClick={() => {
          const backup = encryptedBackup()
          if (!backup) return
          const url = URL.createObjectURL(new Blob([backup], { type: 'application/json' }))
          const link = document.createElement('a')
          link.href = url
          link.download = 'finance-tracker-cifrato.json'
          link.click()
          setTimeout(() => URL.revokeObjectURL(url), 1000)
        }}>Esporta copia cifrata</button></article>}
    </>}
  </div>
}
