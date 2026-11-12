import unittest

from forecasting.corporate_actions import repair_split


class CorporateActionTests(unittest.TestCase):
    def test_partial_split_repair_preserves_moves_and_rejects_double_adjustment(self):
        rows = [{'timestamp': '2026-10-23', 'target': '500'},
                {'timestamp': '2026-10-26', 'target': '5.05'},
                {'timestamp': '2026-10-27', 'target': '5.10'}]
        fixed, count = repair_split(rows, 100, '2026-10-26', '2026-10-27')
        self.assertEqual(count, 1)
        self.assertEqual([r['target'] for r in fixed], [5.0, 5.05, 5.10])
        self.assertEqual(rows[0]['target'], '500')
        with self.assertRaisesRegex(ValueError, 'double-adjust'):
            repair_split(fixed, 100, '2026-10-26', '2026-10-27')


if __name__ == '__main__':
    unittest.main()
