"""Dependency-free data checks and chronological evaluation."""

import csv
from datetime import datetime
import math


def read_series(path, calendar=None):
    """Read a regular series or daily exchange sessions without filling gaps."""
    with open(path, newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) < 3:
        raise ValueError("Provide at least three observations")
    times = [datetime.fromisoformat(row["timestamp"]) for row in rows]
    values = [float(row["target"]) for row in rows]
    if not all(math.isfinite(value) for value in values):
        raise ValueError("Targets must be finite")
    intervals = [b - a for a, b in zip(times, times[1:])]
    if any(x.total_seconds() <= 0 for x in intervals):
        raise ValueError("Timestamps must be ordered and unique")
    if calendar:
        import exchange_calendars as xcals

        if any(t.tzinfo is not None or t.time().isoformat() != "00:00:00" for t in times):
            raise ValueError("Exchange observations must use timezone-free session dates")
        exchange = xcals.get_calendar(calendar, start=times[0].date(), end=times[-1].date())
        expected = [t.date() for t in exchange.sessions_in_range(times[0], times[-1])]
        if [t.date() for t in times] != expected:
            raise ValueError("Missing or unexpected exchange sessions; do not forward-fill prices")
    elif any(x != intervals[0] for x in intervals):
        raise ValueError("Irregular timestamps: specify an exchange --calendar for daily market data")
    return times, values


def log_returns(times, prices):
    if len(times) != len(prices) or len(prices) < 2:
        raise ValueError("Need matching dates and at least two prices")
    if any(not math.isfinite(p) or p <= 0 for p in prices):
        raise ValueError("Log returns require finite positive prices")
    return times[1:], [math.log(b) - math.log(a) for a, b in zip(prices, prices[1:])]


def directional_metrics(actual, predicted):
    """Zeros count as abstentions; report coverage to expose selective accuracy."""
    if len(actual) != len(predicted) or not actual:
        raise ValueError("Direction arrays must have equal nonzero length")
    if not all(math.isfinite(v) for v in [*actual, *predicted]):
        raise ValueError("Directions must be finite")
    active = [(y, p) for y, p in zip(actual, predicted) if p != 0]
    return {"directional_accuracy_active": sum(y * p > 0 for y, p in active) / len(active) if active else None,
            "directional_coverage": len(active) / len(actual)}


def boundaries(size, horizon, min_context):
    if horizon < 1 or min_context < 1:
        raise ValueError("Horizon and minimum context must be positive")
    train_end, validation_end = int(size * 0.6), int(size * 0.8)
    if train_end < min_context or min(validation_end - train_end, size - validation_end) < horizon:
        raise ValueError("Not enough data for 60/20/20 chronological splits")
    return train_end, validation_end


def windows(values, start, end, horizon, context):
    """Non-overlapping forecast targets; later origins can use newly observed history."""
    if not (0 < start < end <= len(values)) or horizon < 1 or context < 1:
        raise ValueError("Invalid evaluation window")
    for origin in range(start, end - horizon + 1, horizon):
        yield origin, values[max(0, origin - context):origin], values[origin:origin + horizon]


def seasonal(history, horizon, period):
    if period < 1 or len(history) < period:
        raise ValueError("Insufficient context for seasonal baseline")
    return [history[-period + i % period] for i in range(horizon)]


def metrics(actual, median, quantiles=None):
    if not actual or len(actual) != len(median):
        raise ValueError("Prediction length mismatch")
    if not all(math.isfinite(x) for x in [*actual, *median]):
        raise ValueError("Non-finite prediction or target")
    error = [p - y for y, p in zip(actual, median)]
    result = {"mae": sum(map(abs, error)) / len(error),
              "rmse": math.sqrt(sum(x*x for x in error) / len(error)),
              "bias": sum(error) / len(error)}
    if quantiles is not None:
        if len(quantiles) != len(actual):
            raise ValueError("Quantile length mismatch")
        loss, covered, width = 0.0, 0, 0.0
        for y, qs in zip(actual, quantiles):
            if len(qs) != 3 or not all(math.isfinite(q) for q in qs) or not qs[0] <= qs[1] <= qs[2]:
                raise ValueError("Invalid or crossing quantiles")
            covered += qs[0] <= y <= qs[2]
            width += qs[2] - qs[0]
            for level, predicted in zip((0.1, 0.5, 0.9), qs):
                residual = y - predicted
                loss += max(level * residual, (level - 1) * residual)
        result.update(pinball=loss / (3 * len(actual)), coverage_80=covered / len(actual),
                      interval_width=width / len(actual))
    return result
