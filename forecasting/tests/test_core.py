import csv
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import unittest

from forecasting.core import boundaries, metrics, read_series, seasonal, windows


class EvaluationTests(unittest.TestCase):
    def test_no_target_leakage_and_disjoint_splits(self):
        data = list(range(100))
        train_end, validation_end = boundaries(len(data), 7, 14)
        validation = list(windows(data, train_end, validation_end, 7, 28))
        test = list(windows(data, validation_end, len(data), 7, 28))
        for origin, history, target in validation + test:
            self.assertLess(max(history), min(target))
            self.assertEqual(history[-1], origin - 1)
            self.assertEqual(len(target), 7)
        self.assertLess(max(y for _, _, ys in validation for y in ys), min(y for _, _, ys in test for y in ys))

    def test_known_errors_and_interval_coverage(self):
        result = metrics([2, 4], [1, 5], [[0, 1, 2], [3, 5, 6]])
        self.assertEqual(result["mae"], 1)
        self.assertEqual(result["rmse"], 1)
        self.assertEqual(result["bias"], 0)
        self.assertEqual(result["coverage_80"], 1)
        self.assertAlmostEqual(result["pinball"], 0.25)

    def test_invalid_predictions_rejected(self):
        for prediction in ([1], [1, float("nan")]):
            with self.assertRaises(ValueError):
                metrics([1, 2], prediction)
        with self.assertRaises(ValueError):
            metrics([1], [1], [[2, 1, 0]])

    def test_multi_season_baseline(self):
        self.assertEqual(seasonal([8, 1, 2, 3], 7, 3), [1, 2, 3, 1, 2, 3, 1])

    def test_csv_rejects_gap_duplicate_and_nan(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "series.csv"
            for offsets, values in [([0, 1, 2], [1, 2, 3]), ([0, 1, 3], [1, 2, 3]),
                                    ([0, 1, 1], [1, 2, 3]), ([0, 1, 2], [1, 2, "nan"])]:
                with path.open("w", newline="") as stream:
                    writer = csv.writer(stream)
                    writer.writerow(["timestamp", "target"])
                    for offset, value in zip(offsets, values):
                        writer.writerow([(datetime(2025, 1, 1) + timedelta(days=offset)).isoformat(), value])
                if offsets == [0, 1, 2] and values == [1, 2, 3]:
                    self.assertEqual(read_series(path)[1], [1, 2, 3])
                else:
                    with self.assertRaises(ValueError):
                        read_series(path)


if __name__ == "__main__":
    unittest.main()
