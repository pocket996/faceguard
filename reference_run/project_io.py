"""Lightweight project paths and atomic result files; no machine-learning runtime import."""
import hashlib
import json
import sys
from pathlib import Path
from app_paths import application_directory

HERE=application_directory()
PROJECT=HERE.parent

# Source training/evaluation uses the central data store. The existing frozen
# reference executable remains self-contained and does not need training data.
if not getattr(sys, 'frozen', False):
    sys.path.insert(0, str(PROJECT / 'src'))
    from faceguard.data_locations import data_location, resolve_data_path
else:
    def resolve_data_path(value, base=None):
        return Path(base) / value if base is not None else Path(value)

    def data_location(name):
        raise RuntimeError('Training data are not bundled with the frozen reference executable')


def save_json(path, value):
    path = resolve_data_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    temp.replace(path)


def digest(path):
    h = hashlib.sha256()
    with resolve_data_path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()
