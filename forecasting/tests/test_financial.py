import csv
from datetime import datetime
import math
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from forecasting.core import directional_metrics, log_returns, read_series
from forecasting.lab import evaluate
from forecasting.market_data import read_portfolio


class FinancialTests(unittest.TestCase):
    def test_returns_are_backward_looking_and_correctly_aligned(self):
        times = [datetime(2025, 1, d) for d in (2, 3, 6)]
        dates, returns = log_returns(times, [100, 110, 99])
        self.assertEqual(dates, times[1:])
        self.assertAlmostEqual(returns[0], math.log(1.1))
        self.assertAlmostEqual(sum(returns), math.log(0.99))
        for bad in (0, -1, float('nan')):
            with self.assertRaises(ValueError):
                log_returns(times, [100, bad, 99])

    def test_zero_direction_is_not_a_successful_trade(self):
        self.assertEqual(directional_metrics([0.1, -0.1], [0, 0]),
                         {'directional_accuracy_active': None, 'directional_coverage': 0})
        result = directional_metrics([0.1, -0.1], [0.2, 0])
        self.assertEqual(result['directional_accuracy_active'], 1)
        self.assertEqual(result['directional_coverage'], 0.5)

    def test_zero_return_reference_and_horizon_units(self):
        args = SimpleNamespace(horizon=2, context=4, period=1, target='log-return')
        result = evaluate([0.01] * 20, args, None, 12, 16)
        self.assertAlmostEqual(result['zero_return']['mae'], 0.01)
        self.assertAlmostEqual(result['horizon_zero_return']['mae'], 0.02)

    def test_calendar_accepts_weekend_and_rejects_missing_session(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'prices.csv'
            # Jan 9, 2025 was a special XNYS closure, not an ordinary weekday.
            dates = ['2025-01-03', '2025-01-06', '2025-01-07', '2025-01-08', '2025-01-10']
            def write(items):
                with path.open('w', newline='') as stream:
                    writer = csv.writer(stream)
                    writer.writerow(['timestamp', 'target'])
                    writer.writerows((d, 100) for d in items)
            write(dates)
            self.assertEqual(len(read_series(path, calendar='XNYS')[0]), 5)
            write([d for d in dates if d != '2025-01-07'])
            with self.assertRaises(ValueError):
                read_series(path, calendar='XNYS')

    def test_portfolio_rejects_path_injection_and_duplicates(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'portfolio.csv'
            for rows in [('SPY,1,USD,XNYS', 'SPY,2,USD,XNYS'), ('../SPY,1,USD,XNYS',)]:
                path.write_text('ticker,quantity,currency,calendar\n' + '\n'.join(rows))
                with self.assertRaises(ValueError):
                    read_portfolio(path)


if __name__ == '__main__':
    unittest.main()
