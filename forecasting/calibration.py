"""Architecture-derived, gradient-free tail edits for Chronos-2.

For both linear output paths, move extreme quantile rows away from the median
row. In normalized output space this implements m + factor*(q-m). The monotone
inverse normalization preserves order; the median is unchanged for a single
output patch. Restrict horizons to one patch to avoid autoregressive feedback.
"""

from .weights import fingerprint


def tail_spread_manifest(pipeline, factor):
    model = pipeline.model
    quantiles = list(pipeline.quantiles)
    patch_size = model.chronos_config.output_patch_size
    median_index = quantiles.index(0.5)
    rows, references = [], []
    for index, quantile in enumerate(quantiles):
        if quantile <= 0.1 or quantile >= 0.9:
            for step in range(patch_size):
                rows.append(index * patch_size + step)
                references.append(median_index * patch_size + step)
    parameters = dict(model.named_parameters())
    names = [f'output_patch_embedding.{layer}.{kind}'
             for layer in ['output_layer', 'residual_layer'] for kind in ['weight', 'bias']]
    return {
        'hypothesis': 'Undercoverage may reflect overly narrow marginal tails. Widen extreme quantile output rows around the median in both residual output paths; preserve the median forecast. This is calibration, not additional directional information.',
        'method': 'architecture_derived_direct_weight_edit_no_gradients',
        'spread_factor': factor,
        'max_validated_horizon': patch_size,
        'tensors': [{'name': name, 'shape': list(parameters[name].shape),
                     'sha256': fingerprint(parameters[name]),
                     'row_spread': {'rows': rows, 'references': references, 'factor': factor}}
                    for name in names],
    }
