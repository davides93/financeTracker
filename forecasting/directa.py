"""Local import of Directa PatrimonioTotale exports (two independent tables)."""
import argparse
import csv
import hashlib
import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path


def money(value):
    value = value.strip().replace("€", "").replace(" ", "")
    if not value:
        raise ValueError("Missing monetary value")
    result = Decimal(value.replace(".", "").replace(",", "."))
    if not result.is_finite():
        raise ValueError("Non-finite monetary value")
    return result


def day(value):
    # This export uses US dates even when its headings are Italian.
    return datetime.strptime(value.strip(), "%m/%d/%y").date().isoformat()


def parse(path):
    path = Path(path)
    raw = path.read_bytes()
    return dict(parse_text(raw.decode("utf-8-sig")), source=str(path.resolve()), source_sha256=hashlib.sha256(raw).hexdigest())


def parse_text(text):
    rows = list(csv.reader(text.removeprefix("\ufeff").splitlines(), delimiter=";"))
    left_start = next(i for i, r in enumerate(rows) if len(r) >= 6 and r[0].strip() == "Data" and r[5].strip() == "Patrimonio")
    right_start = next(i for i, r in enumerate(rows) if len(r) >= 11 and r[8].strip() == "Data" and r[9].strip() == "Descrizione")
    valuations, movements = [], []
    seen = set()
    for index, row in enumerate(rows):
        line = index + 1
        if not any(c.strip() for c in row):
            continue
        row += [""] * max(0, 14 - len(row))
        if index > left_start and row[0].strip():
            date = day(row[0])
            if date in seen:
                raise ValueError(f"Duplicate valuation date {date}")
            seen.add(date)
            values = [money(x) for x in row[1:6]]
            cash, financing, collateral, securities, total = values
            # Short/leveraged portfolios require a separately validated convention.
            if financing != 0 or collateral != 0:
                raise ValueError(f"Unsupported leveraged/short valuation at line {line}")
            if abs(cash + securities - total) > Decimal("0.01"):
                raise ValueError(f"Valuation does not reconcile at line {line}")
            note = row[6].strip()
            valuations.append(dict(date=date, cash_eur=str(cash), securities_eur=str(securities), total_eur=str(total), note=note, provisional="provvisor" in note.lower()))
        if index > right_start and row[8].strip():
            description = row[9].strip()
            lower = description.lower()
            kind = "external_flow" if any(k in lower for k in ("bonifico", "versamento", "prelievo")) else "cost" if "bollo" in lower else "unclassified"
            movements.append(dict(date=day(row[8]), description=description, value_eur=str(money(row[10])), kind=kind, source_line=line))
    valuations.sort(key=lambda x: x["date"])
    confirmed = [v for v in valuations if not v["provisional"]]
    if not confirmed:
        raise ValueError("No confirmed valuations")
    first, last = confirmed[0], confirmed[-1]
    relevant = [m for m in movements if first["date"] < m["date"] <= last["date"]]
    unknown = [m for m in relevant if m["kind"] == "unclassified"]
    flows = sum((Decimal(m["value_eur"]) for m in relevant if m["kind"] == "external_flow"), Decimal(0))
    performance = None if unknown else {
        "external_flows_eur": str(flows),
        "value_change_less_external_flows_eur": str(Decimal(last["total_eur"]) - Decimal(first["total_eur"]) - flows),
        "meaning": "Absolute change after external flows; includes costs; not a rate of return",
    }
    return dict(date_format="MM/DD/YY", valuations=valuations, movements=movements, latest_confirmed=last, performance=performance, warnings=["Movements have their own date column; trade quantities are not supplied."] + (["Unclassified movements: performance withheld."] if unknown else []))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = parse(args.csv)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "import.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    for key in ("valuations", "movements"):
        items = result[key]
        if items:
            with (args.output / f"{key}.csv").open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=items[0].keys())
                writer.writeheader()
                writer.writerows(items)
    print(json.dumps(dict(latest_confirmed=result["latest_confirmed"], performance=result["performance"], warnings=result["warnings"]), ensure_ascii=False))


if __name__ == "__main__":
    main()
