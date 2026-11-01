"""Separate generation/manipulation results, including each detected photo face."""
from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageOps
import torch

from .core import Predictor, detect_face_crops, digest, image_transform, load_detector, score_images
from .generation_common import canonical_face
from faceguard.model_registry import checked_resource

PHOTO_SUFFIXES = ('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tif', '.tiff')


class GenerationPredictor:
    def __init__(self, checkpoint=None, device=None):
        self.device = device or ('cuda' if torch.cuda.is_available() else 'cpu')
        path = Path(checkpoint) if checkpoint else checked_resource('generation.pt')
        if not path.is_file():
            raise FileNotFoundError('整脸生成模型尚未准备好，请按项目 README 准备正式模型。')
        self.model, self.head, self.state = load_detector(path, self.device)
        self.model_sha256=digest(path)
        if self.state.get('task') != 'whole_face_generation':
            raise ValueError('此权重不属于整脸生成模型')
        weight = checked_resource('yunet.onnx')
        if digest(weight) != self.state['yunet_sha256']:
            raise ValueError('YuNet 权重与训练预处理不匹配')
        self.detector = cv2.FaceDetectorYN.create(str(weight), '', (320, 320), .8, .3, 5000)
        self.transform = image_transform()

    @torch.inference_mode()
    def predict(self, path, face_crop=False, progress=None):
        path = Path(path).resolve()
        if path.suffix.lower() not in PHOTO_SUFFIXES:
            raise ValueError('整脸生成检测目前支持照片；视频请使用换脸/篡改检测。')
        if progress:
            progress('reading_image', 0, 1)
        with Image.open(path) as source:
            image = ImageOps.exif_transpose(source).convert('RGB')
            if face_crop:
                detected, count = [dict(face_id=1, bbox=None, image=image)], 1
            else:
                detected, count = detect_face_crops(cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR), self.detector)
        result = dict(path=str(path), media_type='image', task='whole_face_generation',
            faces=len(detected), detected_faces=count, unanalysed_faces=count - len(detected),
            sampled_frames=1, no_face_frames=int(not detected),
            scope='Experimental whole-face generation detector; uncalibrated; see experiment report for evaluation scope',
            training_generators=self.state['training_generators'])
        result['model_sha256']=self.model_sha256
        if not detected:
            return dict(result, decision='no_face', score=None, face_results=[])
        if progress:
            progress('inference', 0, 1)
        scores = score_images(self.model, self.head, self.transform,
                              [canonical_face(row['image']) for row in detected], self.device)
        threshold = self.state['frame_threshold']
        records = []
        for row, value in zip(detected, scores):
            record = {key: value for key, value in row.items() if key != 'image'}
            record.update(score=value, threshold=threshold,
                          decision='suspected_generation' if value >= threshold else 'no_generation_detected')
            records.append(record)
        if len(records) > 1:
            return dict(result, decision='multiple_face_results', score=None, frame_scores=scores, face_results=records,
                        aggregation='No image-level threshold is calibrated for multiple faces; inspect each result.')
        return dict(result, decision=records[0]['decision'], score=scores[0], threshold=threshold,
                    frame_scores=scores, face_results=records)


class FaceAnalyzer:
    def __init__(self, device=None, generation_checkpoint=None, photo_checkpoint=None):
        self.device = device
        self.generation_checkpoint, self.photo_checkpoint = generation_checkpoint, photo_checkpoint
        self.generation, self.manipulation = None, None
        self.photo_manipulation = None

    def predict(self, path, face_crop=False, progress=None, task='auto', video_sampling='adaptive'):
        is_photo = Path(path).suffix.lower() in PHOTO_SUFFIXES
        if task == 'auto':
            task = 'both' if is_photo else 'manipulation'
        if task == 'both':
            if not is_photo:
                raise ValueError('双项检测目前只支持照片；视频使用人脸篡改检测。')
            # Each head keeps its own threshold and score. There is no calibrated combined probability.
            results, errors = {}, {}
            for name in ('generation', 'manipulation'):
                try:
                    results[name] = self.predict(path, face_crop, progress, task=name)
                except (OSError, ValueError, RuntimeError) as exc:
                    errors[name] = str(exc)
            if not results:
                raise ValueError('两项检测均未完成：' + str(errors))
            reference = next(iter(results.values()))
            return dict(path=str(Path(path).resolve()), media_type='image', task='photo_dual', score=None,
                        decision='partial_results' if errors else ('no_face' if all(r['decision'] == 'no_face' for r in results.values()) else 'separate_results'),
                        faces=reference['faces'], sampled_frames=1, no_face_frames=reference['no_face_frames'],
                        detected_faces=reference.get('detected_faces', reference['faces']),
                        unanalysed_faces=reference.get('unanalysed_faces', 0),
                        results=results, errors=errors,
                        scope='Two experimental tasks; inspect each face and task separately. No joint false-positive calibration.')
        if task == 'generation':
            if not is_photo:
                raise ValueError('此项目用于照片。请将上方「检测项目」切换为「自动」或「换脸 / 篡改」。')
            if self.generation is None:
                self.generation = GenerationPredictor(checkpoint=self.generation_checkpoint,device=self.device)
            return self.generation.predict(path, face_crop=face_crop, progress=progress)
        if task != 'manipulation':
            raise ValueError('Unknown detection task')
        if is_photo and self.photo_checkpoint:
            if self.photo_manipulation is None:
                self.photo_manipulation=PhotoManipulationPredictor(self.photo_checkpoint,self.device)
            result=self.photo_manipulation.predict(path,face_crop=face_crop,progress=progress)
            result['task']='face_manipulation'
            return result
        if self.manipulation is None:
            self.manipulation = Predictor(device=self.device)
        if not is_photo and video_sampling not in ('legacy', 'adaptive'):
            raise ValueError('Unknown video sampling method')
        result = self.manipulation.predict(path, face_crop=face_crop, progress=progress,
                                          **({'adaptive_video': video_sampling == 'adaptive'} if not is_photo else {}))
        result['task'] = 'face_manipulation'
        return result


class PhotoManipulationPredictor(Predictor):
    """Explicit opt-in candidate; stable video model is kept separate."""
    def __init__(self,checkpoint,device=None):
        super().__init__(checkpoint,device)
        if self.state.get('task') not in ('photo_manipulation_research','photo_manipulation_calibrated') or self.state.get('preprocessing') not in ('photo128_jpeg90','manipulation256'):
            raise ValueError('此权重不属于照片局部修改监督实验')
        base=image_transform()
        self.transform=(lambda image:base(canonical_face(image))) if self.state['preprocessing']=='photo128_jpeg90' else base

    def predict(self,path,face_crop=False,progress=None):
        if Path(path).suffix.lower() not in PHOTO_SUFFIXES:
            raise ValueError('照片实验模型不用于视频')
        result=super().predict(path,face_crop=face_crop,progress=progress)
        result.pop('photo_validation',None)
        result['scope']='Opt-in research photo manipulation model; validation uses FF++ frames and limited ordinary-photo sources. No independent broad photo-forgery benchmark.'
        result['experimental_photo_model']=True
        result['model_sha256']=self.model_sha256
        result['map_scope']=self.state['mask_scope']
        return result
