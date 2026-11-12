"""Reconstruct the Revolut trading ledger from two CSV strings on stdin."""
import csv
import io
import json
import sys

from .revolut import amount, read_pnl_stream, reconstruct_rows


def main():
    raw = sys.stdin.buffer.read(4_000_001)
    if not raw or len(raw) > 4_000_000:
        raise ValueError("Invalid request size")
    request = json.loads(raw)
    transactions = list(csv.DictReader(io.StringIO(request["account"].removeprefix("\ufeff"))))
    if len(transactions) > 10000:
        raise ValueError("Too many movements")
    pnl = io.StringIO(request["pnl"].removeprefix("\ufeff"))
    snapshot = reconstruct_rows(transactions, *read_pnl_stream(pnl))
    snapshot["movements"] = [
        {
            "date": row["Date"],
            "type": row["Type"],
            "ticker": row["Ticker"],
            "currency": row["Currency"],
            "amount": str(amount(row["Total Amount"], row["Currency"])),
        }
        for row in transactions
    ]
    print(json.dumps(snapshot, allow_nan=False))


if __name__ == "__main__":
    main()
