"""Build a CPU-only, windowless official application and per-user installer."""
import argparse
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from faceguard.version import APP_VERSION


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_fingerprint():
    files = sorted((ROOT / 'src/faceguard').rglob('*.py'))
    files += [ROOT / 'run_app.pyw', ROOT / 'packaging/FaceGuard.spec']
    files += sorted(path for path in (ROOT / 'src/faceguard/ui').rglob('*') if path.is_file()
                    and path.name not in ('import.log', 'import-report.json'))
    return {path.relative_to(ROOT).as_posix(): digest(path) for path in files}


def collect_licenses(target):
    for distribution in metadata.distributions():
        name = distribution.metadata.get('Name', 'unknown').replace('/', '_')
        for entry in distribution.files or []:
            relative = Path(str(entry))
            if relative.is_absolute() or '..' in relative.parts:
                continue
            if not any(word in str(entry).lower() for word in ('license', 'copying', 'copyright', 'notice')) or str(entry).endswith('.py'):
                continue
            source = Path(distribution.locate_file(entry))
            if source.is_file():
                destination = target / name / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
    python_license = Path(sys.base_prefix) / 'LICENSE.txt'
    if python_license.is_file():
        target.mkdir(parents=True, exist_ok=True)
        shutil.copy2(python_license, target / 'Python-LICENSE.txt')


def resources():
    runtime = json.loads((ROOT / 'weights/runtime/manifest.json').read_text(encoding='utf-8'))
    names = ['weights/runtime/manifest.json'] + ['weights/runtime/' + name for name in runtime['files']]
    catalog = json.loads((ROOT / 'weights/generation-candidates/manifest.json').read_text(encoding='utf-8'))
    names += ['weights/generation-candidates/manifest.json'] + ['weights/generation-candidates/' + row['file'] for row in catalog['profiles']]
    names += ['weights/face_detection_yunet_2023mar.onnx', 'weights/YuNet-LICENSE.txt']
    from faceguard.model_registry import checked_generation_profile, checked_resource
    for name in runtime['files']:
        checked_resource(name)
    for row in catalog['profiles']:
        checked_generation_profile(row['id'])
    return sorted(set(names))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'outputs/release-20261104')
    parser.add_argument('--iscc', type=Path, required=True)
    parser.add_argument('--skip-freeze', action='store_true')
    parser.add_argument('--portable', action='store_true')
    args = parser.parse_args()
    output = args.output.resolve()
    # PyInstaller may replace its own dist directory on a rebuild.
    if not output.is_relative_to((ROOT / 'outputs').resolve()):
        raise ValueError('Build output must stay within the project outputs directory')
    output.mkdir(parents=True, exist_ok=True)
    import torch
    if sys.platform != 'win32' or torch.version.cuda is not None:
        raise RuntimeError('Build with Windows x64 CPU-only requirements-release.txt')
    payload = output / 'dist/FaceGuard'
    snapshot_path = output / 'frozen-sources.json'
    if not args.skip_freeze:
        snapshot = source_fingerprint()
        command = [sys.executable, '-m', 'PyInstaller', '--noconfirm',
                   '--distpath', str(output / 'dist'), '--workpath', str(output / 'build'),
                   str(ROOT / 'packaging/FaceGuard.spec')]
        subprocess.run(command, cwd=ROOT, check=True)
        snapshot_path.write_text(json.dumps(snapshot, indent=2), encoding='utf-8')
    else:
        snapshot = json.loads(snapshot_path.read_text(encoding='utf-8'))
        if snapshot != source_fingerprint():
            raise ValueError('Packaged source changed: rebuild instead of relabeling an old executable')
    exe = payload / 'FaceGuard.exe'
    binary = exe.read_bytes()
    pe = struct.unpack_from('<I', binary, 0x3c)[0]
    if struct.unpack_from('<H', binary, pe + 24 + 68)[0] != 2:
        raise ValueError('Executable is not the windowless Windows GUI subsystem')
    entries = []
    for name in resources():
        source, destination = ROOT / name, payload / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        if digest(source) != digest(destination):
            raise ValueError('Resource copy hash mismatch: ' + name)
        entries.append(dict(path=name, sha256=digest(source), bytes=source.stat().st_size))
    for source, name in [(ROOT / 'LICENSE', 'CODE_LICENSE.txt'),
                         (ROOT / 'docs/TEAM_QUICKSTART.md', 'START_HERE.md'),
                         (ROOT / 'docs/MODEL_CARD.md', 'MODEL_CARD.md'),
                         (ROOT / 'docs/PROJECT_LIMITATIONS_PLAIN.md', 'PROJECT_LIMITATIONS.md')]:
        shutil.copy2(source, payload / name)
    (payload / 'START_HERE.txt').write_text(
        f'谛听 FaceGuard {APP_VERSION} · Windows 10/11 x64 CPU 内测版\n\n'
        '通过安装程序安装后，双击桌面或开始菜单的“谛听 FaceGuard”即可启动，无命令行窗口。\n'
        '无需安装 Python、CUDA 或训练数据；照片和视频留在本机。\n'
        '生成与篡改分别显示；视频生成项仅为照片模型的采样人脸线索。\n'
        '桌宠控件在鼠标悬停时出现；设置中可选择生成候选。\n'
        '本版未经代码签名，Windows 可能显示未知发布者；请核对官方下载及 SHA256SUMS.txt。\n'
        '启动诊断：%LOCALAPPDATA%\\FaceGuard\\startup.log。\n'
        '卸载仅移除程序，保留本机设置、日志与检测历史。\n'
        '更多说明见 START_HERE.md / MODEL_CARD.md。\n', encoding='utf-8-sig')
    collect_licenses(payload / 'THIRD_PARTY_LICENSES')
    info = dict(version=APP_VERSION, python=sys.version, compute='CPU',
                source_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                source_tree_dirty=bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip()),
                frozen_sources=snapshot, resources=entries,
                dependencies={d.metadata['Name']: d.version for d in metadata.distributions()},
                training_data_included=False, personal_media_included=False,
                gui_subsystem=True, independent_clean_pc_validation='pending')
    (payload / 'BUILD_INFO.json').write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Compiling per-user installer...', flush=True)
    subprocess.run([str(args.iscc.resolve()), '/Qp', '/DAppVersion=' + APP_VERSION,
                    '/DPayloadDir=' + str(payload), '/DReleaseDir=' + str(output),
                    str(ROOT / 'packaging/FaceGuard.iss')], cwd=ROOT, check=True)
    assets = [output / f'FaceGuard-v{APP_VERSION}-windows-x64-cpu-setup.exe']
    if args.portable:
        target = output / f'FaceGuard-v{APP_VERSION}-windows-x64-cpu.zip'
        with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for path in sorted(payload.rglob('*')):
                if path.is_file():
                    archive.write(path, Path('FaceGuard') / path.relative_to(payload))
        assets.append(target)
    (output / 'SHA256SUMS.txt').write_text(''.join(f'{digest(path)}  {path.name}\n' for path in assets), encoding='ascii')
    report = dict(version=APP_VERSION, source_commit=info['source_commit'],
                  assets=[dict(path=str(path), bytes=path.stat().st_size, sha256=digest(path)) for path in assets])
    (output / 'build-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
