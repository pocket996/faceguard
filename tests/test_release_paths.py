"""Installed models must be found independently of the developer checkout or cwd."""
from pathlib import Path
import sys
import unittest
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


if __name__ == '__main__':
    unittest.main()
