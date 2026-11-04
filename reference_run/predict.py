"""Predict on one photo or video without modifying the source media."""
import argparse
import json
from pathlib import Path
import torch
import cv2
from core import HERE, Predictor, save_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input')
    parser.add_argument('--checkpoint', help='Default: fine-tuned model when available, otherwise frozen baseline')
    parser.add_argument('--generation-checkpoint',type=Path,help='Explicit generation experiment for auto/both')
    parser.add_argument('--photo-checkpoint',type=Path,help='Explicit photo manipulation experiment; video model unchanged')
    parser.add_argument('--face-crop', action='store_true', help='Input image already is a square face crop')
    parser.add_argument('--output')
    parser.add_argument('--device', choices=['cpu', 'cuda'])
    parser.add_argument('--video-sampling', choices=['legacy', 'adaptive'], default='adaptive')
    parser.add_argument('--task', choices=['auto', 'both', 'generation', 'manipulation'], default='auto',
                        help='auto: photos -> both tasks separately, videos -> manipulation')
    args = parser.parse_args()
    if args.checkpoint and (args.generation_checkpoint or args.photo_checkpoint):
        parser.error('Use --checkpoint or the per-task checkpoints, not both')
    torch.set_num_threads(4)
    cv2.setNumThreads(1)
    if args.checkpoint:
        if args.task in ('auto', 'both'):
            parser.error('--checkpoint requires explicit --task generation or manipulation')
        if args.task == 'generation':
            from face_analysis import GenerationPredictor
            predictor = GenerationPredictor(args.checkpoint, args.device)
        else:
            predictor = Predictor(args.checkpoint, args.device)
        if args.task == 'manipulation':
            result = predictor.predict(args.input, args.face_crop, adaptive_video=args.video_sampling == 'adaptive')
        else:
            result = predictor.predict(args.input, args.face_crop)
    else:
        from face_analysis import FaceAnalyzer
        result = FaceAnalyzer(args.device,generation_checkpoint=args.generation_checkpoint,photo_checkpoint=args.photo_checkpoint).predict(args.input, face_crop=args.face_crop, task=args.task,
                                                  video_sampling=args.video_sampling)
    if args.output:
        save_json(args.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
