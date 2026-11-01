"""Check false alerts from both existing heads on genuine-source raw photos; no training."""
from project_io import resolve_data_path, data_location
import argparse
from collections import defaultdict
import csv
import hashlib
import io
from pathlib import Path
import zipfile

import cv2
import numpy as np
from PIL import Image,ImageOps
import torch

from core import HERE,Predictor,detect_face_crops,save_json,score_images
from face_analysis import GenerationPredictor
from generation_common import canonical_face


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=resolve_data_path,required=True)
    parser.add_argument('--output',type=resolve_data_path,required=True)
    parser.add_argument('--per-source',type=int,default=150)
    args=parser.parse_args()
    torch.set_num_threads(2);cv2.setNumThreads(1)
    with args.manifest.open(encoding='utf-8-sig',newline='') as stream:
        rows=[r for r in csv.DictReader(stream) if r['split']=='test' and r['label']=='0']
    sources=defaultdict(list)
    for row in rows:
        sources[row['source']].append(row)
    selected=[]
    for source,group in sorted(sources.items()):
        group.sort(key=lambda r:hashlib.sha256(('photo-task-audit-v1:'+r['sample_id']).encode()).hexdigest())
        selected.extend(group[:args.per_source])
    manipulation=Predictor(device='cpu');generation=GenerationPredictor(device='cpu')
    details=[]
    with torch.inference_mode():
        for row in selected:
            path=resolve_data_path(row['raw_path'])
            if row.get('archive_member'):
                with zipfile.ZipFile(path) as archive:
                    data=archive.read(row['archive_member'])
                path=io.BytesIO(data)
            with Image.open(path) as source:
                image=ImageOps.exif_transpose(source).convert('RGB')
            faces,total=detect_face_crops(cv2.cvtColor(np.asarray(image),cv2.COLOR_RGB2BGR),generation.detector)
            ms=score_images(manipulation.model,manipulation.head,manipulation.transform,[r['image'] for r in faces],'cpu') if faces else []
            gs=score_images(generation.model,generation.head,generation.transform,[canonical_face(r['image']) for r in faces],'cpu') if faces else []
            details.append(dict(sample_id=row['sample_id'],source=row['source'],detected=total,analyzed=len(faces),
                manipulation_scores=ms,generation_scores=gs,
                manipulation_alert=any(p>=manipulation.state['frame_threshold'] for p in ms),
                generation_alert=any(p>=generation.state['frame_threshold'] for p in gs)))
            if len(details)%50==0:
                print(f'Processed {len(details)}/{len(selected)}',flush=True)
    report=dict(n=len(details),by_source={},
        manipulation_threshold=manipulation.state['frame_threshold'],generation_threshold=generation.state['frame_threshold'],
        note='Publisher-real LFW/FFHQ raw photos, convenience sample. FF++ head was calibrated on video frames, not these photos; do not interpret combined OR as a calibrated verdict.')
    for source in sources:
        group=[r for r in details if r['source']==source]
        report['by_source'][source]=dict(n=len(group),no_face=sum(not r['analyzed'] for r in group),
            multiple_faces=sum(r['analyzed']>1 for r in group),
            manipulation_false_alerts=sum(r['manipulation_alert'] for r in group),
            generation_false_alerts=sum(r['generation_alert'] for r in group),
            either_false_alert=sum(r['manipulation_alert'] or r['generation_alert'] for r in group))
    args.output.mkdir(parents=True,exist_ok=True)
    save_json(args.output/'details.json',details);save_json(args.output/'summary.json',report)
    print(report,flush=True)


if __name__=='__main__':
    main()
