"""Development-only explanation diagnostics, never a detection verdict."""
import copy

import cv2
import numpy as np
import torch
from torch.nn import functional as F

from .heatmaps import gradcam, TARGETS


def map_similarity(first, second):
    """No correlation claim for empty/constant maps; report their difference."""
    a, b = np.asarray(first, dtype=float), np.asarray(second, dtype=float)
    if a.shape != b.shape or not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError('Quality comparison needs finite maps with matching shape')
    correlation = float(np.corrcoef(a.ravel(), b.ravel())[0, 1]) if a.std() > 1e-10 and b.std() > 1e-10 else None
    return dict(pearson=correlation, mean_absolute_difference=float(np.abs(a - b).mean()),
                first_nonzero=bool(np.any(a)), second_nonzero=bool(np.any(b)))


def target_logits(model, head, tensors, target='positive_logit', check_cancel=lambda: None):
    if target not in TARGETS or model.training or head.training:
        raise ValueError('Quality probes require a valid target and eval models')
    values = []
    with torch.inference_mode():
        for start in range(0, len(tensors), 4):
            check_cancel()
            batch = torch.cat(tensors[start:start + 4], dim=0)
            scores = head(model(batch)).reshape(-1) * (1 if target == 'positive_logit' else -1)
            if not torch.isfinite(scores).all():
                raise ValueError('Non-finite explanation probe output')
            values.extend(scores.cpu().tolist())
    return values


def deletion_diagnostics(model, head, tensor, grid, target='positive_logit', fractions=(.1, .3), random_repeats=3, seed=20261102, check_cancel=lambda: None):
    """Equal-area top/low/random masks, with both blur and channel-mean fills.

    Perturb after canonical preprocessing to avoid confounding codec changes.
    Drops are signed target-logit differences, not probabilities or pixel truth.
    """
    if tensor.shape[0] != 1 or random_repeats < 1 or any(not 0 < f <= 1 for f in fractions):
        raise ValueError('Invalid deletion probe settings')
    grid = np.asarray(grid, dtype=np.float32)
    if grid.ndim != 2 or not np.isfinite(grid).all():
        raise ValueError('Invalid attention grid')
    if not np.any(grid > 0):
        return dict(state='no_response', comparisons=[], note='Zero maps are not ranked or forced to pass.')
    height, width = tensor.shape[-2:]
    ranked = cv2.resize(grid, (width, height), interpolation=cv2.INTER_LINEAR).reshape(-1)
    top, low = np.argsort(-ranked, kind='stable'), np.argsort(ranked, kind='stable')
    generator = np.random.default_rng(seed)
    kernel = max(1, min(31, (min(height, width) // 2) * 2 - 1))
    radius = kernel // 2
    with torch.inference_mode():
        blurred = F.avg_pool2d(F.pad(tensor, (radius,) * 4, mode='reflect'), kernel, stride=1)
        mean = tensor.mean(dim=(2, 3), keepdim=True).expand_as(tensor)
    reference = target_logits(model, head, [tensor], target, check_cancel)[0]
    probes, descriptions = [], []
    for fraction in fractions:
        count = max(1, min(len(ranked), round(len(ranked) * fraction)))
        random_orders = [generator.permutation(len(ranked)) for _ in range(random_repeats)]
        for baseline, fill in [('blur', blurred), ('channel_mean', mean)]:
            for kind, order in [('top', top), ('low', low)] + [('random', order) for order in random_orders]:
                mask = torch.zeros(height * width, dtype=torch.bool, device=tensor.device)
                mask[torch.as_tensor(order[:count].copy(), device=tensor.device)] = True
                probes.append(torch.where(mask.reshape(1, 1, height, width), fill, tensor))
                descriptions.append((fraction, baseline, kind))
    values = target_logits(model, head, probes, target, check_cancel)
    comparisons = []
    for fraction in fractions:
        for baseline in ('blur', 'channel_mean'):
            drops = {kind: [] for kind in ('top', 'low', 'random')}
            for description, value in zip(descriptions, values):
                if description[:2] == (fraction, baseline):
                    drops[description[2]].append(reference - value)
            top_drop, low_drop, random_drop = (float(np.mean(drops[k])) for k in ('top', 'low', 'random'))
            comparisons.append(dict(fraction=fraction, baseline=baseline, top_drop=top_drop,
                                    low_drop=low_drop, random_drop=random_drop,
                                    top_minus_random=top_drop - random_drop, top_minus_low=top_drop - low_drop))
    return dict(state='measured', target=target, reference_logit=reference, seed=seed,
                random_repeats=random_repeats, comparisons=comparisons,
                note='Perturbation diagnosis only; masks can create out-of-distribution inputs.')


def randomized_diagnostics(model, head, tensor, grid, target='positive_logit', seed=20261102):
    """Randomize independent copies, keeping cached models and RNG untouched."""
    devices = [tensor.device.index or 0] if tensor.is_cuda else []
    with torch.random.fork_rng(devices=devices):
        torch.manual_seed(seed)
        alternative_head = copy.deepcopy(head)
        alternative_head.reset_parameters()
        head_map, _ = gradcam(model, alternative_head, tensor, target)
        comparisons = dict(head_randomized=map_similarity(grid, head_map))
        if hasattr(model, 'layer4'):
            alternative = copy.deepcopy(model)
            for module in alternative.layer4.modules():
                if hasattr(module, 'reset_parameters'):
                    module.reset_parameters()
            layer_map, _ = gradcam(alternative, alternative_head, tensor, target)
            comparisons['last_block_and_head_randomized'] = map_similarity(grid, layer_map)
    return comparisons
