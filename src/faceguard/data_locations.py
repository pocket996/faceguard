"""Canonical data paths and translation of frozen historical manifest paths."""
import os
import json
from functools import lru_cache
from pathlib import Path

DATA_ROOT = Path(os.environ.get('FACEGUARD_DATA_ROOT', 'D:/datasets/faceguard' if os.name == 'nt' else str(Path.home() / 'datasets/faceguard')))

LOCATIONS = {
    'dff': '01_raw/generation/deepfakeface',
    'gan140k': '01_raw/generation/gan140k',
    'fairfacegen': '01_raw/generation/fairfacegen',
    'ffpp': '01_raw/manipulation/ffpp',
    'lfw': '01_raw/real/lfw',
    'ffhq256': '01_raw/real/ffhq256',
    'openfake': '01_raw/mixed/openfake-20261026',
    'ffpp_faces': '02_processed/manipulation/ffpp',
    'generation_faces': '02_processed/generation/baseline128',
    'openfake_faces': '02_processed/generation/openfake-20261026',
    'photo_supervision': '02_processed/manipulation/photo-supervision-20261026',
    'sparse_video': '02_processed/regression/sparse-video-20261026',
    'examples': '02_processed/examples/generation',
    'ffpp_manifests': '03_manifests/ffpp',
    'generation_manifest': '03_manifests/generation-baseline/generation_manifest.csv',
    'clean_generation': '03_manifests/generation-clean-20261026',
    'fairface_evaluation': '04_evaluation/fairface-20261026',
    'locked_evaluation': '04_evaluation/locked-20261026',
    'new_data_evaluation': '04_evaluation/new-data-20261031',
    'source_record': '05_provenance/incoming-20261031/SOURCE.md',
    'import_receipts': '05_provenance/import-20261031',
    'unverified_inspection': '05_provenance/unverified-inspection-20261017.json',
    'unverified_archives': '90_quarantine/third-party-20261017',
    'unverified_previews': '90_quarantine/previews-20261017',
    'dff_update_faces': '02_processed/generation/dff-sd15-20261031-v1',
    'generation_update_manifests': '03_manifests/dff-sd15-20261031-v1',
    'dff_update_provenance': '05_provenance/dff-sd15-20261031-v1',
    'wiki_identity_metadata': '05_provenance/imdb-wiki',
    'generation_joint_manifests': '03_manifests/dff-gpt-joint-20261031-v1',
    'generation_joint_provenance': '05_provenance/dff-gpt-joint-20261031-v1',
    'current_data_audit': '05_provenance/current-data-low-fpr-20261031',
    'current_generation_pools': '03_manifests/current-data-low-fpr-20261031',
}


def data_location(name, root=None):
    return (Path(root) if root is not None else DATA_ROOT) / LOCATIONS[name]


@lru_cache(maxsize=4)
def _path_mappings(root_string):
    root = Path(root_string)
    project = Path(__file__).resolve().parents[2]
    relative = {
        'data/raw/ffpp': 'ffpp', 'data/raw/fairfacegen': 'fairfacegen',
        'data/processed/ffpp': 'ffpp_faces', 'data/manifests': 'ffpp_manifests',
        'reference_run/data/raw/lfw': 'lfw', 'reference_run/data/raw/ffhq256': 'ffhq256',
        'reference_run/data/processed/generation128': 'generation_faces',
        'reference_run/data/examples': 'examples',
        'reference_run/data/generation_manifest.csv': 'generation_manifest',
    }
    mappings = {str(base / old): data_location(key, root)
                for base in {project, Path('D:/faceguard'), Path('D:/deepfake-detection')}
                for old, key in relative.items()}
    catalog = root / 'DATA_CATALOG.json'
    if catalog.is_file():
        data = json.loads(catalog.read_text(encoding='utf-8'))
        original_root = Path(data['root'])
        for entry in data['entries']:
            if not entry.get('legacy_entry'):
                continue
            target = root / Path(entry['directory']).relative_to(original_root)
            source = entry['legacy_entry']
            mappings[source] = target
            if source.lower().startswith('d:\\faceguard\\'):
                mappings['D:\\deepfake-detection\\' + source[len('D:\\faceguard\\'):]] = target
    return sorted(((os.path.normcase(os.path.abspath(old)), target) for old, target in mappings.items()),
                  key=lambda item: -len(item[0]))


def resolve_data_path(value, base=None):
    """Translate old path text without creating a directory or changing frozen CSV bytes."""
    path = Path(value)
    if not path.is_absolute() and base is not None:
        path = Path(base) / path
    absolute = os.path.abspath(path)
    normalized = os.path.normcase(absolute)
    for old, target in _path_mappings(str(DATA_ROOT)):
        if normalized == old:
            return target
        if normalized.startswith(old + os.sep):
            return target / os.path.relpath(absolute, old)
    return Path(absolute)


def ffpp_receipt_key(path):
    resolved = resolve_data_path(path, Path(__file__).resolve().parents[2])
    return 'data/raw/ffpp/' + resolved.relative_to(data_location('ffpp')).as_posix()
