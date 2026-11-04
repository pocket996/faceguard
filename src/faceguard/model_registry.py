"""Explicit local runtime resources, independent of the reference checkout."""
import hashlib
import json
import os
from pathlib import Path
from .paths import application_directory

MODEL_DIRECTORY = Path(os.environ.get('FACEGUARD_MODEL_DIR', application_directory() / 'weights/runtime'))


def generation_profiles():
    profiles = [dict(id='stable', label='稳定版 · FLUX / SD3.5',
                     notice='主要覆盖 FLUX / SD3.5；GPT、StyleGAN 等来源仍可能漏检。')]
    catalog = MODEL_DIRECTORY.parent / 'generation-candidates/manifest.json'
    if catalog.is_file():
        data = json.loads(catalog.read_text(encoding='utf-8'))
        if data.get('schema_version') != 1:
            raise ValueError('不支持此生成候选目录版本。')
        for record in data['profiles']:
            profiles.append(dict(record))
    return profiles


def checked_generation_profile(identifier):
    if identifier == 'stable':
        return checked_resource('generation.pt')
    record = next((p for p in generation_profiles() if p['id'] == identifier), None)
    if record is None:
        raise ValueError('所选生成模型未安装，请在设置中重新选择。')
    folder = (MODEL_DIRECTORY.parent / 'generation-candidates').resolve()
    path = (folder / record['file']).resolve()
    if not path.is_relative_to(folder) or not path.is_file():
        raise ValueError('生成候选路径无效。')
    if path.stat().st_size != record['size'] or digest(path) != record['sha256']:
        raise ValueError('生成候选校验失败，请重新安装；未自动切换模型。')
    return path


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def manifest():
    data = json.loads((MODEL_DIRECTORY / 'manifest.json').read_text(encoding='utf-8'))
    if data.get('schema_version') != 1:
        raise ValueError('不支持此模型资源版本，请重新准备正式模型。')
    return data


def checked_resource(name):
    record = manifest()['files'][name]
    path = MODEL_DIRECTORY / name
    if path.stat().st_size != record['size'] or digest(path) != record['sha256']:
        raise ValueError(f'正式模型资源校验失败：{name}，请重新准备。')
    return path


def resource_status():
    try:
        data = manifest()
        required = ('generation.pt', 'manipulation.pt', 'yunet.onnx', 'video_policy.json')
        for name in required:
            if name not in data['files'] or not (MODEL_DIRECTORY / name).is_file():
                return False, '缺少正式模型资源，请按 README 准备。'
        return True, '稳定双模型已准备 · 首次检测将校验并加载'
    except (OSError, ValueError, KeyError, TypeError):
        return False, '正式模型尚未准备，请按 README 准备。'
