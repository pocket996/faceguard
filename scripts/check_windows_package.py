"""Install, exercise and uninstall the actual package in an isolated test folder."""
import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time


def shell_folder(name):
    return Path(subprocess.check_output(['powershell.exe', '-NoProfile', '-Command',
        f"[Console]::OutputEncoding=[Text.UTF8Encoding]::new(); [Environment]::GetFolderPath('{name}')"],
        text=True, encoding='utf-8', creationflags=subprocess.CREATE_NO_WINDOW).strip())


def inspect_link(path, helper):
    return json.loads(subprocess.check_output(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                                             '-File', str(helper), '-LinkPath', str(path)], text=True,
                                             encoding='utf-8', creationflags=subprocess.CREATE_NO_WINDOW))


class ShellExecuteInfo(ctypes.Structure):
    _fields_ = [('cbSize', wintypes.DWORD), ('fMask', ctypes.c_ulong), ('hwnd', wintypes.HWND),
                ('lpVerb', wintypes.LPCWSTR), ('lpFile', wintypes.LPCWSTR), ('lpParameters', wintypes.LPCWSTR),
                ('lpDirectory', wintypes.LPCWSTR), ('nShow', ctypes.c_int), ('hInstApp', wintypes.HINSTANCE),
                ('lpIDList', ctypes.c_void_p), ('lpClass', wintypes.LPCWSTR), ('hkeyClass', wintypes.HKEY),
                ('dwHotKey', wintypes.DWORD), ('hIcon', wintypes.HANDLE), ('hProcess', wintypes.HANDLE)]


def process_family(pid):
    class ProcessEntry(ctypes.Structure):
        _fields_ = [('dwSize', wintypes.DWORD), ('cntUsage', wintypes.DWORD), ('th32ProcessID', wintypes.DWORD),
                    ('th32DefaultHeapID', ctypes.c_size_t), ('th32ModuleID', wintypes.DWORD),
                    ('cntThreads', wintypes.DWORD), ('th32ParentProcessID', wintypes.DWORD),
                    ('pcPriClassBase', wintypes.LONG), ('dwFlags', wintypes.DWORD), ('szExeFile', wintypes.WCHAR * 260)]
    kernel = ctypes.windll.kernel32
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    snapshot = kernel.CreateToolhelp32Snapshot(2, 0)
    pairs = []
    entry = ProcessEntry()
    entry.dwSize = ctypes.sizeof(entry)
    kernel.Process32FirstW.argtypes = kernel.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)]
    ok = kernel.Process32FirstW(snapshot, ctypes.byref(entry))
    while ok:
        pairs.append((entry.th32ProcessID, entry.th32ParentProcessID))
        ok = kernel.Process32NextW(snapshot, ctypes.byref(entry))
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle(snapshot)
    family = {pid}
    while True:
        expanded = family | {child for child, parent in pairs if parent in family}
        if expanded == family:
            return family
        family = expanded


