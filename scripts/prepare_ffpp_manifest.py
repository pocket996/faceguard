"""Build the complete FF++ manifest from official splits and download receipts."""
import json
from collections import Counter
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from faceguard.data import BASE_FIELDS, validate_manifest, write_manifest
from faceguard.data_locations import data_location


def main():
    receipts = json.loads((data_location('ffpp_manifests') / 'ffpp-download-receipts.json').read_text())
    groups, assignments, partners = {}, {}, {}
    for split in ('train', 'val', 'test'):
        pairs = json.loads((data_location('ffpp_manifests') / 'ffpp-splits' / f'{split}.json').read_text())
        for pair in pairs:
            group = 'ffpp:' + '_'.join(sorted(pair))
            for video_id in pair:
                if video_id in assignments:
                    raise ValueError(f'Duplicate official source ID: {video_id}')
                groups[video_id], assignments[video_id] = group, split
                partners[video_id] = next(i for i in pair if i != video_id)
    if len(assignments) != 1000:
        raise ValueError('Expected 1000 officially split original sequences')
    rows = []
    folders = {'original': 'original_sequences/youtube',
               **{m: f'manipulated_sequences/{m}' for m in
                  ('Deepfakes', 'Face2Face', 'FaceSwap', 'NeuralTextures')}}
    expected_paths = set()
    for method, folder in folders.items():
        for video_id in sorted(assignments):
            names = [video_id] if method == 'original' else [
                video_id + '_' + partners[video_id]]
            for name in names:
                parts = name.split('_')
                legacy_key = f'data/raw/ffpp/{folder}/c23/videos/{name}.mp4'
                path = str(data_location('ffpp') / folder / f'c23/videos/{name}.mp4')
                expected_paths.add(path)
                receipt = receipts.get(legacy_key)
                if not receipt or not (ROOT / path).is_file():
                    raise ValueError(f'Missing official video or receipt: {path}')
                if (ROOT / path).stat().st_size != receipt['bytes']:
                    raise ValueError(f'File size changed: {path}')
                rows.append(dict(sample_id=f'ffpp_{method}_{name}_c23', path=path,
                    label=0 if method == 'original' else 1, dataset='FF++',
                    task='real' if method == 'original' else 'face_manipulation',
                    method=method, compression='c23', target_id=video_id,
                    source_id=parts[1] if len(parts) > 1 else '',
                    group_id=groups[video_id], split=assignments[video_id],
                    media_type='video', provenance_status='verified'))
    actual_paths = {str(p)
                    for folder in folders.values()
                    for p in (data_location('ffpp') / folder / 'c23/videos').glob('*.mp4')}
    if actual_paths != expected_paths:
        raise ValueError('Official directory contains missing or unexpected videos')
    validate_manifest(rows)
    write_manifest(data_location('ffpp_manifests') / 'ffpp-videos.csv', rows, BASE_FIELDS)
    report = {'videos': len(rows), 'groups': len(set(groups.values())),
              'by_split': dict(Counter(r['split'] for r in rows)),
              'by_method': dict(Counter(r['method'] for r in rows)),
              'related_source_split_overlap': False,
              'checks': 'official split, paths, receipt sizes; not full decode or identity audit'}
    (ROOT / 'outputs/ffpp-manifest-check.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
