"""Blender review of real reconstructed geometry, using a neutral clay material.

blender --background --factory-startup --python-exit-code 1
  --python scripts/preview_diting_reconstruction.py -- --mesh ...ply --output ...
"""
import argparse
import json
import math
from pathlib import Path
import shutil
import sys

import bpy
from mathutils import Vector


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mesh', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--views', nargs='+', default=['front', 'left', 'side', 'back'])
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    bpy.ops.wm.ply_import(filepath=str(args.mesh.resolve()))
    obj = bpy.context.object
    obj.name = 'Diting reconstructed real surface (unrigged)'
    # Hunyuan mesh: Y up, +Z image-facing. Blender: Z up, -Y image-facing.
    obj.rotation_euler.x = math.pi / 2
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    points = [obj.matrix_world @ v.co for v in obj.data.vertices]
    low = Vector(tuple(min(p[i] for p in points) for i in range(3)))
    high = Vector(tuple(max(p[i] for p in points) for i in range(3)))
    scale = 3.8 / (high.z - low.z)
    middle = (low + high) * .5
    for v in obj.data.vertices:
        v.co = (v.co - Vector((middle.x, middle.y, low.z))) * scale
    for face in obj.data.polygons:
        face.use_smooth = True

    clay = bpy.data.materials.new('Neutral ivory clay - shape inspection only')
    clay.diffuse_color = (.54, .47, .36, 1)
    clay.use_nodes = True
    shader = clay.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (.54, .47, .36, 1)
    shader.inputs['Roughness'].default_value = .62
    obj.data.materials.clear()
    obj.data.materials.append(clay)

    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 20
    scene.cycles.use_denoising = True
    scene.render.threads_mode = 'FIXED'
    scene.render.threads = 8
    scene.render.resolution_x = 840
    scene.render.resolution_y = 940
    scene.render.resolution_percentage = 100
    scene.world.use_nodes = True
    scene.world.node_tree.nodes.get('Background').inputs[0].default_value = (.77, .75, .69, 1)
    scene.world.node_tree.nodes.get('Background').inputs[1].default_value = .35
    scene.view_settings.view_transform = 'AgX'
    bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, -.035))
    floor = bpy.context.object
    floor.name = 'Studio floor (not character geometry)'
    floor_mat = bpy.data.materials.new('Warm studio floor')
    floor_mat.diffuse_color = (.72, .69, .62, 1)
    floor.data.materials.append(floor_mat)
    for name, location, power, size in [
        ('Key', (-4, -5, 7), 850, 4),
        ('Fill', (4, -2, 4), 260, 3),
        ('Rim', (1, 4, 6), 700, 3),
    ]:
        bpy.ops.object.light_add(type='AREA', location=location)
        lamp = bpy.context.object
        lamp.name = name
        lamp.data.energy = power
        lamp.data.size = size
        lamp.rotation_euler = (Vector((0, 0, 1.9)) - lamp.location).to_track_quat('-Z', 'Y').to_euler()
    bpy.ops.object.camera_add()
    camera = bpy.context.object
    scene.camera = camera
    camera.data.type = 'ORTHO'
    camera.data.ortho_scale = 4.45
    positions = {
        'front': (0, -9, 1.9), 'left': (-5, -8, 2.6),
        'right': (5, -8, 2.6), 'side': (9, 0, 2.5),
        'back': (0, 9, 2.5),
    }
    for view in args.views:
        camera.location = positions[view]
        camera.rotation_euler = (Vector((0, 0, 1.9)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
        scene.render.filepath = str(out / f'{view}-clay.png')
        bpy.ops.render.render(write_still=True)
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.gltf(filepath=str(out / 'diting-clay.glb'), use_selection=True, export_format='GLB')
    text = bpy.data.texts.new('preview_source.py')
    text.write(Path(__file__).read_text(encoding='utf-8'))
    shutil.copyfile(__file__, out / 'preview_source.py')
    bpy.ops.wm.save_as_mainfile(filepath=str(out / 'diting-reconstructed.blend'))
    report = {
        'source_mesh': str(args.mesh.resolve()),
        'vertices': len(obj.data.vertices), 'faces': len(obj.data.polygons),
        'mesh_objects_character': 1, 'image_textures': 0,
        'rigged': False, 'material': 'neutral clay, no texture',
        'views': args.views, 'likeness_approved': False,
    }
    (out / 'preview-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
