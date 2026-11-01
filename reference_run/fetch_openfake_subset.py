"""Bounded public-viewer subset; no remote code, full shards, credentials, or dataset upload."""
from project_io import resolve_data_path, data_location
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request

REPO = 'ComplexDataLab/OpenFake'
REVISION = '3247b942f18d39d1fd476b1077852af033d35d8c'
# Fix the protocol before inference. Final generators must never enter training/selection.
PLAN = [
    ('train', 'gpt-image-1', 600, 'development'),
    ('train', 'pexels', 600, 'development'),
    ('train', 'laion', 300, 'development'),
    ('test', 'gpt-image-1.5', 250, 'locked_external'),
    ('test', 'gpt-image-2', 250, 'locked_external'),
    ('test', 'nano-banana-pro', 250, 'locked_external'),
    ('test', 'docci', 400, 'locked_external'),
]


def request_bytes(url, limit, timeout=40):
    request = urllib.request.Request(url, headers={'User-Agent': 'FaceGuard-bounded-research/0.2'})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                size = int(response.headers.get('Content-Length', 0))
                if size > limit:
                    raise ValueError('Response exceeds byte limit')
                data = response.read(limit + 1)
                if len(data) > limit:
                    raise ValueError('Response exceeds byte limit')
                return data
        except urllib.error.HTTPError as error:
            if error.code != 429 or attempt == 2:
                raise
            retry = error.headers.get('Retry-After', '120')
            wait = int(retry) if retry.isdigit() else 120
            # Respect rate limits. Never rotate proxies/tokens or change endpoints to evade them.
            print(json.dumps(dict(stage='rate_limit', wait_seconds=wait)), flush=True)
            remaining = max(1, wait)
            while remaining:
                delay = min(30, remaining)
                time.sleep(delay)
                remaining -= delay


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=resolve_data_path, required=True)
    parser.add_argument('--metadata-only', action='store_true')
    parser.add_argument('--max-mb', type=int, default=3000)
    parser.add_argument('--scan-rows', action='store_true', help='Use documented rows API if server-side filtering is unavailable')
    parser.add_argument('--scan-limit', type=int, default=15000)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    current = json.loads(request_bytes(f'https://huggingface.co/api/datasets/{REPO}', 5_000_000))['sha']
    if current != REVISION:
        raise ValueError('Dataset revision changed; review and pin a new protocol explicitly')
    protocol = dict(repo=REPO, revision=REVISION, plan=PLAN, max_bytes=args.max_mb * 1_000_000,
        license='CC-BY-NC-4.0 (research only; original source terms still apply)',
        source='https://huggingface.co/datasets/ComplexDataLab/OpenFake',
        representation='Public dataset viewer cached image; may be re-encoded. Store both publisher and downloaded hashes.',
        selection='First N matching rows in published order per generator/source; convenience subset, NOT random benchmark',
        final_protocol='GPT1 development only; GPT1.5/GPT2/nano-banana-pro + DOCCI locked until candidate and thresholds freeze',
        source_name_note='Official card calls GPT2 gpt-image-2.0; cached row metadata uses gpt-image-2. Protocol corrected using metadata only, before any external inference.')
    (args.output / 'PROTOCOL.json').write_text(json.dumps(protocol, indent=2), encoding='utf-8')
    metadata = []
    if args.scan_rows:
        for split in ('train', 'test'):
            targets = {model: (count, use) for s, model, count, use in PLAN if s == split}
            counts = {model: 0 for model in targets}
            for offset in range(0, args.scan_limit, 100):
                params = dict(dataset=REPO, config='core', split=split, offset=offset, length=100)
                cache = args.output / f'scan-{split}-{offset}.json'
                if cache.is_file():
                    body = json.loads(cache.read_text(encoding='utf-8'))
                else:
                    url = 'https://datasets-server.huggingface.co/rows?' + urllib.parse.urlencode(params)
                    body = json.loads(request_bytes(url, 8_000_000, timeout=45))
                    cache.write_text(json.dumps(body), encoding='utf-8')
                    time.sleep(3)
                for item in body['rows']:
                    row = item['row']
                    model = row['model']
                    if model not in targets or counts[model] >= targets[model][0]:
                        continue
                    if f'/--/{REVISION}/--/' not in row['image']['src']:
                        raise ValueError('Viewer revision differs from frozen protocol')
                    if row['label'] not in ('fake', 'real'):
                        raise ValueError('Unexpected label')
                    metadata.append(dict(row, dataset_split=split, use=targets[model][1], row_index=item['row_idx']))
                    counts[model] += 1
                if offset % 1000 == 0:
                    print(json.dumps(dict(stage='scan', split=split, offset=offset, selected=counts)), flush=True)
                if all(counts[m] >= targets[m][0] for m in targets):
                    break
            protocol.setdefault('actual_counts', {})[split] = counts
            (args.output / 'PROTOCOL.json').write_text(json.dumps(protocol, indent=2), encoding='utf-8')
    for split, model, count, use in ([] if args.scan_rows else PLAN):
        for offset in range(0, count, 100):
            params = dict(dataset=REPO, config='core', split=split,
                          where='"model"=\'' + model + "'", offset=offset, length=min(100, count - offset))
            url = 'https://datasets-server.huggingface.co/filter?' + urllib.parse.urlencode(params)
            cache = args.output / f'metadata-{split}-{model}-{offset}.json'
            if cache.is_file():
                body = json.loads(cache.read_text(encoding='utf-8'))
            else:
                body = json.loads(request_bytes(url, 8_000_000, timeout=60))
                cache.write_text(json.dumps(body), encoding='utf-8')
            for item in body['rows']:
                row = item['row']
                asset = row['image']['src']
                if f'/--/{REVISION}/--/' not in asset:
                    raise ValueError('Viewer revision differs from frozen protocol')
                if row['model'] != model or row['label'] not in ('fake', 'real'):
                    raise ValueError('Unexpected source/label')
                metadata.append(dict(row, dataset_split=split, use=use, row_index=item['row_idx']))
            print(json.dumps(dict(stage='metadata', model=model, offset=offset, rows=len(body['rows']))), flush=True)
            if len(body['rows']) < params['length']:
                break
    (args.output / 'selected_metadata.json').write_text(json.dumps(metadata), encoding='utf-8')
    if args.metadata_only:
        print(f'Metadata only: {len(metadata)} records', flush=True)
        return
    image_dir = args.output / 'images'
    image_dir.mkdir(exist_ok=True)
    used = sum(p.stat().st_size for p in image_dir.iterdir() if p.is_file())
    # Sequential accounting in the parent keeps the byte budget strict even with 4 readers.
    def fetch(row):
        name = hashlib.sha256(row['row_id'].encode()).hexdigest()[:24] + '.image'
        path = image_dir / name
        if path.is_file():
            data = path.read_bytes()
        else:
            data = request_bytes(row['image']['src'], 12_000_000)
        return row, path, data
    receipts, failures = [], []
    # Small batches ensure at most 4 requests are in flight, and abort prevents further batches.
    with ThreadPoolExecutor(max_workers=4) as pool:
        for start in range(0, len(metadata), 4):
            if shutil.disk_usage(args.output).free < 30 * 1024**3:
                raise OSError('Less than 30 GiB disk space remains')
            batch = [pool.submit(fetch, row) for row in metadata[start:start + 4]]
            for future in batch:
                try:
                    row, path, data = future.result()
                    if not path.is_file():
                        if used + len(data) > protocol['max_bytes']:
                            raise ValueError('Subset download budget reached')
                        path.write_bytes(data)
                        used += len(data)
                    checksum = hashlib.sha256(data).hexdigest()
                    receipt = {k: v for k, v in row.items() if k not in ('image', 'prompt')}
                    receipt.update(path=str(path.resolve()), downloaded_sha256=checksum, bytes=len(data),
                                   matches_publisher_hash=checksum == row['image_sha256'],
                                   prompt_sha256=hashlib.sha256(row.get('prompt', '').encode()).hexdigest())
                    receipts.append(receipt)
                except (OSError, ValueError, urllib.error.URLError) as exc:
                    failures.append(str(exc))
            if start % 100 == 0 or start + 4 >= len(metadata):
                (args.output / 'receipts.json').write_text(json.dumps(receipts, indent=2), encoding='utf-8')
                (args.output / 'failures.json').write_text(json.dumps(failures, indent=2), encoding='utf-8')
                print(json.dumps(dict(stage='download', completed=len(receipts), failures=len(failures), mb=used/1e6)), flush=True)
            if len(failures) > 12:
                raise RuntimeError('Too many failures; stopped without bypassing service controls')
    print(f'Finished: {len(receipts)} downloaded, {len(failures)} failures', flush=True)


if __name__ == '__main__':
    main()
