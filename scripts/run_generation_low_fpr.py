"""Train/select at a fixed validation FPR budget using existing frozen data only."""
import argparse
import csv
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'reference_run'))
from faceguard.data_locations import data_location
from faceguard.model_registry import checked_resource,digest
from prepare_generation_update import save_json


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'outputs/training-20261031/low-fpr-current-data')
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    if (out/'plan-before-training.json').exists():raise FileExistsError('Use a fresh output directory')
    folder=data_location('generation_joint_manifests');manifest=folder/'manifest.csv'
    protocol=json.loads((folder/'protocol.json').read_text(encoding='utf-8'))
    if digest(manifest)!=protocol['manifest_sha256']:raise ValueError('Frozen input changed')
    previous=ROOT/'outputs/training-20261031/dff-gpt-joint'
    parent_run=ROOT/'outputs/training-20261031/dff-sd15-update'
    parent=parent_run/'candidate/model.pt'
    if digest(parent)!=json.loads((parent_run/'completion.json').read_text(encoding='utf-8'))['candidate_sha256']:
        raise ValueError('Parent checkpoint changed')
    stable={name:digest(checked_resource(name)) for name in ('generation.pt','manipulation.pt','yunet.onnx','video_policy.json')}
    save_json(out/'stable-before.json',stable)
    save_json(out/'plan-before-training.json',dict(epochs=3,seed=20261031,max_validation_real_fpr=.02,
        focus_methods=['gpt-image-1'],manifest_sha256=digest(manifest),init_checkpoint_sha256=digest(parent),
        ranking='Focus-generator group-balanced recall, all-generator group-balanced recall, source/group balanced AUC, lower FPR; deterministic name/earlier epoch tie',
        scope='Current-data engineering and historical regression, not new blind generalization; user image never selects parameters',
        candidate_pool=['stable','sd15-parent','high-sensitivity','new-epoch-001','new-epoch-002','new-epoch-003']))
    start=time.monotonic()
    def run(stage,command):
        print('STAGE '+stage,flush=True)
        save_json(out/'pipeline-progress.json',dict(stage=stage,state='running',seconds=time.monotonic()-start))
        with (out/(stage+'.log')).open('w',encoding='utf-8') as log:
            process=subprocess.Popen([sys.executable]+command,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                text=True,encoding='utf-8',errors='replace',env=dict(os.environ,PYTHONIOENCODING='utf-8'))
            for line in process.stdout:
                log.write(line);log.flush();print(line.rstrip().encode('ascii',errors='backslashreplace').decode(),flush=True)
            code=process.wait()
        if code:
            save_json(out/'pipeline-progress.json',dict(stage=stage,state='failed',returncode=code))
            raise RuntimeError(stage+' failed')
    train=out/'training'
    run('finetune',['reference_run/train_generation.py','--include-sd35','--allow-dff','--allow-openfake',
        '--manifest',str(manifest),'--output',str(train),'--init-checkpoint',str(parent),'--skip-test',
        '--source-balanced-selection','--balanced-sampling','--epochs','3','--batch-size','32','--workers','0',
        '--device','cuda','--backbone-lr','0.00003','--head-lr','0.0001','--seed','20261031',
        '--selection-metric','low_fpr_gpt_recall','--max-val-fpr','0.02','--focus-method','gpt-image-1','--save-epoch-checkpoints'])
    def evaluate(label,checkpoint,split):
        destination=out/'evaluation'/(label+'-'+split)
        run(label+'-'+split,['scripts/evaluate_generation_update.py','--manifest-directory',str(folder),
            '--checkpoint',str(checkpoint),'--split',split,'--batch-size','32','--output',str(destination)])
        return destination
    stable_val=evaluate('stable-original',checked_resource('generation.pt'),'val')
    sources=[('stable',checked_resource('generation.pt'),stable_val/'predictions.csv',stable_val/'metrics.json'),
        ('sd15-parent',parent,previous/'evaluation/sd15-parent-val/predictions.csv',previous/'evaluation/sd15-parent-val/metrics.json'),
        ('high-sensitivity',previous/'candidate/model.pt',previous/'evaluation/joint-val/predictions.csv',previous/'evaluation/joint-val/metrics.json')]
    candidates=[]
    for label,checkpoint,predictions,metrics in sources:
        report=json.loads(metrics.read_text(encoding='utf-8'))
        if report['manifest_sha256']!=digest(manifest) or report['checkpoint_sha256']!=digest(checkpoint):
            raise ValueError('Cached validation evidence belongs to different input/model')
        candidates.append(dict(name=label,checkpoint=str(checkpoint),predictions=str(predictions),
            checkpoint_sha256=digest(checkpoint),predictions_sha256=digest(predictions)))
    for epoch in range(1,4):
        checkpoint=train/'epochs'/f'epoch-{epoch:03d}.pt';predictions=train/'epochs'/f'epoch-{epoch:03d}-val.csv'
        candidates.append(dict(name=f'new-epoch-{epoch:03d}',checkpoint=str(checkpoint),predictions=str(predictions),
            checkpoint_sha256=digest(checkpoint),predictions_sha256=digest(predictions)))
    save_json(out/'candidate-inputs.json',candidates)
    run('validation-ranking',['reference_run/choose_generation_candidate.py','--manifest',str(manifest),
        '--candidates',str(out/'candidate-inputs.json'),'--output',str(out/'selection.json'),
        '--selection-metric','low_fpr_gpt_recall','--max-val-fpr','0.02','--focus-method','gpt-image-1'])
    ranking=json.loads((out/'selection.json').read_text(encoding='utf-8'))
    import torch
    torch.set_num_threads(2)
    calibrated=out/'calibrated';calibrated.mkdir()
    calibrated_paths={}
    for item in ranking['candidates']:
        state=torch.load(item['checkpoint'],map_location='cpu',weights_only=True)
        state['frame_threshold']=state['video_threshold']=item['threshold']
        state['threshold_strategy']='Validation-only empirical overall real-image FPR <=2%; decision-equivalent score midpoint'
        state['operating_point_calibration']=dict(source_checkpoint_sha256=item['checkpoint_sha256'],
            validation_predictions_sha256=item['predictions_sha256'],manifest_sha256=digest(manifest),
            selection_metric='low_fpr_gpt_recall',operating_point=item['operating_point'])
        path=calibrated/(item['name']+'.pt');torch.save(state,path);calibrated_paths[item['name']]=path
    selected_name=ranking['selected']['name'];selected=calibrated_paths[selected_name]
    save_json(out/'locked-before-regression.json',dict(selected_name=selected_name,checkpoint=str(selected),
        checkpoint_sha256=digest(selected),manifest_sha256=digest(manifest),threshold=ranking['selected']['threshold'],
        selection_sha256=digest(out/'selection.json'),test_used_for_selection=False,user_image_used_for_selection=False))
    # Validate the exact serialized operating points before looking at regression.
    for label in ('sd15-parent','high-sensitivity'):
        evaluate(label+'-2pct',calibrated_paths[label],'val')
    selected_val=evaluate('selected-2pct',selected,'val')
    selected_metrics=json.loads((selected_val/'metrics.json').read_text(encoding='utf-8'))
    with manifest.open(encoding='utf-8',newline='') as file:validation=[r for r in csv.DictReader(file) if r['split']=='val']
    with (selected_val/'predictions.csv').open(encoding='utf-8-sig',newline='') as file:predictions={r['sample_id']:float(r['score']) for r in csv.DictReader(file)}
    from faceguard.generation_selection import operating_summary
    point=operating_summary(validation,[predictions[r['sample_id']] for r in validation],selected_metrics['threshold'],.02,['gpt-image-1'])
    if not point['budget_met']:raise ValueError('Serialized selected candidate failed validation FPR check')
    save_json(out/'selected-validation-policy-check.json',point)
    for split in ('test','external_test','gan_dev'):evaluate('selected-2pct',selected,split)
    from faceguard.inference.face_analysis import GenerationPredictor
    import cv2
    cv2.setNumThreads(1)
    case=Path(protocol['user_regression_path'])
    if digest(case)!=protocol['user_regression_raw_sha256']:raise ValueError('User image changed')
    predictor=GenerationPredictor(checkpoint=selected,device='cpu');case_result=predictor.predict(case)
    save_json(out/'user-case-regression.json',dict(result=case_result,note='Previously observed developer regression, not selection or blind accuracy'))
    if stable!={name:digest(checked_resource(name)) for name in stable}:raise ValueError('Stable resources changed')
    save_json(out/'completion.json',dict(state='complete',selected_name=selected_name,checkpoint=str(selected),
        checkpoint_sha256=digest(selected),manifest_sha256=digest(manifest),threshold=ranking['selected']['threshold'],
        selection_sha256=digest(out/'selection.json'),stable_resources_unchanged=True,default_changed=False,
        seconds=time.monotonic()-start,user_case=case_result,
        evaluations={p.parent.name:json.loads(p.read_text(encoding='utf-8')) for p in (out/'evaluation').glob('*/metrics.json')}))
    save_json(out/'pipeline-progress.json',dict(stage='complete',state='complete',seconds=time.monotonic()-start))
    print('LOW-FPR CURRENT-DATA EXPERIMENT COMPLETE',flush=True)


if __name__=='__main__':main()
