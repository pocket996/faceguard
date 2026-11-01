"""Official UI controller checks; no reference inference or training dependency."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

try:
    from PySide6.QtCore import QSettings, QUrl
    from PySide6.QtGui import QImage
    from PySide6.QtWidgets import QApplication
except ModuleNotFoundError as error:
    raise unittest.SkipTest('Install requirements-ui.txt to test the desktop UI.') from error
from faceguard.app import AppController


class DesktopControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)
        self.controller = AppController(QSettings(str(self.root / 'prefs.ini'), QSettings.Format.IniFormat))

    def tearDown(self):
        self.controller.settings.sync()
        self.folder.cleanup()

    def test_unicode_image_is_read_and_can_be_cleared(self):
        path = self.root / '\u6d4b\u8bd5\u7167\u7247.png'
        image = QImage(120, 160, QImage.Format.Format_RGB32)
        image.fill('#a6c6b3')
        self.assertTrue(image.save(str(path)))
        self.controller.load_file(path)
        self.assertEqual(self.controller.fileName, path.name)
        self.assertEqual(Path(self.controller.previewUrl.toLocalFile()), path.resolve())
        self.assertIn('120', self.controller.metadata)
        self.assertFalse(self.controller.errorText)
        self.controller.clearFile()
        self.assertFalse(self.controller.fileName)
        self.assertTrue(self.controller.previewUrl.isEmpty())

    def test_broken_image_does_not_replace_current_selection(self):
        path = self.root / 'bad.png'
        path.write_bytes(b'not an image')
        self.controller.load_file(path)
        self.assertFalse(self.controller.fileName)
        self.assertTrue(self.controller.errorText)

    def test_missing_empty_and_unsupported_files_have_errors(self):
        for name, content in [('missing.png', None), ('empty.png', b''), ('notes.txt', b'text')]:
            if content is not None:
                (self.root / name).write_bytes(content)
            self.controller.load_file(self.root / name)
            self.assertTrue(self.controller.errorText)
            self.assertFalse(self.controller.fileName)

    def test_remote_url_is_rejected(self):
        self.controller.dropFile(QUrl('https://example.com/image.png'))
        self.assertTrue(self.controller.errorText)
        self.assertFalse(self.controller.fileName)

    def test_preferences_are_persistent_and_isolated(self):
        self.controller.toggleReducedMotion()
        self.controller.toggleTopmost()
        second = AppController(self.controller.settings)
        self.assertTrue(second.reducedMotion)
        self.assertTrue(second.topmost)

    def make_photo(self, name='history.png'):
        path = self.root / name
        image = QImage(30, 40, QImage.Format.Format_RGB32)
        image.fill('#a6c6b3')
        self.assertTrue(image.save(str(path)))
        self.assertTrue(self.controller.load_file(path))
        return path

    def test_history_survives_restart_and_reopen_does_not_duplicate(self):
        self.make_photo()
        self.assertEqual(self.controller.historyCount, 1)
        record = self.controller.historyRecords[0]
        self.assertEqual(record['status'], 'pending')
        self.assertTrue(record['created_at'].endswith('+08:00'))
        second = AppController(self.controller.settings)
        self.assertEqual(second.historyCount, 1)
        self.assertTrue(second.reopenRecord(record['id']))
        self.assertEqual(second.fileName, 'history.png')
        self.assertEqual(second.historyCount, 1)

    def test_missing_history_file_reports_error_and_retains_record(self):
        path = self.make_photo()
        record = self.controller.historyRecords[0]
        path.unlink()
        self.assertFalse(self.controller.reopenRecord(record['id']))
        self.assertTrue(self.controller.errorText)
        self.assertEqual(self.controller.historyCount, 1)

    def test_deleting_history_never_deletes_source_media(self):
        path = self.make_photo()
        self.controller.deleteRecord(self.controller.historyRecords[0]['id'])
        self.assertEqual(self.controller.historyCount, 0)
        self.assertTrue(path.exists())
        self.controller.load_file(path)
        self.controller.clearHistory()
        self.assertEqual(self.controller.historyCount, 0)
        self.assertTrue(path.exists())

    def test_failed_import_does_not_create_a_history_record(self):
        broken = self.root / 'broken.png'
        broken.write_bytes(b'not an image')
        self.assertFalse(self.controller.load_file(broken))
        self.assertEqual(self.controller.historyCount, 0)


if __name__ == '__main__':
    unittest.main()
