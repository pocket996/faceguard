"""Historical manifest paths remain usable without creating filesystem aliases."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from faceguard import data_locations as locations


class DataLocationTests(unittest.TestCase):
    def test_missing_legacy_directory_maps_without_a_link(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            store, legacy = root/'store', root/'old-data'
            target = store/'02_processed/faces'
            target.mkdir(parents=True)
            (target/'photo.jpg').write_bytes(b'fixture')
            (store/'DATA_CATALOG.json').write_text(json.dumps(dict(root=str(store), entries=[
                dict(legacy_entry=str(legacy), directory=str(target))])), encoding='utf-8')
            with patch.object(locations, 'DATA_ROOT', store):
                mapped = locations.resolve_data_path(legacy/'photo.jpg')
                self.assertEqual(mapped, target/'photo.jpg')
                self.assertEqual(mapped.read_bytes(), b'fixture')
                self.assertFalse(legacy.exists())
                self.assertEqual(locations.resolve_data_path(root/'unrelated.txt'), root/'unrelated.txt')

    def test_current_and_historical_project_spellings_and_relative_rows(self):
        root = Path(tempfile.gettempdir())/'faceguard-layout-test'
        with patch.object(locations, 'DATA_ROOT', root):
            expected = locations.data_location('ffpp', root)/'original_sequences/movie.mp4'
            self.assertEqual(locations.resolve_data_path('data/raw/ffpp/original_sequences/movie.mp4', ROOT), expected)
            self.assertEqual(locations.resolve_data_path('D:/deepfake-detection/data/raw/ffpp/original_sequences/movie.mp4'), expected)
            self.assertEqual(locations.resolve_data_path('D:/faceguard/data/raw/ffpp/original_sequences/movie.mp4'), expected)

    def test_prefix_siblings_and_parent_traversal_are_not_redirected(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Path(folder)/'store'
            with patch.object(locations, 'DATA_ROOT', store):
                sibling = ROOT/'data/raw/ffpp-extra/movie.mp4'
                self.assertEqual(locations.resolve_data_path(sibling), sibling)
                outside = ROOT/'data/raw/ffpp/../outside.txt'
                self.assertEqual(locations.resolve_data_path(outside), ROOT/'data/raw/outside.txt')

    def test_desktop_reopens_historical_dataset_record_without_an_old_directory(self):
        from PySide6.QtCore import QSettings
        from PySide6.QtWidgets import QApplication
        from PIL import Image
        from faceguard.app import AppController
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);store=root/'store';legacy=root/'old-data'
            actual=store/'01_raw/picture.jpg';actual.parent.mkdir(parents=True)
            Image.new('RGB',(80,100)).save(actual)
            (store/'DATA_CATALOG.json').write_text(json.dumps(dict(root=str(store),entries=[
                dict(legacy_entry=str(legacy),directory=str(actual.parent))])),encoding='utf-8')
            controller=AppController(QSettings(str(root/'prefs.ini'),QSettings.Format.IniFormat))
            identifier=controller.history.add(legacy/'picture.jpg','image','historical fixture')
            with patch.object(locations,'DATA_ROOT',store):
                self.assertTrue(controller.reopenRecord(identifier))
                self.assertEqual(Path(controller.previewUrl.toLocalFile()),actual)
                self.assertFalse(legacy.exists())
            controller.shutdown()


if __name__ == '__main__':
    unittest.main()
