"""Blender expressive seated acting pass with anticipation, follow-through and lids.

Keeps v4 available. Builds named skeletal clips and audits planted paws and body
strain before exporting; larger acting is not a claim of finished feature-film art.
"""
import argparse
import json
import math
from pathlib import Path
import shutil
import struct
import sys

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parent))
from rig_diting_character import create_rig,clear_pose,evaluated_positions


def curve(t,keys):
    if t<=keys[0][0]:return keys[0][1]
    for (a,x),(b,y) in zip(keys,keys[1:]):
        if t<=b:
            u=(t-a)/(b-a);u=u*u*(3-2*u)
            return x+(y-x)*u
    return keys[-1][1]


def blink(seconds,center):
    return curve(seconds,[(center-.08,0),(center,1),(center+.035,1),(center+.15,0)])


def pose(rig,name,t,seconds,eyes):
    clear_pose(rig)
    b=rig.pose.bones
    if name=='Idle':
        wave=math.sin(2*math.pi*t)
        b['Chest'].scale=(1+.018*wave,1+.012*wave,1+.022*wave)
        b['Neck'].rotation_euler.x=math.radians(.6)*wave
        b['Head'].rotation_euler.x=math.radians(1.6)*wave
        b['Head'].rotation_euler.y=math.radians(2.0)*math.sin(2*math.pi*t)
        for bone,amplitude in [('TailBase',4),('TailMid',7),('TailTip',10)]:
            b[bone].rotation_euler.y=math.radians(amplitude)*wave
        flick=curve(t,[(0,0),(.25,0),(.29,-5),(.34,2),(.4,0),(1,0)])
        b['EarUpright'].rotation_euler.z=math.radians(flick)
        closure=max(blink(seconds,1.1),blink(seconds,4.5))
        gaze=math.radians(2)*wave
    elif name=='Respond':
        pitch=curve(t,[(0,0),(.13,-7),(.32,13),(.42,16),(.60,-4.5),(.75,3),(.91,0),(1,0)])
        b['Head'].rotation_euler.x=math.radians(pitch*.62)
        b['Neck'].rotation_euler.x=math.radians(pitch*.30)
        b['Chest'].rotation_euler.x=math.radians(pitch*.36)
        b['Head'].rotation_euler.z=math.radians(curve(t,[(0,0),(.15,-1),(.42,3),(.7,-1),(1,0)]))
        b['Chest'].location.z=curve(t,[(0,0),(.15,-.012),(.42,.028),(.7,-.006),(1,0)])
        lag=curve(t,[(0,0),(.17,5),(.45,-9),(.65,4),(.84,-1),(1,0)])
        b['EarUpright'].rotation_euler.x=math.radians(lag)
        b['EarFolded'].rotation_euler.z=math.radians(lag*.45)
        tail=curve(t,[(0,0),(.18,0),(.46,1),(.7,-.3),(1,0)])
        for bone,amplitude in [('TailBase',2),('TailMid',5),('TailTip',8)]:b[bone].rotation_euler.y=math.radians(amplitude)*tail
        closure=blink(seconds,.32)
        gaze=math.radians(curve(t,[(0,0),(.13,-4),(.37,3),(.7,0),(1,0)]))
    else:
        yaw=curve(t,[(0,0),(.10,-4),(.27,23),(.42,26),(.61,21),(.77,-6),(.93,1.5),(1,0)])
        b['Head'].rotation_euler.y=math.radians(yaw*.26)
        b['Neck'].rotation_euler.y=math.radians(yaw*.55)
        b['Chest'].rotation_euler.y=math.radians(yaw*.54)
        tilt=curve(t,[(0,0),(.12,1),(.33,-10),(.57,-9),(.78,2),(1,0)])
        b['Head'].rotation_euler.z=math.radians(tilt*.3)
        b['Neck'].rotation_euler.z=math.radians(tilt*.4)
        b['Chest'].rotation_euler.z=math.radians(tilt*.3)
        b['Head'].rotation_euler.x=math.radians(curve(t,[(0,0),(.3,-3),(.57,-2),(.8,1),(1,0)]))
        b['EarUpright'].rotation_euler.x=math.radians(curve(t,[(0,0),(.12,-11),(.5,-7),(.76,4),(1,0)]))
        b['EarFolded'].rotation_euler.z=math.radians(tilt*.6)
        b['TailMid'].rotation_euler.y=math.radians(curve(t,[(0,0),(.35,-7),(.62,3),(1,0)]))
        b['TailTip'].rotation_euler.y=b['TailMid'].rotation_euler.y*1.5
        closure=blink(seconds,3.12)
        gaze=math.radians(curve(t,[(0,0),(.10,10),(.32,3),(.57,-5),(.8,1),(1,0)]))
    for eye in eyes:
        b[eye['eye_bone']].rotation_euler.y=gaze*.30
        b[eye['lid_bone']].location.y=-eye['opening_height']*closure
        b[eye['bulge_bone']].location.z=.18*closure


