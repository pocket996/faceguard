"""Optional user-supplied regression stays local; never selects models or thresholds."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image,ImageOps
import torch

from project_io import save_json,digest
from core import crop_face
from face_analysis import FaceAnalyzer
from generation_common import canonical_face


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session',type=Path,required=True)
    parser.add_argument('--user-image',type=Path)
    args=parser.parse_args();base=args.session
    torch.set_num_threads(2);cv2.setNumThreads(1)
    chosen_gen=json.loads((base/'generation-selection.json').read_text())['selected']['checkpoint']
    chosen_photo=json.loads((base/'photo-selection.json').read_text())['selected']['checkpoint']
    analyzer=FaceAnalyzer(device='cpu',generation_checkpoint=chosen_gen,photo_checkpoint=chosen_photo)
    blank=base/'blank-final.png';Image.new('RGB',(512,512),'gray').save(blank)
    result=analyzer.predict(blank);assert result['decision']=='no_face' and result['score'] is None
    broken=base/'corrupt-final.png';broken.write_bytes(b'not-an-image')
    try:analyzer.predict(broken)
    except ValueError:pass
    else:raise AssertionError('Corrupt image must not be labeled real')
    checks=dict(no_face_abstains=True,corrupt_file_is_error=True)
    if args.user_image and args.user_image.is_file():
        checksum=digest(args.user_image)
        result=analyzer.predict(args.user_image)
        with Image.open(args.user_image) as source:image=ImageOps.exif_transpose(source).convert('RGB')
        face=crop_face(cv2.cvtColor(np.asarray(image),cv2.COLOR_RGB2BGR),analyzer.generation.detector)
        if face is not None:
            pixels=hashlib.sha256(canonical_face(face).tobytes()).hexdigest()
            with (base/'openfake-prepared/combined_manifest.csv').open(encoding='utf-8-sig',newline='') as stream:
                training_pixels={r['pixel_sha256'] for r in csv.DictReader(stream) if r['split'] in ('train','val')}
            assert pixels not in training_pixels,'Known user regression overlaps fitting data'
        assert checksum==digest(args.user_image),'Input file changed'
        save_json(base/'user-regression-local.json',dict(image_sha256=checksum,unchanged=True,
            used_for_training_or_selection=False,result=result,
            note='Previously observed user-reported GPT image. Regression only, not a new blind test; never uploaded.'))
        checks['user_image_unchanged_and_excluded']=True
    elif args.user_image:
        checks['user_image_status']='not_found_not_evaluated'
        raise FileNotFoundError('Requested user image was not evaluated: '+str(args.user_image))
    save_json(base/'robustness-regression.json',checks);print(checks,flush=True)


if __name__=='__main__':main()
