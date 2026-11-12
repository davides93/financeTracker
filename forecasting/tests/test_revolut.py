import csv
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from forecasting.revolut import reconstruct


class RevolutTests(unittest.TestCase):
    def test_cash_flows_and_fifo_lots_are_not_double_counted(self):
        with TemporaryDirectory() as folder:
            account, pnl = Path(folder) / 'account.csv', Path(folder) / 'pnl.csv'
            with account.open('w', newline='') as stream:
                writer = csv.writer(stream)
                writer.writerow(['Date', 'Ticker', 'Type', 'Quantity', 'Price per share', 'Total Amount', 'Currency', 'FX Rate'])
                writer.writerows([
                    ['2026-01-01T00:00:00Z', '', 'CASH TOP-UP', '', '', 'EUR 100', 'EUR', '1'],
                    ['2026-01-02T00:00:00Z', 'ABC', 'BUY - MARKET', '5', 'EUR 10', 'EUR 50', 'EUR', '1'],
                    ['2026-01-03T00:00:00Z', 'ABC', 'SELL - MARKET', '2', 'EUR 12', 'EUR 24', 'EUR', '1'],
                    ['2026-01-04T00:00:00Z', '', 'ROBO MANAGEMENT FEE', '', '', 'EUR -1', 'EUR', '1'],
                ])
            pnl.write_text('Income from Sells\nDate acquired,Date sold,Symbol,Security name,ISIN,Country,Quantity,Cost basis,Gross proceeds,Gross PnL,Currency\n2026-01-02,2026-01-03,ABC,Example,IE0000000000,EU,2,20,24,4,EUR\n')
            result = reconstruct(account, pnl)
            self.assertEqual(result['cash']['EUR'], '73')
            self.assertEqual(result['positions'][0]['quantity'], '3')
            self.assertEqual(result['realized_gross_pnl']['EUR'], '4')
            # Inconsistent sold quantity must stop the import.
            pnl.write_text(pnl.read_text().replace(',EU,2,20,24,4,EUR', ',EU,1,20,24,4,EUR'))
            with self.assertRaisesRegex(ValueError, 'reconcile'):
                reconstruct(account, pnl)


if __name__ == '__main__':
    unittest.main()
