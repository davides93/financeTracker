import csv
import tempfile
import unittest
from datetime import date
from pathlib import Path

from forecasting.directa import parse
from forecasting.scenarios import add_months, project, schedule
from forecasting.monitor import refresh


class ScenarioTests(unittest.TestCase):
    def config(self):
        return dict(start_date="2026-11-06", years=5, accounts=dict(directa=dict(initial_eur=10000, monthly_eur=200), revolut=dict(initial_eur=2000, weekly_eur=50)))

    def test_contribution_counts_and_zero_return(self):
        result = project(self.config(), dict(directa=0, revolut=0))
        self.assertEqual(result["contributions_by_account_eur"], dict(directa=12000, revolut=13000))
        self.assertEqual(result["final"]["total_eur"], 37000)
        self.assertEqual(result["final"]["growth_eur"], 0)

    def test_growth_without_flows(self):
        config = dict(start_date="2027-01-01", years=4, accounts=dict(a=dict(initial_eur=100)))
        result = project(config, dict(a=0.1))
        self.assertAlmostEqual(result["final"]["total_eur"], 100 * 1.1 ** 4)
        self.assertLess(project(config, dict(a=-0.1))["final"]["total_eur"], 100)

    def test_end_month_and_no_initial_payment(self):
        self.assertEqual(add_months(date(2028, 1, 31), 1), date(2028, 2, 29))
        self.assertEqual(schedule(date(2028, 1, 31), date(2028, 3, 31), monthly=100), {date(2028, 2, 29): 100, date(2028, 3, 31): 100})

    def test_invalid_inputs(self):
        for rate in (-1, float("nan")):
            with self.assertRaises(ValueError):
                project(self.config(), dict(directa=rate, revolut=0))


class DirectaTests(unittest.TestCase):
    def fixture(self, extra=None):
        rows = [["Data", "Liquidità", "Finanziamento long", "Garanzia short", "Portafoglio", "Patrimonio", "Note", "", "Data", "Descrizione", "Valore", "Descrizione titolo", "Isin", "Ticker"],
                ["1/1/26", "10,00", "0", "0", "1.000,00", "1.010,00", "", "", "1/13/26", "Bonifico", "200,00", "", "", ""],
                ["1/13/26", "10,00", "0", "0", "1.210,00", "1.220,00", "", "", "1/13/26", "Bollo portafoglio titoli*", "-4,00", "", "", ""],
                ["1/14/26", "10,00", "0", "0", "1.220,00", "1.230,00", "Valori provvisori della giornata in corso", "", "", "", "", "", "", ""]]
        if extra:
            rows.append(extra)
        return rows

    def run_parse(self, rows):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "export.csv"
            with path.open("w", encoding="utf-8-sig", newline="") as f:
                csv.writer(f, delimiter=";").writerows(rows)
            return parse(path)

    def test_independent_dates_provisional_and_costs(self):
        result = self.run_parse(self.fixture())
        self.assertEqual(result["movements"][0]["date"], "2026-01-13")
        self.assertEqual(result["latest_confirmed"]["date"], "2026-01-13")
        self.assertEqual(result["performance"]["value_change_less_external_flows_eur"], "10.00")

    def test_unknown_flow_blocks_performance(self):
        rows = self.fixture()
        rows[1][9] = "Rettifica"
        self.assertIsNone(self.run_parse(rows)["performance"])

    def test_offset_headers_preserve_first_deposit(self):
        rows = self.fixture()
        header = rows[0]
        right_header = [""] * 8 + header[8:]
        left_header = header[:8] + rows[1][8:]
        rows[1][8:] = [""] * 6
        result = self.run_parse([right_header, left_header] + rows[1:])
        self.assertEqual(result["performance"]["external_flows_eur"], "200.00")

    def test_bad_total_and_duplicates_fail(self):
        rows = self.fixture()
        rows[1][5] = "1.011,00"
        with self.assertRaises(ValueError):
            self.run_parse(rows)
        rows = self.fixture()
        with self.assertRaises(ValueError):
            self.run_parse(rows + [rows[1]])

    def test_monitor_refresh_and_future_dates(self):
        imported = self.run_parse(self.fixture())
        config = dict(start_date="2026-01-14", years=5, accounts=dict(directa=dict(initial_eur=1, monthly_eur=200), revolut=dict(initial_eur=1, weekly_eur=50)), scenarios=dict(invariato=dict(directa=0, revolut=0)))
        rev = dict(as_of="2026-01-13", estimated_total_value_eur=200)
        snapshot = dict(as_of="2026-01-13", cash_eur=5, securities_eur=1210)
        result = refresh(config, imported, rev, snapshot)
        self.assertEqual(result["audit"]["latest_known_total_eur"], 1420)
        self.assertEqual(result["audit"]["snapshot_cash_difference_eur"], 5)
        self.assertEqual(result["results"]["invariato"]["final"]["total_eur"], 26420)
        self.assertEqual(config["accounts"]["directa"]["initial_eur"], 1)
        config["start_date"] = "2026-01-12"
        with self.assertRaises(ValueError):
            refresh(config, imported, rev, snapshot)


if __name__ == "__main__":
    unittest.main()
