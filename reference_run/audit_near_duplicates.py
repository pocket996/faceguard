"""Screen perceptually similar crops across splits; candidates require review, not identity claims."""
import argparse
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
import time

import cv2
import numpy as np

from project_io import HERE,digest,save_json


def perceptual_hash(path):
    # Reading bytes also supports non-ASCII Windows paths.
    image = cv2.imdecode(np.frombuffer(Path(path).read_bytes(), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ValueError(f'Cannot decode {path}')
    gray = cv2.resize(image, (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32)
    low = cv2.dct(gray)[:8, :8].flatten()
    bits = low > np.median(low[1:])
    bits[0] = False
    return sum(int(bit) << i for i, bit in enumerate(bits))


def near_pairs(values, max_distance):
    """Pigeonhole index: d+1 blocks guarantees candidates for Hamming distance <= d."""
    if not 0 <= max_distance <= 10:
        raise ValueError('Distance must be between 0 and 10')
    block_count = max_distance + 1
    bounds = np.linspace(0, 64, block_count + 1, dtype=int).tolist()
    buckets = [defaultdict(list) for _ in range(block_count)]
    for i, value in enumerate(values):
        keys, candidates = [], set()
        for b, (start, end) in enumerate(zip(bounds, bounds[1:])):
            key = (value >> start) & ((1 << (end - start)) - 1)
            keys.append(key)
            candidates.update(buckets[b][key])
        for j in sorted(candidates):
            distance = (value ^ values[j]).bit_count()
            if distance <= max_distance:
                yield j, i, distance
        for b, key in enumerate(keys):
            buckets[b][key].append(i)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=HERE / 'artifacts/generation/joint/manifest.csv')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--distance', type=int, default=6)
    args = parser.parse_args()
    start = time.monotonic()
    args.output.mkdir(parents=True, exist_ok=True)
    with args.manifest.open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    hashes, candidates = [], []
    for i, row in enumerate(rows):
        hashes.append(perceptual_hash(HERE / row['path']))
        if (i + 1) % 5000 == 0:
            print(json.dumps(dict(stage='hash', done=i + 1, total=len(rows))), flush=True)
    for left, right, distance in near_pairs(hashes, args.distance):
        a, b = rows[left], rows[right]
        if a['split'] == b['split']:
            continue
        candidates.append(dict(left_id=a['sample_id'], right_id=b['sample_id'], distance=distance,
            left_split=a['split'], right_split=b['split'], left_label=a['label'], right_label=b['label'],
            left_source=a['source'], right_source=b['source'], left_path=a['path'], right_path=b['path'],
            same_pixel_hash=a['pixel_sha256'] == b['pixel_sha256']))
    candidates.sort(key=lambda r: (r['distance'], r['left_id'], r['right_id']))
    fields = ['left_id', 'right_id', 'distance', 'left_split', 'right_split', 'left_label', 'right_label',
              'left_source', 'right_source', 'left_path', 'right_path', 'same_pixel_hash']
    with (args.output / 'cross_split_candidates.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(candidates)
    save_json(args.output / 'hashes.json', {r['sample_id']: f'{h:016x}' for r, h in zip(rows, hashes)})
    summary = dict(images=len(rows), manifest_sha256=digest(args.manifest), algorithm='32px grayscale DCT 64-bit pHash (DC excluded)',
        hamming_distance=args.distance, cross_split_candidates=len(candidates),
        by_distance=dict(Counter(r['distance'] for r in candidates)),
        by_source_pair=dict(Counter('/'.join(sorted((r['left_source'], r['right_source']))) for r in candidates)),
        seconds=time.monotonic() - start,
        limitations=['Similarity is a screening signal, not proof of duplication or identity',
                     'Different crops, pose or heavy edits can evade this hash',
                     'No biometric identity matching is performed',
                     'Do not silently remove samples or relabel existing test results'])
    save_json(args.output / 'summary.json', summary)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == '__main__':
    main()
