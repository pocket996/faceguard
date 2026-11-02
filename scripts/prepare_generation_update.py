"""Canonical DFF face preparation. Raw data and historical manifests are read-only."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import csv
import hashlib
import io
import json
from pathlib import Path
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from faceguard.data_locations import DATA_ROOT, data_location
from faceguard.model_registry import checked_resource, digest
from faceguard.inference.media_faces import detect_face_crops
from faceguard.inference.generation_common import encode_canonical

VERSION = 'dff-sd15-20261031-v1'
LOCAL = threading.local()


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name+'.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


def crop_dataset(workers):
    import cv2
    import numpy as np
    from PIL import Image, ImageOps
    cv2.setNumThreads(1)
    source = data_location('dff')
    output = data_location('dff_update_faces')
    receipt = data_location('dff_update_provenance')
    output.mkdir(parents=True, exist_ok=True); receipt.mkdir(parents=True, exist_ok=True)
    weight = checked_resource('yunet.onnx')
    config = dict(yunet_sha256=digest(weight), score=.8, max_faces=1, margin=1.3,
                  canonical='256px AREA face ->128px AREA ->JPEG90 4:4:4', version=1)
    config_path = receipt/'crop-config.json'
    if config_path.exists() and json.loads(config_path.read_text(encoding='utf-8')) != config:
        raise ValueError('Preprocessing config changed; choose a new version directory')
    save_json(config_path, config)
    previous = {}
    cache = receipt/'crop-records.jsonl'
    if cache.exists():
        with cache.open(encoding='utf-8') as file:
            for line in file:
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                previous[row['sample_id']] = row
    jobs = []
    wiki = source/'wiki/wiki'
    for real in sorted(wiki.rglob('*.jpg')):
        relative = real.relative_to(wiki)
        fake = source/'text2img/text2img'/relative
        if not fake.is_file():
            raise FileNotFoundError(fake)
        for label, path, method in [(0, real, 'real'), (1, fake, 'SD15')]:
            jobs.append(dict(sample_id=f'DFF:{label}:{relative.as_posix()}', raw_path=str(path),
                             relative_path=relative.as_posix(), family='dff:'+relative.as_posix(),
                             label=str(label), source='DFF', method=method,
                             path=str(output/('real' if label==0 else 'sd15')/relative)))
    if len(jobs) != 60000:
        raise ValueError('Unexpected DFF inventory')
    start = time.monotonic()
    def process(job):
        raw = Path(job['raw_path']); stat=raw.stat()
        prior=previous.get(job['sample_id'])
        if prior and prior.get('raw_size')==stat.st_size and prior.get('raw_mtime_ns')==stat.st_mtime_ns:
            if prior.get('error') or Path(prior['path']).is_file():
                return prior
        row=dict(job, raw_size=stat.st_size, raw_mtime_ns=stat.st_mtime_ns)
        if not hasattr(LOCAL, 'detector'):
            LOCAL.detector=cv2.FaceDetectorYN.create(str(weight),'',(320,320),.8,.3,5000)
        try:
            with Image.open(raw) as image:
                image=ImageOps.exif_transpose(image).convert('RGB')
                width,height=image.size
                faces,total=detect_face_crops(cv2.cvtColor(np.asarray(image),cv2.COLOR_RGB2BGR), LOCAL.detector,max_faces=1)
            if not faces:
                return dict(row,error='no_face',detected_faces=total)
            encoded=encode_canonical(faces[0]['image'])
            target=Path(row['path']);target.parent.mkdir(parents=True,exist_ok=True)
            temporary=target.with_suffix('.jpg.tmp');temporary.write_bytes(encoded);temporary.replace(target)
            with Image.open(io.BytesIO(encoded)) as decoded:
                pixels=decoded.convert('RGB').tobytes()
            return dict(row,error=None,pixel_sha256=hashlib.sha256(pixels).hexdigest(),
                        encoded_sha256=hashlib.sha256(encoded).hexdigest(),detected_faces=total,
                        raw_width=width,raw_height=height,crop_box=faces[0]['bbox'],
                        detector_confidence=faces[0]['detector_confidence'])
        except Exception as error:
            return dict(row,error=str(error))
    accepted,rejected=[],[]
    with ThreadPoolExecutor(max_workers=workers) as pool, cache.open('a',encoding='utf-8') as file:
        for index,row in enumerate(pool.map(process,jobs),1):
            file.write(json.dumps(row,ensure_ascii=False)+'\n')
            (rejected if row.get('error') else accepted).append(row)
            if index%1000==0:
                file.flush()
                value=dict(stage='crop',done=index,total=len(jobs),accepted=len(accepted),rejected=len(rejected),seconds=time.monotonic()-start)
                save_json(receipt/'progress.json',value);print(json.dumps(value),flush=True)
    fields=sorted(set().union(*(row.keys() for row in accepted)))
    with (receipt/'cropped.csv').open('w',encoding='utf-8',newline='') as file:
        writer=csv.DictWriter(file,fieldnames=fields);writer.writeheader();writer.writerows(accepted)
    save_json(receipt/'rejected.json',rejected)
    report=dict(stage='crop_complete',raw=len(jobs),accepted=len(accepted),rejected=len(rejected),
                rejected_by_reason=dict(Counter(row['error'] for row in rejected)),
                by_label=dict(Counter(row['label'] for row in accepted)),seconds=time.monotonic()-start)
    save_json(receipt/'crop-report.json',report);print(json.dumps(report),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers',type=int,default=2,choices=range(1,5))
    args=parser.parse_args()
    crop_dataset(args.workers)


if __name__=='__main__':
    main()
