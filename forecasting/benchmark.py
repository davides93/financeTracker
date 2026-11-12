"""Small local CPU/MPS inference check; not a forecasting accuracy benchmark."""

import argparse
import platform
import statistics
import time
from types import SimpleNamespace

from .lab import load_pipeline, predict, save_json


def main():
    import torch

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    started = time.perf_counter()
    pipeline = load_pipeline(SimpleNamespace(model=args.model, device='cpu', revision=None))
    report = {'purpose': 'synthetic_inference_smoke_only', 'platform': platform.platform(),
              'torch': torch.__version__, 'parameters': sum(p.numel() for p in pipeline.model.parameters()),
              'load_seconds': time.perf_counter() - started, 'mps_available': torch.backends.mps.is_available(),
              'context': 128, 'horizon': 5, 'model': args.model}
    history = (torch.sin(torch.arange(128) / 9) * 0.01).tolist()
    reference = None
    for device in (['cpu', 'mps'] if report['mps_available'] else ['cpu']):
        pipeline.model.to(device)
        predict(pipeline, history, 5, 128)  # Warm up before timing.
        durations = []
        for _ in range(3):
            if device == 'mps':
                torch.mps.synchronize()
            started = time.perf_counter()
            median, quantiles = predict(pipeline, history, 5, 128)
            durations.append(time.perf_counter() - started)
        quantiles = torch.tensor(quantiles)
        if not torch.isfinite(quantiles).all():
            raise ValueError(f'Non-finite {device} prediction')
        if not (quantiles[:, 1:] >= quantiles[:, :-1]).all():
            raise ValueError(f'Crossing {device} quantiles')
        report[device] = {'median_seconds': statistics.median(durations), 'median_forecast': median}
        if reference is None:
            reference = quantiles
        else:
            report['cpu_mps_max_abs_difference'] = (reference - quantiles).abs().max().item()
            report['cpu_mps_close'] = torch.allclose(reference, quantiles, rtol=1e-3, atol=1e-5)
    save_json(args.output, report)
    print(report, flush=True)


if __name__ == '__main__':
    main()
