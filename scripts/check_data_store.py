"""Check consolidated data, old manifest references and actual sample decoding."""
from collections import Counter
import csv
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from faceguard.data_locations import DATA_ROOT, data_location, resolve_data_path


def sha256(path):
    with path.open('rb') as file:
        return hashlib.file_digest(file, 'sha256').hexdigest()


def main():
    catalog = json.loads((DATA_ROOT / 'DATA_CATALOG.json').read_text(encoding='utf-8'))
    receipt = DATA_ROOT / '05_provenance/consolidation-20261031/verification.json'
    verification = json.loads(receipt.read_text(encoding='utf-8'))
    if not verification['sha256_before_after_equal'] or verification['state'] != 'complete':
        raise ValueError('Consolidation is not fully verified')
    links = []
    for entry in catalog['entries']:
        target = Path(entry['directory'])
        if not target.exists() or not target.resolve().is_relative_to(DATA_ROOT.resolve()):
            raise ValueError('Canonical catalog entry missing or outside the data store')
        if not entry.get('legacy_entry'):
            continue
        legacy = Path(entry['legacy_entry'])
        if entry.get('legacy_status') == 'removed':
            if os.path.lexists(legacy):
                raise ValueError('Removed legacy entry still exists: ' + str(legacy))
        elif not os.path.samefile(target, legacy):
            raise ValueError('Broken legacy entry: ' + str(legacy))
        links.append(entry['dataset_id'])

    manifests = [
        ('ffpp-full', data_location('ffpp_manifests') / 'ffpp-frames-full-93e2b370610e.csv', ROOT),
        ('generation-baseline', data_location('generation_manifest'), ROOT / 'reference_run'),
        ('openfake-combined', data_location('openfake_faces') / 'combined_manifest.csv', ROOT / 'reference_run'),
        ('photo-supervision', data_location('photo_supervision') / 'manifest.csv', ROOT / 'reference_run'),
        ('fairface-exam', data_location('fairface_evaluation') / 'manifest.csv', ROOT / 'reference_run'),
        ('locked-exam', data_location('locked_evaluation') / 'manifest.csv', ROOT / 'reference_run'),
        ('new-data-development', data_location('new_data_evaluation') / 'development-baseline/selection.csv', ROOT),
    ]
    summaries = []
    canonical_root = DATA_ROOT.resolve()
    for name, path, relative_root in manifests:
        with path.open(encoding='utf-8-sig', newline='') as file:
            rows = list(csv.DictReader(file))
        external = 0
        for row in rows:
            image = resolve_data_path(row['path'], relative_root)
            if not image.is_file():
                raise FileNotFoundError(image)
            if not image.is_relative_to(canonical_root):
                external += 1
        summaries.append(dict(name=name, rows=len(rows), sha256=sha256(path),
                              split_counts=dict(Counter(r.get('split', '') for r in rows)),
                              label_counts=dict(Counter(r['label'] for r in rows)), outside_canonical_root=external))
        print(f'{name}: {len(rows)} paths readable; {external} outside canonical store', flush=True)
    baseline = data_location('new_data_evaluation') / 'development-baseline'
    lock = json.loads((baseline / 'selection-lock.json').read_text(encoding='utf-8'))
    if sha256(baseline / 'selection.csv') != lock['selection_sha256']:
        raise ValueError('Historical frozen selection hash changed')
    from PIL import Image
    import cv2
    import pyarrow.parquet as pq
    decoded = []
    for key, path in [('dff-real', next((data_location('dff') / 'wiki/wiki').rglob('*.jpg'))),
                      ('dff-fake', next((data_location('dff') / 'text2img/text2img').rglob('*.jpg'))),
                      ('lfw', next(data_location('lfw').rglob('*.jpg'))),
                      ('ffhq', next((data_location('ffhq256') / 'images').rglob('*.png'))),
                      ('old-generation', next(data_location('generation_faces').rglob('*.jpg')))]:
        with Image.open(path) as image:
            image.load(); decoded.append(dict(name=key, size=image.size))
    video = next(data_location('ffpp').rglob('*.mp4'))
    capture = cv2.VideoCapture(str(video))
    try:
        ok, frame = capture.read()
        if not ok:
            raise ValueError('Canonical FF++ video does not decode')
        decoded.append(dict(name='ffpp-video-first-frame', shape=frame.shape))
    finally:
        capture.release()
    parquet = pq.ParquetFile(data_location('gan140k') / 'validation-00000.parquet')
    if parquet.metadata.num_rows != 10000:
        raise ValueError('Unexpected GAN validation shard size')
    report = dict(passed=True, store=str(DATA_ROOT), original_files_verified=verification['files'],
                  legacy_entries_checked=len(links), legacy_entries_removed=all(e.get('legacy_status') == 'removed' for e in catalog['entries'] if e.get('legacy_entry')), manifests=summaries, sample_decoding=decoded,
                  gan_parquet_rows=parquet.metadata.num_rows, frozen_development_selection_unchanged=True,
                  scope='Data organization and read compatibility only; no new model training or accuracy result')
    output = ROOT / ('outputs/data-cleanup-20261031/access-check.json' if report['legacy_entries_removed'] else 'outputs/data-consolidation-20261031/access-check.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=True, indent=2))


if __name__ == '__main__':
    main()
