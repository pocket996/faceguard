"""Freeze a joint GPT1/SD1.5 experiment without repurposing observed external generators."""
import argparse
from collections import Counter, defaultdict
import hashlib
import io
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'reference_run'))
from faceguard.data_locations import data_location, resolve_data_path
from faceguard.model_registry import checked_resource, digest
from audit_near_duplicates import near_pairs
from split_generation_update import read, write
from prepare_generation_update import save_json


def fingerprint(image):
    import cv2
    import numpy as np
    image = image.convert('RGB')
    low = cv2.dct(cv2.resize(np.asarray(image.convert('L')), (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32))[:8, :8].flatten()
    bits = low > np.median(low[1:]); bits[0] = False
    return hashlib.sha256(image.tobytes()).hexdigest(), sum(int(bit) << i for i, bit in enumerate(bits))


def main():
    import cv2
    import numpy as np
    from PIL import Image, ImageOps
    from faceguard.inference.media_faces import detect_face_crops
    from faceguard.inference.generation_common import encode_canonical
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--regression-image', type=Path, required=True)
    args = parser.parse_args(); cv2.setNumThreads(1)
    folder = data_location('generation_joint_manifests'); folder.mkdir(parents=True, exist_ok=True)
    provenance = data_location('generation_joint_provenance'); provenance.mkdir(parents=True, exist_ok=True)
    if (folder / 'manifest.csv').exists():
        raise FileExistsError('Joint manifest already frozen')
    base_path = data_location('generation_update_manifests') / 'manifest.csv'
    base_protocol = json.loads((base_path.parent / 'protocol.json').read_text(encoding='utf-8'))
    if digest(base_path) != base_protocol['manifest_sha256']:
        raise ValueError('DFF frozen manifest changed')
    base = read(base_path)
    original_path = ROOT / 'reference_run/artifacts/generation/joint/manifest.csv'
    base_ids = {r['sample_id'] for r in base}
    ghosts = [r for r in read(original_path) if r['sample_id'] not in base_ids]
    for row in ghosts:
        with Image.open(resolve_data_path(row['path'], ROOT / 'reference_run')) as image:
            pixel, value = fingerprint(image)
        if pixel != row['pixel_sha256']:
            raise ValueError('Ghost pixels changed')
        row['phash'] = str(value)
    old = base + ghosts
    new_path = data_location('openfake_faces') / 'combined_manifest.csv'
    new = [dict(r, path=str(resolve_data_path(r['path']))) for r in read(new_path) if r['source'].startswith('OpenFake:')]
    for row in new:
        with Image.open(row['path']) as image:
            pixel, value = fingerprint(image)
        if pixel != row['pixel_sha256']:
            raise ValueError('OpenFake pixels changed')
        row['phash'] = str(value)
    detector = cv2.FaceDetectorYN.create(str(checked_resource('yunet.onnx')), '', (320,320), .8, .3, 5000)
    with Image.open(args.regression_image) as image:
        image = ImageOps.exif_transpose(image).convert('RGB')
        faces, _ = detect_face_crops(cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR), detector, max_faces=1)
    if not faces:
        raise ValueError('Regression image has no face')
    with Image.open(io.BytesIO(encode_canonical(faces[0]['image']))) as image:
        case_pixel, case_hash = fingerprint(image)
    bad = {}; case_groups = set(); pairs = []
    by_group = defaultdict(set); by_pixel = defaultdict(list)
    for row in new:
        by_group[row['group']].add(row['split']); by_pixel[row['pixel_sha256']].append(row)
    old_pixels = {r['pixel_sha256'] for r in old}
    for row in new:
        if len(by_group[row['group']]) > 1: bad[row['group']] = 'prompt_crosses_splits'
        if row['pixel_sha256'] in old_pixels: bad[row['group']] = 'exact_match_to_frozen_or_initial_history'
        if len(by_pixel[row['pixel_sha256']]) > 1: bad[row['group']] = 'duplicate_new_pixels'
    border = len(old); all_rows = old + new
    hashes = [int(r['phash']) for r in all_rows] + [case_hash]
    print(json.dumps(dict(stage='joint_similarity_audit', old=len(old), new=len(new))), flush=True)
    for left, right, distance in near_pairs(hashes, 6):
        if right == len(all_rows):
            case_groups.add(all_rows[left]['group']); continue
        if right < border: continue
        a, b = all_rows[left], all_rows[right]
        if left < border:
            bad[b['group']] = 'near_match_to_frozen_or_initial_history'
        elif a['group'] != b['group']:
            bad[a['group']] = bad[b['group']] = 'near_duplicate_new_groups'
        else: continue
        pairs.append(dict(left_id=a['sample_id'], right_id=b['sample_id'], distance=distance))
    accepted = []; rejected = []
    for row in base + new:
        reason = bad.get(row['group'], '')
        if row['group'] in case_groups or row['pixel_sha256'] == case_pixel:
            reason = 'related_to_observed_user_regression_case'
        if reason: rejected.append(dict(row, quarantine_reason=reason))
        else: accepted.append(row)
    for row in accepted:
        if row['split'] in ('train','val') and row['method'] not in ('real','SD15','FLUX','SD35','gpt-image-1'):
            raise ValueError('External generator entered development')
    from train_generation import audit
    audit(accepted, allow_sd35_training=True, allow_openfake=True, allow_dff=True)
    write(folder / 'manifest.csv', accepted)
    write(folder / 'train-val.csv', [r for r in accepted if r['split'] in ('train','val')])
    write(folder / 'regression-test.csv', [r for r in accepted if r['split'] not in ('train','val')])
    if rejected: write(folder / 'quarantined.csv', rejected)
    if pairs: write(provenance / 'near-pairs.csv', pairs)
    report = dict(version='dff-gpt-joint-20261031-v1', manifest_sha256=digest(folder/'manifest.csv'),
        base_manifest_sha256=digest(base_path), openfake_manifest_sha256=digest(new_path),
        user_regression_path=str(args.regression_image.resolve()), user_regression_raw_sha256=digest(args.regression_image),
        user_regression_near_groups=len(case_groups), accepted=len(accepted), quarantined=len(rejected),
        counts=dict(Counter(r['split']+'|'+r['source']+'|'+r['method'] for r in accepted)),
        split_counts=dict(Counter(r['split'] for r in accepted)),
        quarantine_reasons=dict(Counter(r['quarantine_reason'] for r in rejected)),
        policy='DFF frozen roles retained; new OpenFake groups near any frozen or initial-history crop quarantined; GPT1 development only; previously observed GPT1.5/GPT2/nano kept external regression',
        limitations=['Only 96 GPT1 train images before additional quarantine; small convenience subset, prone to overfitting',
                      'User photo motivated this experiment but is excluded from fitting/validation and epoch/threshold selection; observed developer regression, not blind accuracy',
                      'All test sets already observed in earlier experiments; no new independent benchmark'])
    save_json(folder/'protocol.json', report); save_json(provenance/'split-report.json', report)
    print(json.dumps(report, ensure_ascii=True, indent=2), flush=True)


if __name__ == '__main__': main()
