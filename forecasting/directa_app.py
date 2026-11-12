"""Build a portfolio preview from a Directa CSV streamed over stdin."""
import json
import sys
from pathlib import Path

from .directa import parse_text
from .monitor import refresh

ROOT = Path(__file__).resolve().parent


def load(relative):
    return json.loads((ROOT / relative).read_text())


def main():
    text = sys.stdin.buffer.read(2_000_001)
    if not text or len(text) > 2_000_000:
        raise ValueError("Invalid upload size")
    imported = parse_text(text.decode("utf-8-sig"))
    config = load("outputs/combined-five-year/scenarios.json")["config"]
    revolut = load("outputs/revolut-calibration-v1/portfolio-summary.json")
    # Legacy snapshots may have a date in their filename; keep local compatibility.
    snapshots = sorted((ROOT / "data/directa").glob("holdings*.json"))
    if len(snapshots) != 1:
        raise ValueError("Provide exactly one local holdings snapshot in data/directa")
    snapshot = json.loads(snapshots[0].read_text())
    config["start_date"] = max(config["start_date"], imported["latest_confirmed"]["date"], revolut["as_of"])
    bundle = refresh(config, imported, revolut, snapshot)
    bundle["directa_history"] = {
        "valuations": len(imported["valuations"]),
        "from": imported["valuations"][0]["date"],
        "through": imported["latest_confirmed"]["date"],
        "movements": [
            {"date": m["date"], "description": m["description"], "amount": float(m["value_eur"])}
            for m in imported["movements"]
        ],
    }
    print(json.dumps(bundle, allow_nan=False))


if __name__ == "__main__":
    main()
