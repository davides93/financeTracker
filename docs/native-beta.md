# Preparazione beta nativa — stato effettivo

È presente lo scaffold ufficiale Tauri 2 in `src-tauri`, generato dalla CLI
installata nel progetto e bloccata nel package-lock. Riusa la build React
in `dist`. Identificativo provvisorio `app.orizzonte.finance`, da associare
agli account di distribuzione prima del rilascio. CSP limitata al client
locale; nessun accesso remoto o comando bancario abilitato.

Comandi: `npm run native:info`, `npm run native:dev`, `npm run native:build`.

Aggiornamento 6 novembre 2026: installati Rust/Cargo 1.99.1 e compilato
`src-tauri/target/debug/bundle/macos/Orizzonte.app` (build debug locale,
non notarizzata per distribuzione). Avvio reale su macOS, ripristino del
backup sintetico e riapertura dopo uscita completa riusciti. SQLite conserva solo il payload AES-GCM: non è
SQLCipher, metadati di schema e dimensione restano visibili. La passphrase
non viene salvata nel portachiavi. Il contenitore non costituisce ancora
la beta multipiattaforma richiesta.

Rust è in `~/.cargo/bin`, senza modifica automatica del PATH. Per compilare:
`PATH="$HOME/.cargo/bin:$PATH" npm run native:build -- --debug --bundles app`.
Test persistenza: `~/.cargo/bin/cargo test --manifest-path src-tauri/Cargo.toml --lib`.
Il test verifica che una scrittura obsoleta sia respinta senza sovrascrivere.
La suite Rust completa passa, inclusi i doctest (nessun esempio presente).
Il primo errore di risoluzione Tauri non si ripresenta eseguendo test e build
separatamente; evitare compilazioni concorrenti dello stesso target.

## Funzioni ancora da migrare

- Portachiavi nativo ancora da integrare. SQLite nativo ora salva snapshot
  cifrati con transazione e confronto di revisione; il browser continua con
  localStorage cifrato. Migrazione esplicita tramite ripristino del backup
  su archivio nativo vuoto, verificata con campione sintetico.
  L'archivio del browser NON viene trasferito automaticamente.
- Import Directa/Trading, rapporto monitor e copilota Apple: dipendono
  ancora dagli endpoint Vite, assenti nel pacchetto compilato.
- OAuth di sistema per piattaforma, login Google e consenso Drive distinti;
  coda offline, conflitti, recovery e revoca non implementati.
- Condivisione autenticata e distribuzione sicura delle chiavi non implementate.
- Modelli previsionali e adattatori copilota delle altre piattaforme non integrati.

## Prerequisiti di rilascio

Rust/Cargo e target delle piattaforme; dipendenze compilabili disponibili;
account Apple Developer e signing/notarizzazione/TestFlight; ambiente Windows
con toolchain e certificato di firma; configurazione Android e chiavi di
firma; dispositivi reali per i quattro percorsi. OAuth richiede progetto
Google e client per piattaforma, redirect e configurazione del consenso.
Open Banking richiede provider AIS e sandbox con credenziali protette.
Nessun account o requisito di distribuzione è stato simulato come operativo.

Fonti: https://v2.tauri.app/start/create-project/ e
https://v2.tauri.app/start/prerequisites/.
