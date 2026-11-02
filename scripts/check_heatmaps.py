"""Real local photo/candidate explanations; artifacts are never training data."""
import copy
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))


def main():
    import cv2
    import numpy as np
    from PIL import Image, ImageOps
    import torch
    from faceguard.data_locations import data_location
    from faceguard.detection import detail_records
    from faceguard.inference.face_analysis import FaceAnalyzer
    from faceguard.inference.heatmaps import explain_face, render_overlay, valid_cached_map
    from faceguard.model_registry import checked_generation_profile, generation_profiles

    torch.set_num_threads(2)
    cv2.setNumThreads(1)
    output = ROOT / 'outputs/heatmaps-check-20261101/numeric'
    output.mkdir(parents=True, exist_ok=True)
    photo = next(data_location('lfw').rglob('*.jpg'))
    generated = data_location('examples') / 'joint/generation_0.jpg'
    with Image.open(photo) as source:
        image = source.convert('RGB')
    multiple = Image.new('RGB', (image.width * 2, image.height))
    multiple.paste(image, (0, 0))
    multiple.paste(image, (image.width, 0))
    multiple_path = output / 'two-faces.png'
    multiple.save(multiple_path)
    exif_path = output / 'exif-oriented.jpg'
    exif = Image.Exif()
    exif[274] = 6
    image.transpose(Image.Transpose.ROTATE_90).save(exif_path, exif=exif)
    cases = []
    devices = ['cpu'] + (['cuda'] if torch.cuda.is_available() else [])
    for device in devices:
        analyzer = FaceAnalyzer(device=device)
        for name, path in [('real', photo), ('generated', generated), ('multi', multiple_path), ('exif', exif_path)]:
            result = analyzer.predict(path)
            before = copy.deepcopy(result)
            with Image.open(path) as source:
                original = ImageOps.exif_transpose(source).convert('RGB')
            records = detail_records(result)
            assert len(records) >= (4 if name == 'multi' else 2), result
            for index, record in enumerate(records):
                start = time.monotonic()
                payload = explain_face(original, record)
                duration = time.monotonic() - start
                assert valid_cached_map(payload, record)
                overlay = render_overlay(payload, original.size, record['bbox'])
                overlay.save(output / f'{device}-{name}-{index}.png')
                cases.append(dict(device=device, case=name, task=record['task'], face_id=record['face_id'],
                                  score=record['score'], recomputed_score=payload['score'],
                                  difference=abs(record['score'] - payload['score']), seconds=duration,
                                  grid_shape=np.asarray(payload['grid']).shape,
                                  alpha_bbox=overlay.getchannel('A').getbbox()))
            assert result == before
        # Every installed candidate must use its own preprocessing and model hash.
        for profile in generation_profiles()[1:]:
            analyzer = FaceAnalyzer(device=device, generation_checkpoint=checked_generation_profile(profile['id']))
            result = analyzer.predict(generated, task='generation')
            record = detail_records(result)[0]
            with Image.open(generated) as source:
                payload = explain_face(ImageOps.exif_transpose(source).convert('RGB'), record, profile['id'])
            assert valid_cached_map(payload, record)
            cases.append(dict(device=device, case=profile['id'], task='generation', score=record['score'],
                              recomputed_score=payload['score'], difference=abs(record['score'] - payload['score'])))
            print(device, profile['id'], 'passed', flush=True)
    report = dict(passed=True, cases=cases, max_score_difference=max(row['difference'] for row in cases))
    (output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(passed=True, explanations=len(cases), max_score_difference=report['max_score_difference'])))


if __name__ == '__main__':
    main()
