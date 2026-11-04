"""Fixed train/development-only saliency probes. Never tunes a detector."""
import argparse
import io
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))


def main():
    import csv
    import cv2
    import numpy as np
    from PIL import Image, ImageOps
    import torch
    from faceguard.data_locations import data_location, resolve_data_path
    from faceguard.inference.core import image_transform, load_detector
    from faceguard.inference.heatmaps import gradcam, model_face, occlusion_map
    from faceguard.inference.heatmap_quality import deletion_diagnostics, randomized_diagnostics, map_similarity
    from faceguard.model_registry import checked_generation_profile, checked_resource, digest

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'outputs/heatmaps-improved-20261102/quality')
    parser.add_argument('--kind', choices=['gradcam', 'occlusion'], default='gradcam')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if (output / 'report.json').exists():
        raise FileExistsError('Use a fresh output directory; quality evidence is not overwritten.')
    torch.set_num_threads(2)
    cv2.setNumThreads(1)
    manifest = data_location('generation_joint_manifests') / 'manifest.csv'
    with manifest.open(encoding='utf-8-sig', newline='') as stream:
        rows = [r for r in csv.DictReader(stream) if r['split'] == 'train']
    selected = []
    requests = [('DFF', 'real', 2), ('DFF', 'SD15', 2), ('FairFaceGen', 'FLUX', 2),
                ('FairFaceGen', 'SD35', 2), ('LFW', 'real', 1), ('FFHQ-256-mirror', 'real', 1),
                ('OpenFake:gpt-image-1', 'gpt-image-1', 3)]
    for source, method, count in requests:
        candidates = sorted((r for r in rows if r['source'] == source and r['method'] == method), key=lambda r: r['sample_id'])
        selected.extend(candidates[:count])
    assert len(selected) == 13
    models = dict(generation=checked_generation_profile('gpt-low-fpr-20261101'), manipulation=checked_resource('manipulation.pt'))
    before = {task: digest(path) for task, path in models.items()}
    records = []
    def compute(model, head, tensor, target):
        return (occlusion_map(model, head, tensor, target) if args.kind == 'occlusion'
                else gradcam(model, head, tensor, target, True))
    for task, path in models.items():
        model, head, _ = load_detector(path, 'cpu')
        for row in selected:
            with Image.open(resolve_data_path(row['path'])) as source:
                image = ImageOps.exif_transpose(source).convert('RGB')
            tensor = image_transform()(model_face(image, None, task)).unsqueeze(0)
            variants = {}
            buffer = io.BytesIO()
            image.save(buffer, format='JPEG', quality=75)
            buffer.seek(0)
            with Image.open(buffer) as source:
                variants['jpeg75'] = source.convert('RGB')
            smaller = image.resize((max(1, round(image.width * .8)), max(1, round(image.height * .8))), Image.Resampling.BILINEAR)
            variants['down_up_80pct'] = smaller.resize(image.size, Image.Resampling.BILINEAR)
            margin = max(1, round(min(image.size) * .04))
            variants['crop_inset_4pct'] = image.crop((margin, margin, image.width - margin, image.height - margin)).resize(image.size)
            for target in ('positive_logit', 'negative_logit'):
                grid, score, details = compute(model, head, tensor, target)
                probe = deletion_diagnostics(model, head, tensor, grid, target, random_repeats=3)
                randomization = (randomized_diagnostics(model, head, tensor, grid, target) if args.kind == 'gradcam'
                                 else dict(state='not_measured', note='Randomization measured only for the gradient baseline.'))
                stability = {}
                for name, variant in variants.items():
                    changed_tensor = image_transform()(model_face(variant, None, task)).unsqueeze(0)
                    changed_map, changed_score, _ = compute(model, head, changed_tensor, target)
                    stability[name] = dict(map_similarity(grid, changed_map), score_change=changed_score - score,
                                           note='Framing comparison is diagnostic; no pixel-level alignment claim.')
                records.append(dict(sample_id=row['sample_id'], source=row['source'], method=row['method'], split='train',
                                    task=task, target=target, kind=args.kind, score=score, response=details,
                                    deletion=probe, randomization=randomization, stability=stability))
            print(task, row['sample_id'], 'measured', flush=True)
        del model, head
    # Nearby real decoded video frames: retain temporary IoU association, no smoothing.
    video = next(data_location('ffpp').rglob('*.mp4'))
    from faceguard.inference.core import Predictor
    predictor = Predictor(device='cpu')
    from faceguard.inference.media_faces import detect_face_crops
    capture = cv2.VideoCapture(str(video))
    video_records = []
    previous = None
    try:
        for index in (0, 6, 12):
            assert capture.set(cv2.CAP_PROP_POS_FRAMES, index)
            ok, frame = capture.read()
            assert ok and abs(capture.get(cv2.CAP_PROP_POS_FRAMES) - 1 - index) < .5
            faces, _ = detect_face_crops(frame, predictor.detector, max_faces=1)
            if not faces:
                previous = None
                continue
            face = faces[0]
            tensor = predictor.transform(face['image']).unsqueeze(0)
            grid, score = gradcam(predictor.model, predictor.head, tensor)
            item = dict(frame_index=index, bbox=face['bbox'], score=score)
            if previous is not None:
                a, b = previous[0], face['bbox']
                intersection = max(0, min(a[2], b[2])-max(a[0], b[0])) * max(0, min(a[3], b[3])-max(a[1], b[1]))
                overlap = intersection / max(1, (a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-intersection)
                item.update(bbox_iou=overlap, same_spatial_association=overlap >= .5,
                            similarity=map_similarity(previous[1], grid) if overlap >= .5 else None)
            video_records.append(item)
            previous = (face['bbox'], grid)
    finally:
        capture.release()
    after = {task: digest(path) for task, path in models.items()}
    assert before == after
    summaries = []
    for task in models:
        for target in ('positive_logit', 'negative_logit'):
            subset = [r for r in records if r['task'] == task and r['target'] == target]
            comparisons = [c for row in subset for c in row['deletion']['comparisons']]
            summaries.append(dict(task=task, target=target, cases=len(subset), zero_response=sum(r['deletion']['state'] == 'no_response' for r in subset),
                                  measured_mask_comparisons=len(comparisons), top_beats_random=sum(r['top_minus_random'] > 0 for r in comparisons),
                                  mean_top_minus_random=float(np.mean([r['top_minus_random'] for r in comparisons])) if comparisons else None))
    report = dict(integrity_passed=True, weights_unchanged=True, kind=args.kind, date_beijing='2026-11-02', manifest_sha256=digest(manifest),
                  model_sha256=before, selected_training_crops=len(selected), explanations=len(records), cases=records,
                  summaries=summaries, video=dict(path=str(video), frames=video_records, kind='gradcam', note='Unsmoothed adjacent-frame gradient baseline only.'),
                  limitations=['Small deterministic development sample, not new held-out accuracy or a general faithfulness certificate.',
                               'Zero maps are retained; masking and framing shifts can themselves change the input distribution.',
                               'No detector training, threshold fitting, map tuning against tests, temporal smoothing or pixel segmentation claims.'])
    (output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps(dict(explanations=len(records), summaries=summaries, weights_unchanged=True)))


if __name__ == '__main__':
    main()
