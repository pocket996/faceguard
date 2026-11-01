"""Official inference boundaries, cancellation and persisted result correctness."""
from pathlib import Path
import json
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

import numpy as np
from PIL import Image
from PySide6.QtCore import QSettings
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from faceguard.app import AppController
from faceguard.detection import DetectionWorker, DetailPreviewWorker
from faceguard.model_registry import checked_resource, digest
from faceguard.inference.face_analysis import FaceAnalyzer, GenerationPredictor
from faceguard.inference.inference_control import InferenceCancelled


class TwoFaces:
    def setInputSize(self, size):
        pass

    def detect(self, frame):
        return None, np.array([[20, 20, 100, 100] + [0] * 10 + [.99],
                               [180, 20, 40, 40] + [0] * 10 + [.95]], dtype=np.float32)


class OfficialInferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)
        self.path = self.root / '多人照片.png'
        Image.new('RGB', (300, 300)).save(self.path)
        self.controller = AppController(QSettings(str(self.root / 'prefs.ini'), QSettings.Format.IniFormat))

    def tearDown(self):
        self.controller.shutdown()
        self.folder.cleanup()

    def wait_idle(self):
        deadline = time.monotonic() + 5
        while self.controller.busy and time.monotonic() < deadline:
            QTest.qWait(20)
        self.assertFalse(self.controller.busy)

    def test_official_generation_keeps_smaller_suspicious_face_separate(self):
        predictor = GenerationPredictor.__new__(GenerationPredictor)
        predictor.detector, predictor.device = TwoFaces(), 'cpu'
        predictor.state = dict(frame_threshold=.7, training_generators=['fixture'])
        predictor.model_sha256 = 'fixture'
        predictor.model = predictor.head = predictor.transform = None
        with patch('faceguard.inference.face_analysis.score_images', return_value=[.1, .9]):
            result = predictor.predict(self.path)
        self.assertIsNone(result['score'])
        self.assertEqual(result['decision'], 'multiple_face_results')
        self.assertEqual(result['face_results'][1]['decision'], 'suspected_generation')

    def test_partial_failure_does_not_become_joint_verdict_and_cancellation_propagates(self):
        class Good:
            def predict(self, *args, **kwargs):
                return dict(decision='no_generation_detected', faces=1, no_face_frames=0)
        class Broken:
            def predict(self, *args, **kwargs):
                raise ValueError('missing weights')
        analyzer = FaceAnalyzer()
        analyzer.generation, analyzer.manipulation = Good(), Broken()
        result = analyzer.predict(self.path)
        self.assertEqual(result['decision'], 'partial_results')
        self.assertIsNone(result['score'])
        with patch.object(analyzer.generation, 'predict', side_effect=InferenceCancelled):
            with self.assertRaises(InferenceCancelled):
                analyzer.predict(self.path)

    def test_worker_can_cancel_without_importing_or_starting_models(self):
        worker = DetectionWorker(str(self.path))
        received = []
        worker.cancelled.connect(lambda: received.append('cancelled'))
        worker.cancel()
        worker.run()
        self.assertEqual(received, ['cancelled'])
        self.assertIsNone(worker.analyzer)

    def test_model_switch_discards_cached_analyzer_and_stale_result_but_preserves_history(self):
        profiles = [dict(id='stable', label='stable'), dict(id='fixture', label='candidate')]
        self.controller._generation_models = profiles
        self.controller.load_file(self.path)
        identifier = self.controller.historyRecords[0]['id']
        self.controller.history.set_result(identifier, dict(model_sha256='old'))
        self.controller._analyzer = object()
        self.controller._result = dict(model_sha256='old')
        self.controller.setGenerationModel(1)
        self.assertIsNone(self.controller._analyzer)
        self.assertFalse(self.controller.hasResult)
        self.assertEqual(self.controller.history.get(identifier)['status'], 'completed')
        self.assertEqual(self.controller.settings.value('generationModel'), 'fixture')
        with patch('faceguard.app.generation_profiles', return_value=profiles):
            reopened = AppController(self.controller.settings)
        self.assertEqual(reopened.generationModelIndex, 1)
        reopened.shutdown()
        self.controller._busy = True
        self.controller.setGenerationModel(0)
        self.assertEqual(self.controller.generationModelIndex, 1)
        self.controller._busy = False

    def test_candidate_selection_rejects_corrupt_or_escaped_checkpoint(self):
        from faceguard import model_registry
        folder = self.root / 'generation-candidates'
        folder.mkdir()
        model = folder / 'fixture.pt'
        model.write_bytes(b'expected')
        record = dict(id='fixture', label='candidate', file='fixture.pt', size=model.stat().st_size,
                      sha256=model_registry.digest(model))
        with patch.object(model_registry, 'MODEL_DIRECTORY', self.root / 'runtime'), \
             patch.object(model_registry, 'generation_profiles', return_value=[record]):
            self.assertEqual(model_registry.checked_generation_profile('fixture'), model)
            model.write_bytes(b'tampered')
            with self.assertRaisesRegex(ValueError, '校验失败'):
                model_registry.checked_generation_profile('fixture')
            record['file'] = '../outside.pt'
            with self.assertRaisesRegex(ValueError, '路径无效'):
                model_registry.checked_generation_profile('fixture')

    def test_async_result_export_history_reload_and_changed_media_invalidation(self):
        class Analyzer:
            def predict(inner, path, task, progress):
                progress('inference', 1, 1)
                return dict(path=str(path), media_type='image', task='whole_face_generation',
                            decision='no_face', faces=0, no_face_frames=1, score=None, face_results=[])
        self.controller.load_file(self.path)
        self.controller._analyzer = Analyzer()
        with patch('faceguard.app.resource_status', return_value=(True, 'fixture')):
            self.controller.startDetection()
        self.wait_idle()
        self.assertTrue(self.controller.hasResult)
        self.assertEqual(self.controller.historyRecords[0]['status'], 'completed')
        report = self.root / '报告.json'
        self.controller.export_report(report)
        self.assertEqual(json.loads(report.read_text(encoding='utf-8'))['decision'], 'no_face')
        identifier = self.controller.historyRecords[0]['id']
        self.controller.clearFile()
        self.assertTrue(self.controller.reopenRecord(identifier))
        self.assertTrue(self.controller.hasResult)
        Image.new('RGB', (350, 350)).save(self.path)
        self.assertTrue(self.controller.reopenRecord(identifier))
        self.assertFalse(self.controller.hasResult)

    def test_cancelled_job_never_saves_completed_result_or_allows_file_replacement(self):
        class Analyzer:
            def predict(inner, path, task, progress):
                for step in range(100):
                    time.sleep(.01)
                    progress('reading_video', step, 100)
                return {}
        self.controller.load_file(self.path)
        self.controller._analyzer = Analyzer()
        with patch('faceguard.app.resource_status', return_value=(True, 'fixture')):
            self.controller.startDetection()
        self.assertFalse(self.controller.load_file(self.path))
        self.controller.cancelDetection()
        self.wait_idle()
        self.assertFalse(self.controller.hasResult)
        self.assertEqual(self.controller.historyRecords[0]['status'], 'cancelled')

    def test_face_preview_retains_full_image_and_exact_crop(self):
        destination = self.root / 'face-preview.png'
        worker = DetailPreviewWorker(str(self.path), dict(frame_index=-1, bbox=[10, 20, 60, 80]), destination)
        ready = []
        worker.ready.connect(lambda face, frame: ready.append((face, frame)))
        worker.run()
        self.assertEqual(len(ready), 1)
        with Image.open(ready[0][0]) as crop, Image.open(ready[0][1]) as frame:
            self.assertEqual(crop.size, (50, 60))
            self.assertEqual(frame.size, (300, 300))

    def test_shutdown_records_cancellation_before_event_loop_exits(self):
        class Analyzer:
            def predict(inner, path, task, progress):
                time.sleep(.03)
                progress('inference', 0, 1)
                return {}
        self.controller.load_file(self.path)
        self.controller._analyzer = Analyzer()
        with patch('faceguard.app.resource_status', return_value=(True, 'fixture')):
            self.controller.startDetection()
        self.controller.shutdown()
        self.assertEqual(self.controller.historyRecords[0]['status'], 'cancelled')
        self.wait_idle()

    def test_preview_rejects_changed_media_and_failed_detection_stays_failed(self):
        class Broken:
            def predict(inner, *args, **kwargs):
                raise ValueError('bad media')
        self.controller.load_file(self.path)
        self.controller._analyzer = Broken()
        with patch('faceguard.app.resource_status', return_value=(True, 'fixture')):
            self.controller.startDetection()
        self.wait_idle()
        self.assertEqual(self.controller.historyRecords[0]['status'], 'failed')
        self.assertFalse(self.controller.hasResult)
        stat = self.path.stat()
        self.controller._result = dict(source_signature=dict(size=stat.st_size, mtime_ns=stat.st_mtime_ns),
            media_type='image', task='whole_face_generation', decision='suspected_generation',
            face_results=[dict(face_id=1, bbox=[0, 0, 20, 20], score=.9, threshold=.7, decision='suspected_generation')])
        Image.new('RGB', (360, 360)).save(self.path)
        self.controller.selectDetail(0)
        self.assertFalse(self.controller._preview_workers)
        self.assertIn('变化', self.controller.errorText)

    def test_runtime_checksum_mismatch_is_rejected(self):
        resource = self.root / 'generation.pt'
        resource.write_bytes(b'original')
        state = dict(schema_version=1, files={'generation.pt': dict(size=resource.stat().st_size, sha256=digest(resource))})
        (self.root / 'manifest.json').write_text(json.dumps(state), encoding='utf-8')
        with patch('faceguard.model_registry.MODEL_DIRECTORY', self.root):
            self.assertEqual(checked_resource('generation.pt'), resource)
            resource.write_bytes(b'changed!')
            with self.assertRaises(ValueError):
                checked_resource('generation.pt')


if __name__ == '__main__':
    unittest.main()
