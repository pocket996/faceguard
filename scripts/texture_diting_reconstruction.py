"""Blender front-view projection study on the reconstructed 3D surface.

This is a diagnostic texture projection, not a complete multiview texture set.
Side and back remain clay. Does not replace production UI assets.
"""
import argparse
import json
from pathlib import Path
import shutil
import sys

import bpy
from mathutils import Vector
import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scene', type=Path, required=True)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--alignment', type=Path, help='Optional camera-plane landmark deformation JSON')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(args.scene.resolve()))
    scene = bpy.context.scene
    obj = next(o for o in scene.objects if o.name.startswith('Diting reconstructed'))
    camera = scene.camera
    camera.location = (-5, -8, 2.6)
    target = Vector((0, 0, 1.9))
    camera.rotation_euler = (target - camera.location).to_track_quat('-Z', 'Y').to_euler()
    bpy.context.view_layer.update()
    basis = camera.rotation_euler.to_matrix()
    right = np.array(basis @ Vector((1, 0, 0)))
    up = np.array(basis @ Vector((0, 1, 0)))
    toward_camera = np.array((camera.location - target).normalized())
    vertices = np.empty(len(obj.data.vertices) * 3, dtype=np.float32)
    obj.data.vertices.foreach_get('co', vertices)
    vertices = vertices.reshape(-1, 3)
    projected = np.column_stack((vertices @ right, vertices @ up))
    bounds_min = projected.min(axis=0)
    bounds_max = projected.max(axis=0)
    alignment_report = None
    if args.alignment:
        alignment = json.loads(args.alignment.read_text(encoding='utf-8'))
        screen_width, screen_height = alignment['render_size']
        frame_height = camera.data.ortho_scale
        frame_width = frame_height * screen_width / screen_height
        center = np.array((np.array(target) @ right, np.array(target) @ up))
        screen = (projected - center) / np.array((frame_width, -frame_height))
        screen = (screen + .5) * np.array((screen_width, screen_height))
        controls = np.array([pair['from'] for pair in alignment['landmarks']], dtype=np.float64)
        destinations = np.array([pair['to'] for pair in alignment['landmarks']], dtype=np.float64)
        radius = alignment['radius_pixels']
        kernel = np.exp(-np.sum((controls[:, None] - controls[None, :])**2, axis=2) / (2*radius**2))
        weights = np.linalg.solve(kernel + np.eye(len(controls))*.002, destinations-controls)
        delta = np.empty_like(screen)
        for start in range(0, len(screen), 20000):
            distances = np.sum((screen[start:start+20000, None] - controls[None])**2, axis=2)
            delta[start:start+20000] = np.exp(-distances / (2*radius**2)) @ weights
        vertices += ((delta[:, 0] / screen_width * frame_width)[:, None] * right +
                     (-delta[:, 1] / screen_height * frame_height)[:, None] * up)
        obj.data.vertices.foreach_set('co', vertices.astype(np.float32).ravel())
        obj.data.update()
        bpy.context.view_layer.update()
        projected = np.column_stack((vertices @ right, vertices @ up))
        alignment_report = {'path': str(args.alignment.resolve()),
                            'maximum_screen_shift_pixels': float(np.linalg.norm(delta, axis=1).max()),
                            'changes_geometry': True, 'camera_depth_preserved': True}
        shutil.copyfile(args.alignment, out / 'alignment.json')
    normalized = (projected - bounds_min) / (bounds_max - bounds_min)

    reference = bpy.data.images.load(str(args.reference.resolve()), check_existing=True)
    width, height = reference.size
    rgba = np.empty(width * height * 4, dtype=np.float32)
    reference.pixels.foreach_get(rgba)
    rgba = rgba.reshape(height, width, 4)
    yy, xx = np.where(rgba[:, :, 3] > .5)
    uv_min = np.array((xx.min() / width, yy.min() / height))
    uv_max = np.array(((xx.max()+1) / width, (yy.max()+1) / height))
    uv_vertices = uv_min + normalized * (uv_max - uv_min)
    indices = np.empty(len(obj.data.loops), dtype=np.int32)
    obj.data.loops.foreach_get('vertex_index', indices)
    uv = obj.data.uv_layers.new(name='ReferenceProjectionDiagnostic')
    uv.data.foreach_set('uv', uv_vertices[indices].astype(np.float32).ravel())

    material = bpy.data.materials.new('Original image projection - front view diagnostic')
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    bsdf = nodes.get('Principled BSDF')
    bsdf.inputs['Roughness'].default_value = .48
    bsdf.inputs['Coat Weight'].default_value = .12
    image = nodes.new('ShaderNodeTexImage')
    image.image = reference
    image.extension = 'EXTEND'
    coord = nodes.new('ShaderNodeUVMap')
    coord.uv_map = uv.name
    links.new(coord.outputs['UV'], image.inputs['Vector'])
    mix = nodes.new('ShaderNodeMixRGB')
    mix.blend_type = 'MIX'
    mix.inputs[1].default_value = (.54, .47, .36, 1)
    links.new(image.outputs['Alpha'], mix.inputs[0])
    links.new(image.outputs['Color'], mix.inputs[2])
    links.new(mix.outputs[0], bsdf.inputs['Base Color'])
    obj.data.materials.append(material)
    normals = np.empty(len(obj.data.polygons) * 3, dtype=np.float32)
    obj.data.polygons.foreach_get('normal', normals)
    facing = normals.reshape(-1, 3) @ toward_camera
    # Retain clay at the back: never project a second face onto the back of head.
    slots = (facing > .12).astype(np.int32)
    obj.data.polygons.foreach_set('material_index', slots)
    reference.pack()
    scene.render.resolution_x = 1000
    scene.render.resolution_y = 1120
    scene.cycles.samples = 32
    scene.render.filepath = str(out / 'projection-preview.png')
    bpy.ops.render.render(write_still=True)
    # A nearby angle exposes stretch and keeps the diagnostic limitations visible.
    camera.location = (-3.2, -8, 2.6)
    camera.rotation_euler = (target - camera.location).to_track_quat('-Z', 'Y').to_euler()
    scene.render.filepath = str(out / 'projection-angle-check.png')
    bpy.ops.render.render(write_still=True)
    camera.location = (-5, -8, 2.6)
    camera.rotation_euler = (target - camera.location).to_track_quat('-Z', 'Y').to_euler()
    text = bpy.data.texts.new('projection_source.py')
    text.write(Path(__file__).read_text(encoding='utf-8'))
    shutil.copyfile(__file__, out / 'projection_source.py')
    bpy.ops.wm.save_as_mainfile(filepath=str(out / 'diting-projection-study.blend'))
    (out / 'projection-report.json').write_text(json.dumps({
        'kind': 'single-reference projection diagnostic',
        'reference': str(args.reference.resolve()),
        'source_scene': str(args.scene.resolve()),
        'real_geometry_vertices': len(obj.data.vertices),
        'front_projection_faces': int(slots.sum()),
        'back_material': 'neutral clay', 'reference_packed': True,
        'complete_multiview_texture': False, 'rigged': False,
        'production_asset_replaced': False,
        'alignment': alignment_report,
    }, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
