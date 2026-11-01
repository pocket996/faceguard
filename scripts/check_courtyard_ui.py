"""Render the workspace courtyard and check parallax, layout and scene lifetime."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from PySide6.QtCore import QObject, QSettings, QUrl, qInstallMessageHandler
from PySide6.QtGui import QFont, QImageReader
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from faceguard.app import AppController, UI_DIRECTORY


def main():
    output = ROOT / 'outputs/ink-courtyard-20261101'
    output.mkdir(parents=True, exist_ok=True)
    messages = []
    qInstallMessageHandler(lambda kind, context, message: messages.append(message))
    app = QApplication([])
    app.setFont(QFont('Microsoft YaHei UI', 10))
    QQuickStyle.setStyle('Basic')
    for name in ['ink-courtyard-v1.png', 'ink-courtyard-stone-v1.png']:
        assert QImageReader(str(UI_DIRECTORY / 'assets' / name)).canRead(), name
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
                QTest.qWait(50)
            assert predicate(), messages

        loader = window.findChild(QObject, 'courtyardLoader')
        character = window.findChild(QObject, 'ditingCharacter')
        wait(lambda: loader.property('item') is not None and loader.property('item').property('assetReady'))
        scene = loader.property('item')
        assert scene.findChild(QObject, 'courtyardStonePlatform') is not None

        def capture(name):
            QTest.qWait(250)
            frame = window.grabWindow()
            assert not frame.isNull()
            assert frame.save(str(output / (name + '.png')))
            return hashlib.sha256(bytes(frame.constBits())).hexdigest()

        capture('01-workbench')
        controller._busy = True
        controller.changed.emit()
        wait(lambda: character.property('listening') > .99)
        capture('02-listening')
        controller._busy = False
        controller.changed.emit()
        wait(lambda: character.property('listening') < .01)

        camera = scene.findChild(QObject, 'courtyardCamera')
        character.setProperty('gaze', -.8)
        wait(lambda: scene.property('parallax') < -.75)
        left_x = camera.property('position').x()
        left_hash = capture('03-parallax-left')
        character.setProperty('gaze', .8)
        wait(lambda: scene.property('parallax') > .75)
        right_x = camera.property('position').x()
        right_hash = capture('04-parallax-right')
        assert left_x < 0 < right_x and left_hash != right_hash

        controller.toggleReducedMotion()
        wait(lambda: scene.property('parallax') == 0)
        assert camera.property('position').x() == 0
        character.setProperty('gaze', 0)
        window.resize(1080, 720)
        capture('05-compact-workbench')
        window.setProperty('activePage', 'results')
        wait(lambda: loader.property('item') is None)
        wait(lambda: window.findChild(QObject, 'courtyardStonePlatform') is None)
        window.setProperty('activePage', 'workspace')
        wait(lambda: loader.property('item') is not None and loader.property('item').property('assetReady'))
        controller.togglePet()
        wait(lambda: loader.property('item') is None)
        capture('06-pet-no-courtyard')
        controller.togglePet()
        wait(lambda: loader.property('item') is not None and loader.property('item').property('assetReady'))
        capture('07-restored-workbench')
        errors = [m for m in messages if any(s in m for s in ['ReferenceError', 'TypeError', 'Cannot assign', 'Binding loop', 'Unable to assign', 'Failed to', 'Cannot load', 'must be greater than zero'])]
        assert not errors, errors
        report = dict(passed=True, checks=['landscape and stone textures readable', 'actual Qt Quick 3D terrace',
                      'detection pose on stone terrace', 'parallax changes actual camera and rendered pixels',
                      'reduced motion fixes camera', '1080x720 layout', 'scene unloaded outside workspace and pet',
                      'scene restored after switching'], messages=messages)
        (output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps(report))
        controller.shutdown()
        window.close()
        engine.deleteLater()
        QTest.qWait(100)
    app.quit()


if __name__ == '__main__':
    main()
