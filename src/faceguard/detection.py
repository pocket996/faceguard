"""Qt worker and presentation helpers for the independent inference package."""
import threading
import math
from pathlib import Path
from datetime import datetime, timedelta, timezone
from PySide6.QtCore import QThread, Signal

from faceguard.inference.inference_control import InferenceCancelled


class DetectionWorker(QThread):
    progress = Signal(str, int, int)
    completed = Signal(dict)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, path, task='auto', analyzer=None, generation_profile='stable'):
        super().__init__()
        self.path, self.task, self.analyzer = path, task, analyzer
        self.generation_profile = generation_profile
        self.cancel_event = threading.Event()

    def cancel(self):
        self.cancel_event.set()

    def check_cancel(self):
        if self.cancel_event.is_set():
            raise InferenceCancelled()

    def report(self, stage, done, total):
        self.check_cancel()
        self.progress.emit(stage, done, total)

    def run(self):
        try:
            self.report('loading_models', 0, 0)
            if self.analyzer is None:
                import cv2
                import torch
                from faceguard.inference.face_analysis import FaceAnalyzer
                from faceguard.model_registry import checked_generation_profile
                torch.set_num_threads(2)
                cv2.setNumThreads(1)
                self.analyzer = FaceAnalyzer(generation_checkpoint=checked_generation_profile(self.generation_profile))
            self.check_cancel()
            before = Path(self.path).stat()
            result = self.analyzer.predict(self.path, task=self.task, progress=self.report)
            from faceguard.model_registry import generation_profiles
            profile = next(p for p in generation_profiles() if p['id'] == self.generation_profile)
            result['generation_model_profile'] = profile['id']
            generation = result.get('results', {}).get('generation')
            if generation is None and result.get('task') == 'whole_face_generation':
                generation = result
            if generation is not None:
                generation['model_label'] = profile['label']
            after = Path(self.path).stat()
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise ValueError('文件在检测期间发生变化，请重新选择。')
            result['source_signature'] = dict(size=before.st_size, mtime_ns=before.st_mtime_ns)
            result['detected_at_beijing'] = datetime.now(timezone(timedelta(hours=8))).isoformat()
            self.check_cancel()
            self.completed.emit(result)
        except InferenceCancelled:
            self.cancelled.emit()
        except Exception as error:
            self.failed.emit(str(error))


class DetailPreviewWorker(QThread):
    ready = Signal(str, str)
    failed = Signal(str)
    heatmapReady = Signal(str, dict)
    heatmapFailed = Signal(str)

    def __init__(self, source, record, destination, explain=False, generation_profile='stable', source_signature=None):
        super().__init__()
        self.source, self.record, self.destination = source, record, Path(destination)
        self.explain, self.generation_profile = explain, generation_profile
        self.source_signature = source_signature
        self.cancel_event = threading.Event()

    def cancel(self):
        self.cancel_event.set()

    def check_cancel(self):
        if self.cancel_event.is_set():
            raise InferenceCancelled()

    def check_source(self):
        self.check_cancel()
        if self.source_signature is not None:
            stat = Path(self.source).stat()
            if self.source_signature != dict(size=stat.st_size, mtime_ns=stat.st_mtime_ns):
                raise ValueError('原文件已变化，请重新检测。')

    def run(self):
        try:
            self.check_source()
            from PIL import Image, ImageOps
            if self.record['frame_index'] >= 0:
                import cv2
                capture = cv2.VideoCapture(self.source)
                try:
                    if not capture.isOpened() or not capture.set(cv2.CAP_PROP_POS_FRAMES, self.record['frame_index']):
                        raise ValueError('无法读取该视频采样帧')
                    ok, frame = capture.read()
                    if not ok:
                        raise ValueError('视频采样帧无法解码')
                    actual = capture.get(cv2.CAP_PROP_POS_FRAMES) - 1
                    if not math.isfinite(actual) or abs(actual - self.record['frame_index']) > .5:
                        raise ValueError('视频后端未能定位到对应采样帧')
                    image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                finally:
                    capture.release()
            else:
                with Image.open(self.source) as original:
                    image = ImageOps.exif_transpose(original).convert('RGB')
            self.destination.parent.mkdir(parents=True, exist_ok=True)
            face = image.crop(self.record['bbox']) if self.record.get('bbox') else image.copy()
            face.thumbnail((1000, 1000))
            face.save(self.destination, format='PNG')
            frame_path = self.destination.with_name(self.destination.stem + '-frame.png')
            preview = image.copy()
            preview.thumbnail((2000, 2000))
            preview.save(frame_path, format='PNG')
            self.check_source()
            self.ready.emit(str(self.destination), str(frame_path))
            if self.explain:
                try:
                    from .inference.heatmaps import explain_face, render_overlay
                    payload = explain_face(image, self.record, self.generation_profile, self.check_cancel)
                    self.check_source()
                    overlay = render_overlay(payload, image.size, self.record.get('bbox'), output_size=preview.size)
                    heatmap_path = self.destination.with_name(self.destination.stem + '-heatmap.png')
                    overlay.save(heatmap_path, format='PNG')
                    self.check_source()
                    self.heatmapReady.emit(str(heatmap_path), payload)
                except InferenceCancelled:
                    raise
                except Exception as error:
                    self.heatmapFailed.emit(str(error))
        except InferenceCancelled:
            pass
        except Exception as error:
            self.failed.emit(str(error))


