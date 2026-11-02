"""On-demand, positive-logit Grad-CAM; never changes a stored detection decision."""
import math

import cv2
import numpy as np
from PIL import Image
import torch

from faceguard.model_registry import checked_generation_profile, checked_resource, digest
from .core import image_transform, load_detector
from .generation_common import canonical_face


METHOD = 'gradcam_positive_logit_v1'


def gradcam(model, head, tensor):
    """Explain the positive logit, including when the detector is below threshold.

    autograd.grad leaves parameter gradients untouched. The separate forward runs
    in eval mode, outside inference_mode, and never supplies the detection score.
    """
    activations = []
    if hasattr(model, 'layer4'):
        target = model.layer4
        transformer = False
    elif hasattr(model, 'encoder'):
        target = model.encoder.layers[-1].ln_1
        transformer = True
    else:
        raise ValueError('此模型结构暂不支持关注热力图。')
    handle = target.register_forward_hook(lambda module, inputs, output: activations.append(output))
    try:
        with torch.inference_mode(False), torch.enable_grad():
            batch = tensor.detach().clone().requires_grad_(True)
            logit = head(model(batch)).reshape(-1)
            if logit.numel() != 1 or len(activations) != 1:
                raise ValueError('热力图只接受单个人脸、单个检测项目。')
            features = activations[0]
            gradients, = torch.autograd.grad(logit[0], features)
            if transformer:
                side = math.isqrt(features.shape[1] - 1)
                if side * side != features.shape[1] - 1:
                    raise ValueError('无法还原模型图像块的位置。')
                features = features[:, 1:].transpose(1, 2).reshape(1, -1, side, side)
                gradients = gradients[:, 1:].transpose(1, 2).reshape(1, -1, side, side)
            weights = gradients.mean(dim=(2, 3), keepdim=True)
            raw = (features * weights).sum(dim=1).relu()[0].detach().float().cpu().numpy()
            score = float(logit.sigmoid().item())
    finally:
        handle.remove()
    if not np.isfinite(raw).all() or not math.isfinite(score):
        raise ValueError('热力图包含无效数值。')
    peak = float(raw.max())
    # A zero positive CAM is valid. Do not stretch noise or paint an invented spot.
    grid = raw / peak if peak > 1e-12 else np.zeros_like(raw)
    return grid, score


def valid_cached_map(payload, record):
    if not isinstance(payload, dict):
        return False
    try:
        grid = np.asarray(payload['grid'], dtype=np.float32)
        return (payload['method'] == METHOD and payload['target'] == 'positive_logit'
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


def explain_face(image, record, generation_profile='stable', check_cancel=lambda: None):
    """Reproduce the saved crop/preprocessing and verify the historical model."""
    check_cancel()
    box = record.get('bbox')
    if box is not None and not (len(box) == 4 and all(isinstance(value, int) for value in box)
                               and 0 <= box[0] < box[2] <= image.width
                               and 0 <= box[1] < box[3] <= image.height):
        raise ValueError('原检测人脸坐标与图像不匹配，请重新检测。')
    if not math.isfinite(record['score']):
        raise ValueError('原检测分数无效，请重新检测。')
    if valid_cached_map(record.get('heatmap'), record):
        return record['heatmap']
    checkpoint = (checked_generation_profile(generation_profile) if record['task'] == 'generation'
                  else checked_resource('manipulation.pt'))
    sha256 = digest(checkpoint)
    if sha256 != record.get('model_sha256'):
        raise ValueError('原检测模型已变化或缺少模型记录，请重新检测后生成热力图。')
    check_cancel()
    device = record.get('inference_device') or ('cuda' if torch.cuda.is_available() else 'cpu')
    if str(device).startswith('cuda') and not torch.cuda.is_available():
        raise ValueError('原检测使用的 GPU 当前不可用，请重新检测后生成热力图。')
    model, head, _ = load_detector(checkpoint, device)
    check_cancel()
    if box is not None:
        face = Image.fromarray(cv2.resize(np.asarray(image)[box[1]:box[3], box[0]:box[2]],
                                         (256, 256), interpolation=cv2.INTER_AREA))
    else:
        face = image
    if record['task'] == 'generation':
        face = canonical_face(face)
    tensor = image_transform()(face).unsqueeze(0).to(device)
    grid, score = gradcam(model, head, tensor)
    check_cancel()
    if abs(score - record['score']) > 1e-4:
        raise ValueError('复算分数与原检测不一致，请重新检测后查看热力图。')
    return dict(method=METHOD, target='positive_logit', task=record['task'],
                model_sha256=sha256, score=score, grid=grid.tolist(),
                bbox=box, frame_index=record.get('frame_index', -1))


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
    # Blue -> yellow -> red, with zero influence completely transparent.
    colors = cv2.applyColorMap(np.uint8(values * 255), cv2.COLORMAP_JET)[:, :, ::-1]
    rgba = np.dstack((colors, np.uint8(values * 230)))
    overlay = Image.new('RGBA', size)
    overlay.paste(Image.fromarray(rgba), (left, top))
    return overlay
