"""Controlled short-splice regression clips: same re-encoding for real controls and altered clips."""
from project_io import resolve_data_path, data_location
import argparse
from collections import defaultdict
import csv
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

from project_io import HERE,PROJECT,digest,save_json


def prepare(output):
    protocol_path=output/'PROTOCOL.json'
    if protocol_path.is_file():return json.loads(protocol_path.read_text(encoding='utf-8'))
    with (resolve_data_path(PROJECT/'data/manifests/ffpp-frames-full-93e2b370610e.csv')).open(encoding='utf-8-sig',newline='') as stream:
        rows=[r for r in csv.DictReader(stream) if r['split']=='test']
    originals={r['target_id']:r['source_video'] for r in rows if r['label']=='0'}
    unique={r['parent_video_id']:r for r in rows if r['label']=='1'}
    groups=defaultdict(list)
    for row in unique.values():groups[row['method']].append(row)
    selected=[]
    for method,group in sorted(groups.items()):
        group.sort(key=lambda r:hashlib.sha256(('short-splice-v1:'+r['parent_video_id']).encode()).hexdigest())
        selected+=group[:2]
    clips=[];excluded=[];cv2.setNumThreads(1)
    for row in selected:
        fake_path=resolve_data_path(PROJECT/row['source_video'])
        # FF++ method naming alone does not establish which original supplies the visible scene.
        # Choose only a geometrically matching original whose pixels align, before any model scores.
        matches=[]
        for original_id in (row['target_id'],row['source_id']):
            candidate=resolve_data_path(PROJECT/originals[original_id])
            a=cv2.VideoCapture(str(candidate));b=cv2.VideoCapture(str(fake_path));errors=[]
            for index in (0,12,24):
                a.set(cv2.CAP_PROP_POS_FRAMES,index);b.set(cv2.CAP_PROP_POS_FRAMES,index)
                oka,fa=a.read();okb,fb=b.read()
                if not oka or not okb or fa.shape!=fb.shape:break
                aa=cv2.resize(fa,(128,128)).astype(np.float32);bb=cv2.resize(fb,(128,128)).astype(np.float32)
                errors.append(float(np.abs(aa-bb).mean()/255))
            a.release();b.release()
            if len(errors)==3:matches.append((float(np.mean(errors)),candidate))
        matches.sort(key=lambda item:item[0])
        if not matches or matches[0][0]>.15 or (len(matches)>1 and matches[0][0]>.8*matches[1][0]):
            excluded.append(dict(video_id=row['parent_video_id'],reason='Original-scene alignment is absent or ambiguous',errors=[m[0] for m in matches]))
            continue
        alignment_error,real_path=matches[0]
        real=cv2.VideoCapture(str(real_path));fake=cv2.VideoCapture(str(fake_path))
        fps=real.get(cv2.CAP_PROP_FPS);frames=min(int(real.get(cv2.CAP_PROP_FRAME_COUNT)),int(fake.get(cv2.CAP_PROP_FRAME_COUNT)),int(fps*10))
        if not 1<=fps<=120 or frames<fps*2:raise ValueError('Unexpected source video length/FPS')
        width=int(real.get(cv2.CAP_PROP_FRAME_WIDTH));height=int(real.get(cv2.CAP_PROP_FRAME_HEIGHT))
        writers=[];records=[]
        for seconds in (0.,.4,.8):
            name=row['parent_video_id']+('_real_control' if not seconds else f'_splice_{seconds:.1f}s')
            path=output/(name+'.mp4');temporary=output/(name+'.part.mp4')
            writer=cv2.VideoWriter(str(temporary),cv2.VideoWriter_fourcc(*'mp4v'),fps,(width,height))
            if not writer.isOpened():raise ValueError('Cannot encode test clip')
            amount=round(fps*seconds);start=min(frames-amount-1,int(.4*frames));end=start+amount
            records.append(dict(id=name,path=str(path.resolve()),label=int(seconds>0),method=row['method'],
                event_start_frame=start if amount else None,event_end_frame=end if amount else None,
                event_start_seconds=start/fps if amount else None,event_end_seconds=end/fps if amount else None,
                duration_seconds=frames/fps,source_video=row['parent_video_id'],
                matched_real_source=str(real_path),alignment_mean_absolute_error=alignment_error,
                real_source_sha256=digest(real_path),fake_source_sha256=digest(fake_path)))
            writers.append((writer,path,temporary,start,end,amount))
        try:
            for index in range(frames):
                ok0,frame0=real.read();ok1,frame1=fake.read()
                if not ok0 or not ok1 or frame0.shape!=frame1.shape:raise ValueError('Source alignment/decode failed')
                for writer,path,temporary,start,end,amount in writers:
                    writer.write(frame1 if amount and start<=index<end else frame0)
        finally:
            for writer,*_ in writers:writer.release()
            real.release();fake.release()
        for _,path,temporary,*_ in writers:temporary.replace(path)
        clips+=records;print('Prepared control and two short splices:',row['parent_video_id'],flush=True)
    protocol=dict(selection='Fixed hash, 2 test videos per FF++ method, NOT selected by predictions; exclude scene-misaligned originals explicitly',clips=clips,excluded=excluded,
        codec='mp4v, original dimensions/FPS, first <=10 seconds; real controls use exactly same re-encoding',
        ground_truth='Only the scheduled interval is replaced by matching FF++ altered-video frames; frame-level true edit region not manually annotated',
        use='Constructed regression stress check, not new independent cross-dataset evidence; never used to change locked policy')
    save_json(protocol_path,protocol);return protocol


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=resolve_data_path,required=True)
    parser.add_argument('--prepare-only',action='store_true')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    protocol=prepare(args.output)
    if args.prepare_only:return
    import torch
    from core import Predictor
    torch.set_num_threads(2)
    predictor=Predictor(device='cuda');results=[]
    for clip in protocol['clips']:
        result=predictor.predict(clip['path'],adaptive_video=True)
        save_json(args.output/(clip['id']+'_result.json'),result)
        baseline=result['legacy_baseline']['decision']=='suspected_manipulation'
        review=result['temporal_review']['decision']=='review_alerts'
        overlaps=None
        if clip['label']:
            overlaps=any(w['start_seconds']<=clip['event_end_seconds'] and w['end_seconds']>=clip['event_start_seconds'] for w in result['review_windows'])
        results.append(dict(clip,legacy_alert=baseline,local_alert=review,local_window_overlaps_planned_event=overlaps,
            local_score=result['temporal_review']['score'],sampled_frames=result['sampled_frames']))
        save_json(args.output/'scores.json',results)
        print(dict(done=len(results),total=len(protocol['clips']),baseline=baseline,local=review,overlaps=overlaps),flush=True)
    save_json(args.output/'summary.json',dict(n=len(results),results=results,policy_unchanged=True))


if __name__=='__main__':main()
