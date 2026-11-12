"""Refresh local two-account monitoring and five-year sensitivity reports."""
import argparse
import copy
import json
from datetime import date, timedelta
from pathlib import Path

from .scenarios import add_months, project, schedule


def euro(value):
    return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " €"


def refresh(config, directa, revolut, snapshot):
    config = copy.deepcopy(config)
    latest = directa["latest_confirmed"]
    for key, amount, as_of in (("directa", float(latest["total_eur"]), latest["date"]), ("revolut", revolut["estimated_total_value_eur"], revolut["as_of"])):
        if as_of > config["start_date"]:
            raise ValueError("Scenario start precedes a source valuation")
        config["accounts"][key].update(initial_eur=amount, as_of=as_of)
    results = {name: project(config, rates) for name, rates in config["scenarios"].items()}
    total = sum(a["initial_eur"] for a in config["accounts"].values())
    same_date = next((v for v in directa["valuations"] if v["date"] == revolut["as_of"] and not v["provisional"]), None)
    sep = next((v for v in directa["valuations"] if v["date"] == snapshot["as_of"] and not v["provisional"]), None)
    audit = dict(latest_known_total_eur=total, mixed_valuation_dates=latest["date"] != revolut["as_of"], common_date=revolut["as_of"] if same_date else None, common_date_total_eur=float(same_date["total_eur"]) + revolut["estimated_total_value_eur"] if same_date else None, snapshot_cash_difference_eur=round(float(sep["cash_eur"]) - snapshot["cash_eur"], 2) if sep else None, snapshot_securities_match=float(sep["securities_eur"]) == snapshot["securities_eur"] if sep else None, provisional_dates_excluded=[v["date"] for v in directa["valuations"] if v["provisional"]], latest_directa_quantity=None, valuation_age_days={k: (date.fromisoformat(config["start_date"]) - date.fromisoformat(a["as_of"])).days for k, a in config["accounts"].items()})
    return dict(config=config, results=results, audit=audit)


