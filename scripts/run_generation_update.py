"""Run the frozen SD1.5 fine-tuning plan, preserving the deployed runtime bundle."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from faceguard.data_locations import data_location
from faceguard.model_registry import checked_resource,digest
from prepare_generation_update import save_json


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--epochs',type=int,default=5)
    parser.add_argument('--output',type=Path,default=ROOT/'outputs/training-20261031/dff-sd15-update')
    args=parser.parse_args();output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    stable={name:digest(checked_resource(name)) for name in ('generation.pt','manipulation.pt','yunet.onnx','video_policy.json')}
    save_json(output/'stable-before.json',stable)
    start=time.monotonic()
    def run(stage,command):
        print('STAGE '+stage,flush=True)
        save_json(output/'pipeline-progress.json',dict(stage=stage,state='running',seconds=time.monotonic()-start))
        environment=dict(os.environ,PYTHONIOENCODING='utf-8')
        with (output/(stage+'.log')).open('w',encoding='utf-8') as log:
            process=subprocess.Popen([sys.executable]+command,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                                     text=True,encoding='utf-8',errors='replace',env=environment)
            for line in process.stdout:
                log.write(line);log.flush();print(line.rstrip().encode('ascii',errors='backslashreplace').decode(),flush=True)
            code=process.wait()
        if code:
            save_json(output/'pipeline-progress.json',dict(stage=stage,state='failed',returncode=code,seconds=time.monotonic()-start))
            raise RuntimeError(f'{stage} failed; see stage log')
    manifest_folder=data_location('generation_update_manifests')
    if not (manifest_folder/'protocol.json').exists():run('freeze-splits',['scripts/split_generation_update.py'])
    protocol=json.loads((manifest_folder/'protocol.json').read_text(encoding='utf-8'))
    manifest=manifest_folder/'manifest.csv'
    if digest(manifest)!=protocol['manifest_sha256']:raise ValueError('Frozen manifest changed')
    baseline=checked_resource('generation.pt');candidate=output/'candidate'
    evaluations=output/'evaluation'
    run('baseline-validation',['scripts/evaluate_generation_update.py','--checkpoint',str(baseline),'--split','val','--output',str(evaluations/'baseline-val')])
    run('finetune',['reference_run/train_generation.py','--include-sd35','--allow-dff','--manifest',str(manifest),
                    '--output',str(candidate),'--init-checkpoint',str(baseline),'--skip-test',
                    '--source-balanced-selection','--balanced-sampling','--epochs',str(args.epochs),
                    '--batch-size','32','--workers','0','--device','cuda','--backbone-lr','0.00003','--head-lr','0.0001','--seed','20261031'])
    checkpoint=candidate/'model.pt'
    save_json(output/'candidate-locked-before-test.json',dict(checkpoint_sha256=digest(checkpoint),manifest_sha256=digest(manifest),
        note='Epoch and threshold selected from validation only; lock recorded before final test'))
    for label,path in [('baseline',baseline),('candidate',checkpoint)]:
        for split in ('val','test','gan_dev'):
            if label=='baseline' and split=='val':continue
            run(label+'-'+split,['scripts/evaluate_generation_update.py','--checkpoint',str(path),'--split',split,'--output',str(evaluations/(label+'-'+split))])
    after={name:digest(checked_resource(name)) for name in stable}
    if stable!=after:raise ValueError('Stable runtime bundle changed during experiment')
    report=dict(state='complete',epochs_requested=args.epochs,candidate=str(checkpoint),candidate_sha256=digest(checkpoint),
                protocol=str(manifest_folder/'protocol.json'),manifest_sha256=digest(manifest),stable_resources_unchanged=True,
                candidate_activated=False,seconds=time.monotonic()-start,evaluations={})
    for label in ('baseline','candidate'):
        for split in ('val','test','gan_dev'):
            report['evaluations'][label+'-'+split]=json.loads((evaluations/(label+'-'+split)/'metrics.json').read_text(encoding='utf-8'))
    save_json(output/'completion.json',report)
    save_json(output/'pipeline-progress.json',dict(stage='complete',state='complete',seconds=time.monotonic()-start))
    print(json.dumps({key:value for key,value in report.items() if key!='evaluations'},ensure_ascii=True,indent=2),flush=True)


if __name__=='__main__':main()
