"""Video frame generation evidence must stay separate from manipulation verdicts."""
import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from faceguard.detection import detail_records, store_detail_heatmap, task_state, task_summary
from faceguard.inference.face_analysis import FaceAnalyzer, GenerationPredictor
from faceguard.inference.generation_common import canonical_face
from faceguard.inference.inference_control import InferenceCancelled
from faceguard.inference.result_text import result_lines
from faceguard.inference.video_analysis import analyze_video


class Capture:
    def __init__(self, count=300):
        self.count, self.position, self.released = count, 0, False

    def isOpened(self):
        return True

    def get(self, key):
        return {cv2.CAP_PROP_FRAME_COUNT: self.count, cv2.CAP_PROP_FPS: 25,
                cv2.CAP_PROP_POS_FRAMES: self.position}[key]

    def set(self, key, value):
        self.position = value
        return True

    def read(self):
        self.position += 1
        return True, np.zeros((256, 256, 3), dtype=np.uint8)

    def release(self):
        self.released = True


class VideoGenerationTests(unittest.TestCase):
    def setUp(self):
        self.predictor = GenerationPredictor.__new__(GenerationPredictor)
        self.predictor.device, self.predictor.model_sha256 = 'cpu', 'generation-hash'
        self.predictor.state = dict(frame_threshold=.7, training_generators=['fixture'])
        self.predictor.model = self.predictor.head = self.predictor.transform = self.predictor.detector = None
        image = Image.fromarray(np.random.default_rng(9).integers(0, 255, (256, 256, 3), dtype=np.uint8))
        self.faces = [dict(face_id=i, bbox=[0, 0, 256, 256], image=image) for i in (1, 2)]

    def run_video(self, *, no_face=False, progress=None, sampling='adaptive'):
        capture = Capture()
        with patch('faceguard.inference.video_analysis.cv2.VideoCapture', return_value=capture), \
             patch('faceguard.inference.video_analysis.detect_face_crops', return_value=([], 0) if no_face else (self.faces, 2)), \
             patch('faceguard.inference.video_analysis.score_images', return_value=[.1, .9]) as score, \
             patch('faceguard.inference.video_analysis.load_review_policy', side_effect=AssertionError('manipulation policy must never run')):
            result = self.predictor.predict('fixture.mp4', progress=progress, video_sampling=sampling)
            if not no_face:
                np.testing.assert_array_equal(np.asarray(score.call_args.args[3][0]), np.asarray(canonical_face(self.faces[0]['image'])))
        self.assertTrue(capture.released)
        return result

    def test_bounded_sampling_keeps_each_face_and_photo_preprocessing(self):
        result = self.run_video()
        self.assertLessEqual(result['sampled_frames'], 144)
        self.assertGreater(result['sampled_frames'], 16)
        self.assertIsNone(result['score'])
        self.assertNotIn('legacy_baseline', result)
        self.assertNotIn('temporal_review', result)
        self.assertNotIn('threshold', result)
        self.assertEqual(result['model_sha256'], 'generation-hash')
        self.assertEqual([f['decision'] for f in result['observations'][0]['faces']],
                         ['no_generation_detected', 'suspected_generation'])
        self.assertEqual(task_state(result, 'generation'), 'attention')
        self.assertEqual(task_state(result, 'manipulation'), 'unavailable')
        self.assertIn('采样人脸', task_summary(result, 'generation'))

    def test_no_face_and_legacy_sampler_are_explicit(self):
        result = self.run_video(no_face=True, sampling='legacy')
        self.assertEqual(result['sampled_frames'], 16)
        self.assertEqual(result['refined_frames'], 0)
        self.assertEqual(result['decision'], 'no_face')
        self.assertEqual(task_state(result, 'generation'), 'unavailable')
        self.assertIn('未找到人脸', '\n'.join(result_lines(result)))

    def test_cancel_propagates_and_releases_decoder(self):
        capture = Capture()
        with patch('faceguard.inference.video_analysis.cv2.VideoCapture', return_value=capture), \
             patch('faceguard.inference.video_analysis.detect_face_crops', return_value=([], 0)):
            with self.assertRaises(InferenceCancelled):
                self.predictor.predict('fixture.mp4', progress=Mock(side_effect=InferenceCancelled))
        self.assertTrue(capture.released)

    def test_auto_dual_preserves_each_task_and_partial_failure(self):
        generation = self.run_video(sampling='legacy')
        manipulation = dict(media_type='video', task='face_manipulation', faces=1, sampled_frames=16,
                            no_face_frames=0, decision='video_results',
                            legacy_baseline=dict(decision='no_manipulation_detected'), observations=[])
        analyzer = FaceAnalyzer()
        analyzer.generation = Mock(predict=Mock(return_value=generation))
        analyzer.manipulation = Mock(predict=Mock(return_value=manipulation))
        result = analyzer.predict('fixture.mp4', video_sampling='legacy')
        self.assertEqual(set(result['results']), {'generation', 'manipulation'})
        self.assertEqual(result['task'], 'video_dual')
        self.assertEqual(task_state(result, 'manipulation'), 'clear')
        self.assertEqual(task_state(result, 'generation'), 'attention')
        self.assertEqual(analyzer.generation.predict.call_args.kwargs['video_sampling'], 'legacy')
        analyzer.generation.predict.side_effect = ValueError('missing generation weights')
        partial = analyzer.predict('fixture.mp4')
        self.assertEqual(partial['decision'], 'partial_results')
        self.assertEqual(task_state(partial, 'generation'), 'unavailable')
        self.assertIn('未完成', task_summary(partial, 'generation'))
        analyzer.generation.predict.side_effect = InferenceCancelled
        with self.assertRaises(InferenceCancelled):
            analyzer.predict('fixture.mp4')

    def test_dual_history_maps_stay_in_their_task_and_frame(self):
        generation = self.run_video(sampling='legacy')
        manipulation = copy.deepcopy(generation)
        manipulation['task'], manipulation['model_sha256'] = 'face_manipulation', 'other-hash'
        result = dict(media_type='video', results=dict(generation=generation, manipulation=manipulation))
        records = detail_records(result)
        self.assertEqual({r['task'] for r in records}, {'generation', 'manipulation'})
        store_detail_heatmap(result, records[0], dict(grid=[[1]], target='positive_logit', kind='gradcam'))
        self.assertIn('heatmap', generation['observations'][0]['faces'][0])
        self.assertNotIn('heatmap', manipulation['observations'][0]['faces'][0])
        self.assertNotIn('heatmap', generation['observations'][1]['faces'][0])
        self.assertEqual(detail_records(result)[0]['model_sha256'], 'generation-hash')

    def test_invalid_sampling_and_video_face_crop_are_rejected(self):
        with self.assertRaises(ValueError):
            self.predictor.predict('fixture.mp4', video_sampling='unknown')
        with self.assertRaises(ValueError):
            self.predictor.predict('fixture.mp4', face_crop=True)


if __name__ == '__main__':
    unittest.main()
