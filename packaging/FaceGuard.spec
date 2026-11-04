# Build only with requirements-release.txt in a separate Windows environment.
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files

root = Path(SPECPATH).parent
ui = root / 'src/faceguard/ui'
ui_files = [path for path in ui.rglob('*') if path.is_file() and (
    'assets' not in path.relative_to(ui).parts
    or path.is_relative_to(ui / 'assets/diting-motion-v7')
    or path == ui / 'assets/ink-lake-lotus-v3.png')
    and path.name not in ('import.log', 'import-report.json')]
a = Analysis(
    [str(root / 'run_app.pyw')], pathex=[str(root / 'src')],
    datas=[(str(path), str(Path('faceguard/ui') / path.parent.relative_to(ui))) for path in ui_files] + collect_data_files('tzdata'),
    hiddenimports=['PySide6.QtQuick', 'PySide6.QtQuick3D', 'PySide6.QtMultimedia',
                   'PySide6.QtPdf', 'PySide6.QtTest'],
    excludes=['tkinter', 'pandas', 'scipy', 'sklearn', 'pyarrow', 'matplotlib',
              'pytest', 'IPython', 'jupyter', 'tensorboard', 'onnx', 'onnxruntime'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='FaceGuard',
          console=False, debug=False, strip=False, upx=False,
          icon=str(root / 'src/faceguard/ui/brand.ico'))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='FaceGuard')
