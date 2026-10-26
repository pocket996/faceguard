"""Serial session evaluation; lock validation choices before external inference, no post-test re-ranking."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import subprocess
import sys

from project_io import HERE,save_json,digest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session',type=Path,required=True)
    args=parser.parse_args();base=args.session.resolve()
    markers=base/'suite-markers';markers.mkdir(exist_ok=True)
    def run(key,script,arguments):
        command=[sys.executable,str(HERE/script)]+[str(x) for x in arguments]
        marker=markers/(key+'.json')
        if marker.is_file() and json.loads(marker.read_text())['command']==command:
            print('Reusing completed stage:',key,flush=True);return
        save_json(base/'suite-progress.json',dict(stage=key,status='running',utc=datetime.now(timezone.utc).isoformat()))
        print('Starting stage:',key,flush=True)
        subprocess.run(command,cwd=HERE.parent,check=True)
        save_json(marker,dict(command=command,finished_utc=datetime.now(timezone.utc).isoformat()))
    photo_manifest=base/'photo-map-supervision/manifest.csv'
    for key,checkpoint,extra in [
        ('photo-threshold-only',HERE/'artifacts/model_finetuned.pt',['--calibrate']),
        ('photo-map-validation',base/'photo-map-supervision/model.pt',['--probe-masks']),
        ('photo-label-validation',base/'photo-label-only/model.pt',['--probe-masks'])]:
        run(key,'evaluate_photo_supervision.py',['--checkpoint',checkpoint,'--manifest',photo_manifest,
            '--split','val','--output',base/key]+extra)
    photo_candidates=[dict(name='threshold_only',checkpoint=str(base/'photo-threshold-only/model.pt'),predictions=str(base/'photo-threshold-only/predictions.csv')),
        dict(name='regional_supervision',checkpoint=str(base/'photo-map-supervision/model.pt'),predictions=str(base/'photo-map-supervision/val_predictions.csv')),
        dict(name='labels_only',checkpoint=str(base/'photo-label-only/model.pt'),predictions=str(base/'photo-label-only/val_predictions.csv'))]
    gen_candidates=[
        dict(name='original_stable',checkpoint=str(HERE/'artifacts/generation/joint/model.pt'),predictions=str(base/'original-generation-val/val_clean_predictions.csv')),
        dict(name='clean_retrain',checkpoint=str(base/'clean-baseline-evaluation/model_calibrated.pt'),predictions=str(base/'clean-generation-new-val/val_clean_predictions.csv')),
        dict(name='multisource',checkpoint=str(base/'generation-multisource/model.pt'),predictions=str(base/'generation-multisource/val_predictions.csv')),
        dict(name='strong_augmentation',checkpoint=str(base/'generation-multisource-strong/model.pt'),predictions=str(base/'generation-multisource-strong/val_predictions.csv')),
        dict(name='frozen_vit',checkpoint=str(base/'generation-frozen-vit/model.pt'),predictions=str(base/'generation-frozen-vit/val_predictions.csv'))]
    for key,manifest,candidates in [('photo',photo_manifest,photo_candidates),('generation',base/'openfake-prepared/combined_manifest.csv',gen_candidates)]:
        selection=base/(key+'-selection.json')
        config=base/(key+'-candidates.json')
        if selection.is_file():
            locked=json.loads(selection.read_text(encoding='utf-8'))
            if any(digest(c['checkpoint'])!=c['checkpoint_sha256'] for c in locked['candidates']):
                raise RuntimeError('Locked candidate changed; refusing to re-rank after possible external access')
        else:
            save_json(config,candidates)
            run(key+'-selection','choose_generation_candidate.py',['--manifest',manifest,'--candidates',config,'--output',selection])
    chosen_gen=json.loads((base/'generation-selection.json').read_text())['selected']
    chosen_photo=json.loads((base/'photo-selection.json').read_text())['selected']
    if not (base/'exam-locked-models.json').is_file():
        save_json(base/'exam-locked-models.json',dict(generation=chosen_gen,photo=chosen_photo,
            external_results_seen=False,selection_complete_utc=datetime.now(timezone.utc).isoformat(),
            rule='The selected candidates remain fixed even if external results are disappointing'))
    exam=base/'locked-exam/manifest.csv'
    for key,checkpoint in [('original',HERE/'artifacts/generation/joint/model.pt'),('selected',Path(chosen_gen['checkpoint']))]:
        run('generation-external-'+key,'evaluate_generation_candidate.py',['--checkpoint',checkpoint,'--manifest',exam,
            '--split','external_test','--stress','clean,jpeg60,jpeg40,resize64,blur1','--workers','0','--output',base/('generation-external-'+key)])
    for key,checkpoint in [('original',HERE/'artifacts/model_finetuned.pt'),('selected',Path(chosen_photo['checkpoint']))]:
        run('photo-external-'+key,'evaluate_photo_supervision.py',['--checkpoint',checkpoint,'--manifest',exam,
            '--split','external_test','--output',base/('photo-external-'+key)])
        run('photo-test-'+key,'evaluate_photo_supervision.py',['--checkpoint',checkpoint,'--manifest',photo_manifest,
            '--split','test','--output',base/('photo-test-'+key)])
    run('sparse-video','check_sparse_video.py',['--output',base/'sparse-video'])
    run('video-test-report','calibrate_video_review.py',['--validation',base/'video-val','--test',base/'video-test','--output',base/'video-policy'])
    save_json(base/'suite-progress.json',dict(stage='complete',status='complete',utc=datetime.now(timezone.utc).isoformat(),
        note='No candidate or threshold was reselected from external outcomes.'))
    print('All locked evaluations complete.',flush=True)


if __name__=='__main__':main()
