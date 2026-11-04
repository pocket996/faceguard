"""Directional Grad-CAM and blur interventions; never change stored verdicts."""
import math
from contextlib import nullcontext

import cv2
import numpy as np
from PIL import Image
import torch
from torch.nn import functional as F

from faceguard.model_registry import checked_generation_profile, checked_resource, digest
from .core import image_transform, load_detector
from .generation_common import canonical_face
from .explanation_cache import explanation_key


METHOD = 'gradcam_directional_logit_v2'
LEGACY_METHOD = 'gradcam_positive_logit_v1'
OCCLUSION_METHOD = 'occlusion_blur_logit_v1'
TARGETS = ('positive_logit', 'negative_logit')


def response_details(signed, original_logit):
    raw = np.maximum(signed, 0)
    peak = float(raw.max())
    grid = raw / peak if peak > 1e-12 else np.zeros_like(raw)
    return grid, dict(raw_peak=peak, raw_abs_peak=float(np.abs(signed).max()),
                      raw_mean=float(raw.mean(dtype=np.float64)), logit=original_logit,
                      response_fraction=float(np.mean(raw > 1e-12)), grid_shape=list(grid.shape))


def gradcam(model, head, tensor, target='positive_logit', return_details=False):
    """Explain a signed logit, including when the detector is below threshold.

    autograd.grad leaves parameter gradients untouched. The separate forward runs
    in eval mode, outside inference_mode, and never supplies the detection score.
    """
    if target not in TARGETS:
        raise ValueError('不支持此热力图解释方向。')
    if model.training or head.training:
        raise ValueError('关注图必须使用推理模式的模型。')
    activations = []
    if hasattr(model, 'layer4'):
        layer = model.layer4
        transformer = False
    elif hasattr(model, 'encoder'):
        layer = model.encoder.layers[-1].ln_1
        transformer = True
    else:
        raise ValueError('此模型结构暂不支持关注热力图。')
    handle = layer.register_forward_hook(lambda module, inputs, output: activations.append(output))
    try:
        with torch.inference_mode(False), torch.enable_grad():
            batch = tensor.detach().clone().requires_grad_(True)
            logit = head(model(batch)).reshape(-1)
            if logit.numel() != 1 or len(activations) != 1:
                raise ValueError('热力图只接受单个人脸、单个检测项目。')
            features = activations[0]
            gradients, = torch.autograd.grad(logit[0] * (1 if target == 'positive_logit' else -1), features)
            if transformer:
                side = math.isqrt(features.shape[1] - 1)
                if side * side != features.shape[1] - 1:
                    raise ValueError('无法还原模型图像块的位置。')
                features = features[:, 1:].transpose(1, 2).reshape(1, -1, side, side)
                gradients = gradients[:, 1:].transpose(1, 2).reshape(1, -1, side, side)
            weights = gradients.mean(dim=(2, 3), keepdim=True)
            signed = (features * weights).sum(dim=1)[0].detach().float().cpu().numpy()
            score = float(logit.sigmoid().item())
            original_logit = float(logit.item())
    finally:
        handle.remove()
    if not np.isfinite(signed).all() or not math.isfinite(original_logit):
        raise ValueError('热力图包含无效数值。')
    # A zero positive CAM is valid. Do not stretch noise or paint an invented spot.
    grid, details = response_details(signed, original_logit)
    return (grid, score, details) if return_details else (grid, score)


