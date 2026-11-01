"""Measure adaptive review on a fixed source-grouped subset; reuse only validation for calibration."""
from project_io import resolve_data_path, data_location
import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
import hashlib
import json
from pathlib import Path
import threading
import time

import cv2
import torch

from core import HERE, PROJECT, Predictor, digest, save_json
from video_analysis import temporal_alert_score


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--split', choices=['val', 'test'], required=True)
    parser.add_argument('--output', type=resolve_data_path, required=True)
    parser.add_argument('--fake-per-method', type=int, default=35)
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('--device', choices=['cpu', 'cuda'], default='cuda')
    args = parser.parse_args()
    start = time.monotonic()
    args.output.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(2)
    cv2.setNumThreads(1)
    manifest = resolve_data_path(PROJECT / 'data/manifests/ffpp-frames-full-93e2b370610e.csv')
    with manifest.open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    by_method, unique = defaultdict(list), {}
    for row in rows:
        if row['split'] == args.split:
            unique.setdefault(row['parent_video_id'], row)
    for row in unique.values():
        by_method[row['method']].append(row)
    selected = []
    for method, group in sorted(by_method.items()):
        group.sort(key=lambda r: hashlib.sha256(('video-review-v1:' + r['parent_video_id']).encode()).hexdigest())
        selected.extend(group if group[0]['label'] == '0' else group[:args.fake_per_method])
    protocol = dict(split=args.split, videos=len(selected), video_ids=[r['parent_video_id'] for r in selected],
        manifest_sha256=digest(manifest), model_sha256=digest(resolve_data_path(HERE / 'artifacts/model_finetuned.pt')),
        selection='All real videos + first fixed-hash 35 per fake method (unless overridden); source group split retained',
        aggregation='Maximum pair mean within one spatial IoU track and 1.5s; not a learned temporal model',
        calibration='Use validation real videos only to pick false-alert operating point; never test')
    save_json(args.output / 'PROTOCOL.json', protocol)
    local = threading.local()
    def run(row):
        target = args.output / (row['parent_video_id'] + '.json')
        if target.is_file():
            result = json.loads(target.read_text(encoding='utf-8'))
            if result.get('model_sha256') == protocol['model_sha256']:
                return result
        if not hasattr(local, 'predictor'):
            local.predictor = Predictor(device=args.device)
        t0 = time.monotonic()
        result = local.predictor.predict(resolve_data_path(PROJECT / row['source_video']), adaptive_video=True)
        result.update(video_id=row['parent_video_id'], known_label=int(row['label']), method=row['method'],
                      source_group=row['group_id'], split=args.split, seconds_elapsed=time.monotonic()-t0,
                      model_sha256=protocol['model_sha256'])
        result['temporal_alert_score'] = temporal_alert_score(result)
        save_json(target, result)
        return result
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(run, row): row for row in selected}
        for future in as_completed(futures):
            result = future.result()
            results.append(dict(video_id=result['video_id'], label=result['known_label'], method=result['method'],
                score=result['temporal_alert_score'], raw_alert=result.get('raw_frame_alert',result['decision']=='review_alerts'),
                legacy_score=result['legacy_baseline']['score'], frames=result['sampled_frames'],
                seconds=result['seconds_elapsed']))
            save_json(args.output / 'progress.json', dict(done=len(results), total=len(selected), seconds=time.monotonic()-start))
            if len(results) % 10 == 0:
                print(json.dumps(dict(done=len(results), total=len(selected), seconds=time.monotonic()-start)), flush=True)
    results.sort(key=lambda r: r['video_id'])
    save_json(args.output / 'scores.json', results)
    print(f'Completed {len(results)} {args.split} videos in {time.monotonic()-start:.1f}s', flush=True)


if __name__ == '__main__':
    main()
