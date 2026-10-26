"""Validation-only empirical operating points for the fixed adjacent-pair review statistic."""
import argparse
import json
import math
from pathlib import Path

import numpy as np

from core import save_json
from train import metrics


def choose_threshold(real_scores,target_rate):
    if not len(real_scores):
        raise ValueError('No real validation videos')
    # Strictly above the order statistic: ties cannot silently exceed the requested empirical rate.
    rank=min(len(real_scores),math.ceil((len(real_scores)+1)*(1-target_rate)))
    return float(np.nextafter(np.sort(real_scores)[rank-1],np.inf))


def summarize(rows,threshold):
    valid=[r for r in rows if r['score'] is not None]
    y=np.array([r['label'] for r in valid]);p=np.array([r['score'] for r in valid])
    report=metrics(y,p,threshold)
    report['per_method']={}
    for method in sorted({r['method'] for r in valid}):
        group=[r for r in valid if r['method']==method]
        report['per_method'][method]=dict(n=len(group),alerts=sum(r['score']>=threshold for r in group))
    report['unable_to_score']=len(rows)-len(valid)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--validation',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--test',type=Path,help='Only evaluate after policy is already locked on disk')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    validation=json.loads((args.validation/'scores.json').read_text(encoding='utf-8'))
    protocol=json.loads((args.validation/'PROTOCOL.json').read_text(encoding='utf-8'))
    if protocol['split']!='val':raise ValueError('Expected validation split')
    real=np.array([r['score'] for r in validation if r['label']==0 and r['score'] is not None])
    policy_path=args.output/'policy.json'
    if args.test and not policy_path.is_file():raise ValueError('Lock validation policy before examining test')
    if not policy_path.is_file():
        policies={name:choose_threshold(real,rate) for name,rate in [('conservative',.01),('review',.05)]}
        policy=dict(algorithm='adjacent_pair_mean_v1',max_gap_seconds=1.5,
            model_sha256=protocol['model_sha256'],threshold=policies['conservative'],
            operating_point='conservative',alternatives=policies,validation_real_videos=len(real),
            intended_empirical_false_alert_rate=.01,
            selection='Validation real scores only; default conservative preset fixed before test',
            warning='Empirical operating point, not a distribution-free guarantee. Same FF++ validation also selected model; no independent calibration sample. Multi-person and unseen sources not validated.')
        save_json(policy_path,policy)
    policy=json.loads(policy_path.read_text(encoding='utf-8'))
    report=dict(policy=policy,validation={name:summarize(validation,threshold) for name,threshold in policy['alternatives'].items()},
        uncalibrated_validation_false_alerts=sum(r['raw_alert'] for r in validation if r['label']==0),
        validation_real_count=sum(r['label']==0 for r in validation))
    if args.test:
        test=json.loads((args.test/'scores.json').read_text(encoding='utf-8'))
        test_protocol=json.loads((args.test/'PROTOCOL.json').read_text(encoding='utf-8'))
        if test_protocol['split']!='test' or test_protocol['model_sha256']!=policy['model_sha256']:
            raise ValueError('Unexpected test split/model')
        report['test']={name:summarize(test,threshold) for name,threshold in policy['alternatives'].items()}
        report['test_note']='Existing FF++ test regression subset; no thresholds changed after observing these results'
    save_json(args.output/'metrics.json',report)
    print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':main()
