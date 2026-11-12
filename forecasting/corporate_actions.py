"""Repair a documented partial split adjustment without altering the source file."""

import argparse
import csv
from datetime import date
import hashlib
import json
import math
from pathlib import Path


def repair_split(rows, factor, first_adjusted, official_ex_date):
    if not math.isfinite(factor) or factor <= 1:
        raise ValueError('Require a finite forward split factor greater than one')
    if abs((date.fromisoformat(first_adjusted) - date.fromisoformat(official_ex_date)).days) > 3:
        raise ValueError('Observed adjustment and documented split dates are too far apart')
    values = [float(row['target']) for row in rows]
    if not all(math.isfinite(v) and v > 0 for v in values):
        raise ValueError('Positive finite prices required')
    boundary = next((i for i, row in enumerate(rows) if row['timestamp'] >= first_adjusted), None)
    if boundary is None or boundary == 0:
        raise ValueError('Both sides of the split must be present')
    if not 0.8 < (values[boundary - 1] / values[boundary]) / factor < 1.2:
        raise ValueError('Observed price discontinuity does not match the documented split; do not double-adjust')
    output = [{**row, 'target': values[i] / factor if i < boundary else values[i]} for i, row in enumerate(rows)]
    if max(abs(math.log(b['target']) - math.log(a['target'])) for a, b in zip(output, output[1:])) > 0.5:
        raise ValueError('Large discontinuities remain after the adjustment')
    return output, boundary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--csv', required=True)
    parser.add_argument('--factor', type=float, required=True)
    parser.add_argument('--first-adjusted-date', required=True)
    parser.add_argument('--official-ex-date', required=True)
    parser.add_argument('--source-url', required=True, help='Previously verified issuer evidence')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    path = Path(args.output)
    if path.exists() or path.with_suffix('.audit.json').exists():
        parser.error('Output or audit file already exists')
    with open(args.csv) as stream:
        rows = list(csv.DictReader(stream))
    repaired, count = repair_split(rows, args.factor, args.first_adjusted_date, args.official_ex_date)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=['timestamp', 'target'])
        writer.writeheader()
        writer.writerows(repaired)
    audit = {**vars(args), 'rows_rescaled': count,
             'reason': 'Provider history is only partially adjusted; earlier values are normalized into post-split units',
             'source_sha256': hashlib.sha256(Path(args.csv).read_bytes()).hexdigest(),
             'output_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    path.with_suffix('.audit.json').write_text(json.dumps(audit, indent=2))
    print(f'Rescaled {count} historical observations; original data retained')


if __name__ == '__main__':
    main()
