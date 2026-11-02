"""One hash-pinned FairFace mirror shard; deterministic held-out real-face exam only."""
from project_io import resolve_data_path, data_location
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import shutil
import urllib.request

import cv2
import numpy as np
from PIL import Image,ImageOps
import pyarrow.parquet as pq

from audit_near_duplicates import near_pairs,perceptual_hash
from project_io import HERE,digest,save_json
from media_faces import detect_face_crops
from generation_common import encode_canonical
from prepare_openfake_subset import write_rows

REVISION='54d573cdb8b5af490ba8da9da2799628f6e5c496'
FILE='1.25/validation-00000-of-00001-09e3e67bb00ab4ec.parquet'
SIZE=236824583
SHA256='ce47863c011f355ef7ab63d70420d9d4b36fce03cf1621a26597955da21968bb'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=resolve_data_path,required=True)
    parser.add_argument('--old-hashes',type=resolve_data_path,required=True)
    parser.add_argument('--new-manifest',type=resolve_data_path,required=True)
    parser.add_argument('--count',type=int,default=1000)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True);(args.output/'crops').mkdir(exist_ok=True)
    if shutil.disk_usage(args.output).free<30*1024**3:
        raise OSError('Low disk space')
    shard=args.output/'fairface-validation-1.25.parquet'
    url=f'https://huggingface.co/datasets/HuggingFaceM4/FairFace/resolve/{REVISION}/{FILE}?download=true'
    if not shard.is_file() or shard.stat().st_size!=SIZE:
        request=urllib.request.Request(url,headers={'User-Agent':'FaceGuard-research/0.2'})
        part=shard.with_suffix('.part');done=0
        with urllib.request.urlopen(request,timeout=60) as response,part.open('wb') as stream:
            while chunk:=response.read(1024*1024):
                done+=len(chunk)
                if done>SIZE:
                    raise ValueError('Download exceeds pinned shard size')
                stream.write(chunk)
                if done%(25*1024*1024)<1024*1024:
                    print(f'Downloaded {done/1e6:.1f}/{SIZE/1e6:.1f} MB',flush=True)
        if done!=SIZE:
            raise ValueError('Incomplete shard')
        part.replace(shard)
    if digest(shard)!=SHA256:
        raise ValueError('LFS checksum mismatch')
    cv2.setNumThreads(1)
    detector=cv2.FaceDetectorYN.create(str(resolve_data_path(HERE/'weights/face_detection_yunet_2023mar.onnx')),'',(320,320),.8,.3,5000)
    parquet=pq.ParquetFile(shard)
    indices=sorted(range(parquet.metadata.num_rows),key=lambda i:hashlib.sha256(('fairface-exam-v1:'+str(i)).encode()).hexdigest())[:args.count]
    selected=set(indices);rows=[];rejected=[];index=0
    for batch in parquet.iter_batches(batch_size=500,columns=['image']):
        for item in batch.to_pylist():
            row_index=index;index+=1
            if row_index not in selected:
                continue
            data=item['image']['bytes']
            with Image.open(io.BytesIO(data)) as source:
                image=ImageOps.exif_transpose(source).convert('RGB')
            faces,total=detect_face_crops(cv2.cvtColor(np.asarray(image),cv2.COLOR_RGB2BGR),detector,max_faces=1)
            if not faces:
                rejected.append(dict(row_index=row_index,reason='no_face'));continue
            encoded=encode_canonical(faces[0]['image'])
            path=args.output/'crops'/f'fairface_val_{row_index:06d}.jpg';path.write_bytes(encoded)
            face256=args.output/'crops'/f'fairface_val_{row_index:06d}_face256.png'
            faces[0]['image'].save(face256)
            with Image.open(io.BytesIO(encoded)) as decoded:
                pixel_hash=hashlib.sha256(decoded.convert('RGB').tobytes()).hexdigest()
            rows.append(dict(sample_id=f'fairface_val_{row_index:06d}',path=str(path.resolve()),
                group=f'fairface-mirror-image:{row_index}',label='0',source='FairFace-1.25-mirror',method='real',
                split='external_test',pixel_sha256=pixel_hash,raw_width=image.width,raw_height=image.height,
                face256_path=str(face256.resolve()),
                raw_image_sha256=hashlib.sha256(data).hexdigest(),detected_faces=total))
        print(f'Processed shard rows {index}, accepted selected faces {len(rows)}',flush=True)
    old_hashes=[int(v,16) for v in json.loads(args.old_hashes.read_text()).values()]
    with args.new_manifest.open(encoding='utf-8-sig',newline='') as stream:
        new=list(csv.DictReader(stream))
    previous=old_hashes+[perceptual_hash(resolve_data_path(HERE/r['path'])) for r in new]
    border=len(previous);values=previous+[perceptual_hash(r['path']) for r in rows];dropped=set()
    for a,b,distance in near_pairs(values,6):
        if b<border:continue
        if a<border:dropped.add(b-border)
        else:dropped.add(b-border) # Keep the lower index once within this exam, no score-dependent selection.
    kept=[r for i,r in enumerate(rows) if i not in dropped]
    write_rows(args.output/'manifest.csv',kept)
    save_json(args.output/'PROTOCOL.json',dict(repo='HuggingFaceM4/FairFace',revision=REVISION,file=FILE,bytes=SIZE,sha256=SHA256,
        official_source='https://github.com/joojs/fairface',license='Official dataset CC BY 4.0; mirror provenance/per-image terms not independently audited',
        selection='First 1000 row indices ordered by fixed hash, validation split, padding 1.25; no attribute labels used',
        role='Locked external real-only source, never train or tune thresholds on this source',
        selected=len(indices),no_face=len(rejected),similarity_quarantined=len(dropped),accepted=len(kept),
        limitations=['Mirror, not original author-hosted bytes; LFS integrity is not proof of every original license',
                     'No global identity separation guarantee; screening uses pHash, not biometric matching',
                     'Already aligned/cropped real faces; not a universal natural-photo benchmark']))
    save_json(args.output/'rejected.json',rejected)
    print(f'Locked real exam: {len(kept)} usable faces, no model inference performed.',flush=True)


if __name__=='__main__':
    main()
