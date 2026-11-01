"""Validation-only selection at an explicit empirical real-image false-positive budget."""
from collections import defaultdict
import math

import numpy as np


def _validated(rows, scores, max_real_fpr, focus_methods):
    if not 0 <= max_real_fpr < 1:
        raise ValueError('False-positive budget must be in [0, 1)')
    p = np.asarray(scores, dtype=np.float64)
    if p.ndim != 1 or len(p) != len(rows) or not len(p):
        raise ValueError('Validation rows and scores differ')
    if not np.isfinite(p).all() or ((p < 0) | (p > 1)).any():
        raise ValueError('Scores must be finite probabilities in [0, 1]')
    if any(r['split'] != 'val' for r in rows):
        raise ValueError('Operating-point selection requires validation rows only')
    if len({r['sample_id'] for r in rows}) != len(rows):
        raise ValueError('Duplicate validation sample IDs')
    if any(str(r['label']) not in ('0', '1') for r in rows):
        raise ValueError('Unexpected label')
    y = np.asarray([int(r['label']) for r in rows])
    if set(y) != {0, 1}:
        raise ValueError('Both real and fake validation classes are required')
    methods = sorted({r['method'] for r in rows if int(r['label']) == 1})
    focus = sorted(set(focus_methods or [m for m in methods if m.startswith('gpt-')]))
    if not focus or not set(focus).issubset(methods):
        raise ValueError('Requested focus generator absent from validation')
    return p, y, methods, focus


def operating_summary(rows, scores, threshold, max_real_fpr=.02, focus_methods=None):
    p, y, methods, focus = _validated(rows, scores, max_real_fpr, focus_methods)
    if not math.isfinite(threshold):
        raise ValueError('Threshold must be finite')
    predicted = p >= threshold
    real = y == 0
    n_real = int(real.sum())
    allowed = math.floor(max_real_fpr * n_real)
    false_positives = int(predicted[real].sum())
    per_source = {}
    for source in sorted({r['source'] for r in rows if int(r['label']) == 0}):
        indices = [i for i, r in enumerate(rows) if int(r['label']) == 0 and r['source'] == source]
        errors = int(predicted[indices].sum())
        per_source[source] = dict(n=len(indices), false_positives=errors,
                                  false_positive_rate=errors / len(indices), small_sample=len(indices) < 100)
    per_method = {}
    for method in methods:
        indices = [i for i, r in enumerate(rows) if int(r['label']) == 1 and r['method'] == method]
        groups = defaultdict(list)
        for i in indices:
            groups[rows[i]['group']].append(bool(predicted[i]))
        per_method[method] = dict(n=len(indices), detected=int(predicted[indices].sum()),
            recall=float(predicted[indices].mean()), groups=len(groups),
            group_balanced_recall=float(np.mean([np.mean(v) for v in groups.values()])))
    return dict(threshold=float(threshold), max_real_fpr=float(max_real_fpr), n_real=n_real,
        allowed_false_positives=allowed, false_positives=false_positives,
        real_false_positive_rate=false_positives / n_real, budget_met=false_positives <= allowed,
        focus_methods=focus, focus_macro_recall=float(np.mean([per_method[m]['group_balanced_recall'] for m in focus])),
        generator_macro_recall=float(np.mean([per_method[m]['group_balanced_recall'] for m in methods])),
        per_source_real=per_source, per_generator=per_method,
        scope='Empirical overall validation image FPR; not a per-source or deployment guarantee. Group-balanced recall for ranking.')


def select_operating_point(rows, scores, max_real_fpr=.02, focus_methods=None):
    p, y, _, focus = _validated(rows, scores, max_real_fpr, focus_methods)
    real = np.sort(p[y == 0])[::-1]
    allowed = math.floor(max_real_fpr * len(real))
    # With >= decisions, the first disallowed negative must remain below the
    # threshold, including tied scores. nextafter(1, +inf) represents reject-all.
    boundary = float(np.nextafter(real[allowed], np.inf))
    below, above = p[p < boundary], p[p >= boundary]
    threshold = boundary
    if len(below) and len(above):
        midpoint = float(below.max() + (above.min() - below.max()) / 2)
        if midpoint > below.max() and midpoint <= above.min():
            threshold = midpoint
    result = operating_summary(rows, p, threshold, max_real_fpr, focus)
    if not result['budget_met']:
        raise AssertionError('Validation FPR budget violated')
    return result


def operating_rank(summary, validation_auc):
    if not summary['budget_met'] or not math.isfinite(validation_auc):
        raise ValueError('Cannot rank an infeasible or invalid candidate')
    return (summary['focus_macro_recall'], summary['generator_macro_recall'],
            float(validation_auc), -summary['real_false_positive_rate'])
