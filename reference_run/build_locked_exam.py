"""Combine separately frozen external sources; preserve both model-specific input representations."""
import argparse
from collections import Counter
import csv
from pathlib import Path

import cv2
import numpy as np
from PIL import Image,ImageOps

from project_io import HERE,digest,save_json
from media_faces import detect_face_crops
from prepare_openfake_subset import write_rows


def read(path):
    with path.open(encoding='utf-8-sig',newline='') as stream:return list(csv.DictReader(stream))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--openfake',type=Path,required=True)
    parser.add_argument('--fairface',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'raw_faces').mkdir(exist_ok=True)
    rows=[r for r in read(args.openfake) if r['split']=='external_test']+read(args.fairface)
    if any(r['split']!='external_test' for r in rows):raise ValueError('Unexpected development rows')
    if len({r['sample_id'] for r in rows})!=len(rows):raise ValueError('Duplicate exam IDs')
    cv2.setNumThreads(1)
    detector=cv2.FaceDetectorYN.create(str(HERE/'weights/face_detection_yunet_2023mar.onnx'),'',(320,320),.8,.3,5000)
    for row in rows:
        if row['label']=='0' and not row.get('face256_path'):
            with Image.open(row['raw_path']) as source:image=ImageOps.exif_transpose(source).convert('RGB')
            faces,_=detect_face_crops(cv2.cvtColor(np.asarray(image),cv2.COLOR_RGB2BGR),detector,max_faces=1)
            if not faces:raise ValueError('Previously accepted exam face is no longer detected')
            path=args.output/'raw_faces'/(row['sample_id']+'.png');faces[0]['image'].save(path)
            row['face256_path']=str(path.resolve())
    write_rows(args.output/'manifest.csv',rows)
    save_json(args.output/'PROTOCOL.json',dict(openfake_manifest_sha256=digest(args.openfake),fairface_manifest_sha256=digest(args.fairface),
        images=len(rows),by_source=dict(Counter(r['source'] for r in rows)),
        rule='All rows external_test only; no fitting or threshold selection on this manifest; locked candidate selection must precede inference',
        labels='Publisher whole-image generation labels, largest-face assumption. Real-face mirror is new source but global identity separation not proven.'))
    print(f'Locked exam prepared: {len(rows)} faces, no model inference.',flush=True)


if __name__=='__main__':main()
