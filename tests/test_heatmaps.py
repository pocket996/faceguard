"""Faithful explanations, transparent geometry, cache identity and cancellation."""
import copy
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image
import torch
from torch import nn

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from faceguard.inference.heatmaps import METHOD, gradcam, explain_face, render_overlay, valid_cached_map
from faceguard.inference.inference_control import InferenceCancelled
from faceguard.detection import detail_records, store_detail_heatmap


class TinyBackbone(nn.Module):
    def __init__(self):
        super().__init__()
        self.layer4 = nn.Conv2d(3, 2, 1, bias=False)
        with torch.no_grad():
            self.layer4.weight.fill_(1 / 3)

    def forward(self, batch):
        return self.layer4(batch).mean(dim=(2, 3))


class HeatmapTests(unittest.TestCase):
    def fixture(self):
        model = TinyBackbone().eval()
        head = nn.Linear(2, 1).eval()
        with torch.no_grad():
            head.weight.fill_(.5)
            head.bias.fill_(-5)
        return model, head

    def test_positive_logit_map_is_correct_even_for_negative_verdict_and_does_not_mutate_model(self):
        model, head = self.fixture()
        tensor = torch.zeros(1, 3, 4, 4)
        tensor[:, :, 1:3, 2:4] = 1
        before = copy.deepcopy(model.state_dict())
        model.layer4.weight.grad = torch.ones_like(model.layer4.weight)
        # The normal predictor uses inference_mode: the explainer must escape it.
        with torch.inference_mode():
            grid, score = gradcam(model, head, tensor)
            expected_score = head(model(tensor)).sigmoid().item()
        np.testing.assert_array_equal(grid, tensor[0, 0].numpy())
        self.assertAlmostEqual(score, expected_score)
        self.assertLess(score, .5)
        for name, value in model.state_dict().items():
            self.assertTrue(torch.equal(value, before[name]))
        self.assertTrue(torch.equal(model.layer4.weight.grad, torch.ones_like(model.layer4.weight)))
        self.assertFalse(model.layer4._forward_hooks)
        self.assertFalse(model.training)

    def test_zero_response_remains_transparent_and_hooks_are_removed_after_failure(self):
        model, head = self.fixture()
        grid, _ = gradcam(model, head, torch.zeros(1, 3, 4, 4))
        self.assertFalse(grid.any())
        overlay = render_overlay(dict(grid=grid.tolist()), (300, 200))
        self.assertIsNone(overlay.getchannel('A').getbbox())
        with self.assertRaises(ValueError):
            gradcam(model, head, torch.ones(2, 3, 4, 4))
        self.assertFalse(model.layer4._forward_hooks)

    def test_overlay_uses_original_crop_coordinates_and_never_colors_other_faces(self):
        overlay = render_overlay(dict(grid=[[1, 1], [1, 1]]), (800, 400), [200, 100, 600, 300], max_side=400)
        self.assertEqual(overlay.size, (400, 200))
        self.assertEqual(overlay.getchannel('A').getbbox(), (100, 50, 300, 150))
        self.assertEqual(overlay.getpixel((150, 75))[3], 230)
        self.assertEqual(overlay.getpixel((50, 75))[3], 0)

    def record(self):
        return dict(task='generation', model_sha256='a' * 64, score=.2, bbox=[0, 0, 20, 20])

    def payload(self):
        return dict(method=METHOD, target='positive_logit', task='generation',
                    model_sha256='a' * 64, score=.2, grid=[[0., 1.], [.3, .4]],
                    bbox=[0, 0, 20, 20], frame_index=-1)

    def test_cache_requires_matching_model_task_score_and_finite_bounded_grid(self):
        record, payload = self.record(), self.payload()
        self.assertTrue(valid_cached_map(payload, record))
        for key, value in [('model_sha256', 'b' * 64), ('task', 'manipulation'), ('score', .9),
                           ('bbox', [1, 1, 20, 20]), ('frame_index', 8),
                           ('grid', [[float('nan')]]), ('grid', [[-1.]]), ('grid', [[1.1]]),
                           ('grid', []), ('grid', [[1], [1, 0]]), ('target', 'negative_logit')]:
            invalid = dict(payload, **{key: value})
            self.assertFalse(valid_cached_map(invalid, record), key)
        record['heatmap'] = payload
        with patch('faceguard.inference.heatmaps.load_detector', side_effect=AssertionError('should use cache')):
            self.assertEqual(explain_face(Image.new('RGB', (20, 20)), record), payload)

    def test_checkpoint_mismatch_fails_before_loading_and_cancel_propagates(self):
        with patch('faceguard.inference.heatmaps.checked_generation_profile', return_value='fixture'), \
             patch('faceguard.inference.heatmaps.digest', return_value='b' * 64), \
             patch('faceguard.inference.heatmaps.load_detector') as loader:
            with self.assertRaisesRegex(ValueError, '模型已变化'):
                explain_face(Image.new('RGB', (20, 20)), self.record())
            loader.assert_not_called()
        def cancelled():
            raise InferenceCancelled()
        with self.assertRaises(InferenceCancelled):
            explain_face(Image.new('RGB', (20, 20)), self.record(), check_cancel=cancelled)

    def test_saved_map_targets_only_one_face_task_or_video_frame(self):
        face = dict(face_id=1, bbox=[0, 0, 20, 20], score=.2, threshold=.5, decision='no_generation_detected')
        result = dict(results={task: dict(model_sha256='a' * 64, face_results=[copy.deepcopy(face)])
                               for task in ('generation', 'manipulation')})
        before = copy.deepcopy(result)
        record = detail_records(result)[0]
        store_detail_heatmap(result, record, self.payload())
        self.assertEqual(result['results']['manipulation'], before['results']['manipulation'])
        self.assertEqual(result['results']['generation']['face_results'][0].pop('heatmap'), self.payload())
        self.assertEqual(result, before)
        result = dict(media_type='video', observations=[dict(frame_index=i, faces=[copy.deepcopy(face)]) for i in (2, 8)])
        record = detail_records(result)[1]
        store_detail_heatmap(result, record, self.payload())
        self.assertNotIn('heatmap', result['observations'][0]['faces'][0])
        self.assertIn('heatmap', result['observations'][1]['faces'][0])


class HeatmapControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def wait(self, predicate):
        from PySide6.QtTest import QTest
        deadline = time.monotonic() + 10
        while not predicate() and time.monotonic() < deadline:
            QTest.qWait(10)
            time.sleep(.001)
        self.assertTrue(predicate())

    def test_history_cache_survives_restart_and_cancelled_selection_never_attaches_map(self):
        from PySide6.QtCore import QSettings
        from faceguard.app import AppController
        with tempfile.TemporaryDirectory() as folder:
            settings = QSettings(str(Path(folder) / 'prefs.ini'), QSettings.Format.IniFormat)
            path = Path(folder) / '人脸.png'
            Image.new('RGB', (100, 100), 'gray').save(path)
            controller = AppController(settings)
            try:
                controller.load_file(path)
                stat = path.stat()
                fixture = HeatmapTests()
                face = dict(face_id=1, bbox=[10, 10, 90, 90], score=.2, threshold=.5, decision='no_generation_detected')
                result = dict(media_type='image', task='whole_face_generation', decision='no_generation_detected',
                              model_sha256='a' * 64, face_results=[face],
                              source_signature=dict(size=stat.st_size, mtime_ns=stat.st_mtime_ns))
                controller._result = result
                identifier = controller._history_id
                payload = dict(fixture.payload(), bbox=face['bbox'])
                with patch('faceguard.inference.heatmaps.explain_face', return_value=payload):
                    controller.selectDetail(0)
                    self.wait(lambda: not controller._preview_workers)
                self.assertFalse(controller.heatmapUrl.isEmpty())
                controller.shutdown()
                controller = AppController(settings)
                self.assertTrue(controller.reopenRecord(identifier))
                with patch('faceguard.inference.heatmaps.load_detector', side_effect=AssertionError('cache lost')):
                    controller.selectDetail(0)
                    self.wait(lambda: not controller._preview_workers)
                self.assertFalse(controller.heatmapUrl.isEmpty(), controller.heatmapStatus)
                # A late computation must never write into a cleared file/history.
                started = threading.Event()
                def delayed(*args):
                    started.set()
                    time.sleep(.1)
                    return payload
                with patch('faceguard.inference.heatmaps.explain_face', side_effect=delayed):
                    controller.selectDetail(0)
                    self.wait(started.is_set)
                    controller.clearFile()
                    self.wait(lambda: not controller._preview_workers)
                self.assertFalse(controller.hasResult)
                self.assertTrue(controller.heatmapUrl.isEmpty())
            finally:
                controller.shutdown()


if __name__ == '__main__':
    unittest.main()