def occlusion_map(model, head, tensor, target='positive_logit', check_cancel=lambda: None):
    """7x7 equal cells, each blurred independently; positive target-logit drops.

    This is a measured perturbation response, not a segmentation prediction.
    Batches are bounded to four cells and cancellation is checked between them.
    """
    if target not in TARGETS or model.training or head.training or tensor.shape[0] != 1:
        raise ValueError('遮挡对照需要单个人脸和推理模式模型。')
    height, width = tensor.shape[-2:]
    side = min(7, height, width)
    kernel = max(1, min(31, (min(height, width) // 2) * 2 - 1))
    direction = 1 if target == 'positive_logit' else -1
    with torch.inference_mode():
        check_cancel()
        original_logit = float(head(model(tensor)).item())
        blurred = F.avg_pool2d(F.pad(tensor, (kernel // 2,) * 4, mode='reflect'), kernel, stride=1)
        ys, xs = np.linspace(0, height, side + 1, dtype=int), np.linspace(0, width, side + 1, dtype=int)
        effects = []
        for start in range(0, side * side, 3):
            check_cancel()
            probes = []
            for cell in range(start, min(start + 3, side * side)):
                y, x = divmod(cell, side)
                changed = tensor.clone()
                changed[:, :, ys[y]:ys[y+1], xs[x]:xs[x+1]] = blurred[:, :, ys[y]:ys[y+1], xs[x]:xs[x+1]]
                probes.append(changed)
            # Same-batch control avoids turning CPU/CUDA batching roundoff into a response.
            logits = head(model(torch.cat([tensor] + probes))).reshape(-1)
            effects.extend(((logits[0] - logits[1:]) * direction).cpu().tolist())
    signed = np.asarray(effects, dtype=np.float32).reshape(side, side)
    if not np.isfinite(signed).all() or not math.isfinite(original_logit):
        raise ValueError('遮挡对照包含无效数值。')
    grid, details = response_details(signed, original_logit)
    return grid, float(1 / (1 + np.exp(-np.clip(original_logit, -700, 700)))), dict(details, baseline='local_blur', blur_kernel=kernel, control='unperturbed_same_batch')


def valid_cached_map(payload, record):
    if not isinstance(payload, dict):
        return False
    try:
        grid = np.asarray(payload['grid'], dtype=np.float32)
        target = record.get('target', 'positive_logit')
        kind = record.get('kind', 'gradcam')
        if target not in TARGETS or payload['target'] != target:
            return False
        if kind not in ('gradcam', 'occlusion') or (payload['method'] == OCCLUSION_METHOD) != (kind == 'occlusion'):
            return False
        if payload.get('kind', kind) != kind:
            return False
        if kind == 'occlusion' and (payload.get('baseline') != 'local_blur' or payload.get('control') != 'unperturbed_same_batch'
                                    or payload.get('blur_kernel') not in range(1, 32, 2)):
            return False
        if payload['method'] in (METHOD, OCCLUSION_METHOD):
            stats = [payload[k] for k in ('raw_peak', 'raw_abs_peak', 'raw_mean', 'logit', 'response_fraction')]
            if not all(math.isfinite(value) for value in stats):
                return False
            if not (0 <= payload['raw_mean'] <= payload['raw_peak'] <= payload['raw_abs_peak']
                    and 0 <= payload['response_fraction'] <= 1 and payload['grid_shape'] == list(grid.shape)):
                return False
            if abs(float(grid.max()) - (1. if payload['raw_peak'] > 1e-12 else 0.)) > 1e-5:
                return False
            if abs(1 / (1 + math.exp(-max(-700., min(700., payload['logit'])))) - payload['score']) > 1e-5:
                return False
        elif payload['method'] != LEGACY_METHOD or target != 'positive_logit':
            return False
        return (payload['target'] == target
                and payload['model_sha256'] == record['model_sha256']
                and isinstance(record['model_sha256'], str) and len(record['model_sha256']) == 64
                and payload['task'] == record['task']
                and payload['bbox'] == record.get('bbox')
                and payload['frame_index'] == record.get('frame_index', -1)
                and grid.ndim == 2 and 1 <= min(grid.shape) <= max(grid.shape) <= 32
                and np.isfinite(grid).all() and float(grid.min()) >= 0 and float(grid.max()) <= 1
                and math.isfinite(payload['score'])
                and abs(payload['score'] - record['score']) <= 1e-4)
    except (KeyError, TypeError, ValueError):
        return False


def explain_face(image, record, generation_profile='stable', check_cancel=lambda: None, model_cache=None):
    """Reproduce the saved crop/preprocessing and verify the historical model."""
    check_cancel()
    box = record.get('bbox')
    if box is not None and not (len(box) == 4 and all(isinstance(value, int) for value in box)
                               and 0 <= box[0] < box[2] <= image.width
                               and 0 <= box[1] < box[3] <= image.height):
        raise ValueError('原检测人脸坐标与图像不匹配，请重新检测。')
    if not math.isfinite(record['score']):
        raise ValueError('原检测分数无效，请重新检测。')
    target = record.get('target', 'positive_logit')
    kind = record.get('kind', 'gradcam')
    if target not in TARGETS or kind not in ('gradcam', 'occlusion'):
        raise ValueError('不支持此热力图解释方向。')
    cached = record.get('heatmaps', {}).get(explanation_key(target, kind), record.get('heatmap') if kind == 'gradcam' else None)
    if valid_cached_map(cached, record):
        return cached
    checkpoint = (checked_generation_profile(generation_profile) if record['task'] == 'generation'
                  else checked_resource('manipulation.pt'))
    sha256 = digest(checkpoint)
    if sha256 != record.get('model_sha256'):
        raise ValueError('原检测模型已变化或缺少模型记录，请重新检测后生成热力图。')
    check_cancel()
    device = record.get('inference_device') or ('cuda' if torch.cuda.is_available() else 'cpu')
    if str(device).startswith('cuda') and not torch.cuda.is_available():
        raise ValueError('原检测使用的 GPU 当前不可用，请重新检测后生成热力图。')
    face = model_face(image, box, record['task'])
    tensor = image_transform()(face).unsqueeze(0).to(device)
    context = (model_cache.borrow(checkpoint, sha256, device, check_cancel) if model_cache is not None
               else nullcontext(load_detector(checkpoint, device)))
    with context as (model, head, _):
        check_cancel()
        if kind == 'occlusion':
            grid, score, details = occlusion_map(model, head, tensor, target, check_cancel)
        else:
            grid, score, details = gradcam(model, head, tensor, target, return_details=True)
    check_cancel()
    if abs(score - record['score']) > 1e-4:
        raise ValueError('复算分数与原检测不一致，请重新检测后查看热力图。')
    return dict(method=OCCLUSION_METHOD if kind == 'occlusion' else METHOD, kind=kind, target=target, task=record['task'],
                model_sha256=sha256, score=score, grid=grid.tolist(),
                bbox=box, frame_index=record.get('frame_index', -1), **details)


def model_face(image, bbox, task):
    """Shared exact crop/codec path for explanations and quality diagnostics."""
    if bbox is not None:
        face = Image.fromarray(cv2.resize(np.asarray(image)[bbox[1]:bbox[3], bbox[0]:bbox[2]],
                                         (256, 256), interpolation=cv2.INTER_AREA))
    else:
        face = image
    return canonical_face(face) if task == 'generation' else face


def explanation_text(payload, record):
    """Explain a map without presenting its normalized colors as confidence."""
    target = payload['target']
    label = ('整脸生成' if record['task'] == 'generation' else '面部篡改') if target == 'positive_logit' else '未检出方向'
    name = '遮挡对照' if payload['method'] == OCCLUSION_METHOD else '梯度关注'
    if not any(value > 0 for row in payload['grid'] for value in row):
        return f'{name}，当前方向：{label}。没有可显示的正向响应，图层保持透明；不代表文件真实。'
    below = record['score'] < record.get('threshold', 0)
    decision_note = '本项分数未达提示阈值；有颜色不等于检出。' if below else '颜色不是真假概率，也不代表篡改边界。'
    legacy = '旧版缓存未记录原始响应。' if payload['method'] == LEGACY_METHOD else ''
    method = '逐块模糊后的辅助响应对照，未验证可靠定位。' if payload['method'] == OCCLUSION_METHOD else '梯度关注辅助解释，解释质量尚在验证。'
    return f'当前方向：{label}。{decision_note}{method}每张图独立归一化，红色仅表示该图相对较强的响应。{legacy}'


def render_overlay(payload, image_size, bbox=None, max_side=2000, output_size=None):
    """Transparent full-frame overlay, with all pixels outside this face empty."""
    width, height = image_size
    scale = min(1., max_side / max(width, height))
    size = output_size or (max(1, round(width * scale)), max(1, round(height * scale)))
    box = bbox or [0, 0, width, height]
    sx, sy = size[0] / width, size[1] / height
    left, top = min(size[0] - 1, round(box[0] * sx)), min(size[1] - 1, round(box[1] * sy))
    right, bottom = min(size[0], round(box[2] * sx)), min(size[1], round(box[3] * sy))
    right, bottom = max(left + 1, right), max(top + 1, bottom)
    grid = np.asarray(payload['grid'], dtype=np.float32)
    values = np.clip(cv2.resize(grid, (right - left, bottom - top), interpolation=cv2.INTER_LINEAR), 0, 1)
    # Exactly the same blue/yellow/red palette as the visible legend and exports.
    colors = np.rint(np.stack([np.interp(values, [0, .5, 1], channel)
                              for channel in ([55, 227, 189], [86, 190, 60], [168, 87, 54])], axis=-1)).astype(np.uint8)
    rgba = np.dstack((colors, np.uint8(values * 230)))
    overlay = Image.new('RGBA', size)
    overlay.paste(Image.fromarray(rgba), (left, top))
    return overlay
