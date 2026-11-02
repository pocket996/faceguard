"""Shared YuNet face crops without importing PyTorch; preserves training rounding."""
import cv2
import numpy as np
from PIL import Image


def detect_face_crops(frame, detector, max_faces=32):
    """Return stable area-ordered faces and original-image boxes; never hide a limit."""
    height, width = frame.shape[:2]
    scale = min(1., 640 / max(height, width))
    small = cv2.resize(frame, (max(1, int(width * scale)), max(1, int(height * scale))))
    detector.setInputSize((small.shape[1], small.shape[0]))
    _, faces = detector.detect(small)
    if faces is None:
        return [], 0
    ordered = sorted(faces, key=lambda row: (-float(row[2] * row[3]), float(row[0]), float(row[1])))
    records = []
    for face in ordered[:max_faces]:
        x, y, w, h = face[:4] / scale
        if not np.isfinite([x, y, w, h]).all() or w <= 0 or h <= 0:
            continue
        size = min(max(w, h) * 1.3, width, height)
        left = min(max(x + w / 2 - size / 2, 0), width - size)
        top = min(max(y + h / 2 - size / 2, 0), height - size)
        # Preserve the prepared-data rounding, including the old largest-face path.
        box = [left / width, top / height, (left + size) / width, (top + size) / height]
        x1, y1 = int(box[0] * width), int(box[1] * height)
        x2, y2 = min(width, int(np.ceil(box[2] * width))), min(height, int(np.ceil(box[3] * height)))
        if x2 <= x1 or y2 <= y1:
            continue
        face_image = cv2.resize(frame[y1:y2, x1:x2], (256, 256), interpolation=cv2.INTER_AREA)
        records.append(dict(face_id=len(records) + 1, bbox=[int(x1), int(y1), int(x2), int(y2)],
                            detected_bbox=[float(x), float(y), float(w), float(h)],
                            detector_confidence=float(face[-1]),
                            image=Image.fromarray(cv2.cvtColor(face_image, cv2.COLOR_BGR2RGB))))
    return records, len(ordered)


def crop_face(frame, detector):
    """Compatibility path used by existing training/evaluation: largest face only."""
    faces, _ = detect_face_crops(frame, detector, max_faces=1)
    return faces[0]['image'] if faces else None
