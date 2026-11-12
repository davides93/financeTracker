# Orizzonte — personal finance tracker

MVP frontend originale per visualizzare patrimonio netto, spese, budget, investimenti e previsione di cassa. Il repository pubblico contiene codice ed esempi sintetici. Estratti, portafogli, report e configurazioni personali restano locali e sono esclusi da Git. Il collegamento "Sandbox bancaria" dimostra il flusso UI e non invia credenziali né chiama una banca.

## Avvio

```bash
npm install
npm run dev
```

Per una build di produzione:

```bash
npm run build
```

## Laboratorio AI

Il [laboratorio di forecasting](forecasting/README.md) aggiunge strumenti Python
separati per backtest cronologici, Chronos-2, confronto LoRA e modifiche esplicite
dei pesi. È un prototipo di ricerca: non alimenta ancora i grafici demo del frontend.

## Cosa è incluso

- dashboard del patrimonio e previsione dei prossimi 30 giorni;
- cronologia transazioni cliccabile;
- allocazione Liquidità / ETF / Azioni / Crypto;
- budget per categoria e grafico predittivo;
- modal di collegamento sandbox, progettato per sostituire il provider demo con un redirect OAuth/Open Banking.
- area **Condivisi**: spazi per coppia, casa e viaggi, membri, saldo condiviso, movimenti, ricorrenze, regole 50/50 o personalizzate, inviti in bozza e regolazione saldo locale.

## Condivisione e privacy

Uno spazio condiviso non equivale a condividere l'intero patrimonio. Ogni transazione deve avere un `visibility_scope`: `personal` oppure `shared_space`. Solo le transazioni create o approvate nello spazio sono visibili ai suoi membri; conti, saldo personale, investimenti e connessioni bancarie rimangono privati per impostazione predefinita.

Schema aggiuntivo: `shared_spaces`, `shared_space_members`, `shared_expenses`, `expense_splits`, `settlements`, `invites` e `recurring_shared_expenses`. Il backend dovrà verificare l'appartenenza allo spazio per ogni lettura e scrittura, calcolare saldi solo dai movimenti condivisi e registrare gli audit di inviti, approvazioni, modifiche e regolazioni.

## Architettura per la versione con dati reali

Il browser non deve mai raccogliere o memorizzare credenziali bancarie. Per gli istituti europei, usare un provider autorizzato PSD2/Open Banking e il suo redirect di consenso; per carte e broker, preferire API ufficiali o import CSV/OFX quando non esiste un connettore autorizzato.

```text
React client
  -> API backend + database cifrato
      -> provider Open Banking (consenso OAuth/PSD2)
      -> webhooks / sync schedulato
      -> normalizzazione transazioni e deduplica
      -> classificazione, budget e previsione
```

Schema minimo: `users`, `financial_connections` (solo token cifrati e metadati), `accounts`, `transactions`, `holdings`, `prices`, `budgets`, `forecast_snapshots`. Separare sempre identificativi, token cifrati e dati finanziari; includere revoca consenso, cancellazione dati, audit log e retention configurabile.

## Roadmap consigliata

1. Backend TypeScript con PostgreSQL e job queue; autenticazione e cifratura applicativa.
2. Un solo provider PSD2 in sandbox, consenso OAuth, webhook e rinnovo token.
3. Motore transazioni: normalizzazione, deduplica, categorie modificabili e ricorrenze.
4. Motore previsione: saldo giornaliero, entrate/spese ricorrenti, confidence band e spiegazioni delle assunzioni.
5. Portafoglio: import CSV iniziale e quotazioni con provider lecito; confronto con target allocation.
6. Privacy/security review e test end-to-end prima di usare dati reali.

## Decisioni di prodotto derivate dall'analisi competitiva

Il prodotto prende ispirazione solo da pattern generali osservabili in prodotti di gestione spese: chiarezza su chi deve cosa, cronologia leggibile e una riduzione dell'attrito nella registrazione. Orizzonte è invece progettato attorno al singolo nucleo finanziario: patrimonio, budget, investimenti e cassa futura. Non riusa codice, identità, testi o elementi proprietari di Splitwise.

### Archivio privato locale

Apri **Conti** e crea una passphrase di almeno 12 caratteri. Puoi aggiungere
conti e carte in euro, registrare entrate, uscite e trasferimenti in **Spese**
e gestire ripartizioni a metà tra due partecipanti in **Condivisi**. Un
trasferimento produce due movimenti con segno opposto e non entra nel totale
delle spese. Gli spazi locali hanno un registro separato.

