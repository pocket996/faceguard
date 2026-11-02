"""Run INSIDE Blender to validate mesh, rig, rendering and animated GLB export.

Example: blender.exe --background --factory-startup --python-exit-code 1
         --python scripts/check_blender.py -- --output outputs/blender-setup
The generated cube is a tooling check, not a Diting character asset.
"""
import argparse
import json
from pathlib import Path
import struct
import sys

import bpy
from mathutils import Vector


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

    bpy.ops.mesh.primitive_cube_add(size=1.4, location=(0, 0, 0.8))
    cube = bpy.context.object
    cube.name = 'TOOL_CHECK_ONLY_not_Diting'
    bevel = cube.modifiers.new('Soft edges', 'BEVEL')
    bevel.width = 0.12
    bevel.segments = 4
    material = bpy.data.materials.new('Jade material tool check')
    material.use_nodes = True
    shader = material.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (0.35, 0.58, 0.45, 1)
    shader.inputs['Roughness'].default_value = 0.28
    cube.data.materials.append(material)

    bpy.ops.object.armature_add(location=(0, 0, 0))
    rig = bpy.context.object
    rig.name = 'ToolCheckRig'
    bone = rig.pose.bones[0]
    group = cube.vertex_groups.new(name=bone.name)
    group.add(list(range(len(cube.data.vertices))), 1.0, 'REPLACE')
    modifier = cube.modifiers.new('ToolCheckSkin', 'ARMATURE')
    modifier.object = rig
    cube.parent = rig
    bone.rotation_mode = 'XYZ'
    for frame, angle in [(1, 0), (20, 0.35), (40, 0)]:
        bone.rotation_euler.z = angle
        bone.keyframe_insert(data_path='rotation_euler', frame=frame)
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = 1, 40
    scene.frame_set(1)

    bpy.ops.object.camera_add(location=(3, -4, 3))
    camera = bpy.context.object
    camera.rotation_euler = (Vector((0, 0, 0.8)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
    camera.data.type = 'ORTHO'
    camera.data.ortho_scale = 3.3
    scene.camera = camera
    bpy.ops.object.light_add(type='AREA', location=(1, -3, 5))
    bpy.context.object.data.energy = 500
    bpy.context.object.data.shape = 'DISK'
    bpy.context.object.data.size = 4
    scene.world.color = (0.35, 0.35, 0.35)
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 16
    scene.render.resolution_x = scene.render.resolution_y = 320
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.filepath = str(output / 'tool-check.png')
    bpy.ops.wm.save_as_mainfile(filepath=str(output / 'tool-check.blend'))
    bpy.ops.render.render(write_still=True)
    glb = output / 'tool-check.glb'
    bpy.ops.export_scene.gltf(filepath=str(glb), export_format='GLB', export_animations=True)
    data = glb.read_bytes()
    magic, version, size = struct.unpack('<III', data[:12])
    assert magic == 0x46546c67 and version == 2 and size == len(data)
    json_size, json_kind = struct.unpack('<II', data[12:20])
    assert json_kind == 0x4e4f534a
    manifest = json.loads(data[20:20 + json_size])
    assert manifest.get('meshes'), 'No mesh exported'
    assert manifest.get('skins'), 'No rig/skin exported'
    assert manifest.get('animations'), 'No animation exported'
    assert (output / 'tool-check.png').stat().st_size > 1000
    report = {
        'passed': True, 'blender_version': bpy.app.version_string,
        'purpose': 'Tool validation only; NOT a Diting model',
        'checks': ['Python script execution', 'mesh + material', 'armature + skinning',
                   'bone animation', 'CPU render', 'blend save', 'animated GLB export'],
        'mesh_count': len(manifest['meshes']), 'skin_count': len(manifest['skins']),
        'animation_count': len(manifest['animations']),
    }
    (output / 'check.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
