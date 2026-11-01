"""Official inference CLI; no imports from reference_run."""
import argparse
import json
from pathlib import Path
from .face_analysis import FaceAnalyzer
from .result_text import result_lines
from faceguard.data_locations import resolve_data_path
from faceguard.model_registry import checked_generation_profile, generation_profiles


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path', type=Path)
    parser.add_argument('--task', choices=['auto', 'generation', 'manipulation', 'both'], default='auto')
    parser.add_argument('--device', choices=['cpu', 'cuda'])
    parser.add_argument('--sampling', choices=['legacy', 'adaptive'], default='adaptive')
    parser.add_argument('--face-crop', action='store_true', help='Input is already a face crop; not for ordinary photos')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--generation-model', choices=[p['id'] for p in generation_profiles()], default='stable')
    args = parser.parse_args()
    checkpoint = checked_generation_profile(args.generation_model) if args.task != 'manipulation' else None
    result = FaceAnalyzer(device=args.device, generation_checkpoint=checkpoint).predict(resolve_data_path(args.path), task=args.task, face_crop=args.face_crop, video_sampling=args.sampling)
    result['generation_model_profile'] = args.generation_model
    generation = result.get('results', {}).get('generation')
    if generation is None and result.get('task') == 'whole_face_generation':
        generation = result
    if generation is not None:
        generation['model_label'] = next(p['label'] for p in generation_profiles() if p['id'] == args.generation_model)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    print('\n'.join(result_lines(result)))


if __name__ == '__main__':
    main()
