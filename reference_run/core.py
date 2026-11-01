"""Standalone FF++ reference model, data checks, and inference preprocessing."""
from project_io import resolve_data_path, data_location
import csv
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps
import torch
from torch import nn
from torchvision import models, transforms
from project_io import HERE,PROJECT,digest,save_json
from media_faces import detect_face_crops,crop_face

MEAN = [0.485, 0.456, 0.406]
STD = [0.229, 0.224, 0.225]


def load_rows(manifest):
    with resolve_data_path(manifest).open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError('Empty manifest')
    samples, paths = set(), set()
    groups, sources, videos = defaultdict(set), defaultdict(set), defaultdict(set)
    for row in rows:
        if row['sample_id'] in samples or row['path'] in paths:
            raise ValueError('Duplicate sample ID or path')
        samples.add(row['sample_id'])
        paths.add(row['path'])
        if row['split'] not in ('train', 'val', 'test') or row['label'] not in ('0', '1'):
            raise ValueError('Invalid split/label')
        if row['provenance_status'] != 'verified' or row['media_type'] != 'image':
            raise ValueError('Only verified image manifests are supported')
        if not row['group_id'] or not row['parent_video_id']:
            raise ValueError('Source grouping/video ID required')
        groups[row['group_id']].add(row['split'])
        for key in ('target_id', 'source_id'):
            if row.get(key):
                sources[(row['dataset'], row[key])].add(row['split'])
        videos[row['parent_video_id']].add((row['split'], row['label'], row['group_id'], row['method']))
        if not (resolve_data_path(PROJECT / row['path'])).is_file():
            raise FileNotFoundError(row['path'])
    if any(len(v) != 1 for mapping in (groups, sources, videos) for v in mapping.values()):
        raise ValueError('Source/group/video metadata crosses splits or is inconsistent')
    for split in ('train', 'val', 'test'):
        if {r['label'] for r in rows if r['split'] == split} != {'0', '1'}:
            raise ValueError('Each split needs both classes')
    return rows


def image_transform():
    # Input already is a square YuNet face crop. Match this in training/inference.
    return transforms.Compose([transforms.Resize((224, 224)), transforms.ToTensor(),
                               transforms.Normalize(MEAN, STD)])


def backbone(architecture='resnet18'):
    if architecture=='vit_b_16':
        model=models.vit_b_16(weights=None)
        model.heads=nn.Identity()
        return model
    if architecture!='resnet18':
        raise ValueError('Unsupported detector architecture')
    model = models.resnet18(weights=None)
    model.fc = nn.Identity()
    return model


def load_detector(checkpoint, device):
    state = torch.load(checkpoint, map_location='cpu', weights_only=True)
    architecture=state.get('architecture','resnet18')
    model = backbone(architecture)
    model.load_state_dict(state['backbone'])
    model = model.to(device).eval()
    head = nn.Linear(768 if architecture=='vit_b_16' else 512, 1).to(device)
    head.load_state_dict(state['head'])
    head.eval()
    return model, head, state


def score_images(model, head, transform, images, device, batch_size=16):
    """Bound inference memory even when a picture contains many faces."""
    scores = []
    for start in range(0, len(images), batch_size):
        batch = torch.stack([transform(image) for image in images[start:start + batch_size]]).to(device)
        scores.extend(head(model(batch)).sigmoid().flatten().detach().cpu().tolist())
    return scores


