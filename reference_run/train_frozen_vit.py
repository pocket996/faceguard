"""Frozen official ImageNet ViT features + source-balanced linear head, validation-only selection."""
from project_io import resolve_data_path, data_location
import argparse
import csv
import json
from pathlib import Path
import random
import time

import cv2
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler
import torch
from torch import nn
from torch.utils.data import DataLoader
from torchvision import models

from core import HERE,digest,save_json
from train import metrics,select_threshold,write_csv
from train_generation import GenerationImages,audit,balanced_source_weights


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=resolve_data_path,required=True)
    parser.add_argument('--output',type=resolve_data_path,required=True)
    parser.add_argument('--device',default='cuda')
    parser.add_argument('--batch-size',type=int,default=24)
    args=parser.parse_args()
    start=time.monotonic();torch.set_num_threads(2);cv2.setNumThreads(1)
    random.seed(2026);np.random.seed(2026);torch.manual_seed(2026)
    args.output.mkdir(parents=True,exist_ok=True)
    with args.manifest.open(encoding='utf-8-sig',newline='') as stream:
        rows=list(csv.DictReader(stream))
    audit(rows,allow_sd35_training=True,allow_openfake=True)
    # External and old test rows are never encoded or used for selecting the head.
    selected=[r for r in rows if r['split'] in ('train','val')]
    torch.hub.set_dir(str(resolve_data_path(HERE/'weights/torch')))
    weights=models.ViT_B_16_Weights.IMAGENET1K_V1
    encoder=models.vit_b_16(weights=weights).to(args.device).eval()
    encoder.heads=nn.Identity()
    for parameter in encoder.parameters():parameter.requires_grad_(False)
    cached_weight=Path(torch.hub.get_dir())/'checkpoints'/Path(weights.url).name
    fingerprint=dict(manifest_sha256=digest(args.manifest),imagenet_sha256=digest(cached_weight),
                     row_ids=[r['sample_id'] for r in selected],preprocessing='Existing canonical128 JPEG90 crops -> resize224 -> ImageNet normalization')
    feature_file=args.output/'features.npy';cache_file=args.output/'feature_cache.json'
    if feature_file.is_file() and cache_file.is_file() and json.loads(cache_file.read_text())==fingerprint:
        features=np.load(feature_file)
    else:
        features=[]
        loader=DataLoader(GenerationImages(selected),batch_size=args.batch_size,num_workers=0)
        with torch.inference_mode():
            for step,(images,_,_) in enumerate(loader):
                features.append(encoder(images.to(args.device)).cpu().numpy())
                if step%75==0:
                    print(dict(stage='frozen_features',done=min((step+1)*args.batch_size,len(selected)),total=len(selected),seconds=time.monotonic()-start),flush=True)
        features=np.concatenate(features).astype(np.float32)
        np.save(feature_file,features);save_json(cache_file,fingerprint)
    train_mask=np.array([r['split']=='train' for r in selected]);val_mask=~train_mask
    train_rows=[r for r in selected if r['split']=='train'];val_rows=[r for r in selected if r['split']=='val']
    y_train=np.array([int(r['label']) for r in train_rows]);y_val=np.array([int(r['label']) for r in val_rows])
    train_weights=balanced_source_weights(train_rows)*len(train_rows);val_weights=balanced_source_weights(val_rows)
    scaler=StandardScaler().fit(features[train_mask],sample_weight=train_weights)
    train_x=scaler.transform(features[train_mask]);val_x=scaler.transform(features[val_mask])
    best_auc=-1.;history=[]
    for strength in (.01,.1,1.,10.):
        classifier=LogisticRegression(C=strength,max_iter=1000,solver='lbfgs',random_state=2026)
        classifier.fit(train_x,y_train,sample_weight=train_weights)
        values=classifier.predict_proba(val_x)[:,1]
        auc=float(roc_auc_score(y_val,values,sample_weight=val_weights))
        item=dict(C=strength,source_group_balanced_validation_auc=auc,iterations=classifier.n_iter_.tolist())
        history.append(item);print(item,flush=True)
        if auc>best_auc:
            best_auc=auc;boundary=select_threshold(y_val,values,sample_weight=val_weights)
            below,above=values[values<boundary],values[values>=boundary]
            threshold=float((below.max()+above.min())/2) if len(below) and len(above) else boundary
            head=nn.Linear(768,1)
            folded=classifier.coef_[0]/scaler.scale_
            with torch.no_grad():
                head.weight.copy_(torch.tensor(folded[None],dtype=torch.float32))
                head.bias.copy_(torch.tensor(classifier.intercept_-np.dot(folded,scaler.mean_),dtype=torch.float32))
                exported=head(torch.from_numpy(features[val_mask])).sigmoid().flatten().numpy()
            error=float(np.max(np.abs(exported-values)))
            if error>5e-5:raise ValueError('Linear preprocessing export does not match sklearn probabilities')
            state=dict(backbone={k:v.detach().cpu().clone() for k,v in encoder.state_dict().items()},head=head.state_dict(),
                architecture='vit_b_16',task='whole_face_generation',preprocessing='generation128_jpeg90',
                frame_threshold=threshold,video_threshold=threshold,
                yunet_sha256=digest(resolve_data_path(HERE/'weights/face_detection_yunet_2023mar.onnx')),manifest_sha256=digest(args.manifest),
                training_generators=sorted({r['method'] for r in train_rows if r['label']=='1'}),
                real_sources=sorted({r['source'] for r in train_rows if r['label']=='0'}),
                training_scope='Frozen ImageNet ViT + source-balanced linear head. Research-only GPT1 development; unseen generators never used for selection.',
                threshold_strategy='Source-balanced validation midpoint',C=strength,export_validation_max_abs_error=error,
                pretrained_weights_sha256=fingerprint['imagenet_sha256'])
            torch.save(state,args.output/'model.pt')
            write_csv(args.output/'val_predictions.csv',[dict(sample_id=r['sample_id'],path=r['path'],source=r['source'],method=r['method'],group=r['group'],label=r['label'],score=float(p)) for r,p in zip(val_rows,values)])
            save_json(args.output/'val_metrics.json',dict(metrics(y_val,values,threshold),source_group_balanced_auc=auc))
    save_json(args.output/'completion.json',dict(seconds=time.monotonic()-start,history=history,best_validation_auc=best_auc,
        checkpoint_sha256=digest(args.output/'model.pt'),test_or_external_encoded=False,
        pretrained_url=weights.url,pretrained_sha256=fingerprint['imagenet_sha256'],
        comparison='Different frozen representation, not more training images; no whole-face generation guarantee'))


if __name__=='__main__':main()
