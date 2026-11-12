import type { Movement } from './ledgerVault'

function records(text: string, delimiter: string): string[][] {
  const result: string[][] = []
  let row: string[] = [], value = '', quoted = false
  for (let i = 0; i < text.length; i++) {
    const c = text[i]
    if (c === '"') {
      if (quoted && text[i + 1] === '"') { value += '"'; i++ }
      else if (quoted || !value) quoted = !quoted
      else throw new Error('Virgolette non valide nel CSV.')
    } else if (!quoted && (c === delimiter || c === '\n' || c === '\r')) {
      row.push(value.trim()); value = ''
      if (c !== delimiter) {
        if (row.some(Boolean)) result.push(row)
        row = []
        if (c === '\r' && text[i + 1] === '\n') i++
      }
    } else value += c
  }
  if (quoted) throw new Error('Campo CSV non chiuso.')
  row.push(value.trim())
  if (row.some(Boolean)) result.push(row)
  return result
}

export async function prepareHistory(text: string, account: string, existing: Movement[]) {
  const clean = text.replace(/^\uFEFF/, '')
  const rows = records(clean, clean.split(/\r?\n/, 1)[0].includes(';') ? ';' : ',')
  const header = rows.shift()?.map(value => value.toLowerCase()) ?? []
  const index = (...names: string[]) => header.findIndex(value => names.includes(value))
  const dateIndex = index('data', 'date', 'completed date')
  const labelIndex = index('descrizione', 'description')
  const amountIndex = index('importo', 'amount')
  const currencyIndex = index('valuta', 'currency')
  const stateIndex = index('state')
  const feeIndex = index('fee')
  const typeIndex = index('type')
  const idIndex = index('id', 'transaction id')
  if ([dateIndex, labelIndex, amountIndex, currencyIndex].includes(-1)) {
    throw new Error('Servono le colonne Data, Descrizione, Importo e Valuta, oppure le intestazioni inglesi equivalenti.')
  }
  const known = new Set(existing.map(m => m.id))
  const occurrences = new Map<string, number>()
  const movements: Movement[] = []
  let skipped = 0, duplicates = 0
  for (const [i, row] of rows.entries()) {
    if (row.length !== header.length) throw new Error(`Numero di colonne errato alla riga ${i + 2}.`)
    if (stateIndex >= 0 && row[stateIndex].toUpperCase() !== 'COMPLETED') { skipped++; continue }
    if (row[currencyIndex].toUpperCase() !== 'EUR') throw new Error(`Valuta diversa da EUR alla riga ${i + 2}.`)
    const rawDate = row[dateIndex].split(/[ T]/, 1)[0]
    const italian = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(rawDate)
    const date = italian ? `${italian[3]}-${italian[2]}-${italian[1]}` : rawDate
    const label = row[labelIndex]
    const parseMoney = (value: string) => {
      const normalized = value.replace(',', '.')
      return /^-?\d{1,9}(\.\d{1,2})?$/.test(normalized) ? Math.round(Number(normalized) * 100) : NaN
    }
    const fee = feeIndex < 0 || !row[feeIndex] ? 0 : parseMoney(row[feeIndex])
    const cents = parseMoney(row[amountIndex]) - fee
    const parsedDate = new Date(date)
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || !Number.isFinite(+parsedDate) || parsedDate.toISOString().slice(0, 10) !== date ||
        !label || label.length > 500 || !Number.isSafeInteger(cents) || fee < 0) throw new Error(`Dati non validi alla riga ${i + 2}.`)
    const fingerprint = JSON.stringify([row[dateIndex], label, cents, row[typeIndex] ?? ''])
    const occurrence = (occurrences.get(fingerprint) ?? 0) + 1
    occurrences.set(fingerprint, occurrence)
    const identity = row[idIndex] ? ['external', row[idIndex]] : ['content', fingerprint, occurrence]
    const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(JSON.stringify([account, identity])))
    const id = 'csv-' + Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, '0')).join('')
    if (known.has(id)) { duplicates++; continue }
    known.add(id)
    movements.push({ id, account, date, label, cents, kind: cents < 0 ? 'expense' : 'income' })
  }
  movements.sort((a, b) => a.date.localeCompare(b.date))
  return { movements, skipped, duplicates, rows: rows.length }
}
