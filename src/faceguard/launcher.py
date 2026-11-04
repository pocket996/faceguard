"""Windowless startup with persistent Python and native diagnostics."""
import ctypes
from datetime import datetime
import os
from pathlib import Path
import sys
import traceback

from .version import APP_VERSION


def log_directory():
    return Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local')) / 'FaceGuard'


def launch():
    folder = log_directory()
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / 'startup.log'
    if path.exists() and path.stat().st_size > 2 * 1024 * 1024:
        try:
            path.replace(folder / 'startup.previous.log')
        except OSError:
            pass  # Another running instance may still own the previous log.
    stream = path.open('a', encoding='utf-8', buffering=1)
    windowless = sys.stderr is None or getattr(sys, 'frozen', False)
    if windowless:
        sys.stdout = sys.stderr = stream
        if os.name == 'nt':
            import msvcrt
            for descriptor, handle_id in ((1, -11), (2, -12)):
                try:
                    os.dup2(stream.fileno(), descriptor)
                    ctypes.windll.kernel32.SetStdHandle(ctypes.c_ulong(handle_id), ctypes.c_void_p(msvcrt.get_osfhandle(descriptor)))
                except OSError:
                    pass
    print(f'\n[{datetime.now().isoformat(timespec="seconds")}] FaceGuard {APP_VERSION} startup', file=stream)

    def error_report(kind, error, trace):
        traceback.print_exception(kind, error, trace, file=stream)
        stream.flush()
        if os.name == 'nt':
            ctypes.windll.user32.MessageBoxW(None, f'应用遇到问题：{error}\n\n诊断日志：{path}', f'谛听 · FaceGuard {APP_VERSION}', 0x10)

    sys.excepthook = error_report
    try:
        if '--verify-install' in sys.argv:
            from .install_check import main as verify_install
            return verify_install()
        from .app import main
        return main()
    except SystemExit as error:
        if error.code is not None and not isinstance(error.code, int):
            error_report(*sys.exc_info())
            return 1
        raise
    except Exception:
        error_report(*sys.exc_info())
        return 1
