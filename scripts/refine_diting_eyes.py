"""Build layered geometric eyes and staggered listening-ear acting on v6.

Keeps the approved seated body, atlas, skeleton and action timing. Blender writes
an editable scene, self-contained GLB and geometric/occlusion audits to outputs.
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
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
from animate_diting_expressive import curve
from build_diting_face import mesh, full_weight
from rig_diting_character import evaluated_positions, clear_pose


def material(name, color, roughness=.35, coat=.15):
    result = bpy.data.materials.new(name)
    result.use_nodes = True
    shader = next(n for n in result.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    shader.inputs['Base Color'].default_value = (*color,1)
    shader.inputs['Roughness'].default_value = roughness
    shader.inputs['Coat Weight'].default_value = coat
    return result


def skin(obj, bone, rig):
    full_weight(obj, bone)
    modifier = obj.modifiers.new('Facial skin', 'ARMATURE')
    modifier.object = rig
    obj.parent = rig
    obj['facial_geometry'] = True


def layered_eye(eye, rig):
    label = eye['label']
    center, right, up, normal = (Vector(eye[k]) for k in ('center', 'right', 'up', 'normal'))
    radius, width, height = (eye[k] for k in ('radius', 'opening_width', 'opening_height'))
    iris_radius = width * .315
    pupil_radius = iris_radius * .43
    old = bpy.data.objects['EyeSurface' + label]
    bpy.data.objects.remove(old, do_unlink=True)
    sclera_mat = material('Warm recessed sclera ' + label, (.39, .32, .21), .30, .18)
    iris_mat = material('Radial amber iris ' + label, (1, 1, 1), .38, .10)
    pigment = iris_mat.node_tree.nodes.new('ShaderNodeVertexColor')
    pigment.layer_name = 'IrisPigment'
    iris_shader = next(n for n in iris_mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    iris_mat.node_tree.links.new(pigment.outputs['Color'], iris_shader.inputs['Base Color'])
    pupil_mat = material('Recessed pupil ' + label, (.0014, .0009, .0005), .27, .05)
    cornea_mat = material('Transparent convex cornea ' + label, (.93, .97, 1.0), .055, 1)
    shader = next(n for n in cornea_mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    shader.inputs['IOR'].default_value = 1.376
    shader.inputs['Alpha'].default_value = .10
    cornea_mat.surface_render_method = 'DITHERED'

    def point(x, z, offset=0):
        return center + right * x + up * z + normal * (math.sqrt(max(.00001, radius*radius-x*x-z*z)) + offset)

    # Keep a spherical sclera around a genuine hole for the recessed iris.
    vertices, faces = [], []
    columns, rows = 112, 64
    for row in range(rows + 1):
        for column in range(columns + 1):
            x = (column / columns - .5) * width
            shape = max(0, 1-(2*x/width)**2)**.85
            z = (row/rows-.5)*height*shape + .04*x
            vertices.append(point(x, z, .001))
    for row in range(rows):
        for column in range(columns):
            x = ((column+.5)/columns-.5)*width
            shape = max(0, 1-(2*x/width)**2)**.85
            z = ((row+.5)/rows-.5)*height*shape + .04*x
            if math.hypot(x, z) < iris_radius * .985:
                continue
            a = row*(columns+1)+column
            faces.append((a, a+1, a+columns+2, a+columns+1))
    sclera = mesh('EyeSclera' + label, vertices, faces, sclera_mat)
    skin(sclera, eye['eye_bone'], rig)

    # Radial fibres are actual shallow relief, with a concave iris bowl.
    vertices, faces, colors = [], [], []
    segments, rings = 192, 20
    for row in range(rings + 1):
        fraction = row/rings
        r = pupil_radius + (iris_radius-pupil_radius)*fraction
        for column in range(segments):
            theta = column/segments*math.tau
            x, z = r*math.cos(theta), r*math.sin(theta)
            grain = math.sin(theta*83+r*310)*.55 + math.sin(theta*137-r*90)*.30
            relief = .0007*grain*math.sin(fraction*math.pi)
            vertices.append(point(x, z, .001-.009*(1-r/iris_radius)**2+relief))
            brightness = (.76+.30*grain) * (.70-.30*math.sin(theta))
            rim = curve(fraction, [(0,.50),(.16,1),(.70,.86),(.91,.55),(1,.28)])
            colors.append((.32*brightness*rim, .15*brightness*rim, .035*brightness*rim, 1))
    for row in range(rings):
        for column in range(segments):
            a = row*segments+column
            b = row*segments+(column+1)%segments
            faces.append((a,a+segments,b+segments,b))
    iris = mesh('EyeIris' + label, vertices, faces, iris_mat)
    attr = iris.data.color_attributes.new(name='IrisPigment', type='FLOAT_COLOR', domain='POINT')
    attr.data.foreach_set('color', np.array(colors, np.float32).ravel())
    iris.data.color_attributes.render_color_index = 0
    skin(iris, eye['eye_bone'], rig)

    # The black pupil is a cup below the iris, including its inner side wall.
    vertices, faces = [], []
    for row in range(13):
        fraction = row/12
        r = pupil_radius*fraction
        for column in range(segments):
            theta = column/segments*math.tau
            offset = -.017+.015*fraction**6
            vertices.append(point(r*math.cos(theta), r*math.sin(theta), offset))
    for row in range(12):
        for column in range(segments):
            a = row*segments+column
            b = row*segments+(column+1)%segments
            faces.append((a,a+segments,b+segments,b))
    pupil = mesh('EyePupil' + label, vertices, faces, pupil_mat)
    skin(pupil, eye['eye_bone'], rig)

    # Separate convex transparent shell, lit by the runtime lights rather than
    # painting fixed white catchlights into an eye texture.
    vertices, faces = [], []
    for row in range(25):
        r = iris_radius*1.02*row/24
        for column in range(segments):
            theta = column/segments*math.tau
            bulge = .012*max(0, 1-(r/(iris_radius*1.02))**2)**1.5
            vertices.append(point(r*math.cos(theta), r*math.sin(theta), .003+bulge))
    for row in range(24):
        for column in range(segments):
            a = row*segments+column
            b = row*segments+(column+1)%segments
            faces.append((a,a+segments,b+segments,b))
    cornea = mesh('EyeCornea' + label, vertices, faces, cornea_mat)
    skin(cornea, eye['eye_bone'], rig)

    return dict(label=label, layers=[o.name for o in (sclera,iris,pupil,cornea)],
                iris_radius=iris_radius, pupil_radius=pupil_radius,
                iris_recess=.009, pupil_recess=.017, cornea_bulge=.012)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scene', type=Path, required=True)
    parser.add_argument('--face-report', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--render', action='store_true')
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(args.scene.resolve()))
    scene = bpy.context.scene
    rig = bpy.data.objects['DitingRig']
    body = next(o for o in scene.objects if o.name.startswith('Diting reconstructed'))
    eyes = json.loads(args.face_report.read_text())['eyes']
    actions = {name: bpy.data.actions[name] for name in ('Idle','Respond','Listen')}
    rig.animation_data.action = None
    clear_pose(rig)
    bpy.context.view_layer.update()
    eye_report = [layered_eye(eye, rig) for eye in eyes]
    # Preserve the stable socket contour; only soften the inner lid pigment.
    for eye in eyes:
        for prefix in ('UpperLid','LowerLid'):
            lid=bpy.data.objects[prefix+eye['label']]
            attr=lid.data.color_attributes['SkinPigment']
            for vertex in lid.data.vertices:
                row=vertex.index//65
                weight=.72*max(0,1-row/3)**2
                color=attr.data[vertex.index].color
                attr.data[vertex.index].color=(*(color[i]*(1-weight)+(.10,.065,.033)[i]*weight for i in range(3)),1)

    # A small orienting flick with a delayed folded-ear response, then a softer
    # second adjustment. All additive curves are zero at both endpoints.
    action = actions['Listen']
    rig.animation_data.action = action
    cached = []
    for frame in range(1,122):
        scene.frame_set(frame)
        cached.append({name: rig.pose.bones[name].rotation_euler.copy() for name in ('EarUpright','EarFolded')})
    ear_audit = []
    for frame, original in enumerate(cached, 1):
        t = (frame-1)/120
        upright = curve(t,[(0,0),(.17,0),(.24,-8),(.29,4),(.35,0),(.42,0),(.49,-5),(.55,2),(.62,0),(1,0)])
        folded = curve(t,[(0,0),(.21,0),(.29,7),(.35,-3),(.41,0),(.47,0),(.55,5),(.61,-2),(.68,0),(1,0)])
        for name, amount in [('EarUpright',upright),('EarFolded',folded)]:
            bone = rig.pose.bones[name]
            bone.rotation_euler = original[name]
            bone.rotation_euler.z += math.radians(amount)
            bone.rotation_euler.y += math.radians(amount*.4)
            bone.keyframe_insert(data_path='rotation_euler', frame=frame, group=name)
        ear_audit.append(dict(frame=frame, upright_additive_degrees=upright, folded_additive_degrees=folded))

    # Check every body frame after the ear edits; the paws remain planted.
    rig.animation_data.action = None
    clear_pose(rig)
    bpy.context.view_layer.update()
    rest = evaluated_positions(body)
    coords = np.array([v.co[:] for v in body.data.vertices])
    feet = coords[:,2] < .20
    edges = np.array([e.vertices[:] for e in body.data.edges])
    lengths = np.linalg.norm(rest[edges[:,0]]-rest[edges[:,1]],axis=1)
    valid = lengths > 1e-4
    audits, occlusion = [], []
    direction = scene.camera.rotation_euler.to_matrix() @ Vector((0,0,-1))
    for name, count in [('Idle',181),('Respond',73),('Listen',121)]:
        rig.animation_data.action = actions[name]
        maximum_paw, maximum_strain = 0, 0
        endpoints = []
        for frame in range(1,count+1):
            scene.frame_set(frame)
            current = evaluated_positions(body)
            assert np.isfinite(current).all()
            maximum_paw = max(maximum_paw, float(np.linalg.norm(current[feet]-rest[feet],axis=1).max()))
            ratio = np.linalg.norm(current[edges[:,0]]-current[edges[:,1]],axis=1)[valid]/lengths[valid]
            maximum_strain = max(maximum_strain, float(np.percentile(ratio,99)))
            if frame in (1,count): endpoints.append(current.copy())
        endpoint_error = float(np.linalg.norm(endpoints[0]-endpoints[1],axis=1).max())
        assert maximum_paw < 1e-4 and endpoint_error < 1e-4 and maximum_strain < 1.27
        audits.append(dict(clip=name,frames=count,paw_maximum=maximum_paw,endpoint_error=endpoint_error,edge_ratio_p99_maximum=maximum_strain))
        frame = {'Idle':34,'Respond':11,'Listen':95}[name]
        scene.frame_set(frame)
        graph = bpy.context.evaluated_depsgraph_get()
        for eye in eyes:
            label = eye['label']
            # Recessed pupil side walls can also lie behind the socket/liner.
            trees = [BVHTree.FromObject(bpy.data.objects[prefix+label],graph)
                     for prefix in ('UpperLid','LowerLid','UpperLiner','LowerLiner')]
            trees.append(BVHTree.FromObject(body,graph))
            obj = bpy.data.objects['EyePupil'+label]
            evaluated = obj.evaluated_get(graph)
            data = evaluated.to_mesh()
            covered = sum(any((hit:=tree.ray_cast(vertex.co-direction,direction,1.001)[3]) is not None and hit < .9999 for tree in trees) for vertex in data.vertices)
            item = dict(clip=name,frame=frame,eye=label,total=len(data.vertices),covered=covered)
            occlusion.append(item)
            evaluated.to_mesh_clear()
            assert item['total'] == covered, item

    rig.animation_data.action = actions['Idle']
    scene.frame_set(1)
    shutil.copyfile(__file__,out/'eye_source.py')
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'diting-eyes-v7.blend'))
    bpy.ops.object.select_all(action='DESELECT')
    for obj in scene.objects:
        if obj in (rig,body) or obj.get('facial_geometry'): obj.select_set(True)
    bpy.context.view_layer.objects.active = rig
    asset = out/'DitingEyesV7.glb'
    bpy.ops.export_scene.gltf(filepath=str(asset),use_selection=True,export_format='GLB',export_animations=True,
                             export_animation_mode='ACTIONS',export_force_sampling=True,export_skins=True,export_def_bones=True)
    report = dict(bones=len(rig.data.bones),eyes=eye_report,deformation_audit=audits,closed_pupil_checks=occlusion,
                  ear_motion=ear_audit,sha256=hashlib.sha256(asset.read_bytes()).hexdigest())
    (out/'eye-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    if args.render:
        camera = scene.camera
        camera.location = (-3.6,-7.5,3.6)
        target = Vector((.40,-.95,3.02))
        camera.rotation_euler = (target-camera.location).to_track_quat('-Z','Y').to_euler()
        camera.data.ortho_scale = 1.55
        scene.render.resolution_x = 1000
        scene.render.resolution_y = 760
        scene.cycles.samples = 32
        for frame,label in [(1,'open'),(34,'closed')]:
            scene.frame_set(frame)
            scene.render.filepath = str(out/f'eye-{label}.png')
            bpy.ops.render.render(write_still=True)
    print(json.dumps(dict(passed=True,bones=report['bones'],eyes=eye_report,body_audit=audits)),flush=True)


if __name__ == '__main__':
    main()
