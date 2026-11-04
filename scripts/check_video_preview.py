"""Exercise silent preview with real audio streams; --baseline reproduces old wiring."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from PySide6.QtCore import QObject, QMetaObject, QSettings, QUrl, qInstallMessageHandler
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtMultimedia import QVideoSink
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from faceguard.app import AppController, UI_DIRECTORY


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', action='store_true')
    args = parser.parse_args()
    output = ROOT / 'outputs/video-dual-20261103/preview'
    output.mkdir(parents=True, exist_ok=True)
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        raise RuntimeError('ffmpeg required for audio fixtures')
    app = QApplication([])
    QQuickStyle.setStyle('Basic')
    messages = []
    qInstallMessageHandler(lambda kind, context, message: messages.append(message))
    checks = []
    with tempfile.TemporaryDirectory() as folder:
        controller = AppController(QSettings(str(Path(folder) / 'prefs.ini'), QSettings.Format.IniFormat),
                                   history_path=Path(folder) / 'history.sqlite3')
        engine = QQmlApplicationEngine()
        engine.rootContext().setContextProperty('controller', controller)
        source = (UI_DIRECTORY / 'Main.qml').read_text(encoding='utf-8')
        if args.baseline:
            source = source.replace('activeAudioTrack: -1', 'audioOutput: AudioOutput { muted: true }')
            source = source.replace('onTracksChanged: activeAudioTrack = -1', '')
        engine.loadData(source.encode(), QUrl.fromLocalFile(str(UI_DIRECTORY / 'Main.qml')))
        assert engine.rootObjects(), messages
        window = engine.rootObjects()[0]
        controller.window = window
        QTest.qWait(1000)
        player = window.findChild(QObject, 'mediaPlayer')
        for extension, codec, channels in [('mp4', 'aac', 2), ('mkv', 'pcm_s24le', 1)]:
            fixture = Path(folder) / ('audio-preview.' + extension)
            subprocess.run([ffmpeg, '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=s=320x240:r=25:d=4',
                            '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=44100:duration=4',
                            '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', codec, '-ac', str(channels),
                            '-shortest', '-y', str(fixture)], check=True, timeout=25)
            assert controller.load_file(fixture)
            QTest.qWait(600)
            QMetaObject.invokeMethod(player, 'play')
            QTest.qWait(1400)
            assert window.property('videoIsPlaying') and window.property('videoPosition') > 500
            assert not controller.errorText, controller.errorText
            if not args.baseline:
                assert player.property('activeAudioTrack') == -1
                assert player.property('audioOutput') is None
            # Check actual decoded frames, not just an advancing clock.
            sink = player.property('videoOutput').property('videoSink')
            assert isinstance(sink, QVideoSink)
            frame = sink.videoFrame()
            assert frame.isValid() and not frame.toImage().isNull()
            frame.toImage().save(str(output / f'{extension}-decoded.png'))
            QMetaObject.invokeMethod(player, 'pause')
            previous = window.property('videoPosition')
            QTest.qWait(250)
            assert abs(window.property('videoPosition') - previous) < 100
            QMetaObject.invokeMethod(player, 'play')
            QTest.qWait(400)
            assert window.property('videoPosition') > previous
            QMetaObject.invokeMethod(player, 'stop')
            checks.append(dict(codec=codec, channels=channels, decoded=True, pause_resume=True,
                               disabled_audio=player.property('activeAudioTrack') == -1))
        window.grabWindow().save(str(output / ('baseline.png' if args.baseline else 'fixed.png')))
        controller.clearFile()
        QTest.qWait(200)
        controller.shutdown()
        window.close()
        engine.deleteLater()
        QTest.qWait(200)
    errors = [m for m in messages if any(s in m for s in ('ReferenceError', 'TypeError', 'Cannot assign', 'Binding loop'))]
    assert not errors, errors
    report = dict(baseline=args.baseline, passed=True, checks=checks, messages=messages)
    (output / ('baseline.json' if args.baseline else 'fixed.json')).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=True, indent=2), flush=True)
    app.quit()


if __name__ == '__main__':
    main()
