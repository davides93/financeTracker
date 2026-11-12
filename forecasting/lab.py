"""Run with python -m forecasting.lab --help from the repository root."""

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path

from .core import boundaries, directional_metrics, log_returns, metrics, read_series, seasonal, windows


def save_json(path, value):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Never overwrite an existing experiment report.
    with destination.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def load_pipeline(args):
    import torch
    from chronos import Chronos2Pipeline

    torch.manual_seed(0)
    if args.device == "mps" and not torch.backends.mps.is_available():
        raise ValueError("MPS is not available in this environment; use --device cpu")
    kwargs = {"device_map": args.device, "dtype": torch.float32}
    if args.revision:
        kwargs["revision"] = args.revision
    pipeline = Chronos2Pipeline.from_pretrained(args.model, **kwargs)
    pipeline.model.eval()
    return pipeline


def predict(pipeline, history, horizon, context):
    import torch

    with torch.inference_mode():
        quantiles, _ = pipeline.predict_quantiles(
            [torch.tensor(history, dtype=torch.float32)], prediction_length=horizon,
            quantile_levels=[0.1, 0.5, 0.9], context_length=context,
        )
    rows = quantiles[0][0].cpu().tolist()
    return [row[1] for row in rows], rows


def evaluate(values, args, pipeline, start, end):
    actual, naive, seasonal_values, predicted, quantiles, origins = [], [], [], [], [], []
    mean_returns, horizon_actual, horizon_predicted = [], [], []
    for origin, history, target in windows(values, start, end, args.horizon, args.context):
        origins.append(origin)
        actual.extend(target)
        naive.extend([history[-1]] * args.horizon)
        seasonal_values.extend(seasonal(history, args.horizon, args.period))
        if args.target == "log-return":
            mean_returns.extend([sum(history) / len(history)] * args.horizon)
            horizon_actual.append(sum(target))
        if pipeline is not None:
            median, qs = predict(pipeline, history, args.horizon, args.context)
            if len(median) != len(target):
                raise ValueError("Model returned the wrong forecast horizon")
            predicted.extend(median)
            quantiles.extend(qs)
            if args.target == "log-return":
                # Sum of marginal medians is only a point proxy, not a joint quantile.
                horizon_predicted.append(sum(median))
    result = {"origins": origins, "observations": len(actual),
              "last_value": metrics(actual, naive), "seasonal_naive": metrics(actual, seasonal_values)}
    if pipeline is not None:
        result["model"] = metrics(actual, predicted, quantiles)
    if args.target == "log-return":
        result["zero_return"] = metrics(actual, [0.0] * len(actual))
        result["historical_mean_return"] = metrics(actual, mean_returns)
        result["horizon_zero_return"] = metrics(horizon_actual, [0.0] * len(horizon_actual))
        if pipeline is not None:
            result["model"].update(directional_metrics(actual, predicted))
            result["horizon_sum_of_medians_proxy"] = {
                **metrics(horizon_actual, horizon_predicted),
                **directional_metrics(horizon_actual, horizon_predicted),
            }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["baseline", "inspect", "evaluate", "finetune", "export"])
    parser.add_argument("--csv", help="Single regular series: timestamp,target")
    parser.add_argument("--output", required=True, help="New report path or new checkpoint directory")
    parser.add_argument("--model", default="amazon/chronos-2")
    parser.add_argument("--revision", help="Pin a Hugging Face commit for reproducibility")
    parser.add_argument("--device", choices=["cpu", "cuda", "mps"], default="cpu")
    parser.add_argument("--calendar", help="Daily session calendar, e.g. XNYS, XMIL or 24/7")
    parser.add_argument("--target", choices=["level", "log-return"], default="level",
                        help="log-return converts positive input prices to one-session log returns")
    parser.add_argument("--horizon", type=int, default=7)
    parser.add_argument("--context", type=int, default=512)
    parser.add_argument("--min-context", type=int, default=28)
    parser.add_argument("--period", type=int, default=7)
    parser.add_argument("--split", choices=["validation", "test"], default="validation")
    parser.add_argument("--patch", help="JSON manifest with explicit scalar edits")
    parser.add_argument("--steps", type=int, default=200)
    args = parser.parse_args()
    if Path(args.output).exists():
        parser.error("Output already exists; use a new experiment name")
    if args.patch and args.action not in {"evaluate", "export"}:
        parser.error("--patch is supported only for evaluate and export")
    if args.action == "export" and not args.patch:
        parser.error("Export requires --patch")
    if args.action == "finetune" and args.device == "mps":
        parser.error("LoRA on MPS is not validated in this harness; use CPU or CUDA")
    if args.horizon < 1 or args.steps < 1 or not 1 <= args.period <= args.min_context <= args.context:
        parser.error("Require positive horizon/steps and 1 <= period <= min-context <= context")

    metadata = {"arguments": vars(args), "status": "research_only"}
    values = None
    if args.action in {"baseline", "evaluate", "finetune"}:
        if not args.csv:
            parser.error("--csv is required")
        times, values = read_series(args.csv, calendar=args.calendar)
        if args.target == "log-return":
            times, values = log_returns(times, values)
        train_end, validation_end = boundaries(len(values), args.horizon, args.min_context)
        metadata.update(data_sha256=hashlib.sha256(Path(args.csv).read_bytes()).hexdigest(),
                        train_end_exclusive=train_end, validation_end_exclusive=validation_end,
                        total_rows=len(values), units="log_return" if args.target == "log-return" else "input_units",
                        train_last_timestamp=times[train_end - 1].isoformat(),
                        validation_last_timestamp=times[validation_end - 1].isoformat())
        start, end = (train_end, validation_end) if args.split == "validation" else (validation_end, len(values))

    pipeline = None if args.action == "baseline" else load_pipeline(args)
    if pipeline is not None:
        metadata["versions"] = {name: importlib.metadata.version(name)
                                for name in ["torch", "chronos-forecasting", "transformers"]}
        metadata["resolved_revision"] = getattr(pipeline.model.config, "_commit_hash", None)

    if args.action == "inspect":
        from .weights import inventory
        save_json(args.output, {**metadata, "tensors": inventory(pipeline.model)})
    elif args.action == "finetune":
        import torch
        import peft  # Fail early rather than silently falling back to full fine-tuning.

        if train_end < 2 * args.horizon:
            parser.error("Training history must contain at least twice the horizon")
        pipeline.fit([torch.tensor(values[:train_end], dtype=torch.float32)],
                     prediction_length=args.horizon, finetune_mode="lora", learning_rate=1e-5,
                     num_steps=args.steps, batch_size=8, context_length=args.context,
                     output_dir=args.output, report_to="none", seed=0)
        save_json(Path(args.output) / "experiment.json", metadata)
    elif args.action == "export":
        from .weights import edited
        manifest = json.loads(Path(args.patch).read_text())
        with edited(pipeline.model, manifest) as change:
            pipeline.save_pretrained(args.output, safe_serialization=True)
            save_json(Path(args.output) / "experiment.json", {**metadata, "patch": manifest, "change": change})
    else:
        # Always compare the untouched model on exactly the same origins.
        result = {**metadata, "base": evaluate(values, args, pipeline, start, end)}
        if args.patch:
            from .weights import edited
            manifest = json.loads(Path(args.patch).read_text())
            with edited(pipeline.model, manifest) as change:
                result["edited"] = evaluate(values, args, pipeline, start, end)
                result.update(patch=manifest, change=change)
        save_json(args.output, result)
    print(f"Saved: {args.output}")


if __name__ == "__main__":
    main()
