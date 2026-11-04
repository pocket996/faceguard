"""Readable reports for everyday use; JSON remains available to research callers."""
from datetime import datetime
from html import escape
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from PySide6.QtCore import QBuffer, QIODevice, QMarginsF, QSize, QUrl, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPageLayout, QPageSize, QPainter, QPdfWriter, QTextDocument


def write_report(filename, result, result_text):
    path = Path(filename)
    suffix = path.suffix.lower()
    if suffix == '.json':
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
        return
    if suffix not in {'.pdf', '.txt'}:
        raise ValueError('报告请保存为 .pdf 或 .txt。')
    sections = [
        '谛听 · FaceGuard 检测报告',
        '报告导出时间：' + datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y-%m-%d %H:%M:%S（北京时间）'),
        '文件：' + str(result['path']),
        '检测结果\n' + result_text,
        '阅读说明\n分数是模型倾向，不是真假概率。未检出不代表文件真实。\n'
        '各项结果分别解读；本报告不包含热力图或精确篡改定位。',
    ]
    if suffix == '.txt':
        # A BOM lets Windows editors recognize Chinese even on older systems.
        path.write_text('\n\n'.join(sections) + '\n', encoding='utf-8-sig')
        return

    # Render in memory before writing so a rendering failure cannot truncate an existing report.
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    writer = QPdfWriter(buffer)
    writer.setTitle(sections[0])
    writer.setCreator('FaceGuard')
    writer.setResolution(96)
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setPageMargins(QMarginsF(18, 18, 18, 18), QPageLayout.Unit.Millimeter)
    document = QTextDocument()
    document.setDefaultFont(QFont('Microsoft YaHei UI', 11))
    # Break long filenames so they remain inside the printable area.
    paragraphs = []
    for index, section in enumerate(sections):
        if index == 2:
            body = '&#8203;'.join(escape(section[i:i + 32]) for i in range(0, len(section), 32))
        else:
            body = escape(section)
        tag = 'h1' if index == 0 else 'p'
        paragraphs.append(f'<{tag}>' + body.replace('\n', '<br>') + f'</{tag}>')
    document.setHtml('<html><head><style>body { color: #243c33; } '
                     'h1 { font-size: 20pt; } p { line-height: 150%; margin-bottom: 16px; }'
                     '</style></head><body>' + ''.join(paragraphs) + '</body></html>')
    document.print_(writer)
    del writer
    data = bytes(buffer.data())
    buffer.close()
    path.write_bytes(data)


def write_heatmap_diagram(filename, original_path, overlay_path, source_name, detail, status, model_label, opacity=.6):
    """Export the selected frame/face, with matching geometry and interpretation.

    This is a separate illustrated export; the everyday text report stays small.
    Build in memory so invalid inputs cannot truncate an existing destination.
    """
    path = Path(filename)
    if path.suffix.lower() not in {'.png', '.pdf'}:
        raise ValueError('关注图请保存为 .png 或 .pdf。')
    if not 0 <= opacity <= 1:
        raise ValueError('叠加强度必须在 0 到 1 之间。')
    original, overlay = QImage(str(original_path)), QImage(str(overlay_path))
    if original.isNull() or overlay.isNull() or original.size() != overlay.size():
        raise ValueError('原图或关注图缺失、损坏或尺寸不一致，请重新选择人脸。')
    composite = original.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    painter = QPainter(composite)
    painter.setOpacity(opacity)
    painter.drawImage(0, 0, overlay)
    painter.end()
    original = original.scaled(QSize(720, 530), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    composite = composite.scaled(original.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    document = QTextDocument()
    document.setDefaultFont(QFont('Microsoft YaHei UI', 14))
    document.setTextWidth(1504)
    document.addResource(QTextDocument.ResourceType.ImageResource, QUrl('fg-original'), original)
    document.addResource(QTextDocument.ResourceType.ImageResource, QUrl('fg-overlay'), composite)
    timestamp = datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y-%m-%d %H:%M:%S（北京时间）')
    source = '&#8203;'.join(escape(source_name[i:i + 32]) for i in range(0, len(source_name), 32))
    text = escape(detail).replace('\n', '<br>')
    document.setHtml(
        '<html><head><style>body {color:#355349;font-size:20px;} h1 {font-size:32px;}'
        'p {line-height:140%;} td {padding:10px;} </style></head><body>'
        '<h1>谛听 · 模型关注图</h1><p>' + source + '<br>导出时间：' + timestamp + '</p>'
        '<table width="100%"><tr><td width="50%">原始图像 / 视频采样帧</td>'
        '<td width="50%">所选人脸与解释方向</td></tr><tr><td>'
        '<img src="fg-original" width="' + str(original.width()) + '" height="' + str(original.height()) + '"></td><td>'
        '<img src="fg-overlay" width="' + str(composite.width()) + '" height="' + str(composite.height()) + '"></td></tr></table>'
        '<p>' + text + '<br>模型版本：' + escape(model_label) + ' · 叠加强度：' + str(round(opacity * 100)) + '%</p>'
        '<p><span style="color:#3756a8">蓝色：相对低关注</span> → '
        '<span style="color:#a77716">黄色</span> → <span style="color:#bd3c36">红色：相对高关注</span></p>'
        '<p>' + escape(status) + '</p><p>粗粒度模型解释，放大不增加定位信息。'
        '不代表真假概率或精确篡改边界；未检出不代表真实。</p></body></html>')
    height = int(document.size().height())
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if path.suffix.lower() == '.png':
        canvas = QImage(1600, height + 96, QImage.Format.Format_ARGB32)
        canvas.fill(QColor('#fcfbf7'))
        painter = QPainter(canvas)
        painter.translate(48, 48)
        document.drawContents(painter)
        painter.end()
        if not canvas.save(buffer, 'PNG'):
            raise ValueError('关注图编码失败。')
    else:
        writer = QPdfWriter(buffer)
        writer.setTitle('谛听 · 模型关注图')
        writer.setCreator('FaceGuard')
        writer.setResolution(120)
        writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        writer.setPageOrientation(QPageLayout.Orientation.Landscape)
        writer.setPageMargins(QMarginsF(12, 12, 12, 12), QPageLayout.Unit.Millimeter)
        painter = QPainter(writer)
        scale = min(writer.width() / document.size().width(), writer.height() / height)
        painter.translate((writer.width() - document.size().width() * scale) / 2, 0)
        painter.scale(scale, scale)
        document.drawContents(painter)
        painter.end()
        del writer
    data = bytes(buffer.data())
    buffer.close()
    path.write_bytes(data)