def report(bundle, directa, revolut, snapshot):
    c, r, a = bundle["config"], bundle["results"], bundle["audit"]
    first = min(v["date"] for v in directa["valuations"] if not v["provisional"])
    monthly = c["accounts"]["directa"]["monthly_eur"]
    weekly = c["accounts"]["revolut"]["weekly_eur"]
    example = r["esempio"]["final"]
    start = date.fromisoformat(c["start_date"])
    end = date.fromisoformat(example["date"])
    monthly_count = len(schedule(start, end, monthly=monthly))
    weekly_count = len(schedule(start, end, weekly=weekly))
    lines = ["# Portafogli e scenari a cinque anni", "", f"Elaborazione locale al {c['start_date']}. Valori in euro. Dati personali non pubblicati.", "", "## Situazione di partenza", "", "| Conto | Data della valorizzazione | Patrimonio | Nuovi versamenti |", "|---|---|---:|---|", f"| Directa | {c['accounts']['directa']['as_of']} | {euro(c['accounts']['directa']['initial_eur'])} | {euro(monthly)} al mese |", f"| Revolut | {c['accounts']['revolut']['as_of']} | {euro(c['accounts']['revolut']['initial_eur'])} stimati | {euro(weekly)} alla settimana |", "", f"Totale degli ultimi valori disponibili: **{euro(a['latest_known_total_eur'])}**. Le date differiscono: non è una valorizzazione simultanea in tempo reale."]
    if a["common_date"]:
        lines += [f"Alla data comune {a['common_date']} il totale era {euro(a['common_date_total_eur'])}."]
    lines += ["", f"La fotografia Directa del {snapshot['as_of']} documenta le posizioni storiche fornite dall’utente. Il CSV aggiornato contiene i valori del conto, non le quantità attuali. Verificare composizione ed esposizioni con un estratto posizioni aggiornato.", "", "## Controlli sui dati", "", f"- Righe provvisorie escluse: {', '.join(a['provisional_dates_excluded']) or 'nessuna'}.", f"- Liquidità Directa: differenza CSV meno PDF alla data del PDF = {euro(a['snapshot_cash_difference_eur']) if a['snapshot_cash_difference_eur'] is not None else 'non confrontabile'}. Titoli coincidenti: {a['snapshot_securities_match']}. Differenza non corretta automaticamente; causa da riconciliare con i movimenti di cassa.", "- Le due tabelle affiancate nel CSV hanno date indipendenti; la data del movimento non è quella del patrimonio nella stessa riga.", "- Revolut è una ricostruzione da movimenti e quotazioni pubbliche, con le ipotesi e i limiti del precedente rapporto. Il valore va confrontato con un estratto patrimoniale del broker."]
    p = directa["performance"]
    if p:
        lines += [f"- Directa dal {first}: {euro(float(p['external_flows_eur']))} di flussi esterni netti; variazione patrimoniale al netto dei flussi {euro(float(p['value_change_less_external_flows_eur']))}. Include i costi già addebitati; non è una percentuale di rendimento né una previsione."]
    else:
        lines += ["- Performance sospesa: classificare i movimenti non riconosciuti prima di separare flussi e rendimento."]
    lines += ["", "## Scenari, non previsioni", "", "I tassi seguenti sono ipotesi scelte per esplorare la sensibilità: non sono stimati dalla rete, non sono rendimenti promessi e non hanno probabilità assegnate. Gli esiti reali possono essere anche peggiori dello scenario avverso.", "", "| Scenario | Directa annuo | Revolut annuo | Patrimonio finale | Risultato oltre capitale iniziale e nuovi versamenti | Potere d'acquisto iniziale, inflazione 2% |", "|---|---:|---:|---:|---:|---:|"]
    for name, result in r.items():
        f = result["final"]
        lines += [f"| {name} | {result['rates']['directa']:+.0%} | {result['rates']['revolut']:+.0%} | {euro(f['total_eur'])} | {euro(f['growth_eur'])} | {euro(f['purchasing_power_eur'])} |"]
    lines += ["", f"I nuovi versamenti sono {euro(example['new_contributions_eur'])}: {monthly_count} rate mensili Directa e {weekly_count} rate settimanali Revolut. Prima rata mensile {add_months(start, 1)}, prima settimanale {start + timedelta(days=7)}; le date sono assunzioni operative. Non sono stati configurati ordini o bonifici.", "", f"Nello scenario esempio, Directa arriverebbe a {euro(example['accounts_eur']['directa'])}, Revolut a {euro(example['accounts_eur']['revolut'])}.", "", f"Rendimenti annui effettivi costanti, netti dei costi ricorrenti ipotizzati ma prima delle imposte personali. Non viene stimato il netto liquidabile dopo tasse. I tassi non sono tarati sulle commissioni effettive dei conti; TER e commissioni non vanno sottratti una seconda volta se già inclusi nel rendimento usato. Inflazione al {c.get('inflation_assumption', .02):.1%} come ipotesi modificabile. Versamenti investiti immediatamente e quote frazionarie teoriche: nella pratica il PAC Directa può lasciare liquidità per l'acquisto di quote intere.", "", "L'andamento regolare è una semplificazione. Un ribasso vicino alla data di uscita può cambiare molto il risultato: applicando, solo come stress illustrativo, -30% a Directa e -20% a Revolut al valore finale dell'esempio si ottiene " + euro(example['accounts_eur']['directa'] * .7 + example['accounts_eur']['revolut'] * .8) + ". Non è un limite inferiore né una stima di probabilità.", "", "## Come monitorare", "", "1. Ogni mese importa il CSV patrimonio Directa, l'elenco posizioni aggiornato e gli estratti Revolut; confronta titoli e cassa con i broker. Conserva data e provenienza di ogni valore.", "2. Controlla separatamente capitale versato, rendimento, costi, liquidità e massimo calo dai massimi. Per TWR/XIRR servono flussi completi e date; l'import attuale riporta il risultato assoluto al netto dei flussi.", "3. Rivedi periodicamente esposizione azionaria/obbligazionaria, sovrapposizioni, costi e obiettivo finale. Un ribilanciamento richiede obiettivi e tolleranza alle perdite espliciti; qui non viene eseguito.", "4. Se i soldi devono essere disponibili a una data precisa tra cinque anni, valuta la quota che deve essere preservata e l'effetto di un calo vicino alla scadenza. Un orizzonte di cinque anni non garantisce il recupero delle perdite.", "", "Questo monitor è locale e si aggiorna importando nuovi file. Non è ancora collegato alla dashboard dimostrativa, non recupera automaticamente i conti e non invia notifiche periodiche.", "", "## Stato del modello AI", "", f"Il precedente test Revolut ha mostrato un MAE della previsione mediana superiore del {revolut['historical_test_mae_relative_to_zero_return_percent']:.2f}% rispetto alla previsione di rendimento nullo. La modifica dei pesi ha peggiorato la pinball loss di validazione dello {revolut['validation_patch_pinball_change_percent']:.2f}%: non è stata promossa.", "", "Il [lavoro sul weight-space programming](https://rikiyat.github.io/blog/weight-space-programming/) dimostra esperimenti su reti e compiti specifici, non la prevedibilità dei mercati a cinque anni. Nuove modifiche devono superare validazione cronologica e test futuri mai usati per la selezione. Gli estratti conto descrivono esposizioni e flussi, non costituiscono da soli dati sufficienti per addestrare una rete di previsione a lungo termine.", "", "## File e riproducibilità", "", "- Dati Directa, fonti e fotografia del PDF: `forecasting/data/directa/`.", "- Configurazione PAC e ipotesi: `forecasting/data/combined/scenario-config.json`.", "- Risultati, date, controlli e percorsi simulati: `forecasting/outputs/combined-five-year/scenarios.json`.", "- Procedura di aggiornamento: `forecasting/README.md`."]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--directa", type=Path, required=True)
    parser.add_argument("--revolut", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    config, directa, revolut, snapshot = [json.loads(path.read_text()) for path in (args.config, args.directa, args.revolut, args.snapshot)]
    bundle = refresh(config, directa, revolut, snapshot)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "scenarios.json").write_text(json.dumps(bundle, indent=2, ensure_ascii=False) + "\n")
    (args.output / "LEGGIMI.md").write_text(report(bundle, directa, revolut, snapshot))
    print(json.dumps(bundle["audit"], ensure_ascii=False))


if __name__ == "__main__":
    main()