def add_face_rig(rig,eyes,body):
    bpy.context.view_layer.objects.active=rig
    bpy.ops.object.mode_set(mode='EDIT')
    for eye in eyes:
        for name in (eye['eye_bone'],eye['lid_bone'],eye['bulge_bone']):
            bone=rig.data.edit_bones.new(name)
            bone.head=eye['center'];bone.tail=Vector(eye['center'])+Vector((0,0,.16))
            bone.parent=rig.data.edit_bones['Head'];bone.align_roll(Vector(eye['normal']))
    bpy.ops.object.mode_set(mode='OBJECT')
    rig.data.bones['Neck'].inherit_scale='NONE'
    for bone in rig.pose.bones:bone.rotation_mode='XYZ'
    for obj in list(bpy.context.scene.objects):
        if obj==body or obj.type!='MESH' or not obj.get('facial_geometry'):continue
        modifier=obj.modifiers.new('Facial skin','ARMATURE');modifier.object=rig
        modifier.use_deform_preserve_volume=False;obj.parent=rig


def check_closed_pupils(rig,clips,eyes):
    """A moving lid must actually cover the pupil in the approved hero view."""
    scene=bpy.context.scene
    direction=scene.camera.rotation_euler.to_matrix()@Vector((0,0,-1))
    checks=[]
    for clip,frame in [('Idle',34),('Respond',11),('Listen',95)]:
        rig.animation_data.action=clips[clip];scene.frame_set(frame)
        graph=bpy.context.evaluated_depsgraph_get()
        for eye in eyes:
            label=eye['label'];obj=bpy.data.objects['EyeSurface'+label]
            evaluated=obj.evaluated_get(graph);data=evaluated.to_mesh()
            pigment=obj.data.color_attributes['IrisPigment']
            trees=[BVHTree.FromObject(bpy.data.objects[prefix+label],graph) for prefix in ('UpperLid','LowerLid')]
            total=0;covered=0
            for vertex in data.vertices:
                if pigment.data[vertex.index].color[0]>.01:continue
                total+=1
                distances=[tree.ray_cast(vertex.co-direction,direction,1.001)[3] for tree in trees]
                if any(d is not None and d<.9999 for d in distances):covered+=1
            evaluated.to_mesh_clear()
            item={'clip':clip,'frame':frame,'eye':label,'pupil_vertices':total,'covered':covered}
            checks.append(item)
            assert total>0 and covered==total,('Pupil leaks through a closed lid',item)
    return checks


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--scene',type=Path,required=True);p.add_argument('--face-report',type=Path);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(args.scene.resolve()))
    body=next(o for o in bpy.context.scene.objects if o.name.startswith('Diting reconstructed'))
    bpy.ops.object.select_all(action='DESELECT')
    rig,rest,weights,bones=create_rig(body,expressive=True)
    eyes=json.loads(args.face_report.read_text())['eyes'] if args.face_report else []
    add_face_rig(rig,eyes,body)
    scene=bpy.context.scene;scene.render.fps=30
    clips={}
    for name,frames in [('Idle',181),('Respond',73),('Listen',121)]:
        action=bpy.data.actions.new(name);rig.animation_data_create();rig.animation_data.action=action
        for frame in range(1,frames+1):
            pose(rig,name,(frame-1)/(frames-1),(frame-1)/30,eyes)
            for bone in rig.pose.bones:
                if bone.name.startswith('Paw') or bone.name in ('Root','Pelvis'):continue
                for channel in ('rotation_euler','location','scale'):bone.keyframe_insert(data_path=channel,frame=frame,group=bone.name)
        action.use_fake_user=True;clips[name]=action
    edges=np.empty(len(body.data.edges)*2,np.int32);body.data.edges.foreach_get('vertices',edges);edges=edges.reshape(-1,2)
    lengths=np.linalg.norm(rest[edges[:,0]]-rest[edges[:,1]],axis=1);valid=lengths>1e-4
    foot=rest[:,2]<.20;audit=[]
    for name,action in clips.items():
        rig.animation_data.action=action;last=int(action.frame_range[1]);endpoint=[]
        for frame in sorted(set([1,last,int(last*.13),int(last*.27),int(last*.42),int(last*.61),int(last*.77),last//2])):
            scene.frame_set(frame);bpy.context.view_layer.update();current=evaluated_positions(body)
            delta=np.linalg.norm(current-rest,axis=1)
            ratios=np.linalg.norm(current[edges[:,0]]-current[edges[:,1]],axis=1)[valid]/lengths[valid]
            item={'clip':name,'frame':frame,'maximum_displacement':float(delta.max()),'planted_paw_maximum_displacement':float(delta[foot].max()),
                  'edge_ratio_p01_p99':np.percentile(ratios,[1,99]).tolist(),
                  'head_orientation_degrees':math.degrees(rig.pose.bones['Head'].matrix.to_quaternion().rotation_difference(rig.data.bones['Head'].matrix_local.to_quaternion()).angle)}
            high=ratios>np.percentile(ratios,99)
            centers=(rest[edges[valid,0]]+rest[edges[valid,1]])*.5
            if high.any():item['strained_edge_median_xyz']=np.median(centers[high],axis=0).tolist()
            audit.append(item)
            assert np.isfinite(current).all();assert delta[foot].max()<1e-4,item
            if frame in (1,last):endpoint.append(current)
        assert np.max(np.linalg.norm(endpoint[0]-endpoint[-1],axis=1))<1e-4,'Endpoint mismatch'
    # Record strain before deciding whether a candidate is suitable to integrate.
    (out/'deformation-audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
    assert max(item['edge_ratio_p01_p99'][1] for item in audit)<1.25,'Large motion exceeds local strain guard; revise weights'
    blink_checks=check_closed_pupils(rig,clips,eyes)
    rig.animation_data.action=None
    for name,action in clips.items():
        track=rig.animation_data.nla_tracks.new();track.name=name;track.strips.new(name,1,action);track.mute=True
    rig.animation_data.action=clips['Idle'];scene.frame_start=1;scene.frame_end=181;scene.frame_set(1)
    source=bpy.data.texts.new('expressive_source.py');source.write(Path(__file__).read_text(encoding='utf-8'))
    shutil.copyfile(__file__,out/'expressive_source.py')
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'diting-expressive-v5.blend'))
    bpy.ops.object.select_all(action='DESELECT')
    for obj in bpy.context.scene.objects:
        if obj==rig or obj==body or obj.get('facial_geometry'):obj.select_set(True)
    bpy.context.view_layer.objects.active=rig
    bpy.ops.export_scene.gltf(filepath=str(out/'DitingExpressiveV5.glb'),use_selection=True,export_format='GLB',
                             export_animations=True,export_animation_mode='ACTIONS',export_force_sampling=True,export_skins=True,export_def_bones=True)
    data=(out/'DitingExpressiveV5.glb').read_bytes();size=struct.unpack_from('<I',data,12)[0];gltf=json.loads(data[20:20+size])
    assert len(gltf.get('animations',[]))==3 and gltf.get('skins')
    (out/'motion-report.json').write_text(json.dumps({'bone_count':len(rig.data.bones),'clips':[a['name'] for a in gltf['animations']],
        'facial_eyes':len(eyes),'new_eyelid_geometry':bool(eyes),'spine_pitch_nominal_peak_degrees':16*(.62+.30+.36),'spine_yaw_nominal_peak_degrees':26*(.26+.55+.54),
        'sampled_head_orientation_peak_degrees':{name:max(i['head_orientation_degrees'] for i in audit if i['clip']==name) for name in clips},
        'closed_pupil_checks':blink_checks,
        'glb_bytes':len(data),'skin_count':len(gltf['skins']),'frames_per_second':30,'deformation_audit':audit,
        'quality_level':'expressive prototype; not a finished film-quality asset'},indent=2),encoding='utf-8')
    scene.render.resolution_x=840;scene.render.resolution_y=940;scene.cycles.samples=20
    for name,frame,label in [('Idle',34,'blink'),('Respond',31,'respond'),('Listen',51,'listen')]:
        rig.animation_data.action=clips[name];scene.frame_set(frame);scene.render.filepath=str(out/f'{label}-pose.png');bpy.ops.render.render(write_still=True)


if __name__=='__main__':main()
