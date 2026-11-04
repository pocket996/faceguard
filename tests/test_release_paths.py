"""Installed models must be found independently of the developer checkout or cwd."""
from pathlib import Path
import sys
import unittest
import tempfile
import shutil
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from faceguard.paths import application_directory


class ReleasePathTests(unittest.TestCase):
    def test_source_uses_repository_root(self):
        with patch.object(sys, 'frozen', False, create=True):
            self.assertEqual(application_directory(), Path(__file__).resolve().parents[1])

    def test_frozen_uses_executable_directory_outside_internal_folder(self):
        executable = Path('C:/安装 空格/FaceGuard/FaceGuard.exe').resolve()
        with patch.object(sys, 'frozen', True, create=True), patch.object(sys, 'executable', str(executable)), \
             patch.object(sys, '_MEIPASS', str(executable.parent / '_internal'), create=True):
            self.assertEqual(application_directory() / 'weights/runtime', executable.parent / 'weights/runtime')

    def test_yunet_loads_original_bytes_from_unicode_install_directory(self):
        import numpy as np
        from faceguard.inference.media_faces import create_face_detector
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix='faceguard-unicode-') as folder:
            model = Path(folder) / '安装 空格' / '人脸模型.onnx'
            model.parent.mkdir()
            shutil.copyfile(root / 'weights/runtime/yunet.onnx', model)
            detector = create_face_detector(model)
            detector.setInputSize((320, 320))
            _, faces = detector.detect(np.zeros((320, 320, 3), dtype=np.uint8))
            self.assertIsNone(faces)


if __name__ == '__main__':
    unittest.main()
