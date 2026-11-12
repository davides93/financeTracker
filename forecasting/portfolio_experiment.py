"""Chronos-2 experiment with global time cutoffs and small direct tail edits."""

import argparse
from bisect import bisect_right
from contextlib import nullcontext
from datetime import datetime
import json
import math
from pathlib import Path
import statistics
from types import SimpleNamespace

from .calibration import tail_spread_manifest
from .core import log_returns, read_series
from .lab import evaluate, load_pipeline, predict, save_json
from .weights import edited


def section(series, args, pipeline, split):
    results = {}
    for item in series:
        times, values = item['times'], item['returns']
        validation_start = max(args.min_context, bisect_right(times, datetime.fromisoformat(args.train_end)))
        validation_end = bisect_right(times, datetime.fromisoformat(args.validation_end))
        start, end = (validation_start, validation_end) if split == 'validation' else (max(args.min_context, validation_end), len(values))
        if end - start < 4 * args.horizon:
            results[item['ticker']] = {'excluded': 'Fewer than four complete forecast windows'}
            continue
        result = evaluate(values, args, pipeline, start, end)
        # Scale is fixed using only data before the validation period, for both splits.
        scale = max(statistics.pstdev(values[:validation_start]), 1e-8)
        result['normalized_pinball'] = result['model']['pinball'] / scale
        result['first_target'] = times[start].date().isoformat()
        result['last_available_target'] = times[end - 1].date().isoformat()
        results[item['ticker']] = result
    included = [r for r in results.values() if 'excluded' not in r]
    if not included:
        raise ValueError(f'No eligible assets for {split}')
    return {'assets': results, 'macro': {
        'asset_count': len(included),
        'normalized_pinball': statistics.mean(r['normalized_pinball'] for r in included),
        'coverage_80': statistics.mean(r['model']['coverage_80'] for r in included),
        'median_mae': statistics.mean(r['model']['mae'] for r in included),
        'zero_return_mae': statistics.mean(r['zero_return']['mae'] for r in included),
    }}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True, help='market_data manifest.json')
    parser.add_argument('--model', required=True)
    parser.add_argument('--output', required=True, help='New experiment directory')
    parser.add_argument('--device', choices=['cpu', 'mps'], default='cpu')
    parser.add_argument('--train-end', default='2024-12-31')
    parser.add_argument('--validation-end', default='2026-06-30')
    parser.add_argument('--horizon', type=int, default=5)
    parser.add_argument('--context', type=int, default=128)
    args = parser.parse_args()
    if datetime.fromisoformat(args.train_end) >= datetime.fromisoformat(args.validation_end):
        parser.error('Global training cutoff must precede validation cutoff')
    if args.horizon < 1 or args.context < 28:
        parser.error('Require positive horizon and context >= 28')
    root = Path(args.output)
    root.mkdir(parents=True, exist_ok=False)
    args.min_context, args.period, args.target = 28, 5, 'log-return'
    args.revision = None
    manifest = json.loads(Path(args.manifest).read_text())
    if any(a['status'] != 'downloaded_and_calendar_checked' for a in manifest['assets']):
        parser.error('Source manifest contains failed assets; resolve them before this experiment')
    series = []
    for asset in manifest['assets']:
        if asset.get('quality_flag'):
            parser.error(f"Unresolved data-quality flag for {asset['ticker']}: {asset['quality_flag']}")
        times, prices = read_series(asset['file'], calendar=asset['calendar'])
        times, returns = log_returns(times, prices)
        series.append({**asset, 'times': times, 'returns': returns})
    pipeline = load_pipeline(args)
    if args.horizon > pipeline.model.chronos_config.output_patch_size:
        parser.error('Tail calibration is validated only within one output patch')
    report = {'config': vars(args), 'data_sources': manifest, 'limitations': [
        'Historical evaluation on the current holdings, not historical broker portfolio performance',
        'Foundation-model pretraining overlap with historical evaluation is unverified',
        'Latest adjusted price snapshots are not point-in-time data',
        'Tail calibration changes uncertainty; it does not improve median return predictions',
        'Test used once after validation selection; no statistical significance established',
    ]}
    print('Evaluating original checkpoint on validation', flush=True)
    baseline = section(series, args, pipeline, 'validation')
    report['validation_original'] = baseline
    candidates, chosen = [], None
    best_loss = baseline['macro']['normalized_pinball']
    base_coverage_error = abs(baseline['macro']['coverage_80'] - 0.8)
    for factor in [1.05, 1.10, 1.20]:
        patch = tail_spread_manifest(pipeline, factor)
        try:
            with edited(pipeline.model, patch) as change:
                print(f'Evaluating direct weight edit, tail spread {factor}', flush=True)
                result = section(series, args, pipeline, 'validation')
            candidate = {'factor': factor, 'validation': result, 'change': change}
            score = result['macro']['normalized_pinball']
            if (score < best_loss and score < baseline['macro']['normalized_pinball'] * 0.999
                    and abs(result['macro']['coverage_80'] - 0.8) <= base_coverage_error):
                best_loss, chosen = score, patch
        except ValueError as error:
            candidate = {'factor': factor, 'rejected': str(error)}
        candidates.append(candidate)
    report['candidates'] = candidates
    # Freeze the choice before the first read of test outcomes.
    save_json(root / 'frozen-selection.json', {'patch': chosen, 'selection_metric': 'macro normalized pinball on validation',
                                             'train_end': args.train_end, 'validation_end': args.validation_end})
    print('Frozen selection; evaluating final historical test', flush=True)
    report['test_original'] = section(series, args, pipeline, 'test')
    accepted = False
    if chosen:
        with edited(pipeline.model, chosen):
            report['test_edited'] = section(series, args, pipeline, 'test')
        original, proposed = report['test_original']['macro'], report['test_edited']['macro']
        accepted = (proposed['normalized_pinball'] < original['normalized_pinball']
                    and abs(proposed['coverage_80'] - 0.8) <= abs(original['coverage_80'] - 0.8))
        save_json(root / 'selected-patch.json', chosen)
    report['accepted_for_experimental_forecasts'] = accepted
    report['forecast_model'] = 'edited_research_candidate' if accepted else 'original_chronos_2'
    forecasts = []
    with edited(pipeline.model, chosen) if accepted else nullcontext():
        if accepted:
            pipeline.save_pretrained(root / 'edited-checkpoint', safe_serialization=True)
        for item in series:
            median, quantiles = predict(pipeline, item['returns'][-args.context:], args.horizon, args.context)
            forecasts.append({'ticker': item['ticker'], 'as_of_session': item['times'][-1].date().isoformat(),
                              'horizon_sessions': args.horizon, 'median_log_return_by_step': median,
                              'p10_p50_p90_log_return_by_step': quantiles,
                              'cumulative_return_point_proxy': math.expm1(sum(median)),
                              'aggregate_interval': None,
                              'note': 'Sum of marginal medians is a point proxy, not the median or interval of the cumulative return'})
    save_json(root / 'forecasts.json', {'model': report['forecast_model'], 'assets': forecasts})
    save_json(root / 'report.json', report)
    print(json.dumps({'accepted': accepted, 'original_test': report['test_original']['macro'],
                      'edited_test': report.get('test_edited', {}).get('macro')}, indent=2), flush=True)


if __name__ == '__main__':
    main()
