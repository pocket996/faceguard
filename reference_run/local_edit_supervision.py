"""Controlled self-blending exercises with known proxy maps; not a reproduction of SBI/Face X-Ray."""
import io
import random

import cv2
import numpy as np
from PIL import Image
import torch
from torch import nn
from torch.utils.data import Dataset

from core import HERE,backbone,image_transform
from generation_common import canonical_face


def self_blend(image, rng):
    base=cv2.resize(np.asarray(image.convert('RGB')),(128,128),interpolation=cv2.INTER_AREA).astype(np.float32)
    warp=cv2.getRotationMatrix2D((64,64),rng.uniform(-5,5),rng.uniform(.96,1.04))
    warp[:,2]+=rng.uniform(-4,4,size=2)
    source=cv2.warpAffine(base,warp,(128,128),borderMode=cv2.BORDER_REFLECT_101)
    source=np.clip(source*rng.uniform(.85,1.15,size=(1,1,3))+rng.uniform(-12,12,size=(1,1,3)),0,255)
    size=int(rng.integers(72,121))
    source=cv2.resize(cv2.resize(source,(size,size)),(128,128))
    center=rng.uniform(42,86,size=2)
    angles=np.sort(rng.uniform(0,2*np.pi,size=9))
    radius=rng.uniform(24,52,size=(9,1))
    points=np.concatenate([np.cos(angles)[:,None],np.sin(angles)[:,None]],axis=1)*radius+center
    mask=np.zeros((128,128),np.float32)
    cv2.fillConvexPoly(mask,cv2.convexHull(points.astype(np.int32)),1.)
    alpha=cv2.GaussianBlur(mask,(0,0),float(rng.uniform(2,5)))
    image=Image.fromarray(np.clip(base*(1-alpha[...,None])+source*alpha[...,None],0,255).astype(np.uint8))
    # This target is known by construction. It is NOT a ground-truth mask for a real deepfake.
    return image,(4*alpha*(1-alpha)).astype(np.float32)


class LocalEditImages(Dataset):
    def __init__(self,rows,augment=False):
        self.rows,self.augment,self.transform=rows,augment,image_transform()

    def __len__(self):
        return len(self.rows)

    def __getitem__(self,index):
        row=self.rows[index]
        with Image.open(HERE/row['path']) as source:
            image=source.convert('RGB')
        synthetic=bool(row.get('synthetic',False))
        if synthetic:
            seed=random.randrange(2**32) if self.augment else 91000+index
            image,mask=self_blend(image,np.random.default_rng(seed))
        else:
            mask=np.zeros((128,128),np.float32)
            image=Image.fromarray(cv2.resize(np.asarray(image),(128,128),interpolation=cv2.INTER_AREA))
        if self.augment and random.random()<.5:
            image=image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            mask=mask[:,::-1].copy()
        if self.augment:
            size=random.choice((80,96,112,128))
            image=image.resize((size,size),Image.Resampling.BILINEAR).resize((128,128),Image.Resampling.BILINEAR)
            buffer=io.BytesIO();image.save(buffer,format='JPEG',quality=random.randint(55,98),subsampling=0);buffer.seek(0)
            with Image.open(buffer) as decoded:
                image=decoded.convert('RGB')
        else:
            image=canonical_face(image)
        mask=cv2.resize(mask,(14,14),interpolation=cv2.INTER_AREA)
        known=synthetic or int(row['label'])==0
        return self.transform(image),float(row['label']),torch.from_numpy(mask[None]),float(known)


class LocalEditNetwork(nn.Module):
    def __init__(self):
        super().__init__()
        self.encoder=backbone()
        self.head=nn.Linear(512,1)
        self.mask_decoder=nn.Sequential(nn.Conv2d(256,64,3,padding=1),nn.ReLU(),nn.Conv2d(64,1,1))

    def forward(self,x):
        e=self.encoder
        x=e.maxpool(e.relu(e.bn1(e.conv1(x))))
        x=e.layer1(x);x=e.layer2(x);features=e.layer3(x)
        mask=self.mask_decoder(features)
        x=e.layer4(features)
        return self.head(torch.flatten(e.avgpool(x),1)).flatten(),mask
