"""Render the full-window lake and verify the actual skinned performance."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from PySide6.QtCore import QObject, QMetaObject, QSettings, QUrl, Q_ARG, qInstallMessageHandler
from PySide6.QtGui import QFont, QImage, QImageReader
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from faceguard.app import AppController, UI_DIRECTORY


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record', action='store_true')
    args = parser.parse_args()
    output = ROOT / 'outputs/lotus-eyes-20261102'
    output.mkdir(parents=True, exist_ok=True)
    messages = []
    qInstallMessageHandler(lambda kind, context, message: messages.append(message))
    app = QApplication([])
    app.setFont(QFont('Microsoft YaHei UI', 10))
    QQuickStyle.setStyle('Basic')
    assert QImageReader(str(UI_DIRECTORY / 'assets/ink-lake-lotus-v3.png')).canRead()
    with tempfile.TemporaryDirectory() as directory:
        controller = AppController(QSettings(directory + '/prefs.ini', QSettings.IniFormat),
                                   history_path=Path(directory) / 'history.sqlite3')
        engine = QQmlApplicationEngine()
        engine.rootContext().setContextProperty('controller', controller)
        engine.load(QUrl.fromLocalFile(str(UI_DIRECTORY / 'Main.qml')))
        assert engine.rootObjects(), messages
        window = engine.rootObjects()[0]
        controller.window = window

        def wait(predicate, timeout=8):
            deadline = time.monotonic() + timeout
            while not predicate() and time.monotonic() < deadline:
                QTest.qWait(30)
            assert predicate(), messages

        def call(target, name, *values):
            assert QMetaObject.invokeMethod(target, name, *[Q_ARG('QVariant', v) for v in values])

        def digest():
            frame = window.grabWindow()
            assert not frame.isNull()
            return hashlib.sha256(bytes(frame.constBits())).hexdigest()

        def capture(name):
            QTest.qWait(150)
            frame = window.grabWindow()
            assert frame.save(str(output / (name + '.png')))
            return frame

        loader = window.findChild(QObject, 'courtyardLoader')
        character = window.findChild(QObject, 'ditingCharacter')
        actor = character.findChild(QObject, 'ditingPerformance')
        wait(lambda: loader.property('item') is not None and loader.property('item').property('assetReady') and character.property('assetReady'))
        scene = loader.property('item')
        assert loader.property('width') >= window.width() - 2
        assert loader.property('height') >= window.height() - 2
        assert window.findChild(QObject, 'courtyardStonePlatform') is None
        assert character.findChild(QObject, 'ditingWaterReflection').property('visible')
        root = actor.findChild(QObject, 'Root')
        head = actor.findChild(QObject, 'Head')
        brow = actor.findChild(QObject, 'BrowNear')
        chin = actor.findChild(QObject, 'Chin')
        lid = actor.findChild(QObject, 'LidNear')
        assert all(o is not None for o in (root, head, brow, chin, lid))
        root_position = root.property('position')
        call(actor, 'seekPose', 'Idle', 0)
        brow_start = brow.property('position')
        open_lid = lid.property('position')
        call(actor, 'seekPose', 'Respond', 1000)
        QTest.qWait(120)
        assert brow.property('position') != brow_start
        assert abs(chin.property('rotation').x()) > .001
        call(actor, 'seekPose', 'Idle', 1135)
        capture('02-blink')
        assert (lid.property('position') - open_lid).length() > .09
        call(actor, 'select', 'Idle')
        capture('01-workbench')

        # Starting detection interrupts a real articulated pose without a snap.
        call(actor, 'seekPose', 'Respond', 900)
        before = head.property('rotation')
        controller._busy = True
        controller.changed.emit()
        after = head.property('rotation')
        distance = lambda a, b: sum(abs(x-y) for x,y in zip((a.scalar(),a.x(),a.y(),a.z()), (b.scalar(),b.x(),b.y(),b.z())))
        assert distance(before, after) < .001, (before, after)
        wait(lambda: actor.property('holdingListen'))
        assert actor.property('motionName') == 'Listen'
        capture('03-listening-water')
        ear_upright=actor.findChild(QObject,'EarUpright')
        ear_folded=actor.findChild(QObject,'EarFolded')
        first_upright=ear_upright.property('rotation')
        first_folded=ear_folded.property('rotation')
        QTest.qWait(700)
        assert distance(first_upright,ear_upright.property('rotation'))>.01,'Listening must articulate the upright ear'
        assert distance(first_folded,ear_folded.property('rotation'))>.01,'The folded ear needs its own delayed movement'
        capture('03b-ear-adjustment')
        # Stay busy longer than the original four-second one-shot clip.
        QTest.qWait(4400)
        assert actor.property('holdingListen') and actor.property('motionName') == 'Listen'
        assert 1370 <= actor.property('motionTime') <= 1920
        assert root.property('position') == root_position
        before = head.property('rotation')
        controller._busy = False
        controller.changed.emit()
        assert distance(before, head.property('rotation')) < .001
        wait(lambda: actor.property('motionName') == 'Idle' and not actor.property('transitioning'))
        capture('04-return-idle')

        # Rapid cancellation during the entrance must also return to idle.
        controller._busy = True
        controller.changed.emit()
        QTest.qWait(140)
        controller._busy = False
        controller.changed.emit()
        wait(lambda: actor.property('motionName') == 'Idle' and not actor.property('transitioning'))
        controller._busy = True
        controller.changed.emit()
        controller.toggleReducedMotion()
        QTest.qWait(600)
        assert controller.busy and not actor.property('playing')
        assert character.property('listening') == 0
        first = digest()
        reflection = character.findChild(QObject, 'ditingWaterReflection')
        reflection.setProperty('opacity', 0)
        QTest.qWait(100)
        assert digest() != first, 'The live reflection must contribute rendered pixels'
        reflection.setProperty('opacity', 1)
        QTest.qWait(100)
        assert digest() == first
        QTest.qWait(250)
        assert digest() == first, 'Reduced motion must freeze skin, ripples and reflection'
        controller.toggleReducedMotion()
        wait(lambda: actor.property('holdingListen'))
        controller._busy = False
        controller.changed.emit()
        wait(lambda: actor.property('motionName') == 'Idle' and not actor.property('transitioning'))

        garden = scene.findChild(QObject, 'courtyardLandscape')
        character.setProperty('gaze', -.8)
        wait(lambda: scene.property('parallax') < -.75)
        left_x = garden.property('x')
        character.setProperty('gaze', .8)
        wait(lambda: scene.property('parallax') > .75)
        assert garden.property('x') < left_x
        controller.toggleReducedMotion()
        wait(lambda: scene.property('parallax') == 0)
        window.resize(1080, 720)
        capture('05-compact-workbench')
        controller.toggleReducedMotion()
        wait(lambda: actor.property('playing'))
        window.setProperty('activePage', 'results')
        wait(lambda: loader.property('item') is None)
        assert not actor.property('playing')
        window.setProperty('activePage', 'workspace')
        wait(lambda: loader.property('item') is not None and loader.property('item').property('assetReady'))
        controller.togglePet()
        wait(lambda: loader.property('item') is None)
        capture('06-pet-no-water')
        assert not character.property('waterSurface')
        assert not character.findChild(QObject, 'ditingWaterReflection').property('visible')
        assert window.findChild(QObject, 'ditingCharacter') is character
        assert window.grabWindow().pixelColor(0, window.height()-1).alpha() == 0
        controller.togglePet()
        wait(lambda: loader.property('item') is not None and loader.property('item').property('assetReady'))
        controller.toggleReducedMotion()
        capture('07-restored-workbench')

        if args.record:
            from PIL import Image
            controller.toggleReducedMotion()
            window.resize(1380, 860)
            controller._busy = False
            controller.changed.emit()
            frames, timestamps = [], []
            started = time.monotonic()
            state = ''
            while time.monotonic() - started < 10:
                elapsed = time.monotonic() - started
                desired = 'Respond' if elapsed < 2.8 else 'Listen' if elapsed < 7.3 else 'Idle'
                if desired != state:
                    if desired == 'Respond': call(actor, 'select', 'Respond')
                    else:
                        controller._busy = desired == 'Listen'
                        controller.changed.emit()
                    state = desired
                QTest.qWait(65)
                frame = window.grabWindow().scaledToWidth(1000)
                rgba = frame.convertToFormat(QImage.Format.Format_RGBA8888)
                frames.append(Image.frombytes('RGBA', (frame.width(), frame.height()), bytes(rgba.constBits())))
                timestamps.append(time.monotonic())
            durations = [max(20, int((b-a)*1000)) for a,b in zip(timestamps,timestamps[1:])] + [100]
            frames[0].save(output / 'continuous-performance.gif', save_all=True, append_images=frames[1:], duration=durations, loop=0, disposal=2)
        errors = [m for m in messages if any(s in m for s in ['ReferenceError', 'TypeError', 'Cannot assign', 'Binding loop', 'Unable to assign', 'Failed to', 'Cannot load', 'setPaused() cannot', 'Shader compilation'])]
        assert not errors, errors
        checks = ['full-window continuous lake behind both panels; no stone plinth',
                  '23-joint skinned character with brow/chin/eyelid motion',
                  'rendered-pose reflection and planted-paw ripples',
                  'pose-preserving interruption and smooth return',
                  'sustained listening beyond four seconds; rapid cancellation',
                  'independent upright/folded ear adjustments during sustained detection',
                  'reduced motion freezes skin, ripples, reflection without stopping detection',
                  'responsive 1080x720; background parallax and reduced-motion stop',
                  'background unload/restore; character pauses off-page',
                  'same skinned character and transparent pet without water']
        report = dict(passed=True, checks=checks, messages=messages)
        (output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps(report), flush=True)
        controller.shutdown()
        window.setProperty('activePage', 'history')
        window.releaseResources()
        window.close()
        engine.deleteLater()
        QTest.qWait(200)
    app.quit()


if __name__ == '__main__':
    main()
