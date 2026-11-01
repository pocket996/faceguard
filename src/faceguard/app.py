"""Official Diting desktop application with independent local inference."""
import argparse
import json
import os
import sqlite3
from pathlib import Path
import sys
import tempfile
from uuid import uuid4

from PySide6.QtCore import QObject, Property, QPropertyAnimation, QEasingCurve, QSettings, QSize, QStandardPaths, QTimer, QUrl, Signal, Slot, Qt
from PySide6.QtGui import QFont, QIcon, QImageReader
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication, QFileDialog, QMenu, QSystemTrayIcon

from faceguard.history import HistoryStore
from faceguard.detection import DetectionWorker, DetailPreviewWorker, task_summary, detail_records
from faceguard.model_registry import resource_status, generation_profiles
from faceguard.data_locations import resolve_data_path

UI_DIRECTORY = Path(__file__).resolve().parent / 'ui'
# Keep Python-owned QML properties and rendering on the GUI thread on Windows.
os.environ.setdefault('QSG_RENDER_LOOP', 'basic')
PHOTOS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tif', '.tiff'}
VIDEOS = {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v', '.wmv'}


class AppController(QObject):
    changed = Signal()
    settingsChanged = Signal()
    previewMotion = Signal()
    historyChanged = Signal()
    mediaOpened = Signal()
    detectionFinished = Signal()

    def __init__(self, settings=None, history_path=None):
        super().__init__()
        self.settings = settings if settings is not None else QSettings('FaceGuard', 'Diting')
        self._name, self._url, self._metadata, self._error = '', QUrl(), '', ''
        self._kind = 'image'
        self._reduced = self.settings.value('reducedMotion', False, type=bool)
        self._topmost = self.settings.value('topmost', False, type=bool)
        self._pet = False
        self.window = None
        self.tray = None
        self.work_geometry = None
        self._transitioning = False
        self._fade = None
        self._worker, self._analyzer = None, None
        self._generation_models = generation_profiles()
        selected = self.settings.value('generationModel', 'stable')
        self._generation_model_index = next((i for i, p in enumerate(self._generation_models) if p['id'] == selected), 0)
        self._busy, self._cancelling = False, False
        self._progress, self._result = '', {}
        self._history_id = None
        self._detail_url, self._detail_text = QUrl(), ''
        self._frame_url = QUrl()
        self._preview_workers, self._preview_token = [], None
        self._preview_directory = None
        self._engine_ready, self._engine_status = resource_status()
        if history_path is None:
            history_path = (Path(self.settings.fileName()).parent / 'history.sqlite3' if settings is not None
                            else Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)) / 'history.sqlite3')
        self.history = HistoryStore(history_path)

    fileName = Property(str, lambda self: self._name, notify=changed)
    previewUrl = Property(QUrl, lambda self: self._url, notify=changed)
    metadata = Property(str, lambda self: self._metadata, notify=changed)
    errorText = Property(str, lambda self: self._error, notify=changed)
    mediaKind = Property(str, lambda self: self._kind, notify=changed)
    petMode = Property(bool, lambda self: self._pet, notify=settingsChanged)
    petTransitioning = Property(bool, lambda self: self._transitioning, notify=settingsChanged)
    reducedMotion = Property(bool, lambda self: self._reduced, notify=settingsChanged)
    topmost = Property(bool, lambda self: self._topmost, notify=settingsChanged)
    historyRecords = Property('QVariantList', lambda self: self.history.list(), notify=historyChanged)
    historyCount = Property(int, lambda self: len(self.history.list()), notify=historyChanged)
    generationModels = Property('QVariantList', lambda self: self._generation_models, notify=settingsChanged)
    generationModelIndex = Property(int, lambda self: self._generation_model_index, notify=settingsChanged)
    generationModelLabel = Property(str, lambda self: self._generation_models[self._generation_model_index]['label'], notify=settingsChanged)
    generationModelNotice = Property(str, lambda self: self._generation_models[self._generation_model_index].get('notice', '此候选仍可能漏检陌生生成工具，请同时关注真实照片误报。'), notify=settingsChanged)
    busy = Property(bool, lambda self: self._busy, notify=changed)
    cancelling = Property(bool, lambda self: self._cancelling, notify=changed)
    engineReady = Property(bool, lambda self: self._engine_ready, notify=changed)
    engineStatus = Property(str, lambda self: self._engine_status, notify=changed)
    progressText = Property(str, lambda self: self._progress, notify=changed)
    hasResult = Property(bool, lambda self: bool(self._result), notify=changed)
    generationSummary = Property(str, lambda self: ('视频暂不支持此项' if self._kind == 'video' and not self._result else task_summary(self._result, 'generation')), notify=changed)
    manipulationSummary = Property(str, lambda self: task_summary(self._result, 'manipulation'), notify=changed)
    resultDetails = Property('QVariantList', lambda self: detail_records(self._result), notify=changed)
    resultText = Property(str, lambda self: self.result_text(), notify=changed)
    detailPreviewUrl = Property(QUrl, lambda self: self._detail_url, notify=changed)
    selectedFrameUrl = Property(QUrl, lambda self: self._frame_url, notify=changed)
    selectedDetailText = Property(str, lambda self: self._detail_text, notify=changed)

    def _reset_detail(self):
        self._detail_url, self._detail_text, self._preview_token = QUrl(), '', None
        self._frame_url = QUrl()

    @Slot(int)
    def selectDetail(self, index):
        records = detail_records(self._result)
        if not 0 <= index < len(records):
            return
        # Bound outstanding decoders when repeatedly clicking frame rows.
        if self._preview_workers:
            return
        signature = self._result.get('source_signature')
        try:
            stat = Path(self._url.toLocalFile()).stat()
            if signature != dict(size=stat.st_size, mtime_ns=stat.st_mtime_ns):
                raise ValueError('原文件已变化，请重新检测后查看人脸。')
        except (OSError, ValueError) as error:
            self.showError(str(error))
            return
        record = records[index]
        self._detail_text = record['title'] + '\n' + record['text']
        self._detail_url = QUrl()
        self._frame_url = QUrl()
        token = uuid4().hex
        self._preview_token = token
        if self._preview_directory is None:
            self._preview_directory = tempfile.TemporaryDirectory(prefix='faceguard-preview-')
        destination = Path(self._preview_directory.name) / (token + '.png')
        worker = DetailPreviewWorker(self._url.toLocalFile(), record, destination)
        self._preview_workers.append(worker)
        def ready(filename, frame_filename):
            if token == self._preview_token:
                self._detail_url = QUrl.fromLocalFile(filename)
                self._frame_url = QUrl.fromLocalFile(frame_filename)
                self.changed.emit()
        def failed(message):
            if token == self._preview_token:
                self.showError('人脸预览失败：' + message)
        def finished():
            self._preview_workers.remove(worker)
            worker.deleteLater()
        worker.ready.connect(ready)
        worker.failed.connect(failed)
        worker.finished.connect(finished)
        worker.start()
        self.changed.emit()

    def result_text(self):
        if not self._result:
            return '检测完成后显示逐脸或视频采样结果。'
        from faceguard.inference.result_text import result_lines
        return '\n'.join(result_lines(self._result))

    @Slot()
    def startDetection(self):
        if self._busy or not self._name:
            return
        self._engine_ready, self._engine_status = resource_status()
        if not self._engine_ready:
            self.showError(self._engine_status)
            return
        self._busy, self._cancelling, self._result, self._error = True, False, {}, ''
        self._reset_detail()
        self._progress = '正在校验并加载本机模型'
        self._worker = DetectionWorker(self._url.toLocalFile(), analyzer=self._analyzer,
                                       generation_profile=self._generation_models[self._generation_model_index]['id'])
        self._worker.progress.connect(self._on_progress)
        self._worker.completed.connect(self._on_result)
        self._worker.failed.connect(self._on_failure)
        self._worker.cancelled.connect(self._on_cancelled)
        self._worker.finished.connect(self._on_worker_finished)
        self._record_result(None, 'running')
        self.changed.emit()
        self._worker.start()

    @Slot(int)
    def setGenerationModel(self, index):
        if self._busy or not 0 <= index < len(self._generation_models) or index == self._generation_model_index:
            return
        self._generation_model_index = index
        self.settings.setValue('generationModel', self._generation_models[index]['id'])
        self._analyzer = None
        self._result = {}
        self._reset_detail()
        self._progress = '生成模型已切换，请重新检测；历史记录保留原结果'
        self.settingsChanged.emit()
        self.changed.emit()

    @Slot()
    def cancelDetection(self):
        if self._busy and self._worker:
            self._cancelling = True
            self._progress = '正在取消，等待当前模型或采样步骤结束'
            self._worker.cancel()
            self.changed.emit()

    @Slot(str, int, int)
    def _on_progress(self, stage, done, total):
        if self._cancelling:
            return
        names = {'loading_models': '校验并加载模型', 'reading_image': '读取照片与检测人脸',
                 'reading_video': '读取视频', 'inference': '分析人脸特征',
                 'video_coverage': '视频覆盖采样', 'video_refinement': '视频局部复核采样'}
        self._progress = names.get(stage, stage) + (f' · {done}/{total}' if total else '')
        self.changed.emit()

    def _record_result(self, result, status):
        if self._history_id:
            try:
                self.history.set_result(self._history_id, result, status)
                self.historyChanged.emit()
            except (OSError, sqlite3.Error):
                self._error = '检测状态未能写入历史记录，可手动保存报告。'

    @Slot(dict)
    def _on_result(self, result):
        if self._cancelling:
            self._on_cancelled()
            return
        self._result = result
        self._progress = '检测完成' if not result.get('errors') else '部分检测完成，请查看详情'
        self._record_result(result, 'partial' if result.get('errors') else 'completed')
        self.changed.emit()
        self.detectionFinished.emit()

    @Slot(str)
    def _on_failure(self, message):
        self._error, self._progress = '检测未完成：' + message, '检测未完成'
        self._record_result(None, 'failed')
        self.changed.emit()

    @Slot()
    def _on_cancelled(self):
        self._result, self._progress = {}, '检测已取消'
        self._record_result(None, 'cancelled')
        self.changed.emit()

    @Slot()
    def _on_worker_finished(self):
        worker = self._worker
        self._analyzer = worker.analyzer
        self._worker, self._busy, self._cancelling = None, False, False
        worker.deleteLater()
        self.changed.emit()

    def export_report(self, filename):
        if not self._result:
            raise ValueError('请先完成检测。')
        path = Path(filename)
        if path.suffix.lower() == '.json':
            contents = json.dumps(self._result, ensure_ascii=False, indent=2, allow_nan=False)
        elif path.suffix.lower() == '.txt':
            contents = ('谛听 · FaceGuard 检测报告\n文件：' + self._result['path'] + '\n\n' + self.result_text()
                        + '\n\n分数是模型倾向，不是真假概率。热力图与精确定位未包含在本报告中。\n'
                        + '\n技术记录\n' + json.dumps(self._result, ensure_ascii=False, indent=2, allow_nan=False))
        else:
            raise ValueError('报告请保存为 .json 或 .txt。')
        path.write_text(contents, encoding='utf-8')

    @Slot()
    def saveReport(self):
        if not self._result:
            return
        filename, _ = QFileDialog.getSaveFileName(None, '保存检测报告', Path(self._name).stem + '-检测报告.json', 'JSON 报告 (*.json);;文本报告 (*.txt)')
        if filename:
            try:
                self.export_report(filename)
            except (OSError, ValueError) as error:
                self.showError('报告保存失败：' + str(error))

    @Slot()
    def shutdown(self):
        if self._worker:
            self._cancelling = True
            self._worker.cancel()
            self._worker.wait()
            if self._busy:
                self._record_result(None, 'cancelled')
        for worker in self._preview_workers:
            worker.wait()
        if self._preview_directory is not None:
            self._preview_directory.cleanup()
            self._preview_directory = None
        self.savePreferences()

    @Slot(str)
    def chooseFile(self, kind):
        if self._busy:
            self.showError('请等待检测完成或取消后再更换文件。')
            return
        filters = ('照片 (*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff)' if kind == 'image'
                   else '视频 (*.mp4 *.mov *.avi *.mkv *.webm *.m4v *.wmv)')
        path, _ = QFileDialog.getOpenFileName(None, '选择照片' if kind == 'image' else '选择视频', '', filters)
        if path:
            self.load_file(path)

    @Slot(QUrl)
    def dropFile(self, url):
        if url.isLocalFile():
            self.load_file(url.toLocalFile())
        else:
            self.showError('请选择本机照片或视频，不支持网络地址。')

    def load_file(self, filename, record_history=True):
        if self._busy:
            self.showError('请等待检测完成或取消后再更换文件。')
            return False
        path = resolve_data_path(filename)
        try:
            if not path.is_file():
                raise ValueError('文件不存在或无法读取，请重新选择。')
            suffix = path.suffix.lower()
            if suffix not in PHOTOS | VIDEOS:
                raise ValueError('暂不支持此格式，请选择照片或视频。')
            size = path.stat().st_size
            if not size:
                raise ValueError('这是一个空文件，请重新选择。')
            metadata = f'{size / 1024 / 1024:.2f} MB  ·  {suffix[1:].upper()}'
            kind = 'image' if suffix in PHOTOS else 'video'
            if kind == 'image':
                reader = QImageReader(str(path))
                reader.setAutoTransform(True)
                if not reader.canRead():
                    raise ValueError('照片无法解码，文件可能损坏或格式不受支持。')
                dimensions = reader.size()
                if dimensions.width() * dimensions.height() > 80_000_000:
                    raise ValueError('照片尺寸过大，请将分辨率缩小到 8000 万像素以内。')
                if reader.read().isNull():
                    raise ValueError('照片读取失败，请重新选择。')
                metadata += f'  ·  {dimensions.width()} × {dimensions.height()}'
            self._name, self._url = path.name, QUrl.fromLocalFile(str(path.resolve()))
            self._metadata, self._kind, self._error = metadata, kind, ''
            self._result, self._progress, self._history_id = {}, '', None
            self._reset_detail()
            if record_history:
                try:
                    self._history_id = self.history.add(path, kind, metadata)
                    self.historyChanged.emit()
                except (OSError, sqlite3.Error):
                    self._error = '文件已打开，但历史记录写入失败。'
            self.changed.emit()
            if self._pet:
                self.togglePet()
            self.mediaOpened.emit()
            return True
        except (OSError, ValueError) as error:
            self.showError(str(error))
            return False

    @Slot(str, result=bool)
    def reopenRecord(self, identifier):
        record = self.history.get(identifier)
        if record is None:
            self.showError('这条历史记录已不存在。')
            return False
        if not self.load_file(record['file_path'], record_history=False):
            return False
        self._history_id = identifier
        if record.get('result_json'):
            try:
                self._result = json.loads(record['result_json'])
                signature = self._result.get('source_signature')
                stat = Path(self._url.toLocalFile()).stat()
                if signature != dict(size=stat.st_size, mtime_ns=stat.st_mtime_ns):
                    self._result = {}
                    self._progress = '原文件已变化或缺少版本记录，请重新检测'
                else:
                    self._progress = '已读取上次检测记录'
            except (TypeError, ValueError):
                self._error = '历史结果无法读取，请重新检测。'
        self.changed.emit()
        return True

    @Slot(str)
    def deleteRecord(self, identifier):
        self.history.delete(identifier)
        self.historyChanged.emit()

    @Slot()
    def clearHistory(self):
        self.history.clear()
        self.historyChanged.emit()

    @Slot(str)
    def showError(self, message):
        self._error = message
        self.changed.emit()

    @Slot()
    def clearFile(self):
        if self._busy:
            self.showError('请先取消正在进行的检测。')
            return
        self._name, self._url, self._metadata, self._error = '', QUrl(), '', ''
        self._result, self._progress, self._history_id = {}, '', None
        self._reset_detail()
        self.changed.emit()

    @Slot()
    def savePreferences(self):
        if self._pet and self.window:
            self.settings.setValue('petX', self.window.x())
            self.settings.setValue('petY', self.window.y())
        self.settings.sync()

    @Slot()
    def toggleReducedMotion(self):
        self._reduced = not self._reduced
        self.settings.setValue('reducedMotion', self._reduced)
        self.settingsChanged.emit()

    @Slot()
    def toggleTopmost(self):
        self._topmost = not self._topmost
        self.settings.setValue('topmost', self._topmost)
        if self.window:
            self.window.setFlag(Qt.WindowType.WindowStaysOnTopHint, self._topmost)
            self.window.show()
        self.settingsChanged.emit()

    @Slot()
    def togglePet(self):
        if not self.window or self._transitioning:
            return
        if self._reduced or not self.window.isVisible():
            self._apply_pet_mode()
            return
        self._transitioning = True
        self.settingsChanged.emit()
        self._animate_opacity(0, 140, self._switch_then_reveal)

    def _animate_opacity(self, target, duration, finished):
        animation = QPropertyAnimation(self.window, b'opacity', self)
        self._fade = animation
        animation.setStartValue(self.window.opacity())
        animation.setEndValue(target)
        animation.setDuration(duration)
        animation.setEasingCurve(QEasingCurve.Type.InOutSine)
        completed = False

        def complete():
            nonlocal completed
            if completed:
                return
            completed = True
            animation.stop()
            self.window.setOpacity(target)
            finished()
            animation.deleteLater()

        animation.finished.connect(complete)
        # Windows may suspend Qt's frame clock while a transparent window is
        # resized/occluded. A wall-clock fallback prevents an invisible app.
        QTimer.singleShot(duration + 100, complete)
        animation.start()

    def _switch_then_reveal(self):
        self._apply_pet_mode()
        self._animate_opacity(1, 180, self._finish_transition)

    def _finish_transition(self):
        self.window.setOpacity(1)
        self._transitioning = False
        self.settingsChanged.emit()

    def _apply_pet_mode(self):
        screen = self.window.screen().availableGeometry()
        if not self._pet:
            self.work_geometry = self.window.geometry()
            self._pet = True
            self.settingsChanged.emit()
            self.window.setMinimumSize(QSize(260, 320))
            self.window.resize(300, 370)
            x = self.settings.value('petX', screen.right() - 325, type=int)
            y = self.settings.value('petY', screen.bottom() - 405, type=int)
            self.window.setPosition(max(screen.left(), min(x, screen.right() - 300)),
                                    max(screen.top(), min(y, screen.bottom() - 370)))
        else:
            self.settings.setValue('petX', self.window.x())
            self.settings.setValue('petY', self.window.y())
            self._pet = False
            self.settingsChanged.emit()
            if self.work_geometry:
                self.window.setGeometry(self.work_geometry)
            self.window.setMinimumSize(QSize(1080, 720))
        self.window.show()

    @Slot()
    def hideWindow(self):
        if self.window:
            if self.tray and self.tray.isVisible():
                self.window.hide()
            else:
                self.window.showMinimized()

    @Slot()
    def showWorkbench(self):
        if self._pet:
            self.togglePet()
        self.window.setProperty('activePage', 'workspace')
        self.window.showNormal()
        self.window.raise_()
        self.window.requestActivate()

    def install_tray(self, application, icon):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QSystemTrayIcon(icon, application)
        self.tray.setToolTip('谛听 · 青玉守真')
        menu = QMenu()
        menu.addAction('打开检测工作台', self.showWorkbench)
        menu.addAction('桌宠 / 工作台', self.togglePet)
        menu.addAction('选择照片', lambda: self.chooseFile('image'))
        menu.addAction('选择视频', lambda: self.chooseFile('video'))
        menu.addSeparator()
        menu.addAction('退出', application.quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason: self.showWorkbench()
                                   if reason == QSystemTrayIcon.ActivationReason.DoubleClick else None)
        self.tray.show()