def launch_link(path):
    info = ShellExecuteInfo()
    info.cbSize, info.fMask, info.lpFile, info.nShow = ctypes.sizeof(info), 0x40, str(path), 1
    if not ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(info)):
        raise ctypes.WinError()
    kernel = ctypes.windll.kernel32
    kernel.GetProcessId.argtypes = [wintypes.HANDLE]
    pid = kernel.GetProcessId(info.hProcess)
    family = {pid}
    windows = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def visit(hwnd, context):
        owner = wintypes.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value in family and ctypes.windll.user32.IsWindowVisible(hwnd):
            title, kind = ctypes.create_unicode_buffer(512), ctypes.create_unicode_buffer(128)
            ctypes.windll.user32.GetWindowTextW(hwnd, title, len(title))
            ctypes.windll.user32.GetClassNameW(hwnd, kind, len(kind))
            windows.append((hwnd, title.value, kind.value))
        return True
    callback = callback_type(visit)
    deadline = time.monotonic() + 40
    while time.monotonic() < deadline:
        family = process_family(pid)
        windows.clear()
        ctypes.windll.user32.EnumWindows(callback, 0)
        if any('FaceGuard' in title for _, title, _ in windows):
            break
        time.sleep(.2)
    try:
        assert any('FaceGuard' in title for _, title, _ in windows), f'No visible app window for PID {pid}'
        assert not any(kind == 'ConsoleWindowClass' for _, _, kind in windows)
        return dict(pid=pid, windows=[dict(title=title, window_class=kind) for _, title, kind in windows])
    finally:
        for hwnd, _, _ in windows:
            ctypes.windll.user32.PostMessageW(hwnd, 0x10, 0, 0)
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        result = kernel.WaitForSingleObject(info.hProcess, 15000)
        if result == 258:
            # Only the process this test launched can be terminated.
            kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
            kernel.TerminateProcess(info.hProcess, 1)
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle(info.hProcess)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--setup', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--photo', required=True, type=Path)
    parser.add_argument('--video', required=True, type=Path)
    args = parser.parse_args()
    setup, output = args.setup.resolve(), args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    helper = output / 'inspect-link.ps1'
    helper.write_text('param([string]$LinkPath)\n[Console]::OutputEncoding=[Text.UTF8Encoding]::new()\n'
                      '$s=(New-Object -ComObject WScript.Shell).CreateShortcut($LinkPath)\n'
                      '$s | Select-Object TargetPath,Arguments,WorkingDirectory,IconLocation | ConvertTo-Json -Compress\n', encoding='utf-8-sig')
    install = output / '安装 空格/FaceGuard'
    if not install.resolve().is_relative_to(output) or install.exists():
        raise ValueError('Use a fresh, isolated installation folder')
    desktop_link = shell_folder('Desktop') / '谛听 FaceGuard.lnk'
    menu_group = shell_folder('Programs') / '谛听 FaceGuard'
    if menu_group.exists():
        raise ValueError('An existing user installation owns the Start menu group; do not overwrite it')
    original_link = desktop_link.read_bytes() if desktop_link.exists() else None
    report = dict(passed=False, installer_sha256=hashlib.sha256(setup.read_bytes()).hexdigest(),
                  clean_computer_validation=False, test_directory=str(install))
    try:
        subprocess.run([str(setup), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART',
                        '/DIR=' + str(install), '/TASKS=desktopicon', '/LOG=' + str(output / 'install.log')],
                       check=True, timeout=180, creationflags=subprocess.CREATE_NO_WINDOW)
        exe = install / 'FaceGuard.exe'
        assert exe.is_file() and desktop_link.is_file()
        link = inspect_link(desktop_link, helper)
        assert Path(link['TargetPath']).resolve() == exe.resolve(), link
        assert not link['Arguments']
        menu_links = list(menu_group.glob('*.lnk'))
        assert len(menu_links) == 1 and Path(inspect_link(menu_links[0], helper)['TargetPath']).resolve() == exe.resolve()
        report['desktop_shortcut'] = link
        report['shortcut_launch'] = launch_link(desktop_link)
        environment = dict(os.environ)
        for name in ('PYTHONPATH', 'PYTHONHOME', 'VIRTUAL_ENV', 'FACEGUARD_MODEL_DIR', 'FACEGUARD_DATA_ROOT'):
            environment.pop(name, None)
        environment['PATH'] = os.environ['SystemRoot'] + '\\System32;' + os.environ['SystemRoot']
        result = subprocess.run([str(exe), '--verify-install', str(output / 'runtime-check.json'),
                                 '--test-photo', str(args.photo.resolve()), '--test-video', str(args.video.resolve())],
                                cwd=output, env=environment, timeout=300, creationflags=subprocess.CREATE_NO_WINDOW)
        runtime = json.loads((output / 'runtime-check.json').read_text(encoding='utf-8'))
        assert result.returncode == 0 and runtime['passed'], runtime
        report['runtime'] = runtime
        # Snapshot real existing history files, rather than an unrelated marker.
        user_data = shell_folder('LocalApplicationData') / 'FaceGuard'
        history_before = {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                          for path in user_data.rglob('*.sqlite3')} if user_data.exists() else {}
        subprocess.run([str(setup), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART',
                        '/DIR=' + str(install), '/TASKS=desktopicon'], check=True, timeout=180,
                       creationflags=subprocess.CREATE_NO_WINDOW)
        for name, expected in history_before.items():
            assert hashlib.sha256(Path(name).read_bytes()).hexdigest() == expected
        report['existing_history_files_preserved'] = len(history_before)
        report['reinstall_passed'] = True
        report['passed'] = True
    finally:
        uninstaller = install / 'unins000.exe'
        if uninstaller.exists():
            assert install.resolve().is_relative_to(output)
            subprocess.run([str(uninstaller), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART',
                            '/LOG=' + str(output / 'uninstall.log')], check=True, timeout=120,
                           creationflags=subprocess.CREATE_NO_WINDOW)
            report['uninstalled'] = not (install / 'FaceGuard.exe').exists()
            assert report['uninstalled']
            for name, expected in locals().get('history_before', {}).items():
                assert hashlib.sha256(Path(name).read_bytes()).hexdigest() == expected
        if original_link is not None:
            desktop_link.write_bytes(original_link)
        report['source_shortcut_restored'] = original_link is not None
        (output / 'package-check.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(passed=report['passed'], report=str(output / 'package-check.json'))))


if __name__ == '__main__':
    main()
