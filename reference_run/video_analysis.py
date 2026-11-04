"""Bounded coarse coverage + local refinement, with explicitly exploratory per-face alerts."""
import math
import json

import cv2
import numpy as np

from core import HERE,detect_face_crops, score_images


def coarse_targets(frame_count, fps, minimum=48, maximum=96):
    if frame_count < 1:
        raise ValueError('Invalid video frame count')
    legacy = set(np.linspace(0, frame_count - 1, min(16, frame_count), dtype=int).tolist())
    desired = max(minimum, math.ceil(frame_count / fps * 2) + 1) if fps else minimum
    # Include legacy indices exactly for a comparable, unchanged baseline.
    count = min(frame_count, max(1, min(maximum - len(legacy), desired)))
    targets = legacy | set(np.linspace(0, frame_count - 1, count, dtype=int).tolist())
    return sorted(targets), legacy


def refinement_targets(frame_count, fps, observations, threshold, budget=48):
    covered = {r['frame_index'] for r in observations}
    if len(covered) < 2 or budget <= 0:
        return []
    gaps = np.diff(sorted(covered))
    gap = max(1, int(np.median(gaps)))
    candidates = sorted((r for r in observations if any(f['score'] >= threshold - .15 for f in r['faces'])),
                        key=lambda r: (-max(f['score'] for f in r['faces']), r['frame_index']))
    targets = []
    # Round-robin offsets avoid spending the entire budget on just the highest frame.
    for multiplier in (-.25, .25, -.5, .5, -.75, .75):
        for row in candidates:
            target = int(round(row['frame_index'] + multiplier * gap))
            if 0 <= target < frame_count and target not in covered:
                covered.add(target)
                targets.append(target)
                if len(targets) >= budget:
                    return sorted(targets)
    return sorted(targets)


