"""Guided local desktop workflow; model loading starts only on user request."""
import argparse
import json
from pathlib import Path
import queue
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageDraw, ImageOps, ImageTk
from app_paths import APP_VERSION, application_directory
from result_text import result_lines
from inference_control import InferenceCancelled

HERE = application_directory()
BG, CARD, INK, MUTED = '#f3f6fb', '#ffffff', '#15243b', '#64748b'
BLUE, GREEN, RED = '#2563eb', '#087f70', '#bd3d44'
FONT = 'Microsoft YaHei UI'
PHOTOS = ('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tif', '.tiff')
VIDEOS = ('.mp4', '.avi', '.mov', '.mkv', '.webm', '.m4v', '.wmv')
TASK_NAMES = ('自动：照片两项检查，视频查篡改', 'AI 整脸生成（照片）', '换脸 / 面部篡改（照片或视频）')
TASK_VALUES = dict(zip(TASK_NAMES, ('auto', 'generation', 'manipulation')))


class FaceGuardApp:
    def __init__(self, root,analyzer_options=None):
        self.root = root
        self.analyzer_options=analyzer_options or {}
        self.experimental=bool(self.analyzer_options.get('generation_checkpoint') or self.analyzer_options.get('photo_checkpoint'))
        self.path, self.prediction, self.predictor = None, None, None
        self.busy, self.selection, self.started = False, 0, 0
        self.events, self.photo = queue.Queue(), None
        self.cancel_event=threading.Event()
        self.task_var = tk.StringVar(value=TASK_NAMES[0])
        root.title(f'FaceGuard {APP_VERSION} · AI 整脸生成与人脸篡改检测')
        root.geometry(f'1160x{min(900, root.winfo_screenheight() - 100)}')
        root.minsize(1060, 650)
        root.configure(bg=BG)
        style = ttk.Style(root)
        style.theme_use('clam')
        style.configure('Detect.Horizontal.TProgressbar', troughcolor='#e7edf5',
                        background=BLUE, borderwidth=0, thickness=6)
        self._build()
        root.after(80, self.poll)

    def label(self, parent, text, size=11, color=INK, bold=False, **kwargs):
        return tk.Label(parent, text=text, font=(FONT, size, 'bold' if bold else 'normal'),
                        bg=parent.cget('bg'), fg=color, **kwargs)

    def button(self, parent, text, command, primary=False):
        return tk.Button(parent, text=text, command=command, font=(FONT, 11, 'bold'),
            bg=BLUE if primary else '#eef3fc', fg='white' if primary else BLUE,
            activebackground='#1d4ed8' if primary else '#dfe9fc',
            activeforeground='white' if primary else BLUE, relief='flat', bd=0,
            padx=16, pady=11, cursor='hand2', disabledforeground='#94a3b8')

    def _build(self):
        scroll = tk.Canvas(self.root, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.root, orient='vertical', command=scroll.yview)
        scrollbar.pack(side='right', fill='y')
        scroll.pack(side='left', fill='both', expand=True)
        scroll.configure(yscrollcommand=scrollbar.set)
        content = tk.Frame(scroll, bg=BG)
        item = scroll.create_window((0, 0), window=content, anchor='nw')
        content.bind('<Configure>', lambda _: scroll.configure(scrollregion=scroll.bbox('all')))
        def resize(event):
            scroll.itemconfigure(item, width=event.width, height=max(content.winfo_reqheight(), event.height))
        scroll.bind('<Configure>', resize)
        self.root.bind('<MouseWheel>', lambda event: scroll.yview_scroll(-int(event.delta / 120), 'units'))
        header = tk.Frame(content, bg=BG)
        header.pack(fill='x', padx=28, pady=(22, 16))
        self.label(header, 'FaceGuard', 23, bold=True).pack(side='left')
        self.label(header, '实验候选 · AI生成与人脸篡改' if self.experimental else 'AI 整脸生成与人脸篡改检测', 13, MUTED).pack(side='left', padx=16)
        self.label(header, '本机处理 · 文件不会上传', 10, GREEN).pack(side='right')
        guide = tk.Frame(content, bg='#e8f0ff', padx=18, pady=13)
        guide.pack(fill='x', padx=28, pady=(0, 18))
        self.examples_available = (HERE / 'artifacts/generation/joint/example_1.json').is_file() or (HERE / 'artifacts/generation/example_1.json').is_file()
        guide_text = ('第一次使用？点击左侧「载入 AI 生成示例」，再点击「开始检测」。'
                      if self.examples_available else '使用两步：左侧选择照片或视频，再点击蓝色「开始检测」。')
        if self.experimental:
            guide_text='实验候选仍会误判：选择文件 → 开始检测 → 逐脸核对两项结果。请勿将结果当作证明。'
        self.label(guide, guide_text, 12, BLUE, True).pack(anchor='w')
        task_row = tk.Frame(guide, bg=guide.cget('bg'))
        task_row.pack(fill='x', pady=(7, 0))
        self.label(task_row, '照片逐脸检查，两项结果分别展示；视频检查人脸篡改。', 10, MUTED).pack(side='left')
        self.task_selector = ttk.Combobox(task_row, state='readonly', textvariable=self.task_var,
                                          values=TASK_NAMES, width=35, font=(FONT, 10))
        self.task_selector.pack(side='right')
        self.label(task_row, '检测项目：', 10, MUTED).pack(side='right', padx=(8, 4))
        self.task_selector.bind('<<ComboboxSelected>>', self.task_changed)
        body = tk.Frame(content, bg=BG)
        body.pack(fill='both', expand=True, padx=28)
        body.columnconfigure(1, weight=1)
        body.columnconfigure(2, weight=1)
        body.rowconfigure(0, weight=1)
        left = tk.Frame(body, bg=CARD, padx=20, pady=22, width=246, height=600)
        left.grid(row=0, column=0, sticky='nsew', padx=(0, 14))
        left.grid_propagate(False)
        self.label(left, '01  选择文件', 14, bold=True).pack(anchor='w')
        self.label(left, '支持含人脸的照片和视频', 10, MUTED).pack(anchor='w', pady=(6, 18))
        self.select_buttons = []
        for text, callback in [('选择照片…', lambda: self.choose('image')),
                               ('选择视频…', lambda: self.choose('video'))]:
            button = self.button(left, text, callback)
            button.pack(fill='x', pady=(0, 9))
            self.select_buttons.append(button)
        self.label(left, '没有现成文件？先用示例体验' if self.examples_available else '离线使用，无需下载训练数据', 10, MUTED).pack(anchor='w', pady=(20, 9))
        for text, label in [('载入真实照片示例', '0'), ('载入 AI 生成示例', '1')]:
            button = self.button(left, text, lambda value=label: self.load_example(value))
            button.pack(fill='x', pady=(0, 9))
            self.select_buttons.append(button)
            if not self.examples_available:
                button.config(state='disabled')
        example_note = '示例有已知标签，便于对照结果。' if self.examples_available else '本发布包不含个人照片或数据集。\n请使用上方按钮选择自己的文件。'
        self.label(left, example_note, 9, MUTED, wraplength=202, justify='left').pack(anchor='w', pady=(2, 20))
        tk.Frame(left, bg='#e8edf5', height=1).pack(fill='x', pady=(0, 20))
        self.label(left, '02  开始检测', 14, bold=True).pack(anchor='w')
        self.start_button = self.button(left, '开始检测', self.start, primary=True)
        self.start_button.pack(fill='x', pady=(14, 9))
        self.start_button.config(state='disabled')
        self.start_hint = self.label(left, '先在上方选一个文件', 10, MUTED, wraplength=202, justify='left')
        self.start_hint.pack(anchor='w')
        preview_card = tk.Frame(body, bg=CARD, padx=20, pady=22)
        preview_card.grid(row=0, column=1, sticky='nsew', padx=(0, 14))
        self.label(preview_card, '文件预览', 14, bold=True).pack(anchor='w')
        self.preview = tk.Label(preview_card, bg='#edf2f8', fg=MUTED,
            text='尚未选择文件\n\n从左侧选择照片、视频\n或载入一个示例', font=(FONT, 12), justify='center')
        self.preview.pack(fill='both', expand=True, pady=(18, 16))
        self.file_name = self.label(preview_card, '等待选择', 11, bold=True, wraplength=300, justify='left')
        self.file_name.pack(anchor='w')
        self.file_info = self.label(preview_card, '照片显示原图；视频显示首帧', 10, MUTED, wraplength=300, justify='left')
        self.file_info.pack(anchor='w', pady=(7, 0))
        self.sample_note = self.label(preview_card, '', 10, BLUE, wraplength=300, justify='left')
        self.sample_note.pack(anchor='w', pady=(10, 0))
        face_controls=tk.Frame(preview_card,bg=CARD)
        face_controls.pack(fill='x',pady=(12,0))
        self.face_choice=tk.StringVar(value='检测后可选人脸')
        self.face_selector=ttk.Combobox(face_controls,textvariable=self.face_choice,state='disabled',width=14,font=(FONT,10))
        self.face_selector.pack(side='left',padx=(0,7))
        self.face_zoom=tk.Button(face_controls,text='放大这张脸',command=self.show_face,font=(FONT,10),relief='flat',
                                 bg='#eef3fc',fg=BLUE,padx=8,pady=5,state='disabled')
        self.face_zoom.pack(side='left')
        right = tk.Frame(body, bg=CARD, padx=22, pady=22)
        right.grid(row=0, column=2, sticky='nsew')
        self.label(right, '03  查看结果', 14, bold=True).pack(anchor='w')
        self.result_title = self.label(right, '等待检测', 21, MUTED, True, wraplength=290, justify='left')
        self.result_title.pack(anchor='w', pady=(26, 12))
        self.result_description = self.label(right, '选择文件后，点击左侧蓝色的\n「开始检测」按钮。', 11, MUTED, wraplength=290, justify='left')
        self.result_description.pack(anchor='w')
        self.score_label = self.label(right, '', 13, bold=True)
        self.score_label.pack(anchor='w', pady=(24, 10))
        self.gauge = tk.Canvas(right, height=12, bg=CARD, highlightthickness=0)
        self.gauge.pack(fill='x')
        self.gauge.bind('<Configure>', lambda _: self.draw_score())
        self.score_note = self.label(right, '', 9, MUTED, wraplength=290, justify='left')
        self.score_note.pack(anchor='w', pady=(8, 16))
        self.coverage = self.label(right, '', 10, MUTED, wraplength=290, justify='left')
        self.coverage.pack(anchor='w', pady=(0, 16))
        detail_frame = tk.Frame(right, bg=CARD)
        detail_frame.pack(fill='both', expand=True)
        self.face_details = tk.Text(detail_frame, height=9, width=31, wrap='word',
                                    font=(FONT, 10), bg='#f5f8fc', fg=INK, relief='flat', padx=8, pady=8)
        detail_scroll = ttk.Scrollbar(detail_frame, command=self.face_details.yview)
        detail_scroll.pack(side='right', fill='y')
        self.face_details.pack(side='left', fill='both', expand=True)
        self.face_details.config(yscrollcommand=detail_scroll.set, state='disabled')
        progress_row=tk.Frame(right,bg=CARD)
        progress_row.pack(fill='x',pady=(8,10))
        self.progress = ttk.Progressbar(progress_row, style='Detect.Horizontal.TProgressbar', mode='indeterminate')
        self.progress.pack(side='left',fill='x',expand=True)
        self.cancel_button=tk.Button(progress_row,text='取消检测',command=self.cancel_detection,font=(FONT,9),
                                     relief='flat',bg='#eef3fc',fg=BLUE,state='disabled',padx=7,pady=4)
        self.cancel_button.pack(side='right',padx=(7,0))
        self.status = self.label(right, '准备就绪', 10, MUTED, wraplength=290, justify='left')
        self.status.pack(anchor='w')
        actions = tk.Frame(right, bg=CARD)
        actions.pack(fill='x', side='bottom', pady=(18, 0))
        self.export_button = self.button(actions, '保存检测报告', self.export)
        self.export_button.pack(fill='x', pady=(0, 7))
        self.export_button.config(state='disabled')
        self.detail_button = self.button(actions, '查看技术详情', self.details)
        self.detail_button.pack(fill='x')
        self.detail_button.config(state='disabled')
        footer = tk.Frame(content, bg=BG)
        footer.pack(fill='x', padx=28, pady=(14, 18))
        self.label(footer, '照片默认分别检查整脸生成和人脸篡改，按预览编号逐脸查看；视频检查面部篡改。', 10, MUTED).pack(anchor='w')
        self.label(footer, '整脸生成模型为实验版；未检出不等于真实，对未见生成工具仍可能失效。', 10, MUTED).pack(anchor='w', pady=(3, 0))

    def task_changed(self, event=None):
        manipulation = TASK_VALUES[self.task_var.get()] == 'manipulation'
        self.select_buttons[2].config(text='载入真实视频示例' if manipulation else '载入真实照片示例')
        self.select_buttons[3].config(text='载入篡改视频示例' if manipulation else '载入 AI 生成示例')
        if self.path and not self.busy:
            self.select_path(self.path)

    def choose(self, kind):
        filters = [('照片', ' '.join('*' + s for s in PHOTOS))] if kind == 'image' else [('视频', ' '.join('*' + s for s in VIDEOS))]
        path = filedialog.askopenfilename(parent=self.root, title='选择一张含人脸的照片' if kind == 'image' else '选择一段含人脸的视频',
                                         filetypes=filters + [('所有文件', '*.*')])
        if path:
            self.select_path(path)

    def load_example(self, label):
        try:
            manipulation = TASK_VALUES[self.task_var.get()] == 'manipulation'
            if manipulation:
                file = HERE / f'artifacts/finetuned_example_{label}.json'
            else:
                # This path lookup avoids importing Torch just to preview the UI.
                folder = HERE / 'artifacts/generation'
                if (folder / 'joint/READY.json').is_file():
                    folder = folder / 'joint'
                file = folder / f'example_{label}.json'
            data = json.loads(file.read_text(encoding='utf-8'))
            name = ('真实视频示例' if label == '0' else '篡改视频示例') if manipulation else ('真实照片示例' if label == '0' else 'AI 整脸生成示例')
            self.select_path(data['path'], example=name)
        except (OSError, ValueError, KeyError):
            messagebox.showerror('示例暂不可用', '找不到本地示例文件。请先用「选择照片」或「选择视频」选择自己的文件。', parent=self.root)

    def select_path(self, path, example=''):
        if self.busy:
            return
        path = Path(path)
        if not path.is_file() or path.suffix.lower() not in PHOTOS + VIDEOS:
            messagebox.showerror('无法选择此文件', '请选择存在的照片或视频，例如 JPG、PNG、MP4 或 MOV。', parent=self.root)
            return
        self.path, self.prediction = path, None
        self.set_face_details('')
        self.face_selector.config(state='disabled',values=())
        self.face_choice.set('检测后可选人脸')
        self.face_zoom.config(state='disabled')
        self.selection += 1
        self.file_name.config(text=path.name)
        file_size = path.stat().st_size
        size_text = f'{file_size / 1024:.0f} KB' if file_size < 1024**2 else f'{file_size / 1024**2:.1f} MB'
        self.file_info.config(text=f"{'照片' if path.suffix.lower() in PHOTOS else '视频'} · {size_text}")
        self.sample_note.config(text=f'已载入：{example}\n点击「开始检测」查看模型判断。' if example else '文件已选好，点击「开始检测」。')
        self.preview.config(image='', text='正在读取预览…')
        self.photo = None
        self.result_title.config(text='文件已就绪', fg=INK)
        self.result_description.config(text='确认中间的文件预览后，\n点击左侧「开始检测」。')
        self.score_label.config(text='')
        self.score_note.config(text='')
        self.coverage.config(text='')
        self.draw_score()
        self.start_button.config(state='normal', text='开始检测')
        self.start_hint.config(text='已选好文件，可以开始了', fg=BLUE)
        self.export_button.config(state='disabled')
        self.detail_button.config(state='disabled')
        self.status.config(text='等待你点击「开始检测」')
        self.progress.stop()
        self.progress.config(mode='determinate', value=0)
        threading.Thread(target=self._preview_worker, args=(path, self.selection), daemon=True).start()

    def _preview_worker(self, path, token, face_records=()):
        try:
            if path.suffix.lower() in PHOTOS:
                with Image.open(path) as source:
                    image = ImageOps.exif_transpose(source).convert('RGB')
            else:
                import cv2
                capture = cv2.VideoCapture(str(path))
                try:
                    ok, frame = capture.read()
                    if not ok:
                        raise ValueError('无法读取视频首帧')
                    image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                finally:
                    capture.release()
            original_width, original_height = image.size
            image.thumbnail((320, 300), Image.Resampling.LANCZOS)
            draw = ImageDraw.Draw(image)
            for record in face_records:
                if record.get('bbox') is None:
                    continue
                x1, y1, x2, y2 = record['bbox']
                box = (x1 * image.width / original_width, y1 * image.height / original_height,
                       x2 * image.width / original_width, y2 * image.height / original_height)
                draw.rectangle(box, outline=BLUE, width=2)
                draw.text((box[0] + 2, box[1] + 2), f"#{record['face_id']}", fill='white', stroke_width=2, stroke_fill=BLUE)
            self.events.put(('preview', token, image))
        except Exception:
            self.events.put(('preview_error', token, None))

    def start(self):
        if self.busy or self.path is None:
            return
        self.busy, self.started, self.prediction = True, time.monotonic(), None
        self.cancel_event.clear();self.cancel_button.config(state='normal')
        self.face_selector.config(state='disabled')
        self.face_zoom.config(state='disabled')
        for button in self.select_buttons + [self.start_button, self.export_button, self.detail_button]:
            button.config(state='disabled')
        self.start_button.config(text='正在检测…')
        self.task_selector.config(state='disabled')
        self.result_title.config(text='正在检测', fg=BLUE)
        self.result_description.config(text='请稍候，完成后会在这里显示结果。\n你可以保持窗口打开。')
        self.score_label.config(text='')
        self.score_note.config(text='')
        self.coverage.config(text='')
        self.set_face_details('')
        self.draw_score()
        self.progress.config(mode='indeterminate')
        self.progress.start(12)
        self.status.config(text='首次使用正在加载模型，可能需要几十秒…')
        self.start_hint.config(text='处理中，请等待右侧结果', fg=MUTED)
        threading.Thread(target=self._detect_worker, args=(self.path, TASK_VALUES[self.task_var.get()]), daemon=True).start()

    def _detect_worker(self, path, task):
        try:
            if self.predictor is None:
                import torch
                import cv2
                from face_analysis import FaceAnalyzer
                torch.set_num_threads(4)
                cv2.setNumThreads(1)
                self.predictor = FaceAnalyzer(**self.analyzer_options)
            def report(stage,done,total):
                if self.cancel_event.is_set():
                    raise InferenceCancelled()
                self.events.put(('progress',stage,(done,total)))
            if self.cancel_event.is_set():raise InferenceCancelled()
            result = self.predictor.predict(path, task=task,progress=report)
            if self.cancel_event.is_set():raise InferenceCancelled()
            self.events.put(('result', None, result))
        except InferenceCancelled:
            self.events.put(('cancelled',None,None))
        except Exception as exc:
            self.events.put(('error', None, str(exc)))

    def cancel_detection(self):
        if self.busy:
            self.cancel_event.set();self.cancel_button.config(state='disabled')
            self.status.config(text='正在结束当前步骤，请稍候…')

    def poll(self):
        try:
            while True:
                kind, key, value = self.events.get_nowait()
                if kind == 'preview' and key == self.selection:
                    self.photo = ImageTk.PhotoImage(value)
                    self.preview.config(image=self.photo, text='')
                elif kind == 'preview_error' and key == self.selection:
                    self.preview.config(image='', text='无法显示预览\n仍可尝试点击「开始检测」')
                elif kind == 'progress':
                    self.show_progress(key, *value)
                elif kind in ('result', 'error'):
                    if self.cancel_event.is_set():
                        self.finish(None,cancelled=True)
                    else:
                        self.finish(value if kind == 'result' else None, value if kind == 'error' else None)
                elif kind=='cancelled':
                    self.finish(None,cancelled=True)
        except queue.Empty:
            pass
        self.root.after(80, self.poll)

    def show_progress(self, stage, done, total):
        self.progress.stop()
        self.progress.config(mode='determinate')
        if stage in ('video_coverage', 'video_refinement'):
            value = (10 + 50 * done / max(1, total)) if stage == 'video_coverage' else (60 + 35 * done / max(1, total))
            name = '覆盖全段采样' if stage == 'video_coverage' else '在可疑点附近加密采样'
            self.status.config(text=f'{name} · {done}/{total}')
        elif stage == 'reading_video':
            value = 10 + 65 * done / max(1, total)
            self.status.config(text=f'正在读取视频并寻找人脸 · {done / max(1, total):.0%}')
        elif stage == 'reading_image':
            value = 20
            self.status.config(text='正在读取照片并寻找人脸…')
        else:
            value = 85
            self.status.config(text='正在分析人脸，生成检测结果…')
        self.progress.config(value=value)

    def finish(self, prediction, error=None,cancelled=False):
        self.busy = False
        self.cancel_button.config(state='disabled')
        self.task_selector.config(state='readonly')
        self.progress.stop()
        self.progress.config(mode='determinate', value=100 if prediction else 0)
        for button in self.select_buttons + [self.start_button]:
            button.config(state='normal')
        if not self.examples_available:
            for button in self.select_buttons[2:]:
                button.config(state='disabled')
        self.start_button.config(text='重新检测此文件')
        self.start_hint.config(text='可更换文件，继续检测', fg=MUTED)
        if cancelled:
            self.result_title.config(text='已取消检测',fg=MUTED)
            self.result_description.config(text='本次没有生成检测结论。\n文件未被修改，可以重新开始。')
            self.status.config(text='已取消，可重新选择文件或检测')
            return
        if error:
            self.result_title.config(text='这次未能完成', fg=RED)
            self.result_description.config(text='请确认文件能正常打开，再试一次。\n也可以先载入左侧示例检查程序。')
            self.status.config(text='检测失败，文件未被修改')
            self.coverage.config(text='错误详情：' + error)
            return
        self.prediction = prediction
        if self.sample_note.cget('text').startswith('已载入：'):
            self.sample_note.config(text=self.sample_note.cget('text').split('\n')[0] + '\n检测完成，请对照右侧结果。')
        decision = prediction['decision']
        generation = prediction.get('task') == 'whole_face_generation'
        if decision == 'video_results':
            title, color = '请查看视频两项结果', BLUE
            description = '整段判断沿用原16帧规则。\n短片段提示阈值仅在已知来源验证，\n两项结果分别列在下方。' if prediction.get('temporal_review',{}).get('policy_available') else '整段判断沿用原16帧规则。\n短片段规则当前不可用，不作判断。'
        elif decision == 'review_alerts':
            title, color, description = '有片段需要复核', RED, '下方列出建议复核的时间范围。\n这是逐帧模型提示，不能证明篡改，\n也未证明覆盖了全部问题。'
        elif decision == 'no_review_alerts':
            title, color, description = '采样未触发提示', GREEN, '没有触发片段复核提示。\n采样间隙仍可能有短暂篡改；\n这不等于整段视频真实。'
        elif decision in ('separate_results', 'multiple_face_results'):
            title, color, description = '请逐项查看结果', BLUE, '下方按人脸编号列出结果。\n两种检测分别判断，不合成真假概率。'
        elif decision == 'partial_results':
            title, color, description = '部分检测未完成', RED, '已完成的结果和失败原因列在下方。\n没有完成的项目不能当作检测通过。'
        elif decision == 'suspected_generation':
            title, color, description = '疑似 AI 整脸生成', RED, '整脸生成模型检出了可疑特征。\n这与局部换脸/面部篡改是两类检测。'
        elif decision == 'no_generation_detected':
            title, color, description = '未检出明显生成特征', GREEN, '本次检查的是 AI 整脸生成。\n未检出不等于真实；陌生生成工具\n仍可能无法识别。'
        elif decision == 'suspected_manipulation':
            title, color, description = '疑似人脸篡改', RED, '模型发现了疑似篡改特征。\n建议结合原始素材进一步核对。'
        elif decision == 'no_manipulation_detected':
            title, color, description = '未检出明显篡改', GREEN, '本次分析没有检出明显的篡改特征。\n这不等于证明文件真实。'
        else:
            title, color, description = '未找到可分析的人脸', MUTED, '这次无法判断真假。\n请换一张正脸清晰的照片，\n或一段人物脸部清楚的视频。'
        self.result_title.config(text=title, fg=color)
        self.result_description.config(text=description)
        self.set_face_details('\n'.join(result_lines(prediction)) if prediction['media_type'] == 'image' or prediction.get('sampling') == 'adaptive_review' else '')
        if prediction['media_type'] == 'image':
            reference = next(iter(prediction.get('results', {'single': prediction}).values()))
            records=reference.get('face_results',[])
            self.selection+=1 # Invalidate a still-running unannotated preview of the same file.
            choices=[f"人脸 #{r['face_id']}" for r in records if r.get('bbox') is not None]
            if choices:
                self.face_selector.config(values=choices,state='readonly')
                self.face_choice.set(choices[0]);self.face_zoom.config(state='normal')
            threading.Thread(target=self._preview_worker,
                             args=(self.path, self.selection, records), daemon=True).start()
        if prediction['score'] is not None:
            name = '生成' if generation else '篡改'
            self.score_label.config(text=f"{name}倾向分  {prediction['score'] * 100:.1f} / 100", fg=color)
            self.score_note.config(text=f'分数越高，模型越倾向于{name}。\n这是模型分数，不是真假概率。')
        if prediction['media_type'] == 'video':
            value = f"本次采样 {prediction['sampled_frames']} 帧\n其中 {prediction.get('face_frames', prediction['faces'])} 帧检测到人脸"
            if prediction.get('sampling') == 'adaptive_review':
                value += f"\n覆盖采样 {prediction['coarse_frames']}，加密 {prediction['refined_frames']} 帧"
                gap = prediction['max_sample_gap_seconds']
                if gap is not None:
                    value += f"\n最大采样间隔 {gap:.2f} 秒"
            self.coverage.config(text=value)
        else:
            name = '整脸生成 + 人脸篡改' if prediction.get('task') == 'photo_dual' else ('AI整脸生成' if generation else '人脸篡改')
            self.coverage.config(text=f"检测项目：{name}\n本次分析 {prediction['faces']} 张脸，编号见预览\n未分析：{prediction.get('unanalysed_faces', 0)} 张")
            if prediction['score'] is None and prediction['faces']:
                self.score_note.config(text='逐脸分数各自比较阈值，不是真假概率。\n多人/双项检查的整图误报率尚未校准。')
        self.status.config(text=f'检测完成 · 用时 {time.monotonic() - self.started:.1f} 秒')
        self.export_button.config(state='normal')
        self.detail_button.config(state='normal')
        self.draw_score()

    def set_face_details(self, value):
        self.face_details.config(state='normal')
        self.face_details.delete('1.0', 'end')
        self.face_details.insert('1.0', value)
        self.face_details.config(state='disabled')

    def show_face(self):
        if not self.prediction or self.prediction['media_type']!='image':
            return None
        try:
            face_id=int(self.face_choice.get().split('#')[-1])
            tasks=self.prediction.get('results',{'generation' if self.prediction.get('task')=='whole_face_generation' else 'manipulation':self.prediction})
            reference=next(iter(tasks.values()))
            record=next(r for r in reference['face_results'] if r['face_id']==face_id)
            with Image.open(self.path) as source:
                image=ImageOps.exif_transpose(source).convert('RGB').crop(record['bbox'])
            image=ImageOps.contain(image,(380,380),Image.Resampling.LANCZOS)
            dialog=tk.Toplevel(self.root);dialog.title(f'本次分析的人脸 #{face_id}');dialog.configure(bg=CARD)
            photo=ImageTk.PhotoImage(image)
            label=tk.Label(dialog,image=photo,bg=CARD);label.image=photo;label.pack(padx=16,pady=16)
            lines=[]
            for name,item in tasks.items():
                face=next((r for r in item.get('face_results',[]) if r['face_id']==face_id),None)
                if face:
                    lines.extend(result_lines(dict(item,face_results=[face])))
            self.label(dialog,'\n'.join(lines),11,wraplength=430,justify='left').pack(padx=16,pady=(0,12))
            self.label(dialog,'分数不是真假概率。这是模型分析的裁剪区域；放大不会恢复原图没有的细节。',9,MUTED,wraplength=430,justify='left').pack(padx=16,pady=(0,16))
            return dialog
        except (OSError,ValueError,KeyError,StopIteration):
            messagebox.showerror('无法查看','原文件可能已移动或无法读取，请重新选择文件。',parent=self.root)
            return None

    def draw_score(self):
        self.gauge.delete('all')
        if self.prediction is None or self.prediction['score'] is None:
            return
        width = max(20, self.gauge.winfo_width())
        self.gauge.create_rectangle(0, 0, width, 10, fill='#e7edf5', outline='')
        color = RED if self.prediction['decision'] in ('suspected_manipulation', 'suspected_generation') else GREEN
        self.gauge.create_rectangle(0, 0, width * self.prediction['score'], 10, fill=color, outline='')

    def report_text(self):
        p = self.prediction
        name = '整脸生成' if p.get('task') == 'whole_face_generation' else '换脸/面部篡改'
        if p.get('task') == 'photo_dual':
            name = 'AI整脸生成和人脸篡改（分别判断）'
        text = f"FaceGuard 检测报告\n\n文件：{p['path']}\n检测项目：{name}\n结果：{self.result_title.cget('text')}\n"
        if p['score'] is not None:
            text += f"{name}倾向分：{p['score'] * 100:.1f} / 100（不是真假概率）\n"
        if p['media_type'] == 'image' or p.get('sampling') == 'adaptive_review':
            text += '\n' + '\n'.join(result_lines(p)) + '\n'
        coverage_name='分析人脸区域数' if p['media_type']=='image' else '分析的人脸出现次数（逐帧累计）'
        return text + f"{coverage_name}：{p['faces']}\n\n{self.result_description.cget('text')}\n\n当前模型分数不是真实性证明；多人/双项检查尚未做整图联合校准，对未见来源可能失效。\n"

    def export(self):
        if self.prediction is None:
            return
        path = filedialog.asksaveasfilename(parent=self.root, title='保存检测报告',
            initialfile=self.path.stem + '_检测报告.txt', defaultextension='.txt', filetypes=[('中文文本报告', '*.txt')])
        if path:
            try:
                Path(path).write_text(self.report_text(), encoding='utf-8-sig')
                self.status.config(text='报告已保存：' + Path(path).name)
            except OSError:
                messagebox.showerror('保存失败', '无法写入此位置，请换一个文件夹。', parent=self.root)

    def details(self):
        if self.prediction is None:
            return
        dialog = tk.Toplevel(self.root)
        dialog.title('本次检测的技术详情')
        dialog.geometry('760x480')
        text = tk.Text(dialog, wrap='word', font=('Consolas', 11), padx=16, pady=16)
        text.pack(fill='both', expand=True)
        text.insert('1.0', json.dumps(self.prediction, ensure_ascii=False, indent=2))
        text.config(state='disabled')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--smoke-test', action='store_true')
    parser.add_argument('--self-test', action='store_true', help='Exercise real select/start/result/report workflow')
    parser.add_argument('--self-test-task', choices=['auto', 'generation', 'manipulation'], default='generation')
    parser.add_argument('--screenshot', type=Path)
    parser.add_argument('--test-input', type=Path, help='Local input for testing a portable build without bundled datasets')
    parser.add_argument('--test-output', type=Path)
    parser.add_argument('--expected-decision')
    parser.add_argument('--generation-checkpoint',type=Path)
    parser.add_argument('--photo-checkpoint',type=Path)
    parser.add_argument('--device',choices=['cpu','cuda'])
    parser.add_argument('--cancel-after-ms',type=int,help='Self-test cooperative cancellation')
    args = parser.parse_args()
    # Keep Tk coordinates and screenshot pixels consistent on Windows HiDPI displays.
    import sys
    if sys.platform == 'win32':
        import ctypes
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    root = tk.Tk()
    root.tk.call('tk', 'scaling', 1.333333333)
    if args.smoke_test or args.self_test:
        root.withdraw()
    analyzer_options={key:value for key,value in dict(device=args.device,generation_checkpoint=args.generation_checkpoint,photo_checkpoint=args.photo_checkpoint).items() if value is not None}
    app = FaceGuardApp(root,analyzer_options)
    failures = []
    if args.smoke_test and not args.self_test:
        root.after(250, root.destroy)
    if args.self_test:
        app.task_var.set(TASK_NAMES[{'auto': 0, 'generation': 1, 'manipulation': 2}[args.self_test_task]])
        app.task_changed()
        if args.test_input:
            app.select_path(args.test_input)
        else:
            app.load_example('1')
        assert str(app.start_button.cget('state')) == 'normal'
        app.start()
        if args.cancel_after_ms is not None:
            root.after(args.cancel_after_ms,app.cancel_detection)
        assert app.busy and str(app.start_button.cget('state')) == 'disabled'
        deadline = time.monotonic() + 180

        def check():
            if app.busy and time.monotonic() < deadline:
                root.after(150, check)
                return
            try:
                if args.cancel_after_ms is not None:
                    assert app.prediction is None
                    assert app.result_title.cget('text')=='已取消检测'
                    assert str(app.start_button.cget('state'))=='normal'
                    assert str(app.export_button.cget('state'))=='disabled'
                    output=args.test_output or HERE/'artifacts/ui_cancel_check.json'
                    output.parent.mkdir(parents=True,exist_ok=True)
                    output.write_text(json.dumps(dict(cancelled=True,no_result_exported=True)),encoding='utf-8')
                    root.destroy();return
                assert app.prediction is not None, app.coverage.cget('text')
                expected = args.expected_decision or {'auto': 'separate_results', 'generation': 'suspected_generation', 'manipulation': 'video_results'}[args.self_test_task]
                assert app.prediction['decision'] == expected, (app.prediction['decision'], expected)
                assert str(app.export_button.cget('state')) == 'normal'
                assert app.result_title.cget('text') in app.report_text()
                zoom_checked=False
                if app.prediction['media_type']=='image' and app.prediction['faces']:
                    dialog=app.show_face()
                    assert dialog is not None,'Face zoom was unavailable'
                    assert dialog.winfo_children(),'Empty face zoom'
                    dialog.destroy();zoom_checked=True
                output = args.test_output or HERE / f'artifacts/ui_workflow_check_{args.self_test_task}.json'
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(json.dumps({
                    'select_start_result_report': 'passed', 'preview_loaded': app.photo is not None,
                    'decision': app.prediction['decision'], 'score': app.prediction['score'],
                    'face_zoom_checked':zoom_checked}, indent=2), encoding='utf-8')
                if args.screenshot:
                    root.deiconify()
                    root.attributes('-topmost', True)
                    root.update()
                    def capture():
                        from PIL import ImageGrab
                        if sys.platform == 'win32':
                            # A locked/noninteractive desktop can make ImageGrab return another
                            # desktop (including the lock screen) instead of our test window.
                            api = ctypes.windll.user32
                            api.OpenInputDesktop.restype = ctypes.c_void_p
                            api.CloseDesktop.argtypes = [ctypes.c_void_p]
                            api.GetUserObjectInformationW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint, ctypes.POINTER(ctypes.c_uint)]
                            desktop = api.OpenInputDesktop(0, False, 0x0001)
                            name, needed = ctypes.create_unicode_buffer(256), ctypes.c_uint()
                            valid = desktop and api.GetUserObjectInformationW(desktop, 2, name, ctypes.sizeof(name), ctypes.byref(needed)) and name.value.lower() == 'default'
                            if desktop:
                                api.CloseDesktop(desktop)
                            api.GetAncestor.argtypes = [ctypes.c_void_p, ctypes.c_uint]
                            api.GetAncestor.restype = api.GetForegroundWindow.restype = ctypes.c_void_p
                            foreground = api.GetForegroundWindow()
                            own_window = api.GetAncestor(root.winfo_id(), 2)
                            if not valid or foreground != own_window:
                                failures.append('Screenshot skipped: test window is not on the active unlocked desktop')
                                root.destroy()
                                return
                        args.screenshot.parent.mkdir(parents=True, exist_ok=True)
                        x, y = root.winfo_rootx(), root.winfo_rooty()
                        ImageGrab.grab(bbox=(x, y, x + root.winfo_width(), y + root.winfo_height())).save(args.screenshot)
                        root.destroy()
                    root.after(600, capture)
                    return
            except Exception as exc:
                failures.append(str(exc))
            root.destroy()
        root.after(150, check)
    root.mainloop()
    if failures:
        raise RuntimeError('; '.join(failures))


if __name__ == '__main__':
    main()
