"""Freeze a small external development sample, then score the unchanged official model."""
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from faceguard.model_registry import digest, checked_resource
from faceguard.data_locations import DATA_ROOT, data_location


def rank(seed, name):
    return hashlib.sha256(f'{seed}:{name}'.encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root', type=Path, default=DATA_ROOT)
    parser.add_argument('--output', type=Path, default=DATA_ROOT / '04_evaluation/generation-development-current')
    parser.add_argument('--per-class', type=int, default=100)
    parser.add_argument('--seed', type=int, default=20261031)
    parser.add_argument('--device', choices=['cpu', 'cuda'], default='cpu')
    args = parser.parse_args()
    if args.per_class < 1:
        raise ValueError('--per-class must be positive')
    import pyarrow.parquet as pq
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    root = args.data_root.resolve()
    # Explicit old import roots remain readable; new runs default to the canonical store.
    dff = data_location('dff', root) if (root / '01_raw').is_dir() else root / 'dff'
    gan = data_location('gan140k', root) if (root / '01_raw').is_dir() else root / 'gan140k'
    wiki, fake = dff / 'wiki/wiki', dff / 'text2img/text2img'
    real_names = {p.relative_to(wiki).as_posix() for p in wiki.rglob('*.jpg')}
    fake_names = {p.relative_to(fake).as_posix() for p in fake.rglob('*.jpg')}
    if real_names != fake_names or len(real_names) < args.per_class:
        raise ValueError('DFF paired inventory differs or is insufficient')
    names = sorted(real_names, key=lambda name: rank(args.seed, 'dff:' + name))[:args.per_class]
    rows = []
    for name in names:
        for label, folder, method in [(0, wiki, 'real'), (1, fake, 'SD15')]:
            path = folder / name
            rows.append(dict(sample_id=f'DFF:{label}:{name}', path=str(path), label=label, source='DFF',
                             method=method, group='dff:' + name, split='external_dev', original_split='',
                             raw_path=str(path), parquet_row='', original_image_path=name, raw_sha256=digest(path)))
    parquet = gan / 'validation-00000.parquet'
    stream = pq.ParquetFile(parquet)
    metadata = json.loads(stream.schema_arrow.metadata[b'huggingface'])['info']['features']
    if metadata['label']['names'] != ['real', 'fake'] or metadata['generator']['names'] != ['Real', 'StyleGAN']:
        raise ValueError('Unexpected Parquet labels or generator mapping')
    labels = stream.read(columns=['label', 'generator']).to_pylist()
    selected = set()
    for label in (0, 1):
        indices = [i for i, row in enumerate(labels) if row['label'] == label and row['generator'] == label]
        if len(indices) < args.per_class:
            raise ValueError('Insufficient GAN samples')
        selected.update(sorted(indices, key=lambda i: rank(args.seed, 'gan:' + str(i)))[:args.per_class])
    index = 0
    for batch in stream.iter_batches(batch_size=64):
        for row in batch.to_pylist():
            if index in selected:
                path = output / 'original-parquet-bytes' / f'{index:05d}.jpg'
                path.parent.mkdir(exist_ok=True)
                payload = row['image']['bytes']
                if path.exists() and path.read_bytes() != payload:
                    raise ValueError('Existing extracted original differs')
                if not path.exists():
                    path.write_bytes(payload)
                label = int(row['label'])
                rows.append(dict(sample_id=f'GAN140k:validation-00000:{index}', path=str(path), label=label,
                                 source='GAN140k', method='real' if label == 0 else 'StyleGAN',
                                 group=f'gan140k:validation-00000:{index}', split='external_dev', original_split='validation',
                                 raw_path=str(parquet), parquet_row=index, original_image_path=row['image']['path'], raw_sha256=digest(path)))
            index += 1
    manifest_path = output / 'selection.csv'
    import io
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]))
    writer.writeheader(); writer.writerows(rows)
    manifest_text = buffer.getvalue()
    if manifest_path.exists():
        with manifest_path.open(encoding='utf-8', newline='') as existing:
            if existing.read() != manifest_text:
                raise ValueError('Frozen sample differs; use a new output directory')
    with manifest_path.open('w', encoding='utf-8', newline='') as file:
        file.write(manifest_text)
    # Selection is fixed before importing/loading the predictor or seeing scores.
    checkpoint = checked_resource('generation.pt')
    selection = dict(seed=args.seed, per_source_per_class=args.per_class, n=len(rows),
                     selection_sha256=digest(manifest_path), checkpoint_sha256=digest(checkpoint),
                     parquet_sha256=digest(parquet), scope='external development only; cross-library duplicates/identities not audited')
    (output / 'selection-lock.json').write_text(json.dumps(selection, indent=2), encoding='utf-8')
    import cv2
    import torch
    from sklearn.metrics import roc_auc_score
    from faceguard.inference.face_analysis import GenerationPredictor
    torch.set_num_threads(2); cv2.setNumThreads(1)
    predictor = GenerationPredictor(device=args.device)
    threshold = float(predictor.state['frame_threshold'])
    results = []
    start = time.monotonic()
    with (output / 'predictions.jsonl').open('w', encoding='utf-8') as file:
        for step, row in enumerate(rows, 1):
            record = dict(row)
            try:
                result = predictor.predict(row['path'])
                faces = result.get('face_results', [])
                record.update(faces=len(faces), score=faces[0]['score'] if faces else None,
                              face_results=faces, no_face=not faces, error=None)
            except Exception as error:
                record.update(faces=0, score=None, no_face=False, error=str(error))
            file.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + '\n')
            results.append(record)
            if step % 100 == 0:
                print(f'Scored {step}/{len(rows)}', flush=True)
    summary = {}
    for source in ('DFF', 'GAN140k'):
        source_rows = [r for r in results if r['source'] == source]
        scored = [r for r in source_rows if r['score'] is not None]
        truth = [r['label'] for r in scored]; scores = [r['score'] for r in scored]
        counts = Counter(('tp' if r['label'] else 'fp') if r['score'] >= threshold else ('fn' if r['label'] else 'tn') for r in scored)
        real_n, fake_n = truth.count(0), truth.count(1)
        summary[source] = dict(total=len(source_rows), scored=len(scored),
                               no_face=sum(r['no_face'] for r in source_rows), errors=sum(r['error'] is not None for r in source_rows),
                               multiple_faces=sum(r['faces'] > 1 for r in source_rows),
                               real_scored=real_n, fake_scored=fake_n, confusion={k: counts[k] for k in ('tn', 'fp', 'fn', 'tp')},
                               false_positive_rate=counts['fp'] / real_n if real_n else None,
                               fake_recall=counts['tp'] / fake_n if fake_n else None,
                               auc=float(roc_auc_score(truth, scores)) if real_n and fake_n else None)
    report = dict(**selection, threshold=threshold, device=args.device, seconds=time.monotonic()-start,
                  protocol='Raw image -> official YuNet -> largest detected face -> generation128_jpeg90 -> unchanged checkpoint/threshold',
                  results=summary, training_run=False,
                  limitations=['Small development sample; not a new final blind test',
                               'Cross-library exact/near duplicates and celebrity identities not audited',
                               'Metrics exclude no-face/decode failures; counts reported separately',
                               'DFF real/generated families paired; semantic image correspondence is not a pixel mask'])
    (output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=True, indent=2))


if __name__ == '__main__':
    main()