class Predictor:
    def __init__(self, checkpoint=None, device=None):
        if checkpoint is None:
            fine = resolve_data_path(HERE / 'artifacts/model_finetuned.pt')
            checkpoint = fine if fine.is_file() else resolve_data_path(HERE / 'artifacts/model.pt')
        self.device = device or ('cuda' if torch.cuda.is_available() else 'cpu')
        self.checkpoint_path = resolve_data_path(checkpoint).resolve()
        self.model_sha256 = digest(self.checkpoint_path)
        self.model, self.head, self.state = load_detector(checkpoint, self.device)
        weight = resolve_data_path(HERE / 'weights/face_detection_yunet_2023mar.onnx')
        if digest(weight) != self.state['yunet_sha256']:
            raise ValueError('YuNet weights differ from training preprocessing')
        self.detector = cv2.FaceDetectorYN.create(str(weight), '', (320, 320), 0.8, 0.3, 5000)
        self.transform = image_transform()

    @torch.inference_mode()
    def predict(self, path, face_crop=False, progress=None, adaptive_video=False):
        path = resolve_data_path(path).resolve()
        if adaptive_video and path.suffix.lower() not in ('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tif', '.tiff'):
            if face_crop:
                raise ValueError('--face-crop is only supported for images')
            from video_analysis import analyze_video
            return analyze_video(self, path, progress)
        images, skipped, attempted = [], 0, 0
        face_records, detected_count = [], 0
        if path.suffix.lower() in ('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tif', '.tiff'):
            if progress:
                progress('reading_image', 0, 1)
            with Image.open(path) as image:
                image = ImageOps.exif_transpose(image).convert('RGB')
                if face_crop:
                    images.append(image)
                    attempted = 1
                    detected_count = 1
                    face_records = [dict(face_id=1, bbox=None)]
                else:
                    attempted = 1
                    detected, detected_count = detect_face_crops(cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR), self.detector)
                    images = [row['image'] for row in detected]
                    face_records = [{key: value for key, value in row.items() if key != 'image'} for row in detected]
                    if not images:
                        skipped += 1
            kind = 'image'
        else:
            if face_crop:
                raise ValueError('--face-crop is only supported for images')
            cap = cv2.VideoCapture(str(path))
            try:
                if not cap.isOpened():
                    raise ValueError('Cannot open video')
                count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                if count < 1:
                    raise ValueError('Invalid video frame count')
                targets = set(np.linspace(0, count - 1, min(16, count), dtype=int).tolist())
                index = 0
                while cap.grab():
                    if progress and index % max(1, count // 100) == 0:
                        progress('reading_video', index, count)
                    if index in targets:
                        attempted += 1
                        ok, frame = cap.retrieve()
                        if not ok:
                            raise ValueError('Sampled video frame could not decode')
                        face = crop_face(frame, self.detector)
                        if face is None:
                            skipped += 1
                        else:
                            images.append(face)
                    index += 1
                if index != count or attempted != len(targets):
                    raise ValueError('Video is truncated or frame metadata is inconsistent')
            finally:
                cap.release()
            kind = 'video'
        result = dict(path=str(path), media_type=kind, faces=len(images),
                      sampled_frames=attempted, no_face_frames=skipped,
                      scope='FF++ c23 face manipulation baseline; uncalibrated score')
        if not images:
            return dict(result, decision='no_face', score=None)
        if progress:
            progress('inference', 0, len(images))
        scores = score_images(self.model, self.head, self.transform, images, self.device)
        score = float(np.mean(scores))
        threshold = self.state['video_threshold'] if kind == 'video' else self.state['frame_threshold']
        if kind == 'image':
            result['photo_validation'] = 'FF++ video-frame threshold; independent ordinary-photo operating point not established'
            for record, value in zip(face_records, scores):
                record.update(score=value, threshold=threshold,
                              decision='suspected_manipulation' if value >= threshold else 'no_manipulation_detected')
            result.update(face_results=face_records, detected_faces=detected_count,
                          unanalysed_faces=max(0, detected_count - len(face_records)))
            if len(face_records) > 1:
                return dict(result, decision='multiple_face_results', score=None, frame_scores=scores,
                            aggregation='No image-level threshold is calibrated for multiple faces; inspect each result.')
        return dict(result, score=score, threshold=threshold,
                    decision='suspected_manipulation' if score >= threshold else 'no_manipulation_detected',
                    frame_scores=scores)
