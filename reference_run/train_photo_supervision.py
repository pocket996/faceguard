"""Photo-specific manipulation candidate with controlled local-edit proxy supervision."""
from project_io import resolve_data_path, data_location
import argparse
from collections import Counter,defaultdict
import csv
import hashlib
from pathlib import Path
import random
import time

import cv2
import numpy as np
from sklearn.metrics import roc_auc_score
import torch
from torch import nn
from torch.utils.data import DataLoader,WeightedRandomSampler

from core import HERE,PROJECT,digest,save_json
from local_edit_supervision import LocalEditImages,LocalEditNetwork
from prepare_openfake_subset import write_rows
from train import metrics,select_threshold,write_csv
from train_generation import balanced_source_weights


@torch.inference_mode()
def score(network,rows,args):
    network.eval();values=[]
    for images,_,_,_ in DataLoader(LocalEditImages(rows),batch_size=args.batch_size,num_workers=args.workers):
        logits,_=network(images.to(args.device))
        values.extend(logits.sigmoid().cpu().tolist())
    return np.asarray(values)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--photos',type=resolve_data_path,required=True)
    parser.add_argument('--output',type=resolve_data_path,required=True)
    parser.add_argument('--epochs',type=int,default=4)
    parser.add_argument('--batch-size',type=int,default=48)
    parser.add_argument('--device',default='cuda')
    parser.add_argument('--mask-weight',type=float,default=.2)
    parser.add_argument('--workers',type=int,default=0,help='Default single process protects RAM on 16GB laptops')
    args=parser.parse_args()
    start=time.monotonic();torch.set_num_threads(2);cv2.setNumThreads(1)
    random.seed(9026);np.random.seed(9026);torch.manual_seed(9026)
    args.output.mkdir(parents=True,exist_ok=True)
    with args.photos.open(encoding='utf-8-sig',newline='') as stream:
        photos=list(csv.DictReader(stream))
    ffpp_path=resolve_data_path(PROJECT/'data/manifests/ffpp-frames-full-93e2b370610e.csv')
    with ffpp_path.open(encoding='utf-8-sig',newline='') as stream:
        ffpp=list(csv.DictReader(stream))
    by_video=defaultdict(list)
    for row in ffpp:
        by_video[row['parent_video_id']].append(row)
    common=[]
    for video,group in by_video.items():
        group.sort(key=lambda r:int(r['frame_index']))
        # Four train frames/video; two validation/test frames, fixed before inspecting results.
        amount=4 if group[0]['split']=='train' else 2
        indices=np.linspace(0,len(group)-1,min(amount,len(group)),dtype=int)
        for i in indices:
            row=group[i]
            common.append(dict(sample_id=row['sample_id'],path=str((resolve_data_path(PROJECT/row['path'])).resolve()),
                label=row['label'],split=row['split'],group=row['group_id'],source='FF++:'+row['method'],method=row['method'],
                parent_image=row['sample_id']))
    common+=photos
    train=[r.copy() for r in common if r['split']=='train']
    validation=[r for r in common if r['split']=='val']
    # No synthetic exercise goes into the real-forgery validation metric.
    for row in list(train):
        if row['label']=='0':
            synthetic=dict(row,sample_id=row['sample_id']+'_controlled_edit',synthetic=True,label='1',
                           method='controlled_self_blend',source='controlled:'+row['source'])
            train.append(synthetic)
    groups=defaultdict(set)
    for row in common:
        groups[row['group']].add(row['split'])
    if any(len(s)>1 for s in groups.values()):
        raise ValueError('Original identity/source group crosses splits')
    write_rows(args.output/'manifest.csv',common)
    save_json(args.output/'PROTOCOL.json',dict(photos_manifest_sha256=digest(args.photos),ffpp_manifest_sha256=digest(ffpp_path),
        train_counts=dict(Counter(r['source'] for r in train)),validation_counts=dict(Counter(r['source'] for r in validation)),
        mask_weight=args.mask_weight,epochs=args.epochs,
        initialization='Existing FF++ model, no test training; ImageNet-pretrained ResNet18 backbone',
        supervision='Classification + known controlled blending proxy maps + zero maps on publisher-real photos. FF++ fake masks are UNKNOWN and excluded from map loss.',
        references=['https://arxiv.org/abs/2204.08376','https://arxiv.org/abs/1912.13458'],
        warning='Simplified original experiment inspired by paper concepts, NOT official SBI/Face X-Ray reproduction. Proxy maps are not ground truth for real deepfakes; no whole-face generation claim.'))
    network=LocalEditNetwork().to(args.device)
    initial=torch.load(resolve_data_path(HERE/'artifacts/model_finetuned.pt'),map_location='cpu',weights_only=True)
    network.encoder.load_state_dict(initial['backbone']);network.head.load_state_dict(initial['head'])
    optimizer=torch.optim.AdamW([dict(params=network.encoder.parameters(),lr=1e-5),dict(params=network.head.parameters(),lr=1e-4),
                                 dict(params=network.mask_decoder.parameters(),lr=3e-4)],weight_decay=1e-4)
    scaler=torch.amp.GradScaler('cuda',enabled=args.device=='cuda')
    sampler_weights=balanced_source_weights(train);val_weights=balanced_source_weights(validation)
    history=[];best=-1
    for epoch in range(args.epochs):
        sampler=WeightedRandomSampler(sampler_weights,len(train),replacement=True,generator=torch.Generator().manual_seed(9026+epoch))
        loader=DataLoader(LocalEditImages(train,augment=True),batch_size=args.batch_size,sampler=sampler,num_workers=args.workers,
                          generator=torch.Generator().manual_seed(9026+epoch))
        network.train();loss_sum=0;count=0;map_sum=0
        for step,(images,labels,masks,known) in enumerate(loader):
            images,labels,masks,known=[x.to(args.device) for x in (images,labels.float(),masks,known.float())]
            optimizer.zero_grad(set_to_none=True)
            with torch.amp.autocast(device_type=args.device,enabled=args.device=='cuda'):
                logits,predicted_masks=network(images)
                classification=nn.functional.binary_cross_entropy_with_logits(logits,labels)
                pixel_loss=nn.functional.binary_cross_entropy_with_logits(predicted_masks,masks,reduction='none',
                                                                          pos_weight=torch.tensor(4.,device=args.device)).mean((1,2,3))
                map_loss=(pixel_loss*known).sum()/known.sum().clamp_min(1)
                loss=classification+args.mask_weight*map_loss
            scaler.scale(loss).backward();scaler.unscale_(optimizer);nn.utils.clip_grad_norm_(network.parameters(),5)
            scaler.step(optimizer);scaler.update()
            count+=len(labels);loss_sum+=float(loss.detach())*len(labels);map_sum+=float(map_loss.detach())*len(labels)
            if step%100==0:
                print(dict(epoch=epoch+1,done=count,total=len(train),seconds=time.monotonic()-start),flush=True)
        values=score(network,validation,args);labels=np.array([int(r['label']) for r in validation])
        auc=float(roc_auc_score(labels,values,sample_weight=val_weights))
        item=dict(epoch=epoch+1,weighted_validation_auc=auc,train_loss=loss_sum/count,map_loss=map_sum/count,seconds=time.monotonic()-start)
        history.append(item);save_json(args.output/'history.json',history);print(item,flush=True)
        if auc>best:
            best=auc;boundary=select_threshold(labels,values,sample_weight=val_weights)
            below,above=values[values<boundary],values[values>=boundary]
            threshold=float((below.max()+above.min())/2) if len(below) and len(above) else boundary
            state=dict(backbone={k:v.detach().cpu().clone() for k,v in network.encoder.state_dict().items()},
                head={k:v.detach().cpu().clone() for k,v in network.head.state_dict().items()},
                mask_decoder={k:v.detach().cpu().clone() for k,v in network.mask_decoder.state_dict().items()},
                task='photo_manipulation_research',preprocessing='photo128_jpeg90',frame_threshold=threshold,video_threshold=threshold,
                yunet_sha256=digest(resolve_data_path(HERE/'weights/face_detection_yunet_2023mar.onnx')),selected_epoch=epoch+1,
                manifest_sha256=digest(args.output/'manifest.csv'),threshold_strategy='Source-balanced validation midpoint',
                mask_weight=args.mask_weight,mask_scope='Controlled blending proxy only; not proof or true segmentation of real forgeries')
            torch.save(state,args.output/'model.pt')
            write_csv(args.output/'val_predictions.csv',[dict(sample_id=r['sample_id'],label=r['label'],source=r['source'],group=r['group'],score=float(p)) for r,p in zip(validation,values)])
            save_json(args.output/'val_metrics.json',metrics(labels,values,threshold))
    save_json(args.output/'completion.json',dict(history=history,seconds=time.monotonic()-start,test_accessed=False,
        model_sha256=digest(args.output/'model.pt'),selected_by='Source/group balanced real-forgery + ordinary-photo validation AUC; no synthetic examples in selection metric'))


if __name__=='__main__':
    main()
