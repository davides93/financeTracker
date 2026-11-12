"""Resolve broker identifiers through public ISIN searches, never ticker guessing."""

import argparse
import csv
import json
from pathlib import Path


def main():
    import yfinance as yf

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', required=True)
    parser.add_argument('--identities', help='Optional verified ISIN additions: symbol -> isin, name, source')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    snapshot = json.loads(Path(args.snapshot).read_text())
    additions = json.loads(Path(args.identities).read_text()) if args.identities else {}
    root = Path(args.output)
    root.mkdir(parents=True, exist_ok=False)
    yf.set_tz_cache_location(str(root / '.provider-cache'))
    results = []
    for position in snapshot['positions']:
        if not position['open']:
            continue
        position = {**position, **additions.get(position['broker_ticker'], {})}
        result = {**position, 'provider_mapping_status': 'unresolved'}
        if position.get('isin'):
            try:
                quotes = yf.Search(position['isin'], max_results=20, news_count=0, lists_count=0, recommended=0).quotes
                result['isin_search_results'] = quotes
                matches = [q for q in quotes if q.get('symbol') == position['broker_ticker'] + '.DE']
                if len(matches) == 1:
                    result.update(ticker=matches[0]['symbol'], calendar='XETR',
                                  provider_mapping_status='matched_by_isin_search')
            except Exception as error:
                result['error'] = str(error)
        results.append(result)
        print(position['broker_ticker'], result['provider_mapping_status'], flush=True)
        (root / 'mapping.json').write_text(json.dumps(results, indent=2))
    with (root / 'portfolio.csv').open('x', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=['ticker', 'quantity', 'currency', 'calendar'])
        writer.writeheader()
        for result in results:
            if result['provider_mapping_status'] == 'matched_by_isin_search':
                writer.writerow({key: result[key] for key in writer.fieldnames})
    if any(r['provider_mapping_status'] == 'unresolved' for r in results):
        raise SystemExit('Unresolved instruments remain; the generated CSV is a partial portfolio')


if __name__ == '__main__':
    main()
