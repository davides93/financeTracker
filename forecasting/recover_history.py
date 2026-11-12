"""Audit cached downloads, removing only explicitly recorded unfinished tail rows."""

import argparse
import csv
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path

from .core import read_series


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--recent-contiguous', action='store_true', help='Trim history through the last calendar gap, recording all exclusions')
    args = parser.parse_args()
    source, output = Path(args.source), Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    original = json.loads((source / 'manifest.json').read_text())
    results, excluded = [], []
    for index, item in enumerate(original['assets']):
        raw = source / f"{index:03d}-{item['ticker']}" / 'provider-history.csv'
        if not raw.exists():
            excluded.append({**item, 'reason': 'No cached daily history'})
            continue
        with raw.open() as stream:
            rows = list(csv.DictReader(stream))
        removed = []
        while rows and (not math.isfinite(float(rows[-1]['Adj Close'] or 'nan')) or not math.isfinite(float(rows[-1]['Close'] or 'nan'))):
            removed.append(rows.pop()['Date'])
        if not rows or len(removed) > 2:
            excluded.append({**item, 'reason': 'No data or more than two incomplete tail sessions'})
            continue
        gap_audit = None
        if args.recent_contiguous:
            import exchange_calendars as xcals
            dates = [datetime.fromisoformat(row['Date']).date() for row in rows]
            exchange = xcals.get_calendar(item['calendar'], start=dates[0], end=dates[-1])
            expected = {d.date() for d in exchange.sessions_in_range(dates[0], dates[-1])}
            missing, unexpected = expected - set(dates), set(dates) - expected
            if missing or unexpected:
                cutoff = max(missing | unexpected)
                retained = [row for row, day in zip(rows, dates) if day > cutoff]
                gap_audit = {'last_gap_or_unexpected_session': cutoff.isoformat(),
                             'missing_sessions': len(missing), 'unexpected_sessions': len(unexpected),
                             'discarded_earlier_rows': len(rows) - len(retained),
                             'policy': 'Keep only the final complete session segment; no interpolation'}
                rows = retained
        path = output / f"{item['ticker']}.csv"
        try:
            with path.open('x', newline='') as stream:
                writer = csv.writer(stream)
                writer.writerow(['timestamp', 'target'])
                for row in rows:
                    value = float(row['Adj Close'] or 'nan')
                    if not math.isfinite(value) or value <= 0:
                        raise ValueError('Invalid interior adjusted close; no imputation allowed')
                    writer.writerow([datetime.fromisoformat(row['Date']).date().isoformat(), value])
            times, prices = read_series(path, calendar=item['calendar'])
            jump = max(abs(math.log(b) - math.log(a)) for a, b in zip(prices, prices[1:]))
            if jump > 0.5:
                raise ValueError(f'Large unexplained adjusted log return: {jump}')
            # Only recover row-validation failures: these occur after currency validation.
            if not (str(item.get('error', '')).startswith('Invalid adjusted price') or
                    str(item.get('error', '')).startswith('Missing or unexpected exchange sessions')):
                raise ValueError('Original failure does not establish prior currency validation')
            results.append({**{k: item[k] for k in ['ticker', 'quantity', 'currency', 'calendar']},
                            'status': 'downloaded_and_calendar_checked', 'file': str(path),
                            'source': 'Yahoo Finance via cached yfinance download', 'raw_file': str(raw),
                            'csv_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                            'raw_sha256': hashlib.sha256(raw.read_bytes()).hexdigest(),
                            'rows': len(prices), 'first_session': times[0].date().isoformat(),
                            'last_session': times[-1].date().isoformat(), 'last_close': float(rows[-1]['Close']),
                            'max_abs_daily_log_return': jump, 'excluded_unfinished_tail': removed,
                            'calendar_trim': gap_audit,
                            'currency_verified': item['currency'], 'adjustment_vintage': 'latest_snapshot_not_point_in_time'})
        except (ValueError, KeyError) as error:
            excluded.append({**item, 'reason': str(error)})
    report = {'assets': results, 'excluded_assets': excluded, 'original_asset_count': len(original['assets']),
              'partial_portfolio': bool(excluded), 'policy': 'Drop at most two unfinished tail rows; never fill missing interior sessions'}
    (output / 'manifest.json').write_text(json.dumps(report, indent=2, allow_nan=False))
    print(json.dumps({'accepted': len(results), 'excluded': [(x['ticker'], x['reason']) for x in excluded]}, indent=2))


if __name__ == '__main__':
    main()
