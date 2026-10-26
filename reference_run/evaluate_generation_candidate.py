"""Fixed-checkpoint generation evaluation; calibration reads validation predictions only."""
import argparse
from collections import Counter
import csv
import io
import json
from pathlib import Path
import time

import cv2
import numpy as np
from PIL import Image, ImageFilter
import torch
from torch.utils.data import DataLoader, Dataset
from sklearn.metrics import roc_auc_score

from core import HERE, digest, image_transform, load_detector, save_json
from train import metrics, select_threshold, write_csv
from train_generation import balanced_source_weights


class StressImages(Dataset):
    def __init__(self, rows, stress):
        self.rows, self.stress, self.transform = rows, stress, image_transform()

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index):
        with Image.open(HERE / self.rows[index]['path']) as source:
            image = source.convert('RGB')
        if self.stress in ('jpeg40', 'jpeg60'):
            buffer = io.BytesIO()
            image.save(buffer, format='JPEG', quality=int(self.stress[4:]))
            buffer.seek(0)
            with Image.open(buffer) as decoded:
                image = decoded.convert('RGB')
        elif self.stress == 'resize64':
            image = image.resize((64,64),Image.Resampling.BILINEAR)
        elif self.stress == 'blur1':
            image = image.filter(ImageFilter.GaussianBlur(1))
        return self.transform(image)


@torch.inference_mode()
def predict(encoder, head, rows, args, stress):
    values=[]
    loader=DataLoader(StressImages(rows,stress),batch_size=args.batch_size,num_workers=args.workers,pin_memory=args.device=='cuda')
    for images in loader:
        values.extend(head(encoder(images.to(args.device))).sigmoid().flatten().cpu().tolist())
    return np.asarray(values)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint',type=Path,required=True)
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--split',choices=['val','test','external_test','train'],default='val')
    parser.add_argument('--stress',default='clean,jpeg60,jpeg40,resize64,blur1')
    parser.add_argument('--calibrate-from',type=Path,help='CSV of this checkpoint validation predictions only; save new candidate, never overwrite source')
    parser.add_argument('--device',default='cuda' if torch.cuda.is_available() else 'cpu')
    parser.add_argument('--workers',type=int,default=2)
    parser.add_argument('--batch-size',type=int,default=48)
    args=parser.parse_args()
    start=time.monotonic();torch.set_num_threads(2);cv2.setNumThreads(1)
    args.output.mkdir(parents=True,exist_ok=True)
    with args.manifest.open(encoding='utf-8-sig',newline='') as stream:
        all_rows=list(csv.DictReader(stream))
    if args.calibrate_from:
        state=torch.load(args.checkpoint,map_location='cpu',weights_only=True)
        with args.calibrate_from.open(encoding='utf-8-sig',newline='') as stream:
            validation=list(csv.DictReader(stream))
        by_id={r['sample_id']:r for r in all_rows}
        selected=[by_id[r['sample_id']] for r in validation]
        if any(r['split']!='val' for r in selected):
            raise ValueError('Calibration input includes non-validation rows')
        if state['manifest_sha256'] != digest(args.manifest):
            raise ValueError('Checkpoint manifest differs from calibration manifest')
        y=np.array([int(r['label']) for r in validation]);p=np.array([float(r['score']) for r in validation])
        weights=balanced_source_weights(selected) if state.get('source_balanced_selection') else None
        boundary=select_threshold(y,p,sample_weight=weights)
        below,above=p[p<boundary],p[p>=boundary]
        threshold=float((below.max()+above.min())/2) if len(below) and len(above) else boundary
        state['frame_threshold']=state['video_threshold']=threshold
        state['threshold_strategy']='Midpoint of optimal validation balanced-accuracy interval'
        target=args.output/'model_calibrated.pt'
        torch.save(state,target)
        save_json(args.output/'calibration.json',dict(source_checkpoint_sha256=digest(args.checkpoint),
            validation_predictions_sha256=digest(args.calibrate_from), threshold=threshold,boundary=boundary,
            split='validation only', checkpoint=str(target.resolve())))
        args.checkpoint=target
    rows=[r for r in all_rows if r['split']==args.split]
    if not rows:
        raise ValueError('No samples in requested split')
    encoder,head,state=load_detector(args.checkpoint,args.device)
    threshold=state['frame_threshold']
    summary=dict(checkpoint_sha256=digest(args.checkpoint),manifest_sha256=digest(args.manifest),
        split=args.split,n=len(rows),threshold=threshold,results={},
        note='Convenience research subsets and crop-level perturbations, not proof of all-generator or deployment performance')
    for stress in args.stress.split(','):
        if stress not in ('clean','jpeg60','jpeg40','resize64','blur1'):
            raise ValueError('Unknown stress condition')
        values=predict(encoder,head,rows,args,stress)
        y=np.array([int(r['label']) for r in rows])
        report=metrics(y,values,threshold) if len(set(y))==2 else dict(n=len(rows))
        if len(set(y))==2:
            weights=balanced_source_weights(rows)
            report['source_group_balanced_auc']=float(roc_auc_score(y,values,sample_weight=weights))
            report['source_group_balanced_accuracy']=float(np.average((values>=threshold)==y,weights=weights))
        report['per_source']={}
        for source in sorted({r['source'] for r in rows}):
            indices=[i for i,r in enumerate(rows) if r['source']==source]
            yy,pp=y[indices],values[indices]
            negative=yy==0;positive=yy==1
            report['per_source'][source]=dict(n=len(indices),
                real_images=int(negative.sum()),false_positives=int(((pp>=threshold)&negative).sum()),
                fake_images=int(positive.sum()),false_negatives=int(((pp<threshold)&positive).sum()))
        summary['results'][stress]=report
        write_csv(args.output/(args.split+'_'+stress+'_predictions.csv'),[
            dict(sample_id=r['sample_id'],source=r['source'],method=r['method'],group=r['group'],label=int(r['label']),score=float(p),prediction=int(p>=threshold)) for r,p in zip(rows,values)])
        save_json(args.output/'metrics.json',summary)
        print(json.dumps(dict(stress=stress,n=len(rows),seconds=time.monotonic()-start,metrics=report)),flush=True)
    summary['seconds']=time.monotonic()-start
    save_json(args.output/'metrics.json',summary)


if __name__=='__main__':
    main()
