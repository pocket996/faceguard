"""Compare existing weights at validation-only FPR limits, replaying verified historical score files."""
import argparse
import csv
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'reference_run'))
from faceguard.data_locations import data_location
from faceguard.model_registry import checked_resource,digest
from prepare_generation_update import save_json


def read(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as file:return list(csv.DictReader(file))


def matched_scores(rows,predictions):
    mapping={r['sample_id']:r for r in predictions}
    if len(mapping)!=len(predictions):raise ValueError('Duplicate cached sample IDs')
    scores=[]
    for row in rows:
        cached=mapping[row['sample_id']]
        if any(str(cached[k])!=str(row[k]) for k in ('label','source','method')):
            raise ValueError('Cached labels/source differ from manifest')
        if 'group' in cached and cached['group']!=row['group']:
            raise ValueError('Cached group differs from manifest')
        scores.append(float(cached['score']))
    return scores


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'outputs/training-20261031/low-fpr-existing-models')
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    if (out/'plan-before-selection.json').exists():raise FileExistsError('Choose fresh output')
    start=time.monotonic();folder=data_location('generation_joint_manifests');manifest=folder/'manifest.csv'
    protocol=json.loads((folder/'protocol.json').read_text(encoding='utf-8'))
    if digest(manifest)!=protocol['manifest_sha256']:raise ValueError('Frozen manifest changed')
    partitions={split:[] for split in ('val','test','external_test')}
    with manifest.open(encoding='utf-8-sig',newline='') as file:
        for row in csv.DictReader(file):
            if row['split'] in partitions:partitions[row['split']].append(row)
    validation=partitions['val'];v1=ROOT/'outputs/training-20261031/dff-sd15-update';v2=ROOT/'outputs/training-20261031/dff-gpt-joint'
    candidates={'stable':checked_resource('generation.pt'),'sd15-parent':v1/'candidate/model.pt','high-sensitivity':v2/'candidate/model.pt'}
    stable={name:digest(checked_resource(name)) for name in ('generation.pt','manipulation.pt','yunet.onnx','video_policy.json')}
    save_json(out/'stable-before.json',stable)
    save_json(out/'plan-before-selection.json',dict(manifest_sha256=digest(manifest),max_validation_real_fpr=.02,
        focus_methods=['gpt-image-1'],candidate_hashes={name:digest(p) for name,p in candidates.items()},
        policy='Group-balanced GPT recall, generator recall, source/group AUC, lower FPR; name tie; validation only',
        scope='No new full training; cached score replay from unchanged weights, plus missing stable validation CPU inference and raw-image CPU parity check. Historical regression only.'))
    print('Preparing stable validation cache',flush=True)
    original_metrics=json.loads((v1/'evaluation/baseline-val/metrics.json').read_text(encoding='utf-8'))
    if original_metrics['checkpoint_sha256']!=stable['generation.pt']:raise ValueError('Stable cached model changed')
    baseline=read(v1/'evaluation/baseline-val/predictions.csv');known={r['sample_id'] for r in baseline}
    missing=[r for r in validation if r['sample_id'] not in known]
    import torch
    import cv2
    torch.set_num_threads(2);cv2.setNumThreads(1)
    from evaluate_generation_update import evaluate,summarize_scores
    from train import write_csv
    if missing:
        evaluate(candidates['stable'],missing,out/'stable-missing-validation','cpu',8)
        baseline+=read(out/'stable-missing-validation/predictions.csv')
    scores=matched_scores(validation,baseline)
    stable_val=out/'stable-val-predictions.csv'
    write_csv(stable_val,[dict(sample_id=r['sample_id'],path=r['path'],source=r['source'],method=r['method'],group=r['group'],label=r['label'],score=p) for r,p in zip(validation,scores)])
    val_files={'stable':stable_val,'sd15-parent':v2/'evaluation/sd15-parent-val/predictions.csv','high-sensitivity':v2/'evaluation/joint-val/predictions.csv'}
    for name,label in [('sd15-parent','sd15-parent'),('high-sensitivity','joint')]:
        evidence=json.loads((v2/f'evaluation/{label}-val/metrics.json').read_text(encoding='utf-8'))
        if evidence['checkpoint_sha256']!=digest(candidates[name]) or evidence['manifest_sha256']!=digest(manifest):
            raise ValueError('Cached validation evidence differs')
    config=[dict(name=name,checkpoint=str(path),checkpoint_sha256=digest(path),predictions=str(val_files[name]),predictions_sha256=digest(val_files[name])) for name,path in candidates.items()]
    save_json(out/'candidate-inputs.json',config)
    import subprocess,os
    command=[sys.executable,'reference_run/choose_generation_candidate.py','--manifest',str(manifest),'--candidates',str(out/'candidate-inputs.json'),
        '--output',str(out/'selection.json'),'--selection-metric','low_fpr_gpt_recall','--max-val-fpr','.02','--focus-method','gpt-image-1']
    subprocess.run(command,cwd=ROOT,check=True,env=dict(os.environ,PYTHONIOENCODING='utf-8'))
    ranking=json.loads((out/'selection.json').read_text(encoding='utf-8'));calibrated=out/'calibrated';calibrated.mkdir()
    for item in ranking['candidates']:
        state=torch.load(item['checkpoint'],map_location='cpu',weights_only=True)
        state['frame_threshold']=state['video_threshold']=item['threshold']
        state['threshold_strategy']='Validation-only empirical overall real FPR <=2%, group-balanced GPT recall ranking'
        state['operating_point_calibration']=dict(source_checkpoint_sha256=item['checkpoint_sha256'],validation_predictions_sha256=item['predictions_sha256'],manifest_sha256=digest(manifest),operating_point=item['operating_point'])
        torch.save(state,calibrated/(item['name']+'.pt'));del state
    selected=ranking['selected']['name'];selected_path=calibrated/(selected+'.pt')
    save_json(out/'locked-before-regression.json',dict(selected_name=selected,checkpoint_sha256=digest(selected_path),threshold=ranking['selected']['threshold'],manifest_sha256=digest(manifest),selection_sha256=digest(out/'selection.json'),test_used_for_selection=False,user_image_used_for_selection=False))
    # Source score caches contain predictions from exactly the original weights.
    caches={
        'stable':dict(test=v1/'evaluation/baseline-test',external_test=ROOT/'outputs/autonomous-20261026/started-1248/generation-external-original',gan_dev=v1/'evaluation/baseline-gan_dev'),
        'sd15-parent':{s:v2/('evaluation/sd15-parent-'+s) for s in ('test','external_test','gan_dev')},
        'high-sensitivity':{s:v2/('evaluation/joint-'+s) for s in ('test','external_test','gan_dev')}}
    evaluations={}
    for item in ranking['candidates']:
        name=item['name'];threshold=item['threshold'];path=calibrated/(name+'.pt')
        for split in ('val','test','external_test','gan_dev'):
            if split=='val':
                rows=validation;cache=val_files[name];scores=matched_scores(rows,read(cache));source_evidence=None
            else:
                source=caches[name][split];source_evidence=json.loads((source/'metrics.json').read_text(encoding='utf-8'))
                if source_evidence['checkpoint_sha256']!=item['checkpoint_sha256']:raise ValueError('Regression cache model mismatch')
                filename='external_test_clean_predictions.csv' if name=='stable' and split=='external_test' else 'predictions.csv'
                cache=source/filename;stored=read(cache)
                if split=='gan_dev':rows=[dict(r,split='external_dev') for r in stored]
                else:rows=partitions[split]
                scores=matched_scores(rows,stored)
            label=name+'-'+split;destination=out/'evaluation'/label;destination.mkdir(parents=True)
            report=dict(summarize_scores(rows,scores,threshold),split=split,checkpoint_sha256=digest(path),manifest_sha256=digest(manifest),
                evaluation_mode='historical_score_replay_same_source_weights',source_checkpoint_sha256=item['checkpoint_sha256'],
                source_predictions=str(cache),source_predictions_sha256=digest(cache),threshold_recalibrated=False,
                note='Threshold fixed from validation before replay; no new GPU inference or independent benchmark')
            save_json(destination/'metrics.json',report);evaluations[label]=report
            write_csv(destination/'predictions.csv',[dict(sample_id=r['sample_id'],path=r.get('path',''),source=r['source'],method=r['method'],group=r['group'],label=r['label'],score=p,prediction=int(p>=threshold)) for r,p in zip(rows,scores)])
    from faceguard.inference.face_analysis import GenerationPredictor
    predictor=GenerationPredictor(checkpoint=selected_path,device='cpu')
    from faceguard.data_locations import resolve_data_path
    import tempfile,zipfile
    expected={r['sample_id']:r for r in read(out/'evaluation'/(selected+'-val')/'predictions.csv')};checks=[]
    for source,method in [('DFF','real'),('DFF','SD15'),('LFW','real'),('FFHQ-256-mirror','real'),('FairFaceGen','FLUX'),('FairFaceGen','SD35')]:
        row=next(r for r in validation if r['source']==source and r['method']==method);raw=resolve_data_path(row['raw_path'])
        if row.get('archive_member'):
            with tempfile.TemporaryDirectory(prefix='faceguard-parity-') as temporary:
                image=Path(temporary)/'image.jpg'
                with zipfile.ZipFile(raw) as archive:image.write_bytes(archive.read(row['archive_member']))
                result=predictor.predict(image)
        else:result=predictor.predict(raw)
        value=result['face_results'][0]['score'];difference=abs(value-float(expected[row['sample_id']]['score']))
        if difference>1e-4:raise ValueError('Cached prediction no longer matches raw CPU inference')
        checks.append(dict(sample_id=row['sample_id'],absolute_difference=difference))
    case=Path(protocol['user_regression_path'])
    if digest(case)!=protocol['user_regression_raw_sha256']:raise ValueError('User image changed')
    user_result=predictor.predict(case)
    if stable!={name:digest(checked_resource(name)) for name in stable}:raise ValueError('Stable resources changed')
    save_json(out/'completion.json',dict(state='complete',selected_name=selected,checkpoint=str(selected_path),checkpoint_sha256=digest(selected_path),
        threshold=ranking['selected']['threshold'],manifest_sha256=digest(manifest),selection_sha256=digest(out/'selection.json'),
        stable_resources_unchanged=True,default_changed=False,new_full_training_completed=False,evaluation_mode='historical_score_replay_plus_CPU_parity',
        seconds=time.monotonic()-start,evaluations=evaluations,cpu_parity=checks,user_case=user_result))
    print(json.dumps(dict(state='complete',selected=selected,threshold=ranking['selected']['threshold'],user_case=user_result['decision']),ensure_ascii=True),flush=True)


if __name__=='__main__':main()