VERDICTS = {
    'suspected_generation': '疑似 AI 整脸生成',
    'no_generation_detected': '未检出明显生成特征',
    'suspected_manipulation': '疑似换脸 / 面部篡改',
    'no_manipulation_detected': '未检出明显篡改特征',
    'no_face': '未找到人脸，无法判断',
    'multiple_face_results': '多张人脸，请逐脸查看',
}


def task_state(result, task):
    """Presentation tone follows actual decisions, including multi-face alerts."""
    if not result:
        return 'idle'
    if task in result.get('errors', {}):
        return 'unavailable'
    if result.get('media_type') == 'video':
        if task == 'generation':
            return 'unavailable'
        item = result.get('legacy_baseline', result)
        if result.get('temporal_review', {}).get('decision') == 'review_alerts':
            return 'attention'
    else:
        item = result.get('results', {}).get(task)
        if item is None:
            expected = 'whole_face_generation' if task == 'generation' else 'face_manipulation'
            item = result if result.get('task') == expected else {}
    decision = item.get('decision', '')
    if decision.startswith('suspected_') or any(f.get('decision', '').startswith('suspected_') for f in item.get('face_results', [])):
        return 'attention'
    if decision in {'no_generation_detected', 'no_manipulation_detected'}:
        return 'clear'
    return 'unavailable'


def task_summary(result, task):
    if not result:
        return '等待检测'
    if task in result.get('errors', {}):
        return '检测未完成，请查看详情'
    if result.get('media_type') == 'video':
        if task == 'generation':
            return '视频暂不支持此项'
        item = result.get('legacy_baseline', result)
        if result.get('temporal_review', {}).get('decision') == 'review_alerts' and item.get('decision') != 'suspected_manipulation':
            return '局部片段需复核'
    else:
        item = result.get('results', {}).get(task)
        if item is None:
            expected = 'whole_face_generation' if task == 'generation' else 'face_manipulation'
            item = result if result.get('task') == expected else None
        if item is None:
            return '本次未运行此项'
    return VERDICTS.get(item['decision'], '请查看详细结果')


def detail_records(result):
    if not result:
        return []
    records = []
    if result.get('media_type') == 'video':
        for observation in result.get('observations', []):
            seconds = observation.get('seconds')
            frame = observation['frame_index']
            prefix = f'{seconds:.2f} 秒' if seconds is not None else f'帧 {frame}'
            for face in observation['faces']:
                records.append(dict(title=f'{prefix} · 人脸 #{face["face_id"]}',
                                    text=f'{VERDICTS.get(face["decision"], face["decision"])}\n模型分 {face["score"]:.4f} · 阈值 {face["threshold"]:.4f}',
                                    bbox=face['bbox'], frame_index=frame, task='manipulation',
                                    face_id=face['face_id'], score=face['score'],
                                    inference_device=result.get('inference_device'),
                                    model_sha256=result.get('model_sha256'), heatmap=face.get('heatmap')))
    else:
        tasks = result.get('results', {('generation' if result.get('task') == 'whole_face_generation' else 'manipulation'): result})
        for task, item in tasks.items():
            label = '生成' if task == 'generation' else '篡改'
            for face in item.get('face_results', []):
                records.append(dict(title=f'{label} · 人脸 #{face["face_id"]}',
                                    text=f'{VERDICTS.get(face["decision"], face["decision"])}\n模型分 {face["score"]:.4f} · 阈值 {face["threshold"]:.4f}',
                                    bbox=face.get('bbox'), frame_index=-1, task=task,
                                    face_id=face['face_id'], score=face['score'],
                                    inference_device=item.get('inference_device'),
                                    model_sha256=item.get('model_sha256'), heatmap=face.get('heatmap')))
    return records


def store_detail_heatmap(result, record, payload):
    """Persist only the selected face/task/frame, without changing its verdict."""
    if record['frame_index'] >= 0:
        faces = next(row['faces'] for row in result['observations']
                     if row['frame_index'] == record['frame_index'])
    else:
        item = result.get('results', {}).get(record['task'], result)
        faces = item['face_results']
    face = next(face for face in faces if face['face_id'] == record['face_id'])
    face['heatmap'] = payload
