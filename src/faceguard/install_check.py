"""Explicit packaged-installation diagnostic; never runs during normal startup."""
import argparse
import ctypes
import json
from pathlib import Path
import tempfile
import time
import traceback
from zoneinfo import ZoneInfo


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--verify-install', required=True, type=Path)
    parser.add_argument('--test-photo', type=Path)
    parser.add_argument('--test-video', type=Path)
    args = parser.parse_args()
    output = args.verify_install.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    report = dict(passed=False, checks=[], messages=[])
    controller = engine = window = None
    from PySide6.QtCore import QObject, QMetaObject, QSettings, QUrl, QPointF, Qt, qInstallMessageHandler
    from PySide6.QtGui import QCursor, QFont, QIcon
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuickControls2 import QQuickStyle
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from .app import AppController, UI_DIRECTORY
    from .detection import detail_records
    from .model_registry import checked_resource, checked_generation_profile, generation_profiles
    from .version import APP_VERSION
    import torch

    qInstallMessageHandler(lambda kind, context, message: report['messages'].append(message))
    application = QApplication([])
    application.setFont(QFont('Microsoft YaHei UI', 10))
    application.setWindowIcon(QIcon(str(UI_DIRECTORY / 'brand.ico')))
    QQuickStyle.setStyle('Basic')

    def wait(predicate, timeout=180):
        deadline = time.monotonic() + timeout
        while not predicate() and time.monotonic() < deadline:
            QTest.qWait(30)
            time.sleep(.01)
        if not predicate():
            raise AssertionError('Install verification timed out: ' + '\n'.join(report['messages'][-8:]))

    with tempfile.TemporaryDirectory(prefix='faceguard-install-check-') as folder:
        try:
            report.update(version=APP_VERSION, torch=torch.__version__, cuda_available=torch.cuda.is_available(),
                          console_window=bool(ctypes.windll.kernel32.GetConsoleWindow()), timezone=str(ZoneInfo('Asia/Shanghai')))
            assert torch.version.cuda is None
            assert not report['console_window']
            for name in ('generation.pt', 'manipulation.pt', 'yunet.onnx', 'video_policy.json'):
                checked_resource(name)
            for profile in generation_profiles():
                checked_generation_profile(profile['id'])
            report['checks'].append('CPU-only runtime, windowless process, timezone and all model manifests')
            settings = QSettings(str(Path(folder) / 'prefs.ini'), QSettings.Format.IniFormat)
            settings.setValue('reducedMotion', True)
            controller = AppController(settings, history_path=Path(folder) / 'history.sqlite3')
            engine = QQmlApplicationEngine()
            engine.rootContext().setContextProperty('controller', controller)
            engine.load(QUrl.fromLocalFile(str(UI_DIRECTORY / 'Main.qml')))
            assert engine.rootObjects(), report['messages']
            window = engine.rootObjects()[0]
            controller.window = window
            # An unattended diagnostic must not send native cursor movement to
            # another application covering this window.
            window.setFlag(Qt.WindowType.WindowStaysOnTopHint, True)
            window.show()
            wait(lambda: window.findChild(QObject, 'ditingCharacter').property('assetReady'))
            QTest.qWait(600)
            assert window.grabWindow().save(str(output.parent / 'installed-workbench.png'))
            report['checks'].append('Bundled QML, Quick 3D skin, shaders, lake and icon render')
            controller.togglePet()
            QTest.qWait(500)  # Native resize/move events must settle before mapping cursor coordinates.
            report['pet_geometry'] = dict(width=window.width(), height=window.height(),
                minimum_width=window.minimumWidth(), minimum_height=window.minimumHeight(),
                reduced_motion=controller.reducedMotion, transitioning=controller.petTransitioning)
            output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            wait(lambda: window.width() == 300 and window.height() == 370, timeout=10)
            def move_pet_mouse(point):
                # Send the event to this diagnostic window, independent of
                # remote-desktop / foreground activation restrictions.
                QTest.mouseMove(window, point)
                QTest.qWait(150)
            hint, actions = window.findChild(QObject, 'petHint'), window.findChild(QObject, 'petActions')
            move_pet_mouse(QPointF(-30, 150).toPoint())
            wait(lambda: not actions.property('visible'))
            window.grabWindow().save(str(output.parent / 'installed-pet-idle.png'))
            move_pet_mouse(QPointF(150, 170).toPoint())
            wait(lambda: hint.property('visible') and actions.property('visible'), timeout=10)
            window.grabWindow().save(str(output.parent / 'installed-pet-hover.png'))
            expand = window.findChild(QObject, 'petExpand')
            QMetaObject.invokeMethod(expand, 'clicked')
            assert not controller.petMode
            report['checks'].append('Pet hover controls and return to workbench')
            for task_name, path in [('photo', args.test_photo), ('video', args.test_video)]:
                if path is None:
                    continue
                assert controller.load_file(path), controller.errorText
                if task_name == 'video':
                    player = window.findChild(QObject, 'mediaPlayer')
                    QMetaObject.invokeMethod(player, 'play')
                    wait(lambda: window.property('videoPosition') > 300, timeout=25)
                    assert player.property('activeAudioTrack') == -1 and player.property('audioOutput') is None
                    QMetaObject.invokeMethod(player, 'pause')
                controller.startDetection()
                wait(lambda: not controller.busy)
                assert controller.hasResult and not controller._result.get('errors'), controller.errorText
                assert set(controller._result['results']) == {'generation', 'manipulation'}
                records = detail_records(controller._result)
                report[task_name] = dict(details=len(records),
                    generation=controller.generationSummary, manipulation=controller.manipulationSummary)
                selected = [next(i for i, row in enumerate(records) if row['task'] == task)
                            for task in ('generation', 'manipulation')]
                for index in selected:
                    controller.selectDetail(index)
                    wait(lambda: not controller._preview_workers)
                    assert not controller.heatmapUrl.isEmpty(), controller.heatmapStatus
                if task_name == 'photo':
                    controller.export_report(output.parent / 'installed-photo-report.pdf')
                controller.export_report(output.parent / f'installed-{task_name}-report.txt')
                identifier = controller.historyRecords[0]['id']
                controller._explanation_models.clear()
                loads = controller._explanation_models.loads
                controller.clearFile()
                assert controller.reopenRecord(identifier)
                for index in selected:
                    controller.selectDetail(index)
                    wait(lambda: not controller._preview_workers)
                    assert not controller.heatmapUrl.isEmpty(), controller.heatmapStatus
                assert controller._explanation_models.loads == loads
                report['checks'].append(f'Actual {task_name} dual inference, separate Grad-CAM, report and cached history')
            errors = [m for m in report['messages'] if any(term in m for term in
                      ('ReferenceError', 'TypeError', 'Cannot assign', 'Binding loop', 'Unable to assign', 'Failed to create', 'Failed to load shader'))]
            assert not errors, errors
            report['passed'] = True
        except Exception:
            report['error'] = traceback.format_exc()
        finally:
            if controller is not None:
                controller.shutdown()
            if window is not None:
                window.close()
            if engine is not None:
                engine.deleteLater()
            QTest.qWait(150)
            output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    application.quit()
    return 0 if report['passed'] else 1