L'archivio dei movimenti è salvato cifrato nel profilo del browser con AES-GCM
e una chiave derivata dalla passphrase tramite PBKDF2. **Blocca archivio**
rimuove l'accesso dall'interfaccia. La passphrase non viene salvata. Dal **Profilo** puoi esportare una copia cifrata e ripristinarla su un
profilo del browser privo di archivio, usando la stessa passphrase. Portafoglio e Previsioni leggono il rapporto salvato nell’archivio cifrato.
Puoi importarlo dal monitor su loopback o da file JSON. Il file sorgente
esistente resta su disco.

Per il collegamento bancario consultare [la mappa tecnica](docs/open-banking.md).
Il login Google, la sincronizzazione Drive e gli inviti remoti richiedono
configurazioni e servizi distinti. La versione attuale usa il browser locale.

In **Conti**, **Importa storico movimenti** accetta CSV in euro con le colonne
Data, Descrizione, Importo e Valuta e le equivalenti intestazioni inglesi.
Per gli estratti in formato Revolut con State importa le righe COMPLETED e,
se presente, sottrae la colonna Fee dall'importo. Verifica l'anteprima prima
di confermare. Il saldo iniziale va riferito a prima del primo movimento
importato. L'importazione ripetuta dello stesso CSV salta le righe già
presenti. Senza ID esterni, estratti parziali sovrapposti con movimenti
identici richiedono verifica manuale. In Spese puoi filtrare per data e
passare al copilota il totale e un estratto del periodo.

### Valorizzazione Revolut offline (6 novembre 2026)

In **Portafoglio → Valorizza le posizioni Revolut** puoi importare quotazioni
JSON in EUR, controllare copertura, quantità e fonti, poi confermare
l'aggiornamento di patrimonio e scenari. La stima precedente e lo storico
restano conservati separatamente nell'archivio cifrato. Le fonti e le
associazioni strumenti richiedono verifica dell'utente; non c'è download
automatico dei prezzi. [Formato, limiti e prova sintetica](docs/revolut-valuation.md).

`npm test` esegue i test del nuovo motore, incluso il confronto con Python.
L'architettura backend e la roadmap sopra riportate sono proposte storiche:
l'obiettivo attuale è offline-first, contenitore nativo da valutare, storage
locale protetto e sincronizzazione di payload cifrati via Drive, con consensi
Google, Drive e Open Banking separati. L'app rimane un prototipo browser;
non sono ancora disponibili pacchetti installabili o sincronizzazione remota.

### Contenitore nativo in preparazione

Scaffold Tauri 2 disponibile in `src-tauri`: `npm run native:info`,
`npm run native:dev`, `npm run native:build`. **Compilato e provato su macOS con backup sintetico; non ancora beta
multipiattaforma.** [Stato e prerequisiti](docs/native-beta.md).

## File privati esclusi dalla pubblicazione

Il repository non include `forecasting/data/`, `forecasting/outputs/`,
`forecasting/models/`, estratti CSV/PDF, backup, database locali, file `.env`
o chiavi private. Le fixture in `tests/fixtures/` sono sintetiche;
`valuation-vault.json` usa esclusivamente la passphrase demo documentata.
I mockup locali in `design/` e i file compilati sono esclusi.

Le funzioni che leggono report e snapshot locali richiedono file forniti
separatamente dall’utente; senza questi file il monitor e l’anteprima Directa
non sono disponibili. Non aggiungere dati personali alle fixture o al codice.
Prima di ogni pubblicazione controllare i file in staging e usare uno scanner
per segreti; `.gitignore` non rileva dati inseriti dentro un sorgente.

## Controlli automatici su GitHub

La Action [CI](https://github.com/davides93/financeTracker/actions/workflows/ci.yml) viene eseguita a ogni push e
pull request, anche sui branch diversi da `main`, ed è avviabile manualmente.
Esegue build frontend, lint, test JavaScript e Python e Gitleaks su tutta la
cronologia Git disponibile. La build dei pacchetti Tauri non è inclusa.
Le dipendenze dei test Python sono separate dai modelli di ricerca e usano
PyTorch su CPU; i test non richiedono dati personali o pesi scaricati.

Il controllo privacy fallisce anche quando un file tracciato corrisponde alle
regole `.gitignore` (per esempio dati finanziari, backup o `.env` aggiunti con
`git add -f`). Gitleaks oscura i valori rilevati nei log; la CI non carica
report di scansione o artefatti contenenti dati finanziari.

Questi controlli avvengono **dopo il push**: un errore della Action non annulla
la pubblicazione e lo scanner non riconosce ogni possibile dato personale.
Prima del push controllare sempre il contenuto del commit ed eseguire
`gitleaks git . --log-opts="--all" --redact --no-banner`. Se una credenziale
raggiunge GitHub, revocarla o ruotarla subito, anche dopo aver rimosso il file.
