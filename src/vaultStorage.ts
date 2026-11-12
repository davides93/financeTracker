import { invoke, isTauri } from '@tauri-apps/api/core'
const key = 'orizzonte.private-ledger.v1' // Public localStorage identifier, not a credential. gitleaks:allow
let nativeValue: string | null = null
let ready = false
export const nativeStorage = isTauri()
export async function initializeStorage() {
  if (nativeStorage) nativeValue = await invoke<string | null>('vault_read')
  ready = true
}
export function readStorage() {
  if (!ready) throw new Error('Archivio non inizializzato.')
  return nativeStorage ? nativeValue : localStorage.getItem(key)
}
export async function writeStorage(expected: string | null, value: string) {
  if (nativeStorage) {
    await invoke('vault_write', { expected, value })
    nativeValue = value
  } else {
    if (localStorage.getItem(key) !== expected) throw new Error('Archivio modificato in un’altra scheda. Blocca e riapri.')
    localStorage.setItem(key, value)
  }
}
