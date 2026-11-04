"""Extend the approved seated character with brow/chin skin and listening acting.

Run with Blender. Keeps v5 intact, audits every exported frame, and writes the
editable scene and reports to outputs. This is a seated performance rig, not IK
locomotion or an open-mouth facial rig.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys

import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from animate_diting_expressive import pose, curve, check_closed_pupils
from rig_diting_character import evaluated_positions, clear_pose


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scene', type=Path, required=True)
    parser.add_argument('--face-report', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(args.scene.resolve()))
    scene = bpy.context.scene
    rig = bpy.data.objects['DitingRig']
    body = next(o for o in scene.objects if o.name.startswith('Diting reconstructed'))
    eyes = json.loads(args.face_report.read_text())['eyes']
    rig.animation_data_clear()
    clear_pose(rig)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='EDIT')
    controls = [('Chin', (.34, -1.23, 2.65))]
    for eye in eyes:
        controls.append(('Brow' + eye['label'], Vector(eye['center']) + Vector((0, 0, .19))))
    for name, center in controls:
        bone = rig.data.edit_bones.new(name)
        bone.head = center
        bone.tail = Vector(center) + Vector((0, 0, .12))
        bone.parent = rig.data.edit_bones['Head']
    bpy.ops.object.mode_set(mode='OBJECT')
    for bone in rig.pose.bones:
        bone.rotation_mode = 'XYZ'

    # Transfer a bounded portion of existing Head influence along smooth local
    # masks. Never move the eye/lid surfaces or paint a replacement expression.
    coords = np.array([v.co[:] for v in body.data.vertices])
    head_group = body.vertex_groups['Head']
    head = np.array([next((g.weight for g in v.groups if g.group == head_group.index), 0)
                     for v in body.data.vertices])
    masks = []
    x, y, z = coords.T
    masks.append(.65 * np.exp(-((x - .34) / .24) ** 4 - ((y + 1.40) / .22) ** 4
                             - ((z - 2.64) / .115) ** 4))
    for eye in eyes:
        center = np.array(eye['center']) + np.array((0, 0, .19))
        masks.append(.50 * np.exp(-np.sum(((coords - center) / (.21, .20, .09)) ** 2, axis=1)))
    additions = np.stack(masks, axis=1) * head[:, None]
    head_new = head - additions.sum(axis=1)
    assert head_new.min() >= -1e-6
    for (name, _), weights in zip(controls, additions.T):
        group = body.vertex_groups.new(name=name)
        quantized = np.rint(weights * 1024).astype(int)
        for level in np.unique(quantized[quantized > 0]):
            group.add(np.flatnonzero(quantized == level).tolist(), float(level) / 1024, 'REPLACE')
    quantized = np.rint(head_new * 1024).astype(int)
    for level in np.unique(quantized[head > 0]):
        head_group.add(np.flatnonzero((quantized == level) & (head > 0)).tolist(), float(level) / 1024, 'REPLACE')
    # Bound the runtime skin to four normalized influences after adding controls.
    for vertex in body.data.vertices:
        groups = sorted([(g.group, g.weight) for g in vertex.groups if g.weight > 0], key=lambda g: -g[1])
        kept = groups[:4]
        total = sum(w for _, w in kept)
        assert total > 0
        for index, _ in groups[4:]:
            body.vertex_groups[index].remove([vertex.index])
        for index, weight in kept:
            body.vertex_groups[index].add([vertex.index], weight / total, 'REPLACE')

    rest = coords.copy()
    edges = np.array([e.vertices[:] for e in body.data.edges])
    lengths = np.linalg.norm(rest[edges[:, 0]] - rest[edges[:, 1]], axis=1)
    valid = lengths > 1e-4
    feet = rest[:, 2] < .20
    actions = {}
    audit = []
    scene.render.fps = 30
    for name, count in [('Idle', 181), ('Respond', 73), ('Listen', 121)]:
        action = bpy.data.actions.new(name + '_v6')
        rig.animation_data_create()
        rig.animation_data.action = action
        for frame in range(1, count + 1):
            t = (frame - 1) / (count - 1)
            pose(rig, name, t, (frame - 1) / 30, eyes)
            intensity = curve(t, [(0, 0), (.16, .15), (.32, 1), (.60, 1), (.82, .1), (1, 0)])
            if name == 'Listen':
                # Lower the head toward the water with neck/chest support.
                rig.pose.bones['Head'].rotation_euler.x += math.radians(11) * intensity
                rig.pose.bones['Neck'].rotation_euler.x += math.radians(5) * intensity
                rig.pose.bones['EarUpright'].rotation_euler.x -= math.radians(7) * intensity
            expression = intensity if name != 'Idle' else math.sin(t * 2 * math.pi)
            rig.pose.bones['BrowNear'].location.y = .026 * expression
            rig.pose.bones['BrowFar'].location.y = .020 * expression
            rig.pose.bones['Chin'].rotation_euler.x = math.radians(.8) * expression
            for bone in rig.pose.bones:
                if bone.name.startswith('Paw') or bone.name in ('Root', 'Pelvis'):
                    continue
                for channel in ('rotation_euler', 'location', 'scale'):
                    bone.keyframe_insert(data_path=channel, frame=frame, group=bone.name)
        action.use_fake_user = True
        actions[name] = action
        endpoints = []
        maximum_paw = 0
        maximum_strain = 0
        for frame in range(1, count + 1):
            scene.frame_set(frame)
            current = evaluated_positions(body)
            assert np.isfinite(current).all()
            maximum_paw = max(maximum_paw, float(np.linalg.norm(current[feet] - rest[feet], axis=1).max()))
            ratios = np.linalg.norm(current[edges[:, 0]] - current[edges[:, 1]], axis=1)[valid] / lengths[valid]
            maximum_strain = max(maximum_strain, float(np.percentile(ratios, 99)))
            if frame in (1, count):
                endpoints.append(current.copy())
        endpoint_error = float(np.linalg.norm(endpoints[0] - endpoints[-1], axis=1).max())
        audit.append(dict(clip=name, frames=count, paw_maximum=maximum_paw,
                          edge_ratio_p99_maximum=maximum_strain, endpoint_error=endpoint_error))
        assert maximum_paw < 1e-4 and endpoint_error < 1e-4, audit[-1]
        assert maximum_strain < 1.27, audit[-1]
    pupil_checks = check_closed_pupils(rig, actions, eyes)
    rig.animation_data.action = None
    # Remove historical actions from export, leaving exactly three new clips.
    for action in list(bpy.data.actions):
        if action not in actions.values():
            bpy.data.actions.remove(action)
    for name, action in actions.items():
        action.name = name
        track = rig.animation_data.nla_tracks.new()
        track.name = name
        track.strips.new(name, 1, action)
        track.mute = True
    rig.animation_data.action = actions['Idle']
    scene.frame_start = 1
    scene.frame_end = 181
    scene.frame_set(1)
    shutil.copyfile(__file__, out / 'acting_source.py')
    bpy.ops.wm.save_as_mainfile(filepath=str(out / 'diting-acting-v6.blend'))
    bpy.ops.object.select_all(action='DESELECT')
    for obj in scene.objects:
        if obj in (rig, body) or obj.get('facial_geometry'):
            obj.select_set(True)
    bpy.context.view_layer.objects.active = rig
    asset = out / 'DitingActingV6.glb'
    bpy.ops.export_scene.gltf(filepath=str(asset), use_selection=True, export_format='GLB',
                             export_animations=True, export_animation_mode='ACTIONS',
                             export_force_sampling=True, export_skins=True, export_def_bones=True)
    report = dict(bone_count=len(rig.data.bones), clips=list(actions), deformation_audit=audit,
                  closed_pupil_checks=pupil_checks, source_scene=str(args.scene.resolve()),
                  sha256=hashlib.sha256(asset.read_bytes()).hexdigest(),
                  limitations='Seated acting; subtle sealed chin; no open mouth, tongue, quadruped IK or walking')
    (out / 'motion-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
