"""Readable reports for everyday use; JSON remains available to research callers."""
from datetime import datetime
from html import escape
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from PySide6.QtCore import QBuffer, QIODevice, QMarginsF
from PySide6.QtGui import QFont, QPageLayout, QPageSize, QPdfWriter, QTextDocument


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
