"""Local image-to-mesh study, isolated from FaceGuard's detection runtime.

Run with the external reconstruction venv. Install upstream Hunyuan3D-2 and
its official mini checkpoint outside this repository; see asset README.
This produces an unrigged, untextured study, never modifies production assets.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback


def load_shape_pipeline(model_dir: Path):
    """Assign checkpoint tensors to meta modules, avoiding duplicate CPU weights."""
    import torch
    import yaml
    from accelerate import init_empty_weights
    from safetensors import safe_open
    from hy3dgen.shapegen.pipelines import (
        Hunyuan3DDiTFlowMatchingPipeline, instantiate_from_config,
    )

    config = yaml.safe_load((model_dir / 'config.yaml').read_text(encoding='utf-8'))
    components = {}
    with safe_open(str(model_dir / 'model.fp16.safetensors'), framework='pt', device='cpu') as checkpoint:
        keys = list(checkpoint.keys())
        for name in ('model', 'vae', 'conditioner'):
            print(f'Loading {name} without temporary weight copies', flush=True)
            with init_empty_weights(include_buffers=False):
                module = instantiate_from_config(config[name])
            state = {key[len(name)+1:]: checkpoint.get_tensor(key)
                     for key in keys if key.startswith(name + '.')}
            result = module.load_state_dict(state, strict=(name != 'vae'), assign=True)
            if result.missing_keys or result.unexpected_keys:
                print(f'{name}: {len(result.missing_keys)} missing / {len(result.unexpected_keys)} extra keys', flush=True)
            if name == 'vae':
                # Official inference checkpoint omits point-cloud encoding weights.
                # Only post_kl / transformer / geo_decoder are used by this task.
                unexpected_missing = [key for key in result.missing_keys
                                      if not key.startswith(('encoder.', 'pre_kl.'))]
                if unexpected_missing:
                    raise RuntimeError(f'Missing VAE decoding weights: {unexpected_missing}')
                del module.encoder
                del module.pre_kl
            if any(p.is_meta for p in module.parameters()):
                raise RuntimeError(f'{name} has uninitialized meta parameters')
            module.eval().requires_grad_(False)
            components[name] = module
            del state
    return Hunyuan3DDiTFlowMatchingPipeline(
        **components,
        image_processor=instantiate_from_config(config['image_processor']),
        scheduler=instantiate_from_config(config['scheduler']),
        device='cpu', dtype=torch.float16)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--model-dir', type=Path, required=True)
    parser.add_argument('--image', type=Path, default=Path('src/faceguard/ui/assets/diting-v2.png'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seed', type=int, default=20261030)
    parser.add_argument('--steps', type=int, default=40)
    parser.add_argument('--resolution', type=int, default=384)
    parser.add_argument('--chunks', type=int, default=4000)
    parser.add_argument('--offload', choices=['auto', 'model', 'sequential'], default='auto')
    parser.add_argument('--latent', type=Path, help='Reuse saved latents, skipping image encoding and diffusion')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault('HF_HUB_OFFLINE', '1')
    os.environ.setdefault('TRANSFORMERS_OFFLINE', '1')
    sys.path.insert(0, str(args.source_root.resolve()))
    started = time.monotonic()
    report = {
        'status': 'running', 'kind': 'untextured_static_mesh_study',
        'image': str(args.image.resolve()),
        'image_sha256': hashlib.sha256(args.image.read_bytes()).hexdigest(),
        'source_root': str(args.source_root.resolve()),
        'source_commit': subprocess.check_output(
            ['git', '-C', str(args.source_root), 'rev-parse', 'HEAD'], text=True).strip(),
        'source_modifications': subprocess.check_output(
            ['git', '-C', str(args.source_root), 'diff', '--stat'], text=True).strip(),
        'model': 'tencent/Hunyuan3D-2mini/' + args.model_dir.name,
        'model_dir': str(args.model_dir.resolve()),
        'seed': args.seed, 'steps': args.steps,
        'resolution': args.resolution, 'chunks': args.chunks,
        'textured': False, 'rigged': False, 'production_asset_replaced': False,
    }
    (output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    try:
        decoder_source = (args.source_root / 'hy3dgen/shapegen/models/autoencoders/volume_decoders.py')
        if 'dtype=next_points.dtype' in decoder_source.read_text(encoding='utf-8'):
            raise RuntimeError('Apply scripts/hunyuan3d_float_coordinates.patch to the external vendor checkout first')
        print('Importing isolated reconstruction runtime', flush=True)
        import torch
        from PIL import Image
        from hy3dgen.shapegen import Hunyuan3DDiTFlowMatchingPipeline
        from hy3dgen.shapegen.models.autoencoders.volume_decoders import HierarchicalVolumeDecoding

        if not torch.cuda.is_available():
            raise RuntimeError('CUDA is required for this local reconstruction study')
        torch.set_num_threads(4)
        torch.cuda.reset_peak_memory_stats()
        report['gpu'] = torch.cuda.get_device_name()
        print(f"Loading half-precision shape model on CPU; GPU: {report['gpu']}", flush=True)
        # Avoid a temporary float32 copy of the large DINO encoder on a 16 GB PC.
        prior_dtype = torch.get_default_dtype()
        try:
            torch.set_default_dtype(torch.float16)
            pipeline = load_shape_pipeline(args.model_dir)
        finally:
            torch.set_default_dtype(prior_dtype)

        # Upstream's offload helper expects a components dictionary, while this
        # pinned class does not define it. Supply the three existing modules;
        # retain upstream Accelerate hooks without changing the vendor checkout.
        pipeline.components = {
            'conditioner': pipeline.conditioner,
            'model': pipeline.model,
            'vae': pipeline.vae,
        }
        available_vram, _ = torch.cuda.mem_get_info()
        sequential = args.offload == 'sequential' or (
            args.offload == 'auto' and available_vram < 3 * 2**30)
        if sequential:
            from accelerate import cpu_offload
            # The upstream image encoder reads model.device before forward;
            # retain it on CPU instead of exposing meta parameters there.
            for module in (pipeline.model, pipeline.vae):
                cpu_offload(module, execution_device=torch.device('cuda:0'), offload_buffers=True)
            report['offload'] = 'cpu-conditioner+sequential-model-vae'
        else:
            pipeline.enable_model_cpu_offload()
            report['offload'] = 'model'
        print(f"CPU offload: {report['offload']}; free VRAM {available_vram/2**30:.2f} GiB", flush=True)
        pipeline.device = torch.device('cuda:0')
        # Upstream hierarchical decoding queries the surface neighborhood instead
        # of every point in a dense 384^3 cube; no custom CUDA extension needed.
        pipeline.vae.volume_decoder = HierarchicalVolumeDecoding()
        report['volume_decoder'] = 'upstream HierarchicalVolumeDecoding'
        if args.latent:
            latents = torch.load(args.latent, map_location='cuda', weights_only=True)
            report['reused_latent'] = str(args.latent.resolve())
        else:
            print('Reconstructing image-conditioned shape latents', flush=True)
            with Image.open(args.image) as image:
                latents = pipeline(
                    image=image.convert('RGBA'), num_inference_steps=args.steps,
                    guidance_scale=5.0,
                    generator=torch.Generator(device='cuda').manual_seed(args.seed),
                    output_type='latent')
            if not torch.isfinite(latents).all():
                raise ValueError('Shape latents contain nonfinite values')
            torch.save(latents.detach().cpu(), output / 'shape-latents.pt')
        print(f'Extracting surface at {args.resolution}^3, chunk={args.chunks}', flush=True)
        with torch.inference_mode():
            pipeline.set_surface_extractor('mc')
            meshes = pipeline._export(
                latents, output_type='trimesh',
                octree_resolution=args.resolution, num_chunks=args.chunks)
        mesh = meshes[0]
        if mesh is None or len(mesh.vertices) < 1000:
            raise ValueError('No meaningful surface was produced')
        import numpy as np
        if not np.isfinite(mesh.vertices).all():
            raise ValueError('Surface contains nonfinite coordinates')
        mesh.export(output / 'diting-reconstructed.glb')
        mesh.export(output / 'diting-reconstructed.ply')
        report.update({
            'status': 'mesh_exported', 'vertices': len(mesh.vertices),
            'faces': len(mesh.faces), 'bounds': mesh.bounds.tolist(),
            'watertight': bool(mesh.is_watertight),
            'finite_vertices': True,
            'gpu_peak_allocated_gib': torch.cuda.max_memory_allocated() / 2**30,
        })
        if not sequential:
            pipeline.maybe_free_model_hooks()
        print(f"Exported {report['vertices']} vertices / {report['faces']} faces", flush=True)
    except Exception as error:
        report.update(status='failed', error=f'{type(error).__name__}: {error}')
        traceback.print_exc()
        raise
    finally:
        report['elapsed_seconds'] = time.monotonic() - started
        (output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
