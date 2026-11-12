"""Deterministic cash-flow scenarios, not model forecasts or probabilities."""
import argparse
import calendar
import json
import math
from datetime import date, timedelta
from pathlib import Path


def add_months(start, count):
    year, month0 = divmod(start.year * 12 + start.month - 1 + count, 12)
    month = month0 + 1
    return date(year, month, min(start.day, calendar.monthrange(year, month)[1]))


def schedule(start, end, monthly=0, weekly=0):
    if any(not math.isfinite(v) or v < 0 for v in (monthly, weekly)):
        raise ValueError("Contributions must be finite and non-negative")
    events = {}
    for n in range(1, (end.year - start.year) * 12 + 13):
        payment = add_months(start, n)
        if payment > end:
            break
        events[payment] = events.get(payment, 0) + monthly
    payment = start + timedelta(days=7)
    while payment <= end:
        events[payment] = events.get(payment, 0) + weekly
        payment += timedelta(days=7)
    return {d: v for d, v in events.items() if v}


def project(config, rates):
    start = date.fromisoformat(config["start_date"])
    years = config.get("years", 5)
    if not isinstance(years, int) or not 1 <= years <= 50:
        raise ValueError("years must be an integer from 1 to 50")
    end = add_months(start, years * 12)
    inflation = config.get("inflation_assumption", 0.02)
    if not math.isfinite(inflation) or inflation <= -1:
        raise ValueError("Invalid inflation assumption")
    accounts = config["accounts"]
    balances = {key: float(a["initial_eur"]) for key, a in accounts.items()}
    if any(not math.isfinite(x) or x < 0 for x in balances.values()):
        raise ValueError("Invalid initial balance")
    for key in accounts:
        if not math.isfinite(rates[key]) or rates[key] <= -1:
            raise ValueError("Rates must be finite and above -100%")
    events = {k: schedule(start, end, a.get("monthly_eur", 0), a.get("weekly_eur", 0)) for k, a in accounts.items()}
    checkpoints = {add_months(start, i) for i in range(years * 12 + 1)}
    dates = sorted(checkpoints.union(*(set(v) for v in events.values())))
    initial = sum(balances.values())
    contributed = {key: 0 for key in accounts}
    previous = start
    path = []
    for current in dates:
        dt = (current - previous).days / 365.25
        for key in accounts:
            balances[key] *= (1 + rates[key]) ** dt
            payment = events[key].get(current, 0)
            balances[key] += payment
            contributed[key] += payment
        total = sum(balances.values())
        paid = sum(contributed.values())
        path.append(dict(date=current.isoformat(), total_eur=total, accounts_eur=balances.copy(), new_contributions_eur=paid, capital_without_returns_eur=initial + paid, growth_eur=total - initial - paid, purchasing_power_eur=total / (1 + inflation) ** ((current - start).days / 365.25)))
        previous = current
    return dict(rates=rates, method="Constant effective annual net-cost rates; before personal taxes; ACT/365.25; contributions at end of day. Assumptions, not predictions or probability bounds.", contributions_by_account_eur=contributed, final=path[-1], path=path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    results = {name: project(config, rates) for name, rates in config["scenarios"].items()}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(dict(config=config, results=results), ensure_ascii=False, indent=2) + "\n")
    for name, result in results.items():
        print(name, json.dumps(result["final"], ensure_ascii=False))


if __name__ == "__main__":
    main()
