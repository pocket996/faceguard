"""Score frozen update splits at locked checkpoint thresholds; never recalibrate on test."""
import argparse
from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'reference_run'))
from faceguard.data_locations import data_location,resolve_data_path
from faceguard.model_registry import checked_resource,digest
from core import load_detector
from train import metrics,write_csv
from train_generation import GenerationImages,balanced_source_weights,validate_generation_initialization
from prepare_generation_update import save_json


def summarize_scores(rows,scores,threshold):
    import numpy as np
    from sklearn.metrics import roc_auc_score
    p=np.asarray(scores);y=np.asarray([int(r['label']) for r in rows])
    if p.ndim!=1 or len(p)!=len(rows) or not np.isfinite(p).all() or ((p<0)|(p>1)).any():
        raise ValueError('Invalid stored prediction scores')
    report=metrics(y,p,threshold)
    weights=balanced_source_weights(rows)
    report['source_group_balanced_auc']=float(roc_auc_score(y,p,sample_weight=weights))
    report['source_group_balanced_accuracy']=float(np.average((p>=threshold)==y,weights=weights))
    report['by_source_method_label']={}
    for key in sorted({r['source']+'|'+r['method']+'|'+r['label'] for r in rows}):
        indices=[i for i,r in enumerate(rows) if r['source']+'|'+r['method']+'|'+r['label']==key]
        label=int(rows[indices[0]]['label'])
        report['by_source_method_label'][key]=dict(n=len(indices),errors=int(np.sum((p[indices]>=threshold)!=label)),
                                                  error_rate=float(np.mean((p[indices]>=threshold)!=label)))
    for source in sorted({r['source'] for r in rows}):
        indices=[i for i,r in enumerate(rows) if r['source']==source]
        if len(set(y[indices]))==2:report.setdefault('by_dataset',{})[source]=metrics(y[indices],p[indices],threshold)
    return report


def evaluate(checkpoint,rows,output,device,batch_size):
    import torch
    from torch.utils.data import DataLoader
    model,head,state=load_detector(checkpoint,device)
    validate_generation_initialization(state)
    loader=DataLoader(GenerationImages(rows),batch_size=batch_size,num_workers=0,pin_memory=device=='cuda')
    scores=[];start=time.monotonic()
    with torch.inference_mode():
        for step,(images,_,_) in enumerate(loader):
            scores.extend(head(model(images.to(device))).sigmoid().flatten().cpu().tolist())
            if step%100==0:print(json.dumps(dict(stage='evaluate',done=len(scores),total=len(rows),checkpoint=Path(checkpoint).name)),flush=True)
    threshold=float(state['frame_threshold'])
    report=dict(summarize_scores(rows,scores,threshold),checkpoint_sha256=digest(checkpoint),seconds=time.monotonic()-start)
    output.mkdir(parents=True,exist_ok=True)
    write_csv(output/'predictions.csv',[dict(sample_id=r['sample_id'],path=r['path'],source=r['source'],method=r['method'],
                                           group=r['group'],label=int(r['label']),score=float(value),prediction=int(value>=threshold)) for r,value in zip(rows,scores)])
    save_json(output/'metrics.json',report)
    del model,head,loader
    if device=='cuda':torch.cuda.empty_cache()
    return report


def gan_development_rows():
    import cv2
    import numpy as np
    from PIL import Image,ImageOps
    from faceguard.inference.media_faces import detect_face_crops
    from faceguard.inference.generation_common import encode_canonical
    baseline=data_location('new_data_evaluation')/'development-baseline'
    lock=json.loads((baseline/'selection-lock.json').read_text(encoding='utf-8'))
    if digest(baseline/'selection.csv')!=lock['selection_sha256']:raise ValueError('Original development selection changed')
    with (baseline/'selection.csv').open(encoding='utf-8',newline='') as file:original=[r for r in csv.DictReader(file) if r['source']=='GAN140k']
    output=data_location('dff_update_faces').parent/'gan-development-20261031'
    output.mkdir(exist_ok=True)
    detector=cv2.FaceDetectorYN.create(str(checked_resource('yunet.onnx')),'',(320,320),.8,.3,5000)
    rows=[];rejected=[]
    for row in original:
        path=output/(hashlib.sha256(row['sample_id'].encode()).hexdigest()[:24]+'.jpg')
        try:
            with Image.open(resolve_data_path(row['path'])) as image:
                image=ImageOps.exif_transpose(image).convert('RGB')
                faces,total=detect_face_crops(cv2.cvtColor(np.asarray(image),cv2.COLOR_RGB2BGR),detector,max_faces=1)
            if not faces:
                rejected.append(dict(sample_id=row['sample_id'],reason='no_face'));continue
            payload=encode_canonical(faces[0]['image']);path.write_bytes(payload)
            with Image.open(io.BytesIO(payload)) as decoded:pixel=hashlib.sha256(decoded.convert('RGB').tobytes()).hexdigest()
            rows.append(dict(row,path=str(path),split='external_dev',pixel_sha256=pixel,detected_faces=total))
        except Exception as error:rejected.append(dict(sample_id=row['sample_id'],reason=str(error)))
    save_json(data_location('dff_update_provenance')/'gan-development-coverage.json',dict(attempted=len(original),accepted=len(rows),rejected=rejected,
        note='Previously observed fixed development images only; no training or threshold calibration'))
    return rows


def main():
    import cv2
    import torch
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint',type=Path,default=checked_resource('generation.pt'))
    parser.add_argument('--split',choices=['val','test','external_test','gan_dev'],required=True)
    parser.add_argument('--manifest-directory',type=Path,default=data_location('generation_update_manifests'))
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--device',default='cuda')
    parser.add_argument('--batch-size',type=int,default=64)
    args=parser.parse_args();torch.set_num_threads(2);cv2.setNumThreads(1)
    folder=args.manifest_directory;manifest=folder/'manifest.csv'
    protocol=json.loads((folder/'protocol.json').read_text(encoding='utf-8'))
    if digest(manifest)!=protocol['manifest_sha256']:raise ValueError('Frozen manifest changed')
    with manifest.open(encoding='utf-8',newline='') as file:all_rows=list(csv.DictReader(file))
    rows=gan_development_rows() if args.split=='gan_dev' else [r for r in all_rows if r['split']==args.split]
    if args.output.exists() and (args.output/'metrics.json').exists():raise FileExistsError('Evaluation result already exists')
    if args.split in ('test','external_test'):
        # The command is deliberately separate from training. Record the model
        # hash and locked threshold before touching any test pixels.
        state=torch.load(args.checkpoint,map_location='cpu',weights_only=True)
        save_json(args.output/'test-open-lock.json',dict(checkpoint_sha256=digest(args.checkpoint),
            manifest_sha256=digest(manifest),threshold=state['frame_threshold'],threshold_selection='Validation only; test does not change it'))
    report=evaluate(args.checkpoint,rows,args.output,args.device,args.batch_size)
    report.update(split=args.split,manifest_sha256=digest(manifest),threshold_recalibrated=False,
                  note='Grouped within-source holdout; legacy sources are historical regression. No claim of universal or never-observed independent accuracy.')
    save_json(args.output/'metrics.json',report)
    print(json.dumps(report,ensure_ascii=True,indent=2))


if __name__=='__main__':main()
