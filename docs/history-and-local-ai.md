# Storico, previsioni e copilota locale

## Primo import

- Importare saldo iniziale documentato, tutte le pagine disponibili dei movimenti, saldo finale e valuta. Mostrare la prima e l'ultima data, la provenienza, i periodi mancanti e lo stato della riconciliazione. Se il provider limita lo storico, integrare con estratti precedenti senza inventare movimenti. Per Revolut iniziare il backfill subito dopo il consenso e controllare la copertura restituita dal provider.
- Unificare import da file e API per conto, deduplicare con ID stabili o riconciliazione esplicita, conservare originali e rettifiche con provenienza. Ricostruire saldi, flussi e lotti con calcoli deterministici. L'AI locale suggerisce categorie, associazioni e possibili trasferimenti con revisione dell'utente.
- Directa: separare storico patrimoniale, estratto titoli e lista eseguiti. Revolut Investimenti: unire estratti e movimenti Trading e Robo con la rispettiva provenienza. Revolut X: connettore distinto, autenticazione firmata, lettura di saldi e fill privati, paginazione e riconciliazione di commissioni e trasferimenti. Verificare permessi della chiave e copertura reale prima dell'attivazione.

## Copilota

Prototipo disponibile su macOS tramite server Vite locale e helper Swift. Compilazione dalla radice:

```sh
mkdir -p native/apple/.build
xcrun swiftc -parse-as-library native/apple/LocalCopilot.swift -o native/apple/.build/local-copilot
native/apple/.build/local-copilot --status
```

Le sezioni passano un contesto limitato. Condivisi usa solo i registri degli spazi. La cronologia è in memoria e si azzera cambiando schermata. Le domande sono indipendenti in questa versione. Il motore non ha strumenti di scrittura. Per lo storico completo servono interrogazioni locali di sola lettura con periodo e provenienza in risposta, invece di passare l'intero archivio al modello.

Adattatori nativi previsti: Foundation Models su iOS e macOS, Gemini Nano tramite ML Kit su Android, Windows AI APIs con rilevamento a runtime e compatibilità con la transizione da Phi Silica ad Aion Instruct. Sui dispositivi senza motore locale compatibile mostrare indisponibilità. Evitare fallback cloud impliciti.

## Previsioni

Affiancare scenari deterministici e benchmark semplici a Chronos-2 locale. Confrontare TimesFM 2.5 in validazione cronologica usando lo stesso orizzonte, misure di errore e copertura. Controllare la licenza della versione esatta dei pesi prima della distribuzione. Lasciare i modelli a licenza incompatibile fuori dal pacchetto di produzione. Il copilota spiega risultati e limiti; il motore numerico calcola le serie. La precedente modifica dei pesi Chronos non ha superato la validazione e rimane esclusa.

## Importazione del rapporto nell'app

Sblocca l'archivio e apri **Portafoglio**. Usa **Importa dal monitor locale**
oppure seleziona il rapporto JSON `forecasting/outputs/combined-five-year/scenarios.json`.
L'app valida conti, date e serie, salva solo i campi necessari nell'archivio
cifrato e include il rapporto nella copia esportabile. Portafoglio e Previsioni
possono visualizzare la copia archiviata senza interrogare l'API del monitor.
Il file sorgente rimane su disco. Questo flusso importa il rapporto elaborato,
mentre i file grezzi vengono ancora elaborati dal monitor Python.

## Valorizzazione dello storico Revolut

Dal 6 novembre 2026 è disponibile il flusso offline con quotazioni JSON e
conferma esplicita. [Formato, copertura, blocchi e test](revolut-valuation.md).
Il calcolo degli scenari gira nel client; storico, evidenza della conferma e
rapporto precedente sono separati. Le associazioni ISIN/mercato e le fonti
richiedono controllo umano. Cambi e corporate action non sono automatizzati.
