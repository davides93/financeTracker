# Valorizzazione Revolut offline — tranche 6 novembre 2026

Disponibile in **Portafoglio → Valorizza le posizioni Revolut**, dopo aver
salvato storico Trading e rapporto. Il calcolo non dipende da Vite, Python o
servizi esterni: viene eseguito nel client. L'import dello storico Trading
continua invece a dipendere dal motore Python locale.

## Formato quotazioni

```json
{
  "as_of": "2026-11-06",
  "quotes": [{
    "broker_ticker": "DEMO",
    "isin": "IE0000000000",
    "ticker": "DEMO",
    "market": "XETR",
    "currency": "EUR",
    "price": 40,
    "source": "https://example.com/synthetic-not-market-data"
  }]
}
```

Questo esempio è sintetico, non identifica un investimento reale. Il file è
limitato a 500 KB e 500 quotazioni. Tutti i prezzi si riferiscono alla data
`as_of`, devono essere positivi, in EUR e avere una fonte HTTPS consultabile.
L'app valida la struttura ma non certifica la fonte, l'ISIN o il mercato.
L'associazione parte da ticker broker + valuta; l'utente deve verificare
ISIN, ticker di mercato, MIC, quantità e fonte in anteprima. Il CSV Trading
non basta a certificare autonomamente questi identificativi.

La conferma richiede copertura completa e attestazione della completezza
dello storico fino alla data delle quotazioni, con saldo e posizioni iniziali
a zero. Prezzi futuri, anteriori all'ultimo movimento, più vecchi di sette
giorni, cassa non EUR non nulla, associazioni duplicate o anomalie di prezzo
nello storico impediscono l'aggiornamento. Le corporate action non vengono
risolte automaticamente; il warning del parser le blocca solo quando rileva
un'anomalia, non garantisce di individuarle tutte.

Il totale include quantità frazionarie e cassa ricostruita; viene arrotondato
ai centesimi alla fine. I calcoli usano numeri JavaScript, non un registro
contabile a precisione decimale arbitraria. Le quotazioni inutilizzate non
contribuiscono al totale. Il subtotale parziale non sostituisce la stima.

Solo dopo conferma si ricalcolano cinque anni dalla data quotazioni, con
PAC e tassi del rapporto corrente, ACT/365.25 e versamenti a fine giornata.
Gli altri conti conservano saldo e data precedenti: non vengono rivalutati.
La data quotazioni non può precedere la data di un altro conto. Rapporto,
quotazioni usate, snapshot dello storico e rapporto precedente vengono salvati
insieme nell'archivio cifrato. Lo storico importato resta separato. La
conferma successiva conserva il rapporto immediatamente precedente, non un
archivio illimitato di tutte le versioni. Altri import possono sostituire il
rapporto: l'evidenza dell'ultima conferma resta datata e va rivalutata.

## Prova riproducibile con dati sintetici

Requisiti: Node con supporto TypeScript nativo (verificato Node 26.12.1),
Python 3 per confronto numerico; dipendenze già installate.

```sh
npm test
npm run build
npm run lint
forecasting/.venv/bin/python -m unittest discover -s forecasting/tests
node tests/create-valuation-fixture.mjs
npm run dev -- --port 5174 --strictPort
```

1. Aprire `http://127.0.0.1:5174` in un profilo senza archivio su questa origine.
2. Ripristinare `tests/fixtures/valuation-vault.json` con passphrase sintetica
   `orizzonte-demo-only`. Non usare questi file per dati personali.
3. In Portafoglio importare `tests/fixtures/quotes-missing.json`: copertura
   0/1, posizione DEMO mancante, conferma disabilitata anche dopo la spunta.
4. Importare `tests/fixtures/quotes.json`: copertura 1/1, 2,5 quote × 40 EUR
   più 100 EUR di cassa = 200 EUR. Prima di confermare la stima resta 50 EUR.
5. Verificare e spuntare la dichiarazione, confermare: totale conti 10.200 EUR,
   scenario a rendimento zero a cinque anni 35.200 EUR, con i PAC 200 EUR
   mensili Directa e 50 EUR settimanali Revolut.
6. Ricaricare e sbloccare: valori ed evidenza restano disponibili. Il backup
   cifrato include anche il rapporto precedente e lo snapshot alla conferma.

Passi 1–6 verificati nell'interfaccia il 6 novembre 2026. I test automatici
coprono blocchi, calcoli, input e confronto di ogni punto della serie con il
motore Python, inclusi fine mese, anno bisestile, PAC e tassi non nulli.

## Da completare

Quotazioni reali e autorizzazione per identificativi eventualmente nuovi;
anagrafica strumenti verificata; cambi; corporate action e rettifiche;
prove con estratti reali autorizzati. Nessuna richiesta Yahoo o altra richiesta
di mercato è stata effettuata in questa tranche. Nessun pacchetto nativo,
login Google, sync Drive o condivisione remota è stato aggiunto.
