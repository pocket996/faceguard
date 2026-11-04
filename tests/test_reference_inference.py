"""Checks for missed smaller faces, separate model decisions, and task failure reporting."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'reference_run'))
from core import Predictor, crop_face, detect_face_crops
from face_analysis import FaceAnalyzer, GenerationPredictor
from result_text import result_lines


class Detector:
    def setInputSize(self, size):
        pass

    def detect(self, frame):
        # Deliberately return smaller first: the previously ignored face is suspicious.
        return None, np.array([[180, 20, 40, 40] + [0] * 10 + [.95],
                               [20, 20, 100, 100] + [0] * 10 + [.99]], dtype=np.float32)


class InferenceTests(unittest.TestCase):
    def test_largest_face_crop_stays_pixel_identical(self):
        frame = np.arange(300 * 300 * 3, dtype=np.uint32).astype('uint8').reshape(300, 300, 3)
        records, count = detect_face_crops(frame, Detector())
        self.assertEqual(count, 2)
        self.assertEqual(records[0]['bbox'], [5, 5, 135, 135])
        np.testing.assert_array_equal(np.asarray(crop_face(frame, Detector())), np.asarray(records[0]['image']))
        self.assertEqual(records[1]['bbox'], [174, 14, 226, 66])

    def test_unanalysed_faces_are_reported(self):
        records, count = detect_face_crops(np.zeros((300, 300, 3), dtype='uint8'), Detector(), max_faces=1)
        self.assertEqual((len(records), count), (1, 2))

    def test_smaller_suspicious_face_is_preserved_without_uncalibrated_global_score(self):
        for kind in (Predictor, GenerationPredictor):
            predictor = kind.__new__(kind)
            predictor.device, predictor.detector = 'cpu', Detector()
            predictor.model_sha256='fixture-model'
            predictor.state = dict(frame_threshold=.7, training_generators=['test'])
            predictor.model = predictor.head = predictor.transform = None
            module = 'core' if kind is Predictor else 'face_analysis'
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'two.png'
                Image.new('RGB', (300, 300)).save(path)
                with patch(module + '.score_images', return_value=[.1, .9]):
                    result = predictor.predict(path)
            self.assertEqual(result['faces'], 2)
            self.assertIsNone(result['score'])
            self.assertFalse(result['face_results'][0]['decision'].startswith('suspected_'))
            self.assertTrue(result['face_results'][1]['decision'].startswith('suspected_'))
            self.assertIn('人脸 #2：疑似', '\n'.join(result_lines(result)))

    def test_pre_cropped_photo_has_one_attempt_not_zero(self):
        predictor = Predictor.__new__(Predictor)
        predictor.state = dict(frame_threshold=.5)
        predictor.model = predictor.head = predictor.transform = None
        predictor.device = 'cpu'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'crop.jpg'
            Image.new('RGB', (128, 128)).save(path)
            with patch('core.score_images', return_value=[.1]):
                result = predictor.predict(path, face_crop=True)
        self.assertEqual(result['sampled_frames'], 1)

    def test_auto_keeps_both_tasks_and_partial_failure(self):
        class Fake:
            def predict(self, *args, **kwargs):
                return dict(decision='no_generation_detected', faces=1, no_face_frames=0, score=.1)
        class Broken:
            def predict(self, *args, **kwargs):
                raise ValueError('missing weights')
        analyzer = FaceAnalyzer()
        analyzer.generation, analyzer.manipulation = Fake(), Broken()
        result = analyzer.predict('test.jpg')
        self.assertEqual(result['decision'], 'partial_results')
        self.assertIn('generation', result['results'])
        self.assertEqual(result['errors']['manipulation'], 'missing weights')
        self.assertIsNone(result['score'])
        analyzer.manipulation = Fake()
        result = analyzer.predict('test.jpg')
        self.assertEqual(set(result['results']), {'generation', 'manipulation'})
        self.assertEqual(result['decision'], 'separate_results')


if __name__ == '__main__':
    unittest.main()
