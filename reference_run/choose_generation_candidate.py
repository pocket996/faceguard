"""Freeze generation candidate ranking using the same development validation rows only."""
import argparse
import csv
import json
from pathlib import Path

import numpy as np
from sklearn.metrics import roc_auc_score
import torch

from project_io import digest,save_json
from train_generation import balanced_source_weights


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--candidates',type=Path,required=True,help='JSON array of name/checkpoint/predictions')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    with args.manifest.open(encoding='utf-8-sig',newline='') as stream:validation=[r for r in csv.DictReader(stream) if r['split']=='val']
    validation.sort(key=lambda r:r['sample_id']);ids={r['sample_id'] for r in validation}
    y=np.array([int(r['label']) for r in validation]);weights=balanced_source_weights(validation)
    results=[]
    for candidate in json.loads(args.candidates.read_text(encoding='utf-8-sig')):
        with Path(candidate['predictions']).open(encoding='utf-8-sig',newline='') as stream:predictions=list(csv.DictReader(stream))
        mapping={r['sample_id']:r for r in predictions}
        if set(mapping)!=ids or len(predictions)!=len(ids):raise ValueError('Candidate validation population differs')
        state=torch.load(candidate['checkpoint'],map_location='cpu',weights_only=True)
        p=np.array([float(mapping[r['sample_id']]['score']) for r in validation]);threshold=state['frame_threshold']
        item=dict(candidate,source_group_balanced_auc=float(roc_auc_score(y,p,sample_weight=weights)),
            source_group_balanced_accuracy=float(np.average((p>=threshold)==y,weights=weights)),
            checkpoint_sha256=digest(candidate['checkpoint']),threshold=threshold,per_source={})
        for source in sorted({r['source'] for r in validation}):
            ix=np.array([i for i,r in enumerate(validation) if r['source']==source]);yy=y[ix];pp=p[ix]
            item['per_source'][source]=dict(n=len(ix),false_positives=int(((pp>=threshold)&(yy==0)).sum()),
                                         false_negatives=int(((pp<threshold)&(yy==1)).sum()))
        results.append(item)
        del state
    results.sort(key=lambda r:(-r['source_group_balanced_auc'],-r['source_group_balanced_accuracy'],r['name']))
    save_json(args.output,dict(selection='Validation-only source/group balanced AUC, then balanced accuracy; candidates and thresholds frozen before external inference',
        manifest_sha256=digest(args.manifest),candidates=results,selected=results[0],external_exam_used=False,
        limitation='Small GPT1 validation sample can overfit selection; external results must not be used to re-rank and still called fresh.'))
    print('Locked generation candidate:',results[0]['name'],results[0]['source_group_balanced_auc'],flush=True)


if __name__=='__main__':main()
