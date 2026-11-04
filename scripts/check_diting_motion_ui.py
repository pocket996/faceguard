"""Real Qt skeletal playback checks and optional application recording."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from PySide6.QtCore import QObject,QMetaObject,QSettings,QUrl,Q_ARG,QPointF,qInstallMessageHandler
from PySide6.QtGui import QFont, QVector3D, QImage
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from faceguard.app import AppController,UI_DIRECTORY


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--record',action='store_true')
    args=p.parse_args()
    out=ROOT/'outputs/diting-3d/eyes-v7/ui-check';out.mkdir(parents=True,exist_ok=True)
    messages=[]
    def log(kind,context,message):
        messages.append(message);print(message.encode('ascii',errors='backslashreplace').decode(),flush=True)
    qInstallMessageHandler(log)
    app=QApplication([]);app.setFont(QFont('Microsoft YaHei UI',10));QQuickStyle.setStyle('Basic')
    with tempfile.TemporaryDirectory() as tmp:
        controller=AppController(QSettings(str(Path(tmp)/'prefs.ini'),QSettings.IniFormat))
        engine=QQmlApplicationEngine();engine.rootContext().setContextProperty('controller',controller)
        engine.load(QUrl.fromLocalFile(str(UI_DIRECTORY/'Main.qml')))
        assert engine.rootObjects(),messages
        window=engine.rootObjects()[0];controller.window=window;window.resize(1080,720)
        QTest.qWait(600)
        dialog=window.findChild(QObject,'volumePreviewDialog')
        QMetaObject.invokeMethod(dialog,'open')
        volume=None
        for _ in range(80):
            QTest.qWait(100)
            volume=window.findChild(QObject,'ditingVolumePreview')
            if volume and volume.property('assetReady'):break
        assert volume and volume.property('assetReady'),messages
        def call(name,*values):
            assert QMetaObject.invokeMethod(volume,name,*[Q_ARG('QVariant',v) for v in values])
        def digest():
            frame=window.grabWindow()
            assert not frame.isNull()
            return hashlib.sha256(bytes(frame.constBits())).hexdigest()
        def pose(name,milliseconds):
            call('seekPose',name,milliseconds);QTest.qWait(180)
        def capture(name):
            image=window.grabWindow();assert image.save(str(out/f'{name}.png'))
        def vector(obj,prop):
            value=obj.property(prop);return [value.x(),value.y(),value.z()]
        root=volume.findChild(QObject,'Root');chest=volume.findChild(QObject,'Chest');head=volume.findChild(QObject,'Head')
        assert root and chest and head
        root_position=vector(root,'position')
        pose('Idle',0);before=digest();before_chest=vector(chest,'scale')
        pose('Idle',1200);after=digest();after_chest=vector(chest,'scale')
        assert before!=after and before_chest!=after_chest,'Idle must deform the skinned chest'
        assert volume.property('angle')==0 and vector(root,'position')==root_position
        capture('idle-peak')
        lid=volume.findChild(QObject,'LidNear')
        assert lid,'The facial lid must be a real animated joint'
        pose('Idle',0);open_lid=vector(lid,'position')
        # Blender frame 1 is exported at 33.33 ms, so frame 34 (blink peak)
        # lands at 1133.33 ms in the Qt timeline.
        pose('Idle',1135);closed_lid=vector(lid,'position');capture('blink')
        assert sum(abs(a-b) for a,b in zip(open_lid,closed_lid))>.09,('Blink must move the eyelid geometry',open_lid,closed_lid)
        pose('Respond',1000);capture('respond-peak')
        rotation=head.property('rotation')
        assert abs(rotation.x())+abs(rotation.y())+abs(rotation.z())>.01
        pose('Listen',1600);capture('listen-peak')
        assert vector(root,'position')==root_position
        for layer in ('EyeScleraNear','EyeIrisNear','EyePupilNear','EyeCorneaNear'):
            assert volume.findChild(QObject,layer), layer
        camera=volume.findChild(QObject,'ditingPreviewCamera')
        aim=volume.findChild(QObject,'ditingPreviewAim')
        old_camera=camera.property('position');old_aim=aim.property('position')
        magnification=camera.property('horizontalMagnification')
        camera.setProperty('position',QVector3D(-3.6,3.6,7.5))
        aim.setProperty('position',QVector3D(.4,3.02,.95))
        camera.setProperty('horizontalMagnification',magnification*3.1)
        camera.setProperty('verticalMagnification',magnification*3.1)
        pose('Idle',0);capture('eye-open-closeup')
        cornea=volume.findChild(QObject,'Transparent convex cornea Near')
        assert cornea
        before_image=window.grabWindow()
        cornea.setProperty('highlightStrength',0)
        QTest.qWait(150)
        capture('eye-without-reflection')
        from PIL import Image, ImageChops
        # Record the reflection strength in the viewport, excluding the moving
        # workspace visible behind the modal dialog.
        corner=volume.mapToScene(QPointF(0,0))
        def pil_view(frame):
            scale=frame.width()/window.width()
            frame=frame.copy(round(corner.x()*scale),round(corner.y()*scale),round(volume.width()*scale),round(volume.height()*scale)).convertToFormat(QImage.Format.Format_RGBA8888)
            return Image.frombytes('RGBA',(frame.width(),frame.height()),bytes(frame.constBits()))
        difference=ImageChops.difference(pil_view(before_image),pil_view(window.grabWindow()))
        reflection_change=difference.convert('RGB').getextrema()
        print('cornea_pixel_change:',reflection_change,flush=True)
        assert max(pair[1] for pair in reflection_change)>=40,'The wet cornea highlight must be visible, not just numerically different'
        cornea.setProperty('highlightStrength',1)
        QTest.qWait(180);capture('eye-open-closeup')
        pose('Idle',1135);capture('eye-closed-closeup')
        camera.setProperty('position',old_camera);aim.setProperty('position',old_aim)
        camera.setProperty('horizontalMagnification',magnification)
        camera.setProperty('verticalMagnification',magnification)
        call('playMotion','Respond')
        deadline=time.monotonic()+5
        while (volume.property('motionName')!='Idle' or volume.property('transitioning')) and time.monotonic()<deadline:QTest.qWait(50)
        assert volume.property('motionName')=='Idle',('One-shot must return to idle',volume.property('motionName'),volume.property('motionTime'),volume.property('playing'),volume.property('visible'))
        assert volume.property('playing'),'Returning idle must keep playing'
        idle_time=volume.property('motionTime');QTest.qWait(120)
        assert volume.property('motionTime')>idle_time
        pose('Listen',1600)
        old_rotation=head.property('rotation')
        magnitude=lambda q: abs(q.x())+abs(q.y())+abs(q.z())
        call('playMotion','Respond');QTest.qWait(50)
        early=head.property('rotation')
        assert magnitude(early)>.01,('Interruptions must preserve and blend the current turn rather than snap to rest',old_rotation,early)
        assert magnitude(early)<magnitude(old_rotation),'Transition should move toward rest'
        QTest.qWait(300)
        assert volume.property('motionName')=='Respond'
        assert all(abs(v-1)<1e-6 for v in vector(chest,'scale')),'Switch must clear previous breathing scale'
        call('togglePause');t=volume.property('motionTime');QTest.qWait(200)
        assert abs(volume.property('motionTime')-t)<.1
        call('togglePause');QTest.qWait(200)
        assert volume.property('motionTime')>t
        controller.toggleReducedMotion();QTest.qWait(200)
        assert volume.property('reducedMotion') and not volume.property('playing')
        static_frame=digest();QTest.qWait(220);assert digest()==static_frame
        controller.toggleReducedMotion();QTest.qWait(200)
        assert volume.property('playing') and volume.property('motionName')=='Idle'
        checks=['real 23-joint skin rendered','separate sclera/iris/recessed pupil/convex cornea','view-dependent cornea highlight verified in actual viewport pixels','idle changes chest scale and rendered pixels without rotating root',
                'eyelid joint closes during blink','large respond and listen poses render','one-shot returns to idle','interruption blends toward rest before starting next clip',
                'pause/resume retains timeline position','reduced motion stops deformation and resumes idle']
        if args.record and shutil.which('ffmpeg'):
            frames=out/'recording';frames.mkdir(exist_ok=True)
            # Sample the actual Qt skin at fixed times. A busy GPU must not
            # silently skip an entire gesture while grabWindow blocks.
            for i in range(144):
                if i<24:clip,milliseconds='Idle',i/12*1000
                elif i<56:clip,milliseconds='Respond',(i-24)/12*1000
                elif i<112:clip,milliseconds='Listen',(i-56)/12*1000
                else:clip,milliseconds='Idle',(i-112)/12*1000
                call('seekPose',clip,milliseconds);QTest.qWait(40)
                image=window.grabWindow();image.save(str(frames/f'frame-{i:03d}.png'))
            subprocess.run(['ffmpeg','-v','error','-framerate','12','-i',str(frames/'frame-%03d.png'),'-vf','scale=1080:-2','-pix_fmt','yuv420p','-y',str(out/'motion-demo.mp4')],check=True,timeout=60)
            subprocess.run(['ffmpeg','-v','error','-framerate','12','-i',str(frames/'frame-%03d.png'),'-filter_complex','fps=12,scale=810:-1:flags=lanczos,split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=3','-y',str(out/'motion-demo.gif')],check=True,timeout=60)
            checks.append('sampled actual application skin at fixed timeline times to MP4/GIF')
        controller.toggleReducedMotion();QTest.qWait(100)
        QMetaObject.invokeMethod(dialog,'close');QTest.qWait(400)
        loader=window.findChild(QObject,'volumePreviewLoader')
        assert loader.property('item') is None
        checks.append('animated scene released on close')
        forbidden=[m for m in messages if any(t in m for t in ['ReferenceError','TypeError','Cannot assign','Unable to assign','is not a type','Failed to load','Binding loop','Failed to create','setPaused() cannot','Failed to compile','Failed to parse shader'])]
        assert not forbidden,forbidden
        (out/'report.json').write_text(json.dumps({'passed':True,'checks':checks,'messages':messages},indent=2),encoding='utf-8')
        print(json.dumps({'passed':True,'checks':checks},indent=2),flush=True)
        window.close();engine.deleteLater();QTest.qWait(100)
    app.quit()


if __name__=='__main__':main()
