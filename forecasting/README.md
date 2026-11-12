# Laboratorio di previsioni e modifica dei pesi

Prototipo sperimentale separato dal frontend Orizzonte. Non contiene un modello
personalizzato già validato e non modifica le previsioni demo dell'app.
Per scegliere il modello migliore servono target, orizzonte, dati e budget di calcolo.

Per importare un portafoglio, scaricare storici e ripetere gli esperimenti finanziari,
vedi [MARKETS.md](MARKETS.md). Gli esiti di ogni esperimento sono nei rispettivi report:
il codice non presume che una modifica ai pesi sia un miglioramento.

## Cosa ricaviamo dall'articolo

[Sparks of Weight-Space Programming](https://rikiyat.github.io/blog/weight-space-programming/)
descrive interventi diretti sui pesi, motivati da un LLM, senza discesa del gradiente.
Nel caso Qwen l'intervento corregge un comportamento ripetitivo; l'esperimento su
Gemma non stabilisce un miglioramento comparabile. Il trasferimento al forecasting
è una nostra ipotesi di ricerca, non un risultato dimostrato dall'articolo.

Qui separiamo due percorsi:

- **Weight editing:** un'ipotesi sul difetto produce sostituzioni esplicite di pesi;
  confrontiamo modello originale e modificato sugli stessi periodi.
- **LoRA:** adattamento supervisionato con gradienti, utile come confronto ma distinto
  dal metodo dell'articolo. Il comando `finetune` usa esclusivamente il segmento train.

Il codice non include un agente che scopra automaticamente i circuiti,
né una diagnostica delle attivazioni: il manifest rappresenta una proposta formulata
dopo analisi. Scalare pesi a caso non costituisce una spiegazione del comportamento.

## Candidati verificati il 6 novembre 2026

| Modello | Ruolo proposto | Pesi / utilizzo |
| --- | --- | --- |
| [Chronos-2](https://huggingface.co/amazon/chronos-2) | Primo esperimento; 120M, quantili, serie multiple e covariate | Apache-2.0 |
| [TimesFM 2.5](https://github.com/google-research/timesfm) | Secondo confronto; 200M | Apache-2.0 |
| [TimesFM 3.0](https://github.com/google-research/timesfm) | Confronto di ricerca, capacità multivariate native | Pesi limitati a uso non commerciale e non produttivo |
| [Moirai 2.0 R Small](https://huggingface.co/Salesforce/moirai-2.0-R-small) | Confronto di ricerca compatto; 11.4M | CC-BY-NC-4.0 |

L'adapter implementato è solo Chronos-2. La lista è una selezione iniziale,
non una classifica misurata sui tuoi dati. Il primo esperimento gestisce una singola
serie senza covariate; le capacità multivariate di Chronos non sono ancora esposte.

## Dati e protocollo

CSV con intestazione `timestamp,target`, una osservazione per istante e frequenza
regolare. Timestamp ISO 8601, valori finiti, righe ordinate, nessun duplicato o buco.
Non imputiamo automaticamente valori mancanti. Non mettere dati personali in Git:
`forecasting/data/` è ignorata. Tutti i valori devono avere la stessa unità.

```csv
timestamp,target
2025-01-01,125.50
2025-01-02,98.20
2025-01-03,143.10
```

Queste tre righe illustrano solo il formato: per valutare servono molti più dati.
L'orizzonte e la stagionalità sono espressi in osservazioni, non necessariamente giorni.
Per serie di mercato con festività o weekend occorre prima definire il calendario:
questo reader iniziale rifiuta intervalli irregolari e non va aggirato riempiendo prezzi
senza una scelta metodologica esplicita.

Divisione cronologica 60% train / 20% validation / 20% test, senza shuffle.
Ogni previsione vede solo osservazioni precedenti al proprio istante di origine.
Le finestre target non si sovrappongono; eventuali code più corte dell'orizzonte
sono escluse. Alle origini successive lo storico include osservazioni ormai note.

Scegliere ipotesi, pesi e iperparametri sulla validation. Congelare manifest,
checkpoint, split, orizzonte e metriche prima di aprire il test finale. Il CLI
consente di scegliere lo split, ma **non impone tecnicamente** un accesso unico al test:
non iterare sulle patch guardando quei risultati. Per studi seri aggiungere più
fold temporali, analisi della variabilità e segmenti con regimi differenti.

Confronti: ultimo valore e stagionalità ripetuta. Metriche: MAE, RMSE, bias;
per Chronos anche pinball loss, copertura e ampiezza dell'intervallo P10–P90.
Un intervallo nominale all'80% non è automaticamente calibrato all'80%.
Non è implementato un criterio automatico di promozione in produzione.

## Avvio

Eseguire dalla radice del repository. Per la sola baseline basta Python standard:

```bash
python3 -m unittest discover -s forecasting/tests -p test_core.py -v
python3 -m forecasting.lab baseline --csv forecasting/data/series.csv --horizon 7 --period 7 --output forecasting/outputs/baseline-validation.json
```

Per Chronos predisporre un ambiente isolato, ad esempio con Python 3.12 presente
sul Mac. I comandi seguenti installano dipendenze e al primo caricamento scaricano
i pesi da Hugging Face; non inviano il CSV a un servizio di inferenza.

```bash
python3.12 -m venv forecasting/.venv
source forecasting/.venv/bin/activate
python -m pip install -r forecasting/requirements.txt
python -m pip freeze > forecasting/requirements-resolved.txt
python -m forecasting.lab inspect --output forecasting/outputs/chronos-inventory.json
python -m forecasting.lab evaluate --csv forecasting/data/series.csv --output forecasting/outputs/chronos-validation.json
```

Il default è CPU. `--device cuda` richiede una GPU NVIDIA supportata. `--device mps`
è disponibile per inferenza sul Mac; il sandbox dell'agente può nascondere la GPU.
La verifica CPU/Metal è ripetibile con `python -m forecasting.benchmark --model
forecasting/models/chronos-2-base --output forecasting/outputs/new-hardware-check.json`.
LoRA su MPS rimane disabilitato nel CLI perché non validato qui.
Aggiungere `--revision COMMIT_HF` per fissare il checkpoint.
Il report registra le versioni dei pacchetti, la revisione risolta quando disponibile,
l'hash del CSV e i confini degli split. Per checkpoint locali conservare l'intera cartella.

## Proposte di modifica

`inspect` elenca nomi, dimensioni, norme e fingerprint dei tensori. Creare un manifest
solo dopo aver individuato un comportamento da correggere e i pesi coinvolti.
Schema illustrativo, **non una patch valida né una correzione consigliata**:

```json
{
  "hypothesis": "Descrivere difetto, evidenza e motivo della modifica",
  "tensors": [{
    "name": "NOME_ESATTO_DALL_INVENTARIO",
    "shape": [128, 128],
    "sha256": "FINGERPRINT_DALL_INVENTARIO",
    "entries": [{"index": [0, 0], "value": 0.0123}]
  }]
}
```

```bash
python -m forecasting.lab evaluate --csv forecasting/data/series.csv --patch forecasting/proposal.json --output forecasting/outputs/edited-validation.json
python -m forecasting.lab evaluate --csv forecasting/data/series.csv --patch forecasting/proposal.json --split test --output forecasting/outputs/frozen-test.json
python -m forecasting.lab export --patch forecasting/proposal.json --output forecasting/models/chronos-edited
```

L'editor verifica fingerprint, forma, indici, finitezza e duplicati prima di applicare
la proposta. Impone budget sperimentali dell'1% dei parametri e del 5% della norma
del singolo tensore: sono limiti operativi scelti qui, non soglie ricavate dal paper
né garanzie di qualità. Ripristina i valori originali anche in caso di eccezione.
L'export salva una copia separata e non implica che il modello sia migliore.

## Confronto LoRA

```bash
python -m forecasting.lab finetune --csv forecasting/data/series.csv --steps 200 --output forecasting/models/chronos-lora-run
python -m forecasting.lab evaluate --csv forecasting/data/series.csv --model forecasting/models/chronos-lora-run/finetuned-ckpt --output forecasting/outputs/lora-validation.json
```

Il budget di 200 step è un punto di partenza da verificare, non un optimum.
[API ufficiale Chronos](https://github.com/amazon-science/chronos-forecasting/blob/main/src/chronos/chronos2/pipeline.py).
I dati di validation e test non entrano nel fit. L'eventuale scelta del numero di step
va fatta sulla validation e mai sul test finale.

## Stato e passi necessari

Verificati: lettura, split temporali, metriche, calendari, ricostruzione contabile,
controlli e rollback dei pesi; caricamento Chronos e inferenza reale su CPU e Metal.
La modifica delle code mantiene invariata la mediana e ripristina esattamente le
previsioni originali alla chiusura della prova. Le dipendenze installate sono registrate
in `requirements-resolved.txt`. Il confronto numerico CPU/Metal su una serie sintetica
non dimostra efficacia predittiva. LoRA non è ancora stato eseguito.

Prossimo passo: fissare target, orizzonte, storico e hardware, quindi misurare il modello
originale. Solo dagli errori osservati si può formulare una patch sensata. Per cassa
personale distinguere ricorrenze note da spese incerte; per mercati definire prezzi,
rendimenti o volatilità e verificare separatamente un'eventuale strategia operativa.

## Directa e monitoraggio dei due portafogli

L'importatore `directa.py` legge il formato italiano **PatrimonioTotale** con
separatore `;`, numeri decimali con virgola e date **MM/DD/YY**. Le due tabelle
laterali (patrimonio e movimenti) sono indipendenti e possono avere intestazioni
su righe diverse. Le valorizzazioni provvisorie restano nell'audit ma non sono
usate come saldo iniziale. Totali incoerenti, duplicati e posizioni finanziate o
short bloccano l'import; movimenti non classificati sospendono la performance.
Il CSV non contiene le quantità attuali dei titoli.

Dalla radice del repository:

```sh
forecasting/.venv/bin/python -m forecasting.directa /percorso/PatrimonioTotale.csv --output forecasting/data/directa
forecasting/.venv/bin/python -m forecasting.monitor \
  --config forecasting/data/combined/scenario-config.json \
  --directa forecasting/data/directa/import.json \
  --revolut forecasting/outputs/revolut-calibration-v1/portfolio-summary.json \
  --snapshot forecasting/data/directa/holdings.json \
  --output forecasting/outputs/combined-five-year
```

Prima di aggiornare il monitor, aggiorna anche il riepilogo Revolut seguendo la
procedura precedente e imposta `start_date` nella configurazione alla nuova
data di elaborazione. Il monitor rilegge i saldi dai due import e segnala età
e disallineamento delle valorizzazioni. La fotografia titoli PDF deve essere
aggiornata con un estratto posizioni, senza dedurre quantità dal patrimonio.
Il confronto PDF/CSV segnala la differenza di cassa senza inventarne la causa.

La configurazione locale deve specificare i versamenti periodici scelti
dall’utente, le ipotesi di rendimento e l’inflazione. Gli scenari
sono **sensibilità deterministiche**, senza probabilità: non derivano da
Chronos e non sono intervalli di confidenza. I rendimenti ipotizzati sono netti
dei costi ricorrenti e precedono le imposte personali. I versamenti sono
posticipati: primo pagamento mensile dopo un mese, settimanale dopo 7 giorni.
Il motore usa capitalizzazione annua effettiva ACT/365.25 e non simula ordini,
vincoli sulle quote intere o tasse alla vendita. Contributi ed effetto dei
rendimenti sono separati. `scenarios.json` include tutti gli eventi e l'audit;
`LEGGIMI.md` contiene il rapporto leggibile. Dati e risultati rimangono nelle
cartelle escluse dal versionamento. Nessun collegamento automatico ai broker
o alla dashboard dimostrativa è attivo.

```sh
forecasting/.venv/bin/python -m unittest forecasting.tests.test_scenarios -v
```
