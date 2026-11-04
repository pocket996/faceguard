"""Exercise real official image/video detection and results through the Qt window."""
import json
from pathlib import Path
import sys
import tempfile
import time
import faulthandler
import copy
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from PySide6.QtCore import QObject, QMetaObject, QSettings, QUrl, QPointF, Qt, qInstallMessageHandler
from PySide6.QtGui import QFont
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from faceguard.app import AppController, UI_DIRECTORY
from faceguard.data_locations import data_location


def main():
    output = ROOT / 'outputs/video-dual-20261103/ui'
    output.mkdir(parents=True, exist_ok=True)
    trace = (output / 'thread-traces.txt').open('w', encoding='utf-8')
    faulthandler.dump_traceback_later(25, repeat=True, file=trace)
    messages = []
    qInstallMessageHandler(lambda kind, context, text: messages.append(text))
    app = QApplication([])
    app.setFont(QFont('Microsoft YaHei UI', 10))
    QQuickStyle.setStyle('Basic')
    def wait(predicate, timeout=90):
        deadline = time.monotonic() + timeout
        while not predicate() and time.monotonic() < deadline:
            QTest.qWait(50)
            time.sleep(.01)  # Give Python imports/inference in QThread time to acquire the GIL.
        assert predicate(), 'UI timed out: ' + '\n'.join(messages[-10:])
    with tempfile.TemporaryDirectory() as directory:
        controller = AppController(QSettings(str(Path(directory) / 'prefs.ini'), QSettings.Format.IniFormat),
                                   history_path=Path(directory) / 'history.sqlite3')
        last_stage = [None]
        def log_stage():
            stage = controller.progressText.split(' · ')[0]
            if stage and stage != last_stage[0]:
                print(stage.encode('ascii', errors='backslashreplace').decode(), flush=True)
                last_stage[0] = stage
        controller.changed.connect(log_stage)
        engine = QQmlApplicationEngine()
        engine.rootContext().setContextProperty('controller', controller)
        engine.load(QUrl.fromLocalFile(str(UI_DIRECTORY / 'Main.qml')))
        assert engine.rootObjects(), '\n'.join(messages)
        window = engine.rootObjects()[0]
        controller.window = window
        result_page = window.findChild(QObject, 'resultPage')
        QTest.qWait(500)
        def capture(name):
            QTest.qWait(250)
            assert window.grabWindow().save(str(output / (name + '.png')))
        photo = next(data_location('lfw').rglob('*.jpg'))
        assert controller.load_file(photo)
        assert window.findChild(QObject, 'startDetection').property('enabled')
        QMetaObject.invokeMethod(window.findChild(QObject, 'startDetection'), 'clicked')
        assert controller.busy
        character = window.findChild(QObject, 'ditingCharacter')
        wait(lambda: character.property('listening') > .99 or not controller.busy, timeout=5)
        if controller.busy:
            capture('00-detecting-listening')
        wait(lambda: not controller.busy)
        wait(lambda: character.property('listening') < .01, timeout=5)
        assert controller.hasResult, controller.errorText
        assert not controller._result.get('errors'), controller._result
        assert window.property('activePage') == 'workspace', 'Detection must not navigate away from the workspace'
        capture('00-photo-completed-workspace')
        QMetaObject.invokeMethod(window.findChild(QObject, 'resultsEntry'), 'clicked')
        assert window.property('activePage') == 'results'
        assert controller.resultDetails
        original_result = copy.deepcopy(controller._result)
        assert window.findChild(QObject, 'saveReport').property('enabled')
        controller.selectDetail(0)
        wait(lambda: not controller._preview_workers)
        assert not controller.heatmapUrl.isEmpty(), controller.heatmapStatus
        wait(lambda: result_page.property('heatmapReady'))
        assert not controller.selectedFrameUrl.isEmpty()
        result_page.setProperty('viewMode', 2)
        capture('01-photo-results')
        for index in range(len(controller.resultDetails)):
            controller.selectDetail(index)
            wait(lambda: not controller._preview_workers)
            assert not controller.heatmapUrl.isEmpty(), controller.heatmapStatus
            capture(f'01-photo-heatmap-{index}')
        loads = controller._explanation_models.loads
        controller.setHeatmapTarget(1)
        wait(lambda: not controller._preview_workers)
        assert controller._heatmap_payload['target'] == 'negative_logit'
        assert controller._explanation_models.loads == loads, 'Target switch must reuse the model'
        capture('01c-negative-direction')
        method_selector = window.findChild(QObject, 'heatmapMethodSelector')
        point = method_selector.mapToScene(QPointF(method_selector.width() / 2, method_selector.height() / 2)).toPoint()
        QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, point)
        wait(lambda: window.findChild(QObject, 'heatmapMethodPopup').property('visible'))
        QTest.keyClick(window, Qt.Key_End)
        QTest.keyClick(window, Qt.Key_Return)
        wait(lambda: controller.heatmapMethodIndex == 1)
        wait(lambda: not controller._preview_workers)
        assert controller._heatmap_payload['kind'] == 'occlusion'
        assert controller._heatmap_payload['target'] == 'negative_logit'
        assert controller._explanation_models.loads == loads
        capture('01d-occlusion-negative')
        controller.setHeatmapTarget(0)
        wait(lambda: not controller._preview_workers)
        assert controller._heatmap_payload['kind'] == 'occlusion'
        capture('01e-occlusion-positive')
        controller.export_heatmap(output / 'selected-heatmap.png', .6)
        controller.export_heatmap(output / 'selected-heatmap.pdf', .6)
        controller.setHeatmapMethod(0)
        wait(lambda: not controller._preview_workers)
        # Explanation is separate from prediction: not one existing value changes.
        explained = copy.deepcopy(controller._result)
        for item in explained['results'].values():
            for face in item['face_results']:
                assert face.pop('heatmap')['model_sha256'] == item['model_sha256']
                assert face.pop('heatmaps')['positive_logit']['model_sha256'] == item['model_sha256']
        assert explained == original_result
        summary = window.findChild(QObject, 'resultSummaryScroll').property('contentItem')
        summary.setProperty('contentY', max(0, summary.property('contentHeight') - summary.property('height')))
        capture('01b-readable-photo-detail')
        controller.export_report(output / 'photo-report.json')
        controller.export_report(output / 'photo-report.txt')
        controller.export_report(output / 'photo-report.pdf')
        identifier = controller.historyRecords[0]['id']
        controller.clearFile()
        assert controller.reopenRecord(identifier) and controller.hasResult
        controller._explanation_models.clear()
        with patch('faceguard.inference.heatmaps.load_detector', side_effect=AssertionError('history must use saved map')), \
             patch('faceguard.inference.core.load_detector', side_effect=AssertionError('history must use saved map')):
            controller.selectDetail(0)
            wait(lambda: not controller._preview_workers)
            controller.selectDetail(1)
            wait(lambda: not controller._preview_workers)
            controller.setHeatmapTarget(1)
            wait(lambda: not controller._preview_workers)
            assert controller._heatmap_payload['target'] == 'negative_logit'
            controller.setHeatmapMethod(1)
            wait(lambda: not controller._preview_workers)
            assert controller._heatmap_payload['kind'] == 'occlusion'
            controller.setHeatmapTarget(0)
            wait(lambda: not controller._preview_workers)
            assert controller._heatmap_payload['target'] == 'positive_logit'
            controller.setHeatmapMethod(0)
            wait(lambda: not controller._preview_workers)
        assert not controller.heatmapUrl.isEmpty(), controller.heatmapStatus
        wait(lambda: result_page.property('heatmapReady'))
        capture('02-restored-results')
        video = next(data_location('ffpp').rglob('*.mp4'))
        assert controller.load_file(video)
        controller.startDetection()
        controller.cancelDetection()
        wait(lambda: not controller.busy)
        assert not controller.hasResult
        assert controller.historyRecords[0]['status'] == 'cancelled'
        wait(lambda: character.property('listening') < .01, timeout=5)
        controller.startDetection()
        wait(lambda: not controller.busy)
        assert controller.hasResult, controller.errorText
        assert controller._result['task'] == 'video_dual'
        generation = controller._result['results']['generation']
        manipulation = controller._result['results']['manipulation']
        assert generation['sampling'] == 'generation_frame_review' and generation['observations']
        assert manipulation['sampling'] == 'adaptive_review' and manipulation['observations']
        assert controller.generationState != 'unavailable'
        assert '未标定整段视频' in controller.result_text()
        assert '整段基线' in controller.result_text()
        wait(lambda: character.property('listening') < .01, timeout=5)
        assert window.property('activePage') == 'workspace', 'Video completion must also stay on the workspace'
        QMetaObject.invokeMethod(window.findChild(QObject, 'resultsEntry'), 'clicked')
        controller.selectDetail(0)
        wait(lambda: not controller._preview_workers)
        assert not controller.heatmapUrl.isEmpty(), controller.heatmapStatus
        wait(lambda: result_page.property('heatmapReady'))
        from PIL import Image
        with Image.open(controller.heatmapUrl.toLocalFile()) as overlay, Image.open(controller.selectedFrameUrl.toLocalFile()) as frame:
            assert overlay.size == frame.size
            has_response = controller._heatmap_payload.get('raw_peak', 0) > 1e-12
            assert (overlay.getchannel('A').getbbox() is not None) == has_response
        capture('03-video-results')
        video_id = controller.historyRecords[0]['id']
        from faceguard.detection import detail_records
        manipulation_index = next(i for i, row in enumerate(detail_records(controller._result)) if row['task'] == 'manipulation')
        controller.selectDetail(manipulation_index)
        wait(lambda: not controller._preview_workers)
        assert not controller.heatmapUrl.isEmpty(), controller.heatmapStatus
        assert controller._heatmap_payload['task'] == 'manipulation'
        capture('03a-video-manipulation')
        controller.setHeatmapMethod(1)
        wait(lambda: not controller._preview_workers)
        assert controller._heatmap_payload['kind'] == 'occlusion'
        capture('03b-video-occlusion')
        controller.export_heatmap(output / 'video-heatmap.png')
        controller.export_heatmap(output / 'video-heatmap.pdf')
        controller.setHeatmapMethod(0)
        wait(lambda: not controller._preview_workers)
        # Rapid clicks settle on the last selected frame, without concurrent models.
        last = len(controller.resultDetails) - 1
        controller.selectDetail(0)
        controller.selectDetail(min(1, last))
        controller.selectDetail(last)
        wait(lambda: not controller._preview_workers)
        assert controller.selectedDetailIndex == last
        assert not controller.heatmapUrl.isEmpty(), controller.heatmapStatus
        # Cancel after the decoder has supplied a preview; don't attach a late map.
        controller.selectDetail(0)
        controller.cancelDetail()
        wait(lambda: not controller._preview_workers)
        assert controller.heatmapUrl.isEmpty()
        controller.selectDetail(0)
        wait(lambda: not controller._preview_workers)
        wait(lambda: result_page.property('heatmapReady'))
        controller.export_report(output / 'video-report.json')
        controller.export_report(output / 'video-report.txt')
        controller.clearFile()
        assert controller.reopenRecord(video_id)
        with patch('faceguard.inference.heatmaps.load_detector', side_effect=AssertionError('cached video map')), \
             patch('faceguard.inference.core.load_detector', side_effect=AssertionError('cached video map')):
            for index in (0, manipulation_index):
                controller.selectDetail(index)
                wait(lambda: not controller._preview_workers)
                assert not controller.heatmapUrl.isEmpty(), controller.heatmapStatus
        window.resize(1080, 720)
        capture('04-compact-results')
        summary.setProperty('contentY', max(0, summary.property('contentHeight') - summary.property('height')))
        capture('04b-readable-compact-detail')
        window.setProperty('activePage', 'history')
        capture('05-detected-history')
        assert not any('reference_run' in str(getattr(m, '__file__', '')) for m in list(sys.modules.values()) if m)
        errors = [message for message in messages if any(term in message for term in ('ReferenceError', 'TypeError', 'is not a type', 'Cannot assign', 'Binding loop', 'Unable to assign', 'Failed to create'))]
        assert not errors, '\n'.join(errors)
        report = dict(passed=True, checks=['actual photo dual inference + separate positive-logit Grad-CAM maps', 'stored scores/thresholds/decisions unchanged', 'completion stays on workspace; explicit results entry', 'face preview', 'PDF/text report + technical JSON API', 'history reload without loading a model',
                                          'cooperative cancellation', 'actual dual video inference with photo-model frame generation evidence', 'separate generation/manipulation video history maps', 'video face preview',
                                          'video heatmap/decoded-frame geometry', 'latest frame wins rapid selection', 'heatmap cancellation', 'gradient/blur-occlusion with separate direction caches', 'dual explanation directions with bounded model reuse', 'annotated PNG/PDF export', '1080x720 results', 'independent runtime imports'], messages=messages)
        (output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(report, ensure_ascii=True, indent=2))
        controller.shutdown()
        window.close()
        engine.deleteLater()
        QTest.qWait(100)
    app.quit()
    faulthandler.cancel_dump_traceback_later()
    trace.close()


if __name__ == '__main__':
    main()
