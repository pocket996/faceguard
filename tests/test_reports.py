"""Common report formats, readable Chinese and save-dialog behavior."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from PySide6.QtCore import QSettings
from PySide6.QtPdf import QPdfDocument
from PySide6.QtWidgets import QApplication
from faceguard.app import AppController
from faceguard.reports import write_report


class ReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.result = dict(path='D:/照片/老人 & 家人.png', task='whole_face_generation',
                           decision='no_face', model_sha256='technical-only-hash')
        self.text = 'AI整脸生成\n  未找到人脸，无法判断'

    def tearDown(self):
        self.directory.cleanup()

    def test_text_is_readable_chinese_without_raw_technical_dump(self):
        path = self.root / '报告.txt'
        write_report(path, self.result, self.text)
        contents = path.read_text(encoding='utf-8-sig')
        self.assertIn(self.result['path'], contents)
        self.assertIn(self.text, contents)
        self.assertIn('不是真假概率', contents)
        self.assertNotIn('technical-only-hash', contents)

    def test_pdf_contains_chinese_results_and_paginates_long_reports(self):
        path = self.root / '报告.pdf'
        write_report(path, self.result, self.text + '\n逐脸结果：疑似生成 · 81.0/100' * 110)
        self.assertTrue(path.read_bytes().startswith(b'%PDF-'))
        document = QPdfDocument()
        self.assertEqual(document.load(str(path)), QPdfDocument.Error.None_)
        self.assertGreater(document.pageCount(), 1)
        text = ''.join(document.getAllText(i).text() for i in range(document.pageCount()))
        self.assertIn('FaceGuard', text)
        self.assertIn('疑似生成', text)
        self.assertIn('不是真假概率', text)
        self.assertNotIn('technical-only-hash', text)
        document.close()

    def test_save_dialog_defaults_to_pdf_and_honors_extensionless_text_selection(self):
        controller = AppController(QSettings(str(self.root / 'prefs.ini'), QSettings.Format.IniFormat))
        controller._result = self.result
        controller._name = '照片.png'
        with patch('faceguard.app.QFileDialog.getSaveFileName', return_value=(str(self.root / '我的报告'), '文本文档 (*.txt)')) as dialog:
            controller.saveReport()
        self.assertTrue(dialog.call_args.args[2].endswith('.pdf'))
        self.assertNotIn('*.json', dialog.call_args.args[3])
        self.assertTrue((self.root / '我的报告.txt').exists())
        with patch('faceguard.app.QFileDialog.getSaveFileName', return_value=(str(self.root / '默认报告'), 'PDF 文档 (*.pdf)')):
            controller.saveReport()
        self.assertTrue((self.root / '默认报告.pdf').read_bytes().startswith(b'%PDF-'))
        controller.shutdown()

    def test_unsupported_extension_does_not_overwrite_existing_file(self):
        path = self.root / '报告.docx'
        path.write_bytes(b'original')
        with self.assertRaises(ValueError):
            write_report(path, self.result, self.text)
        self.assertEqual(path.read_bytes(), b'original')


if __name__ == '__main__':
    unittest.main()
