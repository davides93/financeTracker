import { readStorage, writeStorage } from './vaultStorage'
import type { SavedValuation } from './RevolutValuation'
import type { RevolutSnapshot } from './RevolutInvestments'
import type { Report } from './portfolioReport'
export type Account = { id: string; name: string; provider: string; opening: number }
export type Movement = { id: string; account: string; date: string; label: string; cents: number; kind: 'income' | 'expense' | 'transfer' }
export type SharedExpense = { id: string; label: string; cents: number; payer: 'me' | 'other' }
export type Space = { id: string; name: string; member: string; expenses: SharedExpense[] }
export type Ledger = { accounts: Account[]; movements: Movement[]; spaces: Space[]; portfolio?: Report; revolutInvestments?: RevolutSnapshot; revolutValuation?: SavedValuation }

const encoder = new TextEncoder()
export const emptyLedger: Ledger = { accounts: [], movements: [], spaces: [] }
export const hasVault = () => readStorage() !== null

export const encryptedBackup = () => readStorage()

export async function unlockVault(password: string, backup?: string) {
  const raw = readStorage()
  if (backup && raw !== null) throw new Error('Ripristino disponibile solo su un profilo senza archivio.')
  const source = backup ?? raw
  const stored = source ? JSON.parse(source) as { salt: number[]; iv: number[]; data: number[] } : undefined
  const salt = stored ? Uint8Array.from(stored.salt) : crypto.getRandomValues(new Uint8Array(16))
  const material = await crypto.subtle.importKey('raw', encoder.encode(password), 'PBKDF2', false, ['deriveKey'])
  const key = await crypto.subtle.deriveKey(
    { name: 'PBKDF2', salt, iterations: 600_000, hash: 'SHA-256' },
    material, { name: 'AES-GCM', length: 256 }, false, ['encrypt', 'decrypt'],
  )
  const ledger = stored ? JSON.parse(new TextDecoder().decode(await crypto.subtle.decrypt(
    { name: 'AES-GCM', iv: Uint8Array.from(stored.iv) }, key, Uint8Array.from(stored.data),
  ))) as Ledger : emptyLedger
  if (!Array.isArray(ledger.accounts) || !Array.isArray(ledger.movements) || !Array.isArray(ledger.spaces)) {
    throw new Error('Formato archivio non valido.')
  }
  let revision = raw
  let currentLedger = ledger
  async function save(next: Ledger, previous: Ledger = currentLedger) {
    if (previous !== currentLedger) throw new Error('Archivio aggiornato durante l’operazione. Riprova.')
    const expected = revision
    const iv = crypto.getRandomValues(new Uint8Array(12))
    const data = await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, key, encoder.encode(JSON.stringify(next)))
    if (readStorage() !== expected) throw new Error('Archivio modificato in un’altra scheda. Blocca e riapri.')
    const serialized = JSON.stringify({ salt: [...salt], iv: [...iv], data: [...new Uint8Array(data)] })
    await writeStorage(expected, serialized)
    revision = serialized
    currentLedger = next
  }
  if (!stored || backup) await save(ledger)
  return { ledger, save }
}
