# Previsioni finanziarie locali

Il laboratorio usa Chronos-2 per previsioni marginali dei rendimenti logaritmici
giornalieri. L'esperimento iniziale ha orizzonte di cinque sedute. Il forecast non
è un ordine di acquisto o vendita, e non è integrato nei grafici demo del frontend.
Non è attivo un aggiornamento pianificato.

## Ambiente sul Mac

L'ambiente è `forecasting/.venv`; il checkpoint scaricato è
`forecasting/models/chronos-2-base`. Le versioni effettive sono registrate in
`requirements-resolved.txt`. Sul Mac M4 Pro con 24 GiB sono state verificate inferenza
CPU e MPS. Per un batch sintetico di una serie, contesto 128 e orizzonte 5, la mediana
di tre inferenze dopo warm-up è stata circa 21 ms CPU e 12 ms MPS; il caricamento circa
3,1 s. Il massimo scarto fra i quantili CPU/MPS è stato 2,8e-9.
Questi tempi non stimano il costo del training o di batch grandi.

```bash
source forecasting/.venv/bin/activate
python -m unittest discover -s forecasting/tests -v
```

## Importazione e dati pubblici

`revolut.py` legge il CSV movimenti e le sezioni del CSV PnL, ricostruisce quantità e
liquidità, riconcilia le quantità vendute con i lotti fiscali e segnala salti nei prezzi.
Il PnL non viene sommato nuovamente al saldo. Le quantità presuppongono un saldo
iniziale nullo e l'assenza di operazioni/corporate action mancanti: senza un estratto
delle posizioni finali la ricostruzione non equivale a una conferma del broker.

```bash
python -m forecasting.revolut --account /percorso/movimenti.csv --pnl /percorso/pnl.csv --output forecasting/data/nuovo-import.json
```

`resolve.py` usa l'ISIN per cercare una quotazione pubblica; una ricerca senza risultato
non autorizza a sostituire l'ETF con un fondo simile. Le quotazioni alternative dello
stesso ISIN possono richiedere verifica di simbolo, classe, valuta, calendario e liquidità.
La valuta di negoziazione EUR non elimina l'esposizione valutaria degli attivi sottostanti.

Fonte del prototipo: [yfinance](https://github.com/ranaroussi/yfinance), accesso non ufficiale
a Yahoo Finance. Destinazione delle richieste: identificativi pubblici e date. I CSV
contabili e le quantità restano locali. Storici e risultati personali sono in cartelle
ignorate da Git, ma non sono cifrati dal laboratorio.

```bash
python -m forecasting.market_data --portfolio forecasting/portfolio.example.csv --start 2018-01-01 --end 2026-11-06 --output forecasting/data/nuovo-download
```

Il CSV del portafoglio contiene `ticker,quantity,currency,calendar`. La data `--end`
è esclusiva. Il downloader conserva anche OHLCV, dividendi e split restituiti dal
provider. Non utilizza i prezzi di esecuzione del broker come serie di mercato.

`recover_history.py` permette un recupero esplicito dei download incompleti: esclude
al massimo due righe finali prive di chiusura e, con `--recent-contiguous`, conserva
solo il segmento successivo all'ultima lacuna di calendario. Ogni taglio è registrato.
Non interpola e non riempie prezzi. Non estende il calendario specifico della borsa
a titoli sospesi o illiquidi senza segnalarne i limiti.

`corporate_actions.py` normalizza uno split documentato solo se il salto osservato
corrisponde al fattore dichiarato; rifiuta una seconda applicazione. La data in cui
la serie del provider cambia unità può differire dalla data ufficiale di efficacia:
entrambe vengono registrate e il file originale viene preservato.

## Esperimento sui pesi

L'output Chronos-2 somma due proiezioni lineari. Per i quantili estremi <= P10 o >= P90
applichiamo in entrambe le proiezioni:

`W_q' = W_mediana + fattore * (W_q - W_mediana)`

La stessa trasformazione viene applicata ai bias. Con fattore > 1, in spazio
normalizzato le code si allontanano dalla mediana. L'inversa monotona della
normalizzazione mantiene l'ordine. È una modifica diretta motivata dalla struttura
della rete, senza gradienti, per correggere eventuale sottocopertura degli intervalli.
**Non cambia la mediana e non aggiunge informazione sulla direzione del mercato.**

Il prototipo limita l'orizzonte a un singolo patch di output, per evitare che le code
modificate retroagiscano nei passaggi autoregressivi. La proposta tocca 368.832 valori
su 119.477.664 parametri (circa 0,309%); controlla fingerprint e budget prima di ogni prova.
Il fattore 1,05 supera i controlli; 1,10 e 1,20 sono stati scartati dal budget di norma.

```bash
HF_HUB_OFFLINE=1 python -m forecasting.portfolio_experiment --manifest forecasting/data/revolut/experiment-dataset/manifest.json --model forecasting/models/chronos-2-base --output forecasting/outputs/nuovo-esperimento --device cpu --horizon 5 --context 128 --train-end 2024-12-31 --validation-end 2026-06-30
```

Il comando produce:

- `frozen-selection.json`: scelta congelata prima di vedere il test;
- `report.json`: confronto per ETF e medio tra ETF, con esclusioni e limiti;
- `selected-patch.json`, se una modifica supera la selezione in validation;
- `edited-checkpoint/`, solo se la modifica supera anche il controllo finale;
- `forecasts.json`: quantili dei rendimenti di ciascuna delle prossime cinque sedute.

Il criterio di selezione richiede miglioramento della pinball loss normalizzata in
validation e copertura non più lontana dall'80%. Il test viene letto solo dopo la scelta.
Se il controllo finale fallisce, il forecast usa il checkpoint originale. Non è una
promozione automatica in produzione e non costituisce un test di significatività.

## Interpretazione corretta

Il confronto usa confini di calendario globali per tutti gli ETF, così la validation
di un titolo non può includere periodi successivi al test di un altro. Per serie nuove
si riservano almeno 28 osservazioni iniziali al contesto; segmenti troppo corti vengono
esclusi dalle metriche. La scelta degli attuali ETF è retrospettiva: il backtest non
ricostruisce la performance storica dell'intero portafoglio Revolut.

La sovrapposizione fra dati di pretraining del foundation model e backtest storico non
è esclusa. I prezzi aggiustati sono snapshot correnti, non dati point-in-time.
Occorre una verifica prospettica su nuovi dati prima di sostenere un vantaggio stabile.

Si confrontano anche rendimento zero e media storica. Le somme delle mediane giornaliere
sono soltanto una previsione puntuale approssimata del rendimento cumulato: non sono
quantili aggregati. Non si sommano gli intervalli degli ETF per ottenere un intervallo
di portafoglio; servono dipendenze fra strumenti e fra sedute.

Versamenti, prelievi, ribilanciamenti e commissioni sono separati dal rendimento di
mercato. Le cifre simulate del report Robo-Advisor non sono etichette di training né
obiettivi che il modello deve riprodurre. Per ripetere o ampliare gli esperimenti dopo
aver visto il test, occorre un nuovo periodo finale realmente non utilizzato.
