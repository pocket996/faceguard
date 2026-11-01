"""Isolated raw-photo crops for ordinary-photo false-alert and local-edit supervision experiments."""
from project_io import resolve_data_path, data_location
import argparse
from collections import Counter
import csv
import hashlib
from pathlib import Path

import cv2
import numpy as np
from PIL import Image,ImageOps

from project_io import HERE,digest,save_json
from media_faces import detect_face_crops
from prepare_openfake_subset import write_rows


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=resolve_data_path,required=True)
    parser.add_argument('--output',type=resolve_data_path,required=True)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'crops').mkdir(exist_ok=True)
    cv2.setNumThreads(1)
    detector=cv2.FaceDetectorYN.create(str(resolve_data_path(HERE/'weights/face_detection_yunet_2023mar.onnx')),'',(320,320),.8,.3,5000)
    with args.manifest.open(encoding='utf-8-sig',newline='') as stream:
        original=[r for r in csv.DictReader(stream) if r['label']=='0']
    selected=[]
    for split,count in [('train',600),('val',150),('test',150)]:
        for source in ('LFW','FFHQ-256-mirror'):
            group=[r for r in original if r['split']==split and r['source']==source]
            group.sort(key=lambda r:hashlib.sha256(('photo-supervision-v1:'+r['sample_id']).encode()).hexdigest())
            selected.extend(group[:count])
    rows,rejected=[],[]
    for index,row in enumerate(selected):
        with Image.open(resolve_data_path(row['raw_path'])) as source:
            image=ImageOps.exif_transpose(source).convert('RGB')
        faces,total=detect_face_crops(cv2.cvtColor(np.asarray(image),cv2.COLOR_RGB2BGR),detector,max_faces=4)
        if not faces:
            rejected.append(row['sample_id'])
        for face in faces:
            identity=row['sample_id']+'_face'+str(face['face_id'])
            path=args.output/'crops'/(identity+'.png')
            # PNG retains the 256px crop; codec augmentation is then shared by both classes.
            face['image'].save(path)
            rows.append(dict(sample_id=identity,path=str(path.resolve()),group=row['group'],split=row['split'],
                label='0',source=row['source'],method='real',parent_image=row['sample_id'],
                pixel_sha256=hashlib.sha256(face['image'].tobytes()).hexdigest(),detected_faces=total))
        if (index+1)%100==0:
            print(f'Prepared {index+1}/{len(selected)} photos, {len(rows)} crops',flush=True)
    write_rows(args.output/'manifest.csv',rows)
    save_json(args.output/'protocol.json',dict(original_manifest_sha256=digest(args.manifest),
        selected_images=len(selected),crops=len(rows),rejected_images=rejected,
        counts=dict(Counter(r['split']+'|'+r['source'] for r in rows)),
        selection='Fixed hash, per source 600 train / 150 val / 150 test images; up to 4 faces per image, identity/source groups retained',
        role='Research-only real-photo negatives and controlled self-blending inputs. Test subset is a regression subset, not a fresh final benchmark.'))


if __name__=='__main__':
    main()
