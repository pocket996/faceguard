"""Finite joint GPT1/SD1.5 fine-tuning; user image and observed regression sets never select weights."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from faceguard.data_locations import data_location
from faceguard.model_registry import checked_resource, digest
from prepare_generation_update import save_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'outputs/training-20261031/dff-gpt-joint')
    args = parser.parse_args(); output = args.output.resolve(); output.mkdir(parents=True, exist_ok=True)
    if (output/'pipeline-progress.json').exists(): raise FileExistsError('Choose a fresh run directory')
    folder = data_location('generation_joint_manifests')
    protocol = json.loads((folder/'protocol.json').read_text(encoding='utf-8'))
    manifest = folder/'manifest.csv'
    if digest(manifest) != protocol['manifest_sha256']: raise ValueError('Joint manifest changed')
    parent = ROOT/'outputs/training-20261031/dff-sd15-update/candidate/model.pt'
    parent_lock = json.loads((parent.parent.parent/'candidate-locked-before-test.json').read_text(encoding='utf-8'))
    if digest(parent) != parent_lock['checkpoint_sha256']: raise ValueError('Parent checkpoint changed')
    case = Path(protocol['user_regression_path'])
    if digest(case) != protocol['user_regression_raw_sha256']: raise ValueError('User image changed')
    stable = {name: digest(checked_resource(name)) for name in ('generation.pt','manipulation.pt','yunet.onnx','video_policy.json')}
    save_json(output/'stable-before.json', stable)
    save_json(output/'plan-before-training.json', dict(epochs=3, seed=20261031, backbone_lr=3e-5, head_lr=1e-4,
        parent_sha256=digest(parent), manifest_sha256=digest(manifest), selection='Validation source/group balanced AUC only; threshold validation only',
        user_case='Observed regression only; never fitted or used to choose epoch/threshold', external='Historical regression, not fresh blind test'))
    start = time.monotonic()
    def run(stage, command):
        print('STAGE '+stage, flush=True)
        save_json(output/'pipeline-progress.json', dict(stage=stage,state='running',seconds=time.monotonic()-start))
        with (output/(stage+'.log')).open('w', encoding='utf-8') as log:
            p = subprocess.Popen([sys.executable]+command,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                                 text=True,encoding='utf-8',errors='replace',env=dict(os.environ,PYTHONIOENCODING='utf-8'))
            for line in p.stdout:
                log.write(line);log.flush(); print(line.rstrip().encode('ascii',errors='backslashreplace').decode(),flush=True)
            code = p.wait()
        if code:
            save_json(output/'pipeline-progress.json',dict(stage=stage,state='failed',returncode=code))
            raise RuntimeError(stage+' failed')
    def evaluate(label, checkpoint, split):
        run(label+'-'+split, ['scripts/evaluate_generation_update.py','--manifest-directory',str(folder),
            '--checkpoint',str(checkpoint),'--split',split,'--output',str(output/'evaluation'/(label+'-'+split))])
    evaluate('sd15-parent',parent,'val')
    candidate = output/'candidate'
    run('finetune',['reference_run/train_generation.py','--include-sd35','--allow-dff','--allow-openfake',
        '--manifest',str(manifest),'--output',str(candidate),'--init-checkpoint',str(parent),'--skip-test',
        '--source-balanced-selection','--balanced-sampling','--epochs','3','--batch-size','32','--workers','0',
        '--device','cuda','--backbone-lr','0.00003','--head-lr','0.0001','--seed','20261031'])
    checkpoint = candidate/'model.pt'
    save_json(output/'candidate-locked-before-regression.json',dict(checkpoint_sha256=digest(checkpoint),manifest_sha256=digest(manifest),
        policy='Validation choices fixed before all post-training regression, including user photo'))
    for label, path in [('sd15-parent',parent),('joint',checkpoint)]:
        for split in ('val','test','external_test','gan_dev'):
            if label=='sd15-parent' and split=='val': continue
            evaluate(label,path,split)
    import torch
    import cv2
    from faceguard.inference.face_analysis import GenerationPredictor
    torch.set_num_threads(2);cv2.setNumThreads(1)
    predictor = GenerationPredictor(checkpoint=checkpoint,device='cpu')
    result = predictor.predict(case)
    if digest(case) != protocol['user_regression_raw_sha256']: raise ValueError('User image changed')
    save_json(output/'user-case-regression.json',dict(result=result,source='User-reported GPT, exact version unknown',
        note='Observed single-image regression after validation-only lock; no accuracy/generalization claim'))
    if stable != {name:digest(checked_resource(name)) for name in stable}: raise ValueError('Stable resources changed')
    save_json(output/'completion.json',dict(state='complete',candidate=str(checkpoint),candidate_sha256=digest(checkpoint),
        manifest_sha256=digest(manifest),stable_resources_unchanged=True,candidate_activated=False,
        seconds=time.monotonic()-start,evaluations={p.parent.name:json.loads(p.read_text(encoding='utf-8')) for p in (output/'evaluation').glob('*/metrics.json')},
        user_case=result))
    save_json(output/'pipeline-progress.json',dict(state='complete',stage='complete',seconds=time.monotonic()-start))
    print('JOINT EXPERIMENT COMPLETE',flush=True)


if __name__ == '__main__': main()
