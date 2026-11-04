"""Render the actual official QML UI and verify state transitions; outputs are ignored."""
import json
from pathlib import Path
import sys
import tempfile
import faulthandler
import shutil
import subprocess
import hashlib
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from PySide6.QtCore import QObject, QMetaObject, QSettings, QUrl, QPointF, Qt, QSize, qInstallMessageHandler
from PySide6.QtGui import QCursor, QFont, QIcon, QImage
from PySide6.QtQml import QQmlApplicationEngine, QQmlProperty
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from faceguard.app import AppController, UI_DIRECTORY


def main():
    faulthandler.dump_traceback_later(90)
    output = ROOT / 'outputs' / 'desktop-ui-check'
    output.mkdir(parents=True, exist_ok=True)
    messages = []
    def log(kind, context, message):
        messages.append(message)
        print(message.encode('ascii', errors='backslashreplace').decode(), flush=True)
    qInstallMessageHandler(log)
    app = QApplication([])
    icon = QIcon(str(UI_DIRECTORY / 'brand.ico'))
    assert not icon.isNull()
    for size in (16, 20, 24, 32, 40, 48, 64, 128, 256):
        assert QSize(size, size) in icon.availableSizes()
        assert not icon.pixmap(size, size).isNull()
    app.setWindowIcon(icon)
    app.setFont(QFont('Microsoft YaHei UI', 10))
    QQuickStyle.setStyle('Basic')
    with tempfile.TemporaryDirectory() as temporary:
        controller = AppController(QSettings(str(Path(temporary) / 'prefs.ini'), QSettings.Format.IniFormat))
        engine = QQmlApplicationEngine()
        engine.rootContext().setContextProperty('controller', controller)
        print('Loading QML...', flush=True)
        engine.load(QUrl.fromLocalFile(str(UI_DIRECTORY / 'Main.qml')))
        print('QML loaded; waiting for render...', flush=True)
        if not engine.rootObjects():
            raise RuntimeError('\n'.join(messages))
        window = engine.rootObjects()[0]
        window.setIcon(icon)
        controller.window = window
        QTest.qWait(1800)

        def capture(name):
            print(f'Capturing {name}...', flush=True)
            QTest.qWait(500)
            screenshot = window.grabWindow()
            assert not screenshot.isNull(), f'Empty capture: {name}'
            assert screenshot.save(str(output / f'{name}.png'))

        def wait_for(predicate, timeout=3.5):
            deadline = time.monotonic() + timeout
            while not predicate() and time.monotonic() < deadline:
                QTest.qWait(50)
            assert predicate(), 'UI state did not settle before deadline'

        def visual_items(name):
            def visit(item):
                found = [item] if item.objectName() == name else []
                for child in item.childItems():
                    found.extend(visit(child))
                return found
            return visit(window.contentItem())

        capture('01-workbench')
        assert not window.icon().isNull()
        mark=window.findChild(QObject,'brandMark')
        assert mark.property('assetReady') and str(mark.property('source').toString()).endswith('brand.png')
        character = window.findChild(QObject, 'ditingCharacter')
        assert character is not None
        assert character.property('assetReady')
        assert '23-joint skinned 3D' in character.property('representation')
        assert not window.findChild(QObject, 'startDetection').property('enabled')
        assert not any('reference_run' in str(getattr(m, '__file__', '')) for m in list(sys.modules.values()) if m)
        controller._busy = True
        controller.changed.emit()
        wait_for(lambda: character.property('listening') > 0.99)
        capture('02-listening')
        controller.toggleReducedMotion()
        wait_for(lambda: character.property('listening') < 0.01)
        assert controller.busy, 'Reducing animation must not cancel detection'
        controller.toggleReducedMotion()
        wait_for(lambda: character.property('listening') > 0.99)
        controller._busy = False
        controller.changed.emit()
        wait_for(lambda: character.property('listening') < 0.01)

        fixture = Path(temporary) / 'preview.png'
        image = QImage(600, 800, QImage.Format.Format_RGB32)
        image.fill('#b8cdbc')
        image.save(str(fixture))
        controller.load_file(fixture)
        QTest.qWait(300)
        assert window.property('mediaImageReady')
        capture('03-imported')
        window.setProperty('activePage', 'results')
        QTest.qWait(200)
        result_page = window.findChild(QObject, 'resultPage')
        assert result_page.property('visible')
        assert not result_page.property('heatmapReady')
        result_page.setProperty('viewMode', 2)
        capture('07-result-comparison')
        result_page.setProperty('zoom', 2)
        QTest.qWait(150)
        viewports = visual_items('resultViewport')
        assert len(viewports) == 2
        viewports[0].setProperty('contentX', 50.0)
        viewports[0].setProperty('contentY', 40.0)
        QTest.qWait(150)
        assert abs(viewports[1].property('contentX') - 50.0) < 1
        assert abs(viewports[1].property('contentY') - 40.0) < 1
        QMetaObject.invokeMethod(result_page, 'fitImage')
        QTest.qWait(100)
        assert all(abs(v.property('contentX')) < 1 for v in viewports)
        for original in visual_items('resultOriginal'):
            assert abs(original.property('paintedWidth') / original.property('paintedHeight') - 0.75) < 0.01, (original.property('sourceSize'), original.property('paintedWidth'), original.property('paintedHeight'))
        window.setProperty('activePage', 'history')
        QTest.qWait(200)
        assert window.findChild(QObject, 'historyPage').property('visible')
        assert controller.historyCount == 1
        capture('08-history')
        history_page = window.findChild(QObject, 'historyPage')
        history_page.setProperty('query', 'no-match')
        QTest.qWait(100)
        assert window.findChild(QObject, 'historyList').property('count') == 0
        history_page.setProperty('query', '')
        record = controller.historyRecords[0]
        assert controller.reopenRecord(record['id'])
        QTest.qWait(100)
        assert controller.historyCount == 1
        assert window.property('activePage') == 'workspace'
        controller.togglePet()
        assert controller.petTransitioning
        controller.togglePet()  # A rapid second click cannot reverse halfway.
        wait_for(lambda: not controller.petTransitioning)
        assert abs(window.opacity() - 1) < 0.001
        assert window.width() == 300
        assert window.findChild(QObject, 'ditingCharacter') is character
        pet_hint = window.findChild(QObject, 'petHint')
        pet_actions = window.findChild(QObject, 'petActions')
        def move_pet_mouse(point):
            # Use native movement for both entry and exit. Mixing QTest's
            # synthetic moves with a stationary OS cursor can miss Leave.
            window.raise_()
            window.requestActivate()
            QCursor.setPos(window.mapToGlobal(point))
            QTest.qWait(150)
        move_pet_mouse(QPointF(-30, 150).toPoint())
        wait_for(lambda: not pet_hint.property('visible') and not pet_actions.property('visible'))
        capture('04-desktop-pet')
        # Verify a transparent native window, not an ivory screenshot rectangle.
        assert window.grabWindow().pixelColor(0, window.height() - 1).alpha() == 0
        move_pet_mouse(QPointF(150, 170).toPoint())
        wait_for(lambda: pet_hint.property('visible') and pet_actions.property('visible'))
        capture('04b-desktop-pet-hover')
        for name, kind in [('petPhoto', 'image'), ('petVideo', 'video')]:
            button = window.findChild(QObject, name)
            center = button.mapToScene(QPointF(button.width() / 2, button.height() / 2)).toPoint()
            move_pet_mouse(center)
            QTest.qWait(150)
            assert pet_hint.property('visible') and pet_actions.property('visible'), (name, center, window.mapFromGlobal(QCursor.pos()), button.property('hovered'))
            with patch('faceguard.app.QFileDialog.getOpenFileName', return_value=('', '')) as choose:
                QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, center)
                assert choose.call_count == 1
                assert ('选择照片' if kind == 'image' else '选择视频') in choose.call_args.args
        move_pet_mouse(QPointF(150, 20).toPoint())
        QTest.qWait(100)
        assert pet_actions.property('visible')
        move_pet_mouse(QPointF(-30, 150).toPoint())
        wait_for(lambda: not pet_hint.property('visible') and not pet_actions.property('visible'))
        expand = window.findChild(QObject, 'petExpand')
        center = expand.mapToScene(QPointF(expand.width() / 2, expand.height() / 2)).toPoint()
        move_pet_mouse(QPointF(150, 170).toPoint())
        wait_for(lambda: pet_actions.property('visible'))
        move_pet_mouse(center)
        QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, center)
        wait_for(lambda: not controller.petTransitioning)
        assert window.width() == 1380
        assert controller.fileName == 'preview.png'
        controller.toggleReducedMotion()
        QTest.qWait(1000)
        assert character.property('reducedMotion')
        window.resize(1080, 720)
        capture('05-small-window')
        details = window.findChild(QObject, 'technicalDetails')
        assert not details.property('visible'), 'Technical details must not appear on the workspace'
        settings = window.findChild(QObject, 'settingsDialog')
        QMetaObject.invokeMethod(settings, 'open')
        QTest.qWait(300)
        assert details.property('visible')
        advanced = window.findChild(QObject, 'advancedModelOptions')
        selector = window.findChild(QObject, 'generationModelSelector')
        assert not selector.property('visible'), 'Experimental versions must be collapsed initially'
        capture('13-settings')
        marks=visual_items('dialogBrandMark')
        assert marks and all(m.property('assetReady') and m.property('source').toString().endswith('brand.png') for m in marks)
        reduced_switch = visual_items('reducedMotionSwitch')[0]
        reduced_before = controller.reducedMotion
        switch_point = reduced_switch.mapToScene(QPointF(20, reduced_switch.height() / 2)).toPoint()
        QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, switch_point)
        wait_for(lambda: controller.reducedMotion != reduced_before)
        assert reduced_switch.property('checked') == controller.reducedMotion
        QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, switch_point)
        wait_for(lambda: controller.reducedMotion == reduced_before)
        assert reduced_switch.property('checked') == controller.reducedMotion
        QMetaObject.invokeMethod(advanced, 'clicked')
        QTest.qWait(300)
        assert selector.property('visible')
        assert settings.property('height') <= window.height() - 60
        capture('14-settings-advanced')
        selector_center = selector.mapToScene(QPointF(selector.width() / 2, selector.height() / 2)).toPoint()
        QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, selector_center)
        wait_for(lambda: QQmlProperty(selector, 'popup.visible').read())
        capture('15-model-choices')
        QTest.keyClick(window, Qt.Key_Escape)
        wait_for(lambda: not QQmlProperty(selector, 'popup.visible').read())
        assert settings.property('visible')
        QMetaObject.invokeMethod(settings, 'close')
        for name, screenshot in [('guideDialog', '16-guide'), ('technicalDetailsDialog', '17-technical'), ('mediaPreviewDialog', '18-media-preview')]:
            dialog = window.findChild(QObject, name)
            QMetaObject.invokeMethod(dialog, 'open')
            capture(screenshot)
            assert dialog.property('visible')
            assert dialog.property('height') <= window.height() - 50
            QMetaObject.invokeMethod(dialog.findChild(QObject, 'dialogConfirm'), 'clicked')
            wait_for(lambda: not dialog.property('visible'))
        clear_dialog = window.findChild(QObject, 'clearHistoryDialog')
        history_count = controller.historyCount
        QMetaObject.invokeMethod(clear_dialog, 'open')
        capture('19-history-confirmation')
        QMetaObject.invokeMethod(clear_dialog.findChild(QObject, 'dialogCancel'), 'clicked')
        wait_for(lambda: not clear_dialog.property('visible'))
        assert controller.historyCount == history_count
        window.setProperty('activePage', 'results')
        capture('09-small-results')
        window.setProperty('activePage', 'history')
        capture('10-small-history')
        window.setProperty('activePage', 'workspace')
        controller.togglePet()
        assert not controller.petTransitioning
        assert window.width() == 300
        move_pet_mouse(QPointF(-30, 150).toPoint())
        wait_for(lambda: not pet_actions.property('visible'))
        move_pet_mouse(QPointF(150, 170).toPoint())
        wait_for(lambda: pet_actions.property('visible'))
        QTest.mouseDClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPointF(150, 170).toPoint())
        assert window.width() == 1080
        checks = ['reference-derived 23-joint skinned 3D character', 'busy-bound listening and return', 'reduced motion stops listening without cancelling detection', 'styled dialogs accept/reject; history cancel preserves records', 'model dropdown opens by mouse and closes by Escape', 'image import', 'same character retained across modes', 'transparent pet window', 'file retained across modes', 'reduced motion', '1080x720 layout', 'technical details only in settings; experimental versions initially collapsed', 'detection requires a selected file', 'reference_run not imported', 'large original/heatmap/comparison result area', 'no fabricated heatmaps', 'history filtering and reopening without duplication', 'synchronized comparison panning + fit reset', 'fade transition + rapid-click guard']
        checks.append('pet hint/actions hide on native pointer exit; remain visible over buttons; photo/video/expand clicks and reduced-motion double-click work')
        ffmpeg = shutil.which('ffmpeg')
        if ffmpeg:
            fixture_video = Path(temporary) / 'preview.mp4'
            subprocess.run([ffmpeg, '-v', 'error', '-f', 'lavfi', '-i', 'color=c=0xb8cdbc:s=320x240:d=3', '-pix_fmt', 'yuv420p', '-y', str(fixture_video)], check=True, timeout=15)
            controller.load_file(fixture_video)
            QTest.qWait(500)
            video_player = window.findChild(QObject, 'mediaPlayer')
            QMetaObject.invokeMethod(video_player, 'play')
            QTest.qWait(1000)
            assert window.property('videoIsPlaying')
            assert window.property('videoPosition') > 0
            assert not controller.errorText
            capture('06-video')
            QMetaObject.invokeMethod(video_player, 'stop')
            controller.clearFile()
            QTest.qWait(200)
            checks.append('actual local MP4 decoding and playback')
        # Exercise the prepared skinned asset through the actual Qt renderer.
        volume_dialog = window.findChild(QObject, 'volumePreviewDialog')
        assert volume_dialog is not None
        QMetaObject.invokeMethod(volume_dialog, 'open')
        volume = None
        for _ in range(60):
            QTest.qWait(200)
            volume = window.findChild(QObject, 'ditingVolumePreview')
            if volume is not None and volume.property('assetReady'):
                break
        assert volume is not None and volume.property('assetReady'), '\n'.join(messages)
        capture('11-volume-preview')
        before_frame = window.grabWindow()
        before_turn = hashlib.sha256(bytes(before_frame.constBits())).hexdigest()
        volume.setProperty('angle', 160.0)
        QTest.qWait(350)
        capture('12-volume-rotated')
        after_frame = window.grabWindow()
        after_turn = hashlib.sha256(bytes(after_frame.constBits())).hexdigest()
        assert before_turn != after_turn, 'Rotating the loaded mesh must change rendered pixels'
        QMetaObject.invokeMethod(volume, 'resetOrientation')
        assert abs(volume.property('angle')) < .01
        QMetaObject.invokeMethod(volume_dialog, 'close')
        QTest.qWait(500)
        volume_loader = window.findChild(QObject, 'volumePreviewLoader')
        assert volume_loader.property('item') is None, 'Closing preview must release its scene'
        checks.extend(['prepared textured skin loads in Qt Quick 3D', '3D rotation changes actual rendered pixels', '3D orientation reset', '3D preview releases scene on close'])
        forbidden = [m for m in messages if any(term in m for term in ('ReferenceError', 'TypeError', 'is not a type', 'Cannot assign', 'Binding loop', 'Unable to assign', 'Failed to create', 'Failed to load shader', 'Shader compilation failed'))]
        assert not forbidden, '\n'.join(forbidden)
        report = {'passed': True, 'checks': checks, 'video_check': 'passed' if ffmpeg else 'skipped: ffmpeg not installed', 'messages': messages}
        (output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(report, ensure_ascii=True, indent=2))
        faulthandler.cancel_dump_traceback_later()
        window.close()
        engine.deleteLater()
        QTest.qWait(100)
    app.quit()


if __name__ == '__main__':
    main()
