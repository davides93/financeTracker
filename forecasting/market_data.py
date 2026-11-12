"""Download daily adjusted prices for a user-supplied portfolio, without trading."""

import argparse
import csv
from datetime import date, datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re

from .core import read_series


def read_portfolio(path):
    with open(path, newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError("Empty portfolio")
    result, seen = [], set()
    for row in rows:
        ticker = row["ticker"].strip().upper()
        currency, calendar = row["currency"].strip(), row["calendar"].strip()
        quantity = float(row["quantity"])
        if not re.fullmatch(r"[A-Z0-9^][A-Z0-9.^=\-]{0,39}", ticker):
            raise ValueError(f"Invalid Yahoo ticker: {ticker!r}")
        if ticker in seen or not math.isfinite(quantity) or quantity <= 0:
            raise ValueError("Use one row per ticker with a finite positive quantity")
        if not currency or not calendar:
            raise ValueError("Currency and calendar are required")
        seen.add(ticker)
        result.append(dict(ticker=ticker, quantity=quantity, currency=currency, calendar=calendar))
    return result


def download(position, start, end, output):
    import yfinance as yf

    ticker = position["ticker"]
    asset = yf.Ticker(ticker)
    frame = asset.history(start=start, end=end, interval="1d", auto_adjust=False,
                          actions=True, repair=False, raise_errors=True)
    if frame.empty or "Adj Close" not in frame.columns:
        raise ValueError(f"No adjusted daily history for {ticker}")
    provider_metadata = asset.get_history_metadata()
    actual_currency = provider_metadata.get("currency")
    if actual_currency != position["currency"]:
        raise ValueError(f"Currency mismatch for {ticker}: expected {position['currency']}, received {actual_currency}")
    # Keep the raw download and its corporate actions for later data-quality checks.
    frame.to_csv(output / "provider-history.csv")
    path = output / "prices.csv"
    with path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["timestamp", "target"])
        for timestamp, value in frame["Adj Close"].items():
            if not math.isfinite(float(value)) or value <= 0:
                raise ValueError(f"Invalid adjusted price for {ticker} at {timestamp}")
            writer.writerow([timestamp.date().isoformat(), float(value)])
    times, prices = read_series(path, calendar=position["calendar"])
    largest_jump = max(abs(math.log(b) - math.log(a)) for a, b in zip(prices, prices[1:]))
    return {**position, "status": "downloaded_and_calendar_checked", "source": "Yahoo Finance via yfinance",
            "yfinance_version": yf.__version__, "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
            "requested_start": start, "requested_end_exclusive": end,
            "first_session": times[0].date().isoformat(), "last_session": times[-1].date().isoformat(),
            "rows": len(times), "price_field": "Adj Close", "adjustment_vintage": "latest_provider_snapshot_not_point_in_time",
            "last_close": float(frame['Close'].iloc[-1]), "last_adjusted_close": prices[-1],
            "max_abs_daily_log_return": largest_jump,
            "quality_flag": "review_large_price_jump" if largest_jump > 0.5 else None,
            "exchange": provider_metadata.get("exchangeName"), "currency_verified": actual_currency,
            "csv_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "file": str(path)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--portfolio", required=True)
    parser.add_argument("--start", required=True, help="YYYY-MM-DD, inclusive")
    parser.add_argument("--end", required=True, help="YYYY-MM-DD, exclusive; exclude incomplete sessions")
    parser.add_argument("--output", required=True, help="New directory, never overwritten")
    args = parser.parse_args()
    if date.fromisoformat(args.start) >= date.fromisoformat(args.end):
        parser.error("start must precede end")
    positions = read_portfolio(args.portfolio)
    root = Path(args.output)
    root.mkdir(parents=True, exist_ok=False)
    import yfinance as yf
    yf.set_tz_cache_location(str(root / ".provider-cache"))
    results = []
    for index, position in enumerate(positions):
        folder = root / f"{index:03d}-{position['ticker']}"
        folder.mkdir()
        try:
            result = download(position, args.start, args.end, folder)
        except Exception as error:
            result = {**position, "status": "failed", "error": str(error)}
        results.append(result)
        print(f"{position['ticker']}: {result['status']}", flush=True)
    with (root / "manifest.json").open("x", encoding="utf-8") as stream:
        json.dump({"assets": results, "purpose": "personal_research", "orders_placed": False}, stream, indent=2, allow_nan=False)
        stream.write("\n")
    if any(result["status"] == "failed" for result in results):
        raise SystemExit("Some downloads failed; inspect manifest.json before using any data")


if __name__ == "__main__":
    main()
