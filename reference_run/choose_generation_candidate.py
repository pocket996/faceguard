"""Freeze generation candidate ranking using the same development validation rows only."""
from project_io import resolve_data_path, data_location
import argparse
import csv
import json
from pathlib import Path

import numpy as np
from sklearn.metrics import roc_auc_score
import torch

from project_io import digest,save_json
from train_generation import balanced_source_weights
from faceguard.generation_selection import select_operating_point, operating_rank


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=resolve_data_path,required=True)
    parser.add_argument('--candidates',type=resolve_data_path,required=True,help='JSON array of name/checkpoint/predictions')
    parser.add_argument('--output',type=resolve_data_path,required=True)
    parser.add_argument('--selection-metric',choices=['validation_auc','low_fpr_gpt_recall'],default='validation_auc')
    parser.add_argument('--max-val-fpr',type=float,default=.02)
    parser.add_argument('--focus-method',action='append',default=[])
    args=parser.parse_args()
    low_fpr = args.selection_metric == 'low_fpr_gpt_recall'
    if low_fpr and args.output.exists():
        raise FileExistsError('Frozen ranking already exists; choose a fresh output')
    with args.manifest.open(encoding='utf-8-sig',newline='') as stream:validation=[r for r in csv.DictReader(stream) if r['split']=='val']
    validation.sort(key=lambda r:r['sample_id']);ids={r['sample_id'] for r in validation}
    y=np.array([int(r['label']) for r in validation]);weights=balanced_source_weights(validation)
    results=[]
    for candidate in json.loads(args.candidates.read_text(encoding='utf-8-sig')):
        with Path(candidate['predictions']).open(encoding='utf-8-sig',newline='') as stream:predictions=list(csv.DictReader(stream))
        mapping={r['sample_id']:r for r in predictions}
        if set(mapping)!=ids or len(predictions)!=len(ids):raise ValueError('Candidate validation population differs')
        for row in validation:
            prediction=mapping[row['sample_id']]
            if any(str(prediction[key])!=str(row[key]) for key in ('label','source','method','group')):
                raise ValueError('Prediction labels or provenance differ from validation manifest')
        for field,path in [('checkpoint_sha256',candidate['checkpoint']),('predictions_sha256',candidate['predictions'])]:
            if field in candidate and candidate[field]!=digest(path):raise ValueError('Candidate file changed: '+field)
        state=torch.load(candidate['checkpoint'],map_location='cpu',weights_only=True)
        p=np.array([float(mapping[r['sample_id']]['score']) for r in validation]);threshold=state['frame_threshold']
        item=dict(candidate,source_group_balanced_auc=float(roc_auc_score(y,p,sample_weight=weights)),
            source_group_balanced_accuracy=float(np.average((p>=threshold)==y,weights=weights)),
            checkpoint_sha256=digest(candidate['checkpoint']),threshold=threshold,per_source={})
        if low_fpr:
            point=select_operating_point(validation,p,args.max_val_fpr,args.focus_method)
            item.update(checkpoint_original_threshold=threshold,threshold=point['threshold'],
                operating_point=point,selection_key=list(operating_rank(point,item['source_group_balanced_auc'])),
                source_group_balanced_accuracy=float(np.average((p>=point['threshold'])==y,weights=weights)))
            threshold=point['threshold']
        for source in sorted({r['source'] for r in validation}):
            ix=np.array([i for i,r in enumerate(validation) if r['source']==source]);yy=y[ix];pp=p[ix]
            item['per_source'][source]=dict(n=len(ix),false_positives=int(((pp>=threshold)&(yy==0)).sum()),
                                         false_negatives=int(((pp<threshold)&(yy==1)).sum()))
        results.append(item)
        del state
    if low_fpr:
        results.sort(key=lambda r:tuple(-v for v in r['selection_key'])+(r['name'],))
    else:
        results.sort(key=lambda r:(-r['source_group_balanced_auc'],-r['source_group_balanced_accuracy'],r['name']))
    selection=('Validation overall real FPR budget; focus-generator group-balanced recall, all-generator recall, source/group AUC, lower FPR; name on exact tie' if low_fpr else 'Validation-only source/group balanced AUC, then balanced accuracy')
    save_json(args.output,dict(selection=selection+'; frozen before regression inference',
        manifest_sha256=digest(args.manifest),candidates=results,selected=results[0],external_exam_used=False,
        selection_metric=args.selection_metric,max_validation_real_fpr=args.max_val_fpr if low_fpr else None,
        limitation='Small GPT1 validation sample can overfit selection; external results must not be used to re-rank and still called fresh.'))
    print('Locked generation candidate:',results[0]['name'],results[0]['source_group_balanced_auc'],flush=True)


if __name__=='__main__':main()
