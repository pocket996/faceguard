"""Launch the official FaceGuard application independently of reference_run."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / 'src'))

try:
    from faceguard.app import main
except ModuleNotFoundError as error:
    if error.name and error.name.startswith('PySide6'):
        raise SystemExit('缺少正式界面依赖。请先在根目录执行：\n'
                         '.\\.venv\\Scripts\\python.exe -m pip install -r requirements-ui.txt') from None
    raise

if __name__ == '__main__':
    main()
