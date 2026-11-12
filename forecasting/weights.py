"""Sparse, fingerprint-checked weight edits, without optimization or gradients."""

from contextlib import contextmanager
import hashlib
import math


def fingerprint(tensor):
    # Canonical float32 representation; shape is independently checked in the manifest.
    return hashlib.sha256(tensor.detach().cpu().float().contiguous().numpy().tobytes()).hexdigest()


def inventory(model):
    return [{"name": name, "shape": list(p.shape), "sha256": fingerprint(p),
             "norm": p.detach().float().norm().item()}
            for name, p in model.named_parameters()]


@contextmanager
def edited(model, manifest):
    """Apply explicit scalar replacements atomically, then restore even on failure.

    This is a mechanism, not a discovery algorithm: each proposal needs a causal
    hypothesis and validation evidence. No random perturbation is generated here.
    """
    import torch

    if not isinstance(manifest.get("hypothesis"), str) or not manifest["hypothesis"].strip():
        raise ValueError("An explanatory hypothesis is required")
    patches = manifest.get("tensors", [])
    if not patches:
        raise ValueError("The manifest contains no edits")
    parameters = dict(model.named_parameters())
    backups, seen, count = [], set(), 0
    total = sum(p.numel() for p in parameters.values())
    # Validate every proposed edit before mutating any tensor.
    for patch in patches:
        name = patch["name"]
        if name in seen or name not in parameters:
            raise ValueError(f"Unknown or repeated tensor: {name}")
        seen.add(name)
        param = parameters[name]
        if list(param.shape) != patch["shape"] or fingerprint(param) != patch["sha256"]:
            raise ValueError(f"Base checkpoint mismatch: {name}")
        if 'row_spread' in patch:
            if 'entries' in patch or param.ndim not in (1, 2):
                raise ValueError('Row spread requires a vector/matrix and no scalar entries')
            spread = patch['row_spread']
            rows, references, factor = spread['rows'], spread['references'], spread['factor']
            if not rows or len(rows) != len(references) or len(set(rows)) != len(rows):
                raise ValueError('Invalid row spread mapping')
            if any(type(i) is not int or not 0 <= i < param.shape[0] for i in rows + references):
                raise ValueError('Invalid row index')
            if not isinstance(factor, (float, int)) or not math.isfinite(factor) or factor < 1:
                raise ValueError('Spread factor must be finite and at least one')
            indices = (torch.tensor(rows, device=param.device),)
            before = param.detach()[indices].clone()
            reference = param.detach()[torch.tensor(references, device=param.device)]
            after = (reference.float() + factor * (before.float() - reference.float())).to(param.dtype)
        else:
            entries = patch['entries']
            if not entries:
                raise ValueError('Empty tensor edit')
            positions, values = [], []
            for entry in entries:
                index, value = entry['index'], entry['value']
                if len(index) != param.ndim or any(type(i) is not int or i < 0 or i >= dim for i, dim in zip(index, param.shape)):
                    raise ValueError('Invalid tensor index')
                if not isinstance(value, (float, int)) or not math.isfinite(value):
                    raise ValueError('Weights must be finite')
                positions.append(tuple(index))
                values.append(value)
            if len(set(positions)) != len(positions):
                raise ValueError('Duplicate scalar index')
            indices = tuple(torch.tensor(axis, device=param.device) for axis in zip(*positions))
            before = param.detach()[indices].clone()
            after = torch.tensor(values, dtype=param.dtype, device=param.device)
        if not torch.isfinite(after).all():
            raise ValueError("Replacement overflows the model dtype")
        relative_delta = (after.float() - before.float()).norm().item() / max(param.detach().float().norm().item(), 1e-12)
        if relative_delta > 0.05:
            raise ValueError(f"Edit exceeds experimental 5% tensor norm budget: {name}")
        backups.append((param, indices, before, after))
        count += before.numel()
    if count / total > 0.01:
        raise ValueError("Edit exceeds experimental 1% parameter count budget")
    try:
        with torch.no_grad():
            for param, indices, _, after in backups:
                param[indices] = after
        yield {"edited_scalars": count, "total_scalars": total, "fraction": count / total}
    finally:
        with torch.no_grad():
            for param, indices, before, _ in backups:
                param[indices] = before
