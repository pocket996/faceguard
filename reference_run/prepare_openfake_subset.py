"""Canonical largest-face research crops, prompt grouping, and cross-source similarity quarantine."""
import argparse
from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps

from audit_near_duplicates import near_pairs, perceptual_hash
from project_io import HERE,digest,save_json
from media_faces import detect_face_crops
from generation_common import encode_canonical


def write_rows(path, rows):
    fields = sorted(set().union(*(row.keys() for row in rows)))
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--subset', type=Path, required=True)
    parser.add_argument('--clean-manifest', type=Path, required=True)
    parser.add_argument('--old-hashes', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    output_images = args.output / 'crops'
    output_images.mkdir(exist_ok=True)
    cv2.setNumThreads(1)
    detector = cv2.FaceDetectorYN.create(str(HERE/'weights/face_detection_yunet_2023mar.onnx'), '', (320,320), .8, .3, 5000)
    receipts_path = args.subset / 'receipts.json'
    receipts = json.loads(receipts_path.read_text(encoding='utf-8'))
    with args.clean_manifest.open(encoding='utf-8-sig', newline='') as stream:
        old_rows = list(csv.DictReader(stream))
    rows, rejected = [], []
    for index, item in enumerate(receipts):
        try:
            raw_path = Path(item['path'])
            if digest(raw_path) != item['downloaded_sha256']:
                raise ValueError('Downloaded image checksum changed')
            with Image.open(raw_path) as source:
                image = ImageOps.exif_transpose(source).convert('RGB')
            detected, total = detect_face_crops(cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR), detector, max_faces=1)
            if not detected:
                rejected.append(dict(row_id=item['row_id'], model=item['model'], reason='no_face'))
                continue
            encoded = encode_canonical(detected[0]['image'])
            target = output_images / (hashlib.sha256(item['row_id'].encode()).hexdigest()[:24]+'.jpg')
            target.write_bytes(encoded)
            with Image.open(io.BytesIO(encoded)) as decoded:
                pixels = hashlib.sha256(decoded.convert('RGB').tobytes()).hexdigest()
            prompt = item['prompt_sha256']
            empty_prompt = hashlib.sha256(b'').hexdigest()
            group = 'openfake-prompt:' + (prompt if prompt != empty_prompt else item['image_sha256'])
            split = 'external_test' if item['use'] == 'locked_external' else ('val' if int(hashlib.sha256(('openfake-dev-v1:'+group).encode()).hexdigest()[:8],16)/2**32 >= .8 else 'train')
            rows.append(dict(sample_id=item['row_id'], path=str(target.resolve()), raw_path=str(raw_path.resolve()),
                archive_member='', group=group, label='0' if item['label']=='real' else '1',
                method='real' if item['label']=='real' else item['model'], source='OpenFake:'+item['model'],
                split=split, pixel_sha256=pixels, raw_width=image.width, raw_height=image.height,
                publisher_image_sha256=item['image_sha256'], downloaded_sha256=item['downloaded_sha256'],
                detected_faces=total, label_scope='Image-level publisher label assumed applicable to largest face crop; not a per-face manual forensic annotation'))
        except (OSError, ValueError, Image.DecompressionBombError) as error:
            rejected.append(dict(row_id=item['row_id'], model=item['model'], reason=str(error)))
        if (index+1)%100==0:
            print(json.dumps(dict(done=index+1,total=len(receipts),accepted=len(rows))), flush=True)
    # Do not allow the same prompt or exact pixels to link development and locked exam data.
    groups = {}
    for row in rows:
        groups.setdefault(row['group'], set()).add(row['split'])
    drop = {row['sample_id']: 'prompt_crosses_development_and_external' for row in rows
            if 'external_test' in groups[row['group']] and len(groups[row['group']])>1}
    pixel_groups = {}
    for row in old_rows+rows:
        pixel_groups.setdefault(row['pixel_sha256'], set()).add(row['sample_id'])
    for row in rows:
        if len(pixel_groups[row['pixel_sha256']])>1:
            drop[row['sample_id']]='exact_duplicate'
    old_hash_map = json.loads(args.old_hashes.read_text(encoding='utf-8'))
    old_hashes = [int(v,16) for v in old_hash_map.values()]
    values = old_hashes + [perceptual_hash(row['path']) for row in rows]
    border = len(old_hashes)
    for left, right, distance in near_pairs(values, 6):
        if right < border:
            continue
        b = rows[right-border]
        if left < border:
            drop[b['sample_id']]='perceptually_similar_to_existing_data'
        else:
            a = rows[left-border]
            if a['group'] != b['group']:
                drop[a['sample_id']]=drop[b['sample_id']]='perceptually_similar_new_group'
    bad_groups = {r['group'] for r in rows if r['sample_id'] in drop}
    accepted = [r for r in rows if r['group'] not in bad_groups]
    quarantined = [dict(r,quarantine_reason=drop.get(r['sample_id'],'related_group')) for r in rows if r['group'] in bad_groups]
    write_rows(args.output/'new_manifest.csv',accepted)
    write_rows(args.output/'combined_manifest.csv',old_rows+accepted)
    if quarantined:
        write_rows(args.output/'quarantined.csv',quarantined)
    save_json(args.output/'rejected.json',rejected)
    save_json(args.output/'summary.json',dict(receipts_sha256=digest(receipts_path), received=len(receipts),
        accepted=len(accepted), rejected=len(rejected), quarantined=len(quarantined),
        by_split_source=dict(Counter(r['split']+'|'+r['source'] for r in accepted)),
        excluded_sources=dict(Counter(r['model']+'|'+r['reason'] for r in rejected)),
        label_limitations='Publisher image-level labels, one largest detected face, noncommercial convenience subset. No-face images are abstentions, not true negatives. No identity guarantee.'))
    print(f'Accepted {len(accepted)}, rejected {len(rejected)}, conservatively quarantined {len(quarantined)}',flush=True)


if __name__ == '__main__':
    main()
