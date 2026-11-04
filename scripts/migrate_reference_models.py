"""Install an explicit stable runtime bundle; preserve all reference models."""
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from faceguard.model_registry import digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', type=Path, default=ROOT / 'reference_run')
    parser.add_argument('--destination', type=Path, default=ROOT / 'weights/runtime')
    args = parser.parse_args()
    import torch
    reference, target = args.reference.resolve(), args.destination.resolve()
    if target == reference or target.is_relative_to(reference):
        raise ValueError('Runtime directory must be separate from reference')
    originals = {
        'generation.pt': reference / 'artifacts/generation/joint/model.pt',
        'manipulation.pt': reference / 'artifacts/model_finetuned.pt',
        'yunet.onnx': reference / 'weights/face_detection_yunet_2023mar.onnx',
        'video_policy.json': reference / 'artifacts/video_review/policy.json',
        'YuNet-LICENSE.txt': ROOT / 'weights/YuNet-LICENSE.txt',
    }
    hashes = {name: digest(path) for name, path in originals.items()}
    ready = json.loads((reference / 'artifacts/generation/joint/READY.json').read_text(encoding='utf-8'))
    if hashes['generation.pt'] != ready['model_sha256']:
        raise ValueError('Joint generation model does not match its validated READY marker')
    states = {name: torch.load(originals[name], map_location='cpu', weights_only=True)
              for name in ('generation.pt', 'manipulation.pt')}
    generation = states['generation.pt']
    if generation.get('task') != 'whole_face_generation' or generation.get('preprocessing') != 'generation128_jpeg90':
        raise ValueError('Unexpected generation task/preprocessing')
    for state in states.values():
        if state['yunet_sha256'] != hashes['yunet.onnx'] or state.get('input_size', 224) != 224 or state.get('feature_normalization', 'ImageNet') != 'ImageNet' or state.get('architecture', 'resnet18') != 'resnet18':
            raise ValueError('Unsupported runtime preprocessing')
    policy = json.loads(originals['video_policy.json'].read_text(encoding='utf-8'))
    if policy['model_sha256'] != hashes['manipulation.pt']:
        raise ValueError('Video policy belongs to a different manipulation model')
    target.mkdir(parents=True, exist_ok=True)
    records = {}
    for name, source in originals.items():
        path = target / name
        if path.exists() and digest(path) != hashes[name]:
            raise ValueError(f'Existing runtime resource differs; preserved: {path}')
        if not path.exists():
            temporary = path.with_name(name + '.copying')
            shutil.copy2(source, temporary)
            if digest(temporary) != hashes[name]:
                raise ValueError(f'Copy mismatch: {name}')
            temporary.rename(path)
        records[name] = dict(sha256=hashes[name], size=path.stat().st_size, copied_from=str(source))
    value = dict(schema_version=1, installed_at_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),
                 selection='Stable FLUX/SD3.5 joint generation + FF++ fully finetuned manipulation; experimental candidates are not activated',
                 files=records, models={name: {k: v for k, v in state.items() if k not in ('backbone', 'head')}
                                      for name, state in states.items()},
                 reference_preserved=all(digest(path) == hashes[name] for name, path in originals.items()))
    temporary = target / 'manifest.json.tmp'
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(target / 'manifest.json')
    print(json.dumps(value, ensure_ascii=True, indent=2))


if __name__ == '__main__':
    main()
