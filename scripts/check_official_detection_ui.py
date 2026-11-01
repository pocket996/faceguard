"""Exercise real official image/video detection and results through the Qt window."""
import json
from pathlib import Path
import sys
import tempfile
import time
import faulthandler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from PySide6.QtCore import QObject, QMetaObject, QSettings, QUrl, qInstallMessageHandler
from PySide6.QtGui import QFont
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from faceguard.app import AppController, UI_DIRECTORY
from faceguard.data_locations import data_location


def main():
    output = ROOT / 'outputs/model-migration-20261031/ui'
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
        controller = AppController(QSettings(str(Path(directory) / 'prefs.ini'), QSettings.Format.IniFormat))
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
        QTest.qWait(500)
        def capture(name):
            QTest.qWait(250)
            assert window.grabWindow().save(str(output / (name + '.png')))
        photo = next(data_location('lfw').rglob('*.jpg'))
        assert controller.load_file(photo)
        assert window.findChild(QObject, 'startDetection').property('enabled')
        QMetaObject.invokeMethod(window.findChild(QObject, 'startDetection'), 'clicked')
        assert controller.busy
        wait(lambda: not controller.busy)
        assert controller.hasResult, controller.errorText
        assert not controller._result.get('errors'), controller._result
        assert window.property('activePage') == 'results'
        assert controller.resultDetails
        assert window.findChild(QObject, 'saveReport').property('enabled')
        controller.selectDetail(0)
        wait(lambda: not controller.detailPreviewUrl.isEmpty())
        assert not controller.selectedFrameUrl.isEmpty()
        capture('01-photo-results')
        controller.export_report(output / 'photo-report.json')
        controller.export_report(output / 'photo-report.txt')
        identifier = controller.historyRecords[0]['id']
        controller.clearFile()
        assert controller.reopenRecord(identifier) and controller.hasResult
        capture('02-restored-results')
        video = next(data_location('ffpp').rglob('*.mp4'))
        assert controller.load_file(video)
        controller.startDetection()
        controller.cancelDetection()
        wait(lambda: not controller.busy)
        assert not controller.hasResult
        assert controller.historyRecords[0]['status'] == 'cancelled'
        controller.startDetection()
        wait(lambda: not controller.busy)
        assert controller.hasResult, controller.errorText
        assert controller._result['sampling'] == 'adaptive_review'
        assert controller._result['observations']
        controller.selectDetail(0)
        wait(lambda: not controller.detailPreviewUrl.isEmpty())
        capture('03-video-results')
        controller.export_report(output / 'video-report.json')
        window.resize(1080, 720)
        capture('04-compact-results')
        window.setProperty('activePage', 'history')
        capture('05-detected-history')
        assert not any('reference_run' in str(getattr(m, '__file__', '')) for m in list(sys.modules.values()) if m)
        errors = [message for message in messages if any(term in message for term in ('ReferenceError', 'TypeError', 'is not a type', 'Cannot assign', 'Binding loop', 'Unable to assign', 'Failed to create'))]
        assert not errors, '\n'.join(errors)
        report = dict(passed=True, checks=['actual photo dual inference', 'face preview', 'JSON/text report', 'history reload',
                                          'cooperative cancellation', 'actual adaptive video inference', 'video face preview',
                                          '1080x720 results', 'independent runtime imports'], messages=messages)
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