def spatial_tracks(observations, fps):
    """Short-lived IoU associations, not facial identity recognition."""
    active, next_id = {}, 1
    def iou(a, b):
        intersection = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
        return intersection / max(1, (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - intersection)
    for row in sorted(observations, key=lambda r: r['frame_index']):
        index, used = row['frame_index'], set()
        for face in row['faces']:
            matches = [(iou(face['bbox'], state[1]), track) for track, state in active.items()
                       if track not in used and index - state[0] <= (3 * fps if fps else 90)]
            match = max(matches, default=(0, 0))
            if match[0] >= .3:
                track = match[1]
            else:
                track, next_id = next_id, next_id + 1
            face['track_id'] = track
            active[track] = (index, face['bbox'])
            used.add(track)


def review_windows(observations, fps, threshold):
    if not fps:
        return []
    windows = []
    for row in sorted(observations, key=lambda r: r['frame_index']):
        flagged = [f for f in row['faces'] if f['score'] >= threshold]
        if not flagged:
            continue
        center = row['frame_index'] / fps
        start, end = max(0., center - .5), center + .5
        if windows and start <= windows[-1]['end_seconds']:
            window = windows[-1]
            window['end_seconds'] = end
            window['evidence_frames'].append(row['frame_index'])
            window['peak_score'] = max(window['peak_score'], max(f['score'] for f in flagged))
            window['track_ids'] = sorted(set(window['track_ids']) | {f['track_id'] for f in flagged})
        else:
            windows.append(dict(start_seconds=start, end_seconds=end,
                                peak_score=max(f['score'] for f in flagged), evidence_frames=[row['frame_index']],
                                track_ids=sorted({f['track_id'] for f in flagged})))
    return windows


def temporal_pairs(result, max_gap_seconds=1.5):
    tracks = {}
    for row in result['observations']:
        for face in row['faces']:
            tracks.setdefault(face['track_id'], []).append((row['frame_index'], face['score']))
    pairs = []
    for track, observations in tracks.items():
        for a, b in zip(observations, observations[1:]):
            if result['fps'] and (b[0] - a[0]) / result['fps'] <= max_gap_seconds:
                pairs.append(dict(track_id=track, first_frame=a[0], last_frame=b[0], score=(a[1]+b[1])/2))
    return pairs


def temporal_alert_score(result, max_gap_seconds=1.5):
    return max((p['score'] for p in temporal_pairs(result,max_gap_seconds)),default=None)


def load_review_policy(model_sha256):
    path=HERE/'artifacts/video_review/policy.json'
    try:
        policy=json.loads(path.read_text(encoding='utf-8'))
        if policy['algorithm']!='adjacent_pair_mean_v1' or policy['model_sha256']!=model_sha256:
            return None
        if not 0<=policy['threshold']<=1.0000000001 or policy['max_gap_seconds']!=1.5:
            return None
        return policy
    except (OSError,ValueError,KeyError,TypeError):
        return None


def calibrated_windows(pairs, threshold, fps, duration):
    windows=[]
    for pair in sorted((p for p in pairs if p['score']>=threshold),key=lambda p:p['first_frame']):
        start=max(0.,pair['first_frame']/fps-.25);end=min(duration,pair['last_frame']/fps+.25)
        if windows and start<=windows[-1]['end_seconds']:
            window=windows[-1];window['end_seconds']=max(window['end_seconds'],end)
            window['evidence_frames']=sorted(set(window['evidence_frames'])|{pair['first_frame'],pair['last_frame']})
            window['track_ids']=sorted(set(window['track_ids'])|{pair['track_id']})
            window['peak_score']=max(window['peak_score'],pair['score'])
        else:
            windows.append(dict(start_seconds=start,end_seconds=end,evidence_frames=[pair['first_frame'],pair['last_frame']],
                                track_ids=[pair['track_id']],peak_score=pair['score']))
    return windows


def analyze_video(predictor, path, progress=None):
    capture = cv2.VideoCapture(str(path))
    try:
        if not capture.isOpened():
            raise ValueError('Cannot open video')
        count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        raw_fps = float(capture.get(cv2.CAP_PROP_FPS))
        fps = raw_fps if math.isfinite(raw_fps) and .1 <= raw_fps <= 240 else None
        initial, legacy_indices = coarse_targets(count, fps)
        observations = []
        frame_threshold = float(predictor.state['frame_threshold'])
        def sample(targets, phase):
            for step, index in enumerate(targets):
                if not capture.set(cv2.CAP_PROP_POS_FRAMES, index):
                    raise ValueError('Video backend cannot seek accurately')
                ok, frame = capture.read()
                if not ok:
                    raise ValueError(f'Video sample {index} could not decode')
                actual = capture.get(cv2.CAP_PROP_POS_FRAMES) - 1
                if not math.isfinite(actual) or abs(actual - index) > .5:
                    raise ValueError('Video frame seeking position is inconsistent')
                detected, total = detect_face_crops(frame, predictor.detector)
                scores = score_images(predictor.model, predictor.head, predictor.transform,
                                      [r['image'] for r in detected], predictor.device) if detected else []
                faces = []
                for record, value in zip(detected, scores):
                    face = {k: v for k, v in record.items() if k != 'image'}
                    face.update(score=float(value), threshold=frame_threshold,
                                decision='suspected_manipulation' if value >= frame_threshold else 'no_manipulation_detected')
                    faces.append(face)
                observations.append(dict(frame_index=index, seconds=index / fps if fps else None,
                    phase=phase, detected_faces=total, unanalysed_faces=total-len(faces), faces=faces))
                if progress:
                    progress('video_' + phase, step + 1, len(targets))
        sample(initial, 'coverage')
        extra = refinement_targets(count, fps, observations, frame_threshold)
        sample(extra, 'refinement')
    finally:
        capture.release()
    observations.sort(key=lambda row: row['frame_index'])
    spatial_tracks(observations, fps)
    duration = count / fps if fps else None
    legacy_scores = [r['faces'][0]['score'] for r in observations if r['frame_index'] in legacy_indices and r['faces']]
    legacy_score = float(np.mean(legacy_scores)) if legacy_scores else None
    video_threshold = float(predictor.state['video_threshold'])
    baseline = dict(score=legacy_score, threshold=video_threshold, sampled_frames=len(legacy_indices),
                    decision='no_face' if legacy_score is None else ('suspected_manipulation' if legacy_score >= video_threshold else 'no_manipulation_detected'))
    seen_faces = sum(len(r['faces']) for r in observations)
    flagged = any(f['score'] >= frame_threshold for row in observations for f in row['faces'])
    gaps = np.diff([r['frame_index'] for r in observations])
    result = dict(path=str(path), media_type='video', task='face_manipulation', sampling='adaptive_review',
        score=None, decision='no_face' if not seen_faces else 'video_results',raw_frame_alert=flagged,
        faces=seen_faces, face_frames=sum(bool(r['faces']) for r in observations),
        sampled_frames=len(observations), no_face_frames=sum(not r['faces'] for r in observations),
        unanalysed_faces=sum(r['unanalysed_faces'] for r in observations),
        fps=fps, duration_seconds=duration, coarse_frames=len(initial), refined_frames=len(extra),
        max_sample_gap_seconds=float(max(gaps, default=0) / fps) if fps else None,
        legacy_baseline=baseline, review_windows=[], observations=observations,
        scope='Exploratory per-frame review alerts, not a newly calibrated video verdict. Scores are not probabilities.',
        limitations=['Short events between samples can still be missed',
                     'More faces and frames increase false alerts; image/video-level error rate is not calibrated',
                     'IoU track IDs are temporary spatial associations and can swap at cuts or crossings',
                     'Timestamps use nominal FPS; variable-frame-rate and decoder metadata may be approximate',
                     'Coverage budget is capped at 96 coarse + 48 refined frames; not full-video temporal analysis'])
    policy=load_review_policy(getattr(predictor,'model_sha256',None))
    pairs=temporal_pairs(result)
    value=max((p['score'] for p in pairs),default=None)
    result['temporal_review']=dict(score=value,policy_available=policy is not None,
        threshold=policy['threshold'] if policy else None,
        decision='unavailable' if value is None or policy is None else ('review_alerts' if value>=policy['threshold'] else 'no_review_alerts'))
    if policy is not None:
        result['review_policy']=policy
        if fps and pairs:
            result['review_windows']=calibrated_windows(pairs,policy['threshold'],fps,duration)
    return result