def main():
    parser = argparse.ArgumentParser(description='谛听 · 青玉守真 — FaceGuard 正式桌面界面')
    parser.add_argument('--pet', action='store_true', help='以透明桌宠模式启动')
    parser.add_argument('--file', type=Path, help='启动时预览本机媒体文件')
    args = parser.parse_args()
    application = QApplication([sys.argv[0]])
    application.setFont(QFont('Microsoft YaHei UI', 10))
    QQuickStyle.setStyle('Basic')
    application.setApplicationName('谛听 · FaceGuard')
    application.setOrganizationName('FaceGuard')
    icon = QIcon(str(UI_DIRECTORY / 'brand.svg'))
    application.setWindowIcon(icon)
    controller = AppController()
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty('controller', controller)
    engine.load(QUrl.fromLocalFile(str(UI_DIRECTORY / 'Main.qml')))
    if not engine.rootObjects():
        raise SystemExit('无法加载谛听界面，请检查 Qt Quick 图形运行环境。')
    controller.window = engine.rootObjects()[0]
    application.aboutToQuit.connect(controller.shutdown)
    if controller.topmost:
        controller.window.setFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        controller.window.show()
    controller.install_tray(application, icon)
    if args.file:
        controller.load_file(args.file)
    if args.pet:
        QTimer.singleShot(200, controller.togglePet)
    raise SystemExit(application.exec())
