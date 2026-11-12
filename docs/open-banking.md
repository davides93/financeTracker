# Collegamenti bancari italiani

L'app separa tre consensi: identità Google, sincronizzazione privata su Drive e lettura bancaria. Il login Google identifica l'utente. La banca autorizza il provider di account information. Drive riceve solo i dati cifrati dal client se l'utente attiva la sincronizzazione.

| Istituto | Prodotto da verificare in sandbox e produzione | Integrazione |
|---|---|---|
| ING Italia | Conto Corrente Arancio e, separatamente, Conto Arancio | AIS in sola lettura. ING documenta saldo e lista movimenti. Verificare i due prodotti nel catalogo del provider scelto. |
| Revolut | Conto personale italiano, valute e saldo per conto | AIS in sola lettura per conti, saldi e transazioni. Trading e Robo-Advisor rimangono nel canale di importazione investimenti. |
| American Express Italia | Carta e soggetto emittente italiani | Copertura PSD2 non confermata. La documentazione pubblica Amex elenca UK e Francia. Salt Edge elenca un canale italiano non regolamentato, da valutare separatamente. Prima versione tramite estratto esportato, con parser verificato su campione anonimizzato. |

## Flusso nell'app

1. In Conti scegli l'istituto. Per le connessioni verificate apri il consenso nel browser di sistema, sul flusso ospitato dal provider. Per gli estratti usa il selettore di file.
2. Un servizio minimo crea il collegamento e valida il ritorno con stato monouso legato alla sessione. Il client secret e i token del provider rimangono nel servizio protetto. Le credenziali della banca si inseriscono nel flusso ufficiale.
3. L'utente sceglie i conti autorizzati. L'app mostra provenienza, data dell'ultimo aggiornamento, stato del consenso e azioni per aggiornare, rinnovare o revocare.
4. Il client normalizza conto, valuta, saldo, data contabile, descrizione, importo e stato. Deduplica per identificativo del provider nel conto, riconcilia pending e booked e segnala corrispondenze ambigue tra file e API. Gestisce i trasferimenti interni separatamente dalle spese, incluso l'addebito del saldo Amex già rappresentato dalle singole spese carta.
5. I movimenti entrano nello spazio personale. Lo spazio condiviso riceve solo la spesa e i campi che l'utente sceglie di pubblicare, con controllo dei membri a ogni accesso. Il provider AIS tratta i dati necessari alla connessione. Per il servizio dell'app preferire transito minimo e nessuna persistenza dei movimenti grezzi. Conservare localmente i dati normalizzati protetti e cifrarli prima del backup Drive.

## Gate prima del collegamento reale

- Verificare l'emittente e il prodotto in Italia tramite catalogo live del provider AIS, storico disponibile, saldi, stato delle transazioni, rinnovo, revoca e callback sulle quattro piattaforme. TrueLayer documenta la verifica delle capacità per banca nella Console. Verificare anche condizioni contrattuali, ruolo del provider nel servizio, trattamento dei dati e condizioni di accesso alla produzione prima della scelta.
- Per Revolut pianificare la prima importazione immediatamente dopo il consenso. La sua API documenta accesso allo storico completo nei primi cinque minuti e finestra di 90 giorni dopo. Confermare come l'aggregatore espone questo comportamento.
- Provare l'intero flusso in sandbox con dati sintetici, poi verificare il prodotto reale con consenso esplicito. Criterio minimo: due sincronizzazioni dello stesso intervallo non duplicano i movimenti, la revoca impedisce ulteriori letture e i membri di uno spazio non ricevono la cronologia bancaria privata.

## Fonti ufficiali

- [ING Italia: PSD2 e servizi AIS](https://www.ing.it/faq/conti/servizi-digitali/che-cos-e-psd2-come-funziona.html)
- [Revolut: Open Banking API](https://developer.revolut.com/docs/api/open-banking)
- [American Express: Open Banking APIs](https://developer.americanexpress.com/open-banking)
- [Salt Edge: copertura Italia](https://www.saltedge.com/products/account_information/coverage/it)
- [TrueLayer: capacità per provider](https://docs.truelayer.com/docs/supported-providers-table)
- [Google: configurazione OAuth per il login web](https://developers.google.com/identity/gsi/web/guides/get-google-api-clientid)
