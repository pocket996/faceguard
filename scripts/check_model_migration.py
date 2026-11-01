"""Compare real stable reference and official inference on identical local inputs."""
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from faceguard.data_locations import data_location


def main():
    import cv2
    import numpy as np
    from PIL import Image
    import torch
    torch.set_num_threads(2)
    cv2.setNumThreads(1)
    output = ROOT / 'outputs/model-migration-20261031'
    output.mkdir(parents=True, exist_ok=True)
    photo = next(data_location('lfw').rglob('*.jpg'))
    generated = data_location('examples') / 'joint/generation_0.jpg'
    blank = output / 'no-face.png'
    Image.new('RGB', (300, 300), '#eeeeee').save(blank)
    multiple = output / 'multiple-faces.jpg'
    with Image.open(photo) as im:
        image = im.convert('RGB')
        canvas = Image.new('RGB', (image.width * 2, image.height), '#eeeeee')
        canvas.paste(image, (0, 0)); canvas.paste(image, (image.width, 0))
        canvas.save(multiple)
    video = next(data_location('ffpp').rglob('*.mp4'))
    # Separate processes prevent reference imports from satisfying official imports.
    code = '''import json,sys,cv2,torch
from pathlib import Path
root=Path(sys.argv[1]);mode=sys.argv[2];cases=json.loads(Path(sys.argv[3]).read_text(encoding='utf-8'))
torch.set_num_threads(2);cv2.setNumThreads(1)
if mode=='reference':
 sys.path.insert(0,str(root/'reference_run'))
 from face_analysis import FaceAnalyzer
else:
 sys.path.insert(0,str(root/'src'))
 from faceguard.inference.face_analysis import FaceAnalyzer
analyzer=FaceAnalyzer(device='cpu');results=[]
for case in cases:
 result=analyzer.predict(case['path'],video_sampling=case.get('sampling','adaptive'))
 results.append(result)
if mode=='official':
 assert not any('reference_run' in str(getattr(m,'__file__','')) for m in list(sys.modules.values()) if m)
Path(sys.argv[4]).write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
'''
    cases = [{'name': 'real-photo', 'path': str(photo)}, {'name': 'generated-photo', 'path': str(generated)},
             {'name': 'multiple-faces', 'path': str(multiple)}, {'name': 'no-face', 'path': str(blank)},
             {'name': 'video-legacy', 'path': str(video), 'sampling': 'legacy'},
             {'name': 'video-adaptive', 'path': str(video), 'sampling': 'adaptive'}]
    (output / 'cases.json').write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding='utf-8')
    for mode in ('reference', 'official'):
        print('Running ' + mode, flush=True)
        subprocess.run([sys.executable, '-c', code, str(ROOT), mode, str(output / 'cases.json'), str(output / (mode + '.json'))], check=True)
    reference = json.loads((output / 'reference.json').read_text(encoding='utf-8'))
    official = json.loads((output / 'official.json').read_text(encoding='utf-8'))
    maximum_error = 0.
    def compare(left, right, location='result'):
        nonlocal maximum_error
        if isinstance(left, dict):
            # Official manipulation reports add the model hash; all old fields remain.
            assert set(left) <= set(right), location
            for key in left:
                compare(left[key], right[key], location + '.' + key)
        elif isinstance(left, list):
            assert len(left) == len(right), location
            for i, (a, b) in enumerate(zip(left, right)):
                compare(a, b, f'{location}[{i}]')
        elif isinstance(left, (float, int)) and not isinstance(left, bool):
            error = abs(left - right)
            maximum_error = max(maximum_error, error)
            assert error <= 1e-6, (location, left, right)
        else:
            assert left == right, (location, left, right)
    compare(reference, official)
    assert reference[0]['faces'] > 0 and reference[2]['faces'] >= 2
    assert reference[3]['decision'] == 'no_face'
    from faceguard.model_registry import manifest, checked_resource
    resources = manifest()
    for name in resources['files']:
        checked_resource(name)
    provenance = json.loads((output / 'code-provenance.json').read_text(encoding='utf-8'))
    for record in provenance:
        original = ROOT / 'reference_run' / record['module']
        assert hashlib.sha256(original.read_bytes()).hexdigest() == record.get('source_after_data_path_update_sha256', record['source_sha256'])
        if record.get('original_source_backup'):
            assert hashlib.sha256(Path(record['original_source_backup']).read_bytes()).hexdigest() == record['source_sha256']
    report = dict(passed=True, cases=[x['name'] for x in cases], device='cpu', maximum_absolute_difference=maximum_error,
                  independent_runtime_imports=True, reference_code_preserved=True, reference_data_paths_updated=True, resource_checksums_verified=True,
                  scope='Functional parity only; these fixtures do not measure new-data accuracy')
    (output / 'verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
