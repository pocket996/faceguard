"""Compare photo candidates, validation-only recalibration, and controlled-map diagnostics."""
from project_io import resolve_data_path, data_location
import argparse
import csv
from pathlib import Path

import numpy as np
from PIL import Image
from sklearn.metrics import roc_auc_score
import torch
from torch.utils.data import Dataset,DataLoader

from core import HERE,image_transform,load_detector
from project_io import digest,save_json
from generation_common import canonical_face
from local_edit_supervision import LocalEditImages,LocalEditNetwork
from train import metrics,select_threshold,write_csv
from train_generation import balanced_source_weights


class PhotoImages(Dataset):
    def __init__(self,rows,canonical):self.rows,self.canonical,self.transform=rows,canonical,image_transform()
    def __len__(self):return len(self.rows)
    def __getitem__(self,index):
        row=self.rows[index]
        with Image.open(resolve_data_path(HERE/(row.get('face256_path') or row['path']))) as source:image=source.convert('RGB')
        if self.canonical:image=canonical_face(image)
        return self.transform(image)


@torch.inference_mode()
def probe_masks(state,rows,device):
    originals=[r for r in rows if r['label']=='0' and not r['source'].startswith('FF++')][:64]
    paired=originals+[dict(r,label='1',synthetic=True) for r in originals]
    if not originals:return dict(status='no ordinary-photo validation examples')
    network=LocalEditNetwork().to(device).eval()
    network.encoder.load_state_dict(state['backbone']);network.head.load_state_dict(state['head']);network.mask_decoder.load_state_dict(state['mask_decoder'])
    predictions=[];targets=[];scores=[]
    for images,_,masks,_ in DataLoader(LocalEditImages(paired),batch_size=16,num_workers=0):
        logits,maps=network(images.to(device));scores.extend(logits.sigmoid().cpu().tolist())
        predictions.extend(maps.sigmoid().cpu().numpy());targets.extend(masks.numpy())
    predictions=np.array(predictions)[:,0];targets=np.array(targets)[:,0];n=len(originals)
    binary=predictions[n:]>=.5;truth=targets[n:]>=.3
    def iou(a,b):return np.sum(a&b,axis=(1,2))/np.maximum(1,np.sum(a|b,axis=(1,2)))
    return dict(pairs=n,pixel_auc=float(roc_auc_score((targets>=.3).ravel(),predictions.ravel())),
        exercise_classification_auc=float(roc_auc_score([0]*n+[1]*n,scores)),
        synthetic_proxy_iou=float(iou(binary,truth).mean()),
        wrong_pair_proxy_iou=float(iou(binary,np.roll(truth,1,axis=0)).mean()),
        unmodified_photo_flagged_pixel_fraction=float((predictions[:n]>=.5).mean()),
        warning='Known synthetic exercise only. Map is a controlled-blending proxy, not proven true localization or explanation on genuine deepfakes.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint',type=resolve_data_path,required=True)
    parser.add_argument('--manifest',type=resolve_data_path,required=True)
    parser.add_argument('--split',choices=['val','test','external_test'],default='val')
    parser.add_argument('--output',type=resolve_data_path,required=True)
    parser.add_argument('--calibrate',action='store_true',help='Only for validation; make a new threshold-only checkpoint')
    parser.add_argument('--probe-masks',action='store_true')
    parser.add_argument('--device',default='cuda')
    args=parser.parse_args();torch.set_num_threads(2)
    if args.calibrate and args.split!='val':raise ValueError('Calibration must use validation only')
    with args.manifest.open(encoding='utf-8-sig',newline='') as stream:rows=[r for r in csv.DictReader(stream) if r['split']==args.split]
    if args.split=='external_test':rows=[r for r in rows if r['label']=='0'] # Whole-generation labels are NOT manipulation truth.
    if not rows:raise ValueError('No samples')
    args.output.mkdir(parents=True,exist_ok=True)
    encoder,head,state=load_detector(args.checkpoint,args.device)
    canonical=state.get('preprocessing')=='photo128_jpeg90'
    values=[]
    with torch.inference_mode():
        for images in DataLoader(PhotoImages(rows,canonical),batch_size=32,num_workers=0):
            values.extend(head(encoder(images.to(args.device))).sigmoid().flatten().cpu().tolist())
    values=np.array(values);labels=np.array([int(r['label']) for r in rows]);weights=balanced_source_weights(rows)
    threshold=state['frame_threshold']
    if args.calibrate:
        boundary=select_threshold(labels,values,sample_weight=weights);below,above=values[values<boundary],values[values>=boundary]
        threshold=float((below.max()+above.min())/2) if len(below) and len(above) else boundary
        state['frame_threshold']=state['video_threshold']=threshold
        state['task']='photo_manipulation_calibrated'
        state['preprocessing']='manipulation256'
        state['calibration_manifest_sha256']=digest(args.manifest)
        state['mask_scope']='No regional supervision: unchanged original classifier, validation-only photo threshold'
        state['threshold_strategy']='Source/group-balanced photo validation midpoint'
        torch.save(state,args.output/'model.pt')
    report=metrics(labels,values,threshold) if len(set(labels))==2 else dict(n=len(rows),threshold=threshold)
    if len(set(labels))==2:
        report['source_group_balanced_auc']=float(roc_auc_score(labels,values,sample_weight=weights))
        report['source_group_balanced_accuracy']=float(np.average((values>=threshold)==labels,weights=weights))
    report['per_source']={}
    for source in sorted({r['source'] for r in rows}):
        ix=np.array([i for i,r in enumerate(rows) if r['source']==source]);yy=labels[ix];pp=values[ix]
        parent={}
        for i in ix:
            key=rows[i].get('parent_image') or rows[i]['sample_id']
            parent[key]=max(parent.get(key,0),float(values[i]))
        report['per_source'][source]=dict(n=len(ix),real_images=int((yy==0).sum()),false_positives=int(((pp>=threshold)&(yy==0)).sum()),
            fake_images=int((yy==1).sum()),false_negatives=int(((pp<threshold)&(yy==1)).sum()),
            parent_images=len(parent),parent_images_with_alerts=sum(p>=threshold for p in parent.values()))
    report.update(split=args.split,checkpoint_sha256=digest(args.checkpoint),manifest_sha256=digest(args.manifest),
                  preprocessing='canonical128 JPEG90' if canonical else 'direct256 crop',
                  note='Publisher-real photo negatives and FF++ video-frame positives; no claim of broad actual forged-photo coverage or calibrated multi-face image verdict.')
    if args.probe_masks and 'mask_decoder' in state:
        del encoder,head
        if args.device=='cuda':torch.cuda.empty_cache()
        report['controlled_mask_probe']=probe_masks(state,rows,args.device)
    write_csv(args.output/'predictions.csv',[dict(sample_id=r['sample_id'],source=r['source'],method=r['method'],group=r['group'],label=r['label'],score=float(p)) for r,p in zip(rows,values)])
    save_json(args.output/'metrics.json',report)
    print(report,flush=True)


if __name__=='__main__':main()
