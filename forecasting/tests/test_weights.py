import unittest

import torch

from forecasting.weights import edited, fingerprint


class WeightEditTests(unittest.TestCase):
    def setUp(self):
        self.model = torch.nn.Linear(10, 10, bias=False)
        with torch.no_grad():
            self.model.weight.fill_(1.0)
        self.base = self.model.weight.detach().clone()
        self.manifest = {'hypothesis': 'Test a bounded scalar edit and exact rollback', 'tensors': [{
            'name': 'weight', 'shape': [10, 10], 'sha256': fingerprint(self.model.weight),
            'entries': [{'index': [0, 0], 'value': 1.01}],
        }]}

    def test_rollback_after_inference_failure(self):
        with self.assertRaisesRegex(RuntimeError, 'inference failed'):
            with edited(self.model, self.manifest):
                self.assertAlmostEqual(self.model.weight[0, 0].item(), 1.01, places=5)
                raise RuntimeError('inference failed')
        self.assertTrue(torch.equal(self.model.weight, self.base))

    def test_mismatched_checkpoint_is_never_edited(self):
        self.manifest['tensors'][0]['sha256'] = 'wrong'
        with self.assertRaisesRegex(ValueError, 'mismatch'):
            with edited(self.model, self.manifest):
                self.fail('Should not enter edit scope')
        self.assertTrue(torch.equal(self.model.weight, self.base))

    def test_excessive_delta_rejected_before_mutation(self):
        self.manifest['tensors'][0]['entries'][0]['value'] = 100.0
        with self.assertRaisesRegex(ValueError, 'norm budget'):
            with edited(self.model, self.manifest):
                self.fail('Should not enter edit scope')
        self.assertTrue(torch.equal(self.model.weight, self.base))

    def test_row_edit_changes_only_selected_row_and_restores(self):
        self.model.register_parameter('padding', torch.nn.Parameter(torch.ones(900)))
        with torch.no_grad():
            self.model.weight[1].fill_(2.0)
        base = self.model.weight.detach().clone()
        patch = self.manifest['tensors'][0]
        patch['sha256'] = fingerprint(self.model.weight)
        del patch['entries']
        patch['row_spread'] = {'rows': [1], 'references': [0], 'factor': 1.01}
        with edited(self.model, self.manifest) as change:
            self.assertEqual(change['edited_scalars'], 10)
            self.assertTrue(torch.equal(self.model.weight[0], base[0]))
            self.assertTrue(torch.allclose(self.model.weight[1], torch.full((10,), 2.01)))
        self.assertTrue(torch.equal(self.model.weight, base))


if __name__ == '__main__':
    unittest.main()
