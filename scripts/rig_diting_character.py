"""Blender: first seated Diting control rig, skin weights and three bone clips.

Keeps the existing mesh, UV and material. Regional weights are intended for
small seated motions; this is not a finished quadruped locomotion rig.
"""
import argparse
import json
import math
from pathlib import Path
import shutil
import struct
import sys

import bpy
import bmesh
from mathutils import Vector
import numpy as np


def smooth(values, low, high):
    x=np.clip((values-low)/(high-low),0,1)
    return x*x*(3-2*x)


def create_rig(obj, expressive=False):
    data=bpy.data.armatures.new('Diting seated skeleton')
    rig=bpy.data.objects.new('DitingRig',data)
    bpy.context.collection.objects.link(rig)
    bpy.context.view_layer.objects.active=rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    controls=[
        ('Root',(0,0,.1),None),
        ('Pelvis',(.1,.2,.55),'Root'),
        ('Chest',(.25,-.25,1.45),'Pelvis'),
        ('Neck',(.3,-.55,2.22),'Chest'),
        ('Head',(.35,-.65,2.6),'Neck'),
        ('EarUpright',(-.25,-.65,3.22),'Head'),
        ('EarFolded',(1.0,-.55,3.03),'Head'),
        ('TailBase',(-.7,.65,.45),'Pelvis'),
        ('TailMid',(-1.05,1.2,1.03),'TailBase'),
        ('TailTip',(-1.04,1.15,1.6),'TailMid'),
        ('PawFrontL',(-.25,-1.2,.1),'Root'),
        ('PawFrontR',(.95,-1.2,.1),'Root'),
        ('PawRearL',(-.55,.7,.1),'Root'),
        ('PawRearR',(.85,.7,.1),'Root'),
    ]
    for name,head,parent in controls:
        bone=data.edit_bones.new(name)
        bone.head=head
        bone.tail=Vector(head)+Vector((0,0,.28))
        if parent:bone.parent=data.edit_bones[parent]
        bone.use_connect=False
    bpy.ops.object.mode_set(mode='OBJECT')
    rig.show_in_front=True
    for bone in rig.pose.bones:bone.rotation_mode='XYZ'
    coords=np.empty(len(obj.data.vertices)*3,np.float32)
    obj.data.vertices.foreach_get('co',coords)
    coords=coords.reshape(-1,3)
    x,y,z=coords.T
    names=[c[0] for c in controls]
    weights=np.zeros((len(coords),len(names)),np.float32)
    idx={name:i for i,name in enumerate(names)}
    head=smooth(z,2.35,2.78)
    if expressive:
        # Keep the muzzle and facial surface rigid with the skull during large
        # nods; distribute bending through the back of the mane and neck.
        face=smooth(z,2.28,2.52)*smooth(-y,.78,1.12)
        head=np.maximum(smooth(z,1.95,2.90),face)
    neck=np.maximum(smooth(z,2.04,2.65)-head,0)*.65
    neck=np.minimum(neck,1-head)
    chest=smooth(z,.45,1.65)*(1-head-neck)*.85
    if expressive:
        # In the neck, blend only adjacent spine controls. Retaining a residual
        # pelvis influence here pins the mane while the skull turns and stretches
        # it badly. The wide partition transfers from chest to neck to skull.
        neck=smooth(z,1.25,2.10)*(1-head)
        chest=smooth(z,.45,1.65)*(1-head-neck)
    weights[:,idx['Head']]=head
    weights[:,idx['Neck']]=neck
    weights[:,idx['Chest']]=chest
    weights[:,idx['Pelvis']]=1-head-neck-chest
    # Separate the curled tail from the seated body and back mane.
    tail=smooth(-x,.55,.98)*smooth(y,.30,.90)*(1-smooth(z,1.92,2.2))*smooth(z,.26,.62)
    if expressive:
        # The tail curls alongside the torso at neck height. A height/box field
        # assigns neck weights to its inner surface. Follow mesh connectivity
        # above the low tail root instead, keeping the entire tuft on tail bones.
        bm=bmesh.new();bm.from_mesh(obj.data);bm.verts.ensure_lookup_table()
        seed=int(np.argmin(np.sum((coords-np.array((-1.05,1.25,1.7)))**2,axis=1)))
        for cutoff in (.62,.85,1.05,1.25,1.45):
            selected=np.zeros(len(coords),bool);stack=[seed]
            while stack:
                i=stack.pop()
                if selected[i] or coords[i,2]<cutoff:continue
                selected[i]=True
                for edge in bm.verts[i].link_edges:
                    other=edge.other_vert(bm.verts[i]).index
                    if not selected[other] and coords[other,2]>=cutoff:stack.append(other)
            if 500<int(selected.sum())<len(coords)*.40:break
        bm.free()
        assert 500<int(selected.sum())<len(coords)*.40,('Ambiguous tail component',int(selected.sum()))
        edges=np.empty(len(obj.data.edges)*2,np.int32);obj.data.edges.foreach_get('vertices',edges);edges=edges.reshape(-1,2)
        a,b=edges.T
        degree=np.maximum(np.bincount(edges.ravel(),minlength=len(coords)),1)
        fixed_zero=((x>-.30)|(y<.15)|(z>2.2)|(z<.35))&~selected
        tail=tail.astype(np.float64);tail[selected]=1;tail[fixed_zero]=0
        # Harmonic surface diffusion extends the isolated tuft seed down its
        # actual branch. It avoids assigning neck influence simply by height.
        for _ in range(1600):
            next_tail=(np.bincount(a,weights=tail[b],minlength=len(coords))+np.bincount(b,weights=tail[a],minlength=len(coords)))/degree
            next_tail[selected]=1;next_tail[fixed_zero]=0
            change=np.max(np.abs(next_tail-tail));tail=next_tail
            if change<1e-5:break
        tail=tail.astype(np.float32)
        rig['tail_topology_vertices']=int(selected.sum())
    weights*=1-tail[:,None]
    mid=smooth(z,.58,1.15)
    tip=smooth(z,1.2,1.78)
    weights[:,idx['TailBase']]=tail*(1-mid)
    weights[:,idx['TailMid']]=tail*mid*(1-tip)
    weights[:,idx['TailTip']]=tail*mid*tip
    ear_l=smooth(z,3.22,3.58)*(1-smooth(x,-.3,.08))*smooth(-y,.1,.7)
    ear_r=np.exp(-((x-1.03)/.30)**2-((y+.55)/.50)**2)*smooth(z,3.00,3.40)*.85
    ears=np.clip(ear_l+ear_r,0,1)
    weights*=1-ears[:,None]
    weights[:,idx['EarUpright']]=ear_l
    weights[:,idx['EarFolded']]=ear_r
    # Paw influences fade into the body above the ankles; all paw bones stay fixed.
    planted=1-smooth(z,.25,.8)
    paw_heads=np.array([c[1][:2] for c in controls if c[0].startswith('Paw')])
    distances=np.sum((coords[:,None,:2]-paw_heads[None,:,:])**2,axis=2)
    nearest=np.argmin(distances,axis=1)
    weights*=1-planted[:,None]
    for i,name in enumerate(('PawFrontL','PawFrontR','PawRearL','PawRearR')):
        weights[:,idx[name]]+=planted*(nearest==i)
    # Keep no more than four normalized joint influences for the runtime skin.
    best=np.argsort(weights,axis=1)[:,-4:]
    keep=np.zeros_like(weights,dtype=bool)
    np.put_along_axis(keep,best,True,axis=1)
    weights[~keep]=0
    weights/=weights.sum(1)[:,None]
    assert np.isfinite(weights).all() and np.allclose(weights.sum(1),1,atol=1e-5)
    for name in names:obj.vertex_groups.new(name=name)
    # Quantization bounds Blender Python calls and matches glTF's practical precision.
    for name,i in idx.items():
        quantized=np.rint(weights[:,i]*1024).astype(np.int32)
        for level in np.unique(quantized[quantized>0]):
            vertices=np.flatnonzero(quantized==level).tolist()
            obj.vertex_groups[name].add(vertices,float(level)/1024,'REPLACE')
    modifier=obj.modifiers.new('Diting skeletal skin','ARMATURE')
    modifier.object=rig
    modifier.use_deform_preserve_volume=False  # Match the glTF linear skinning runtime.
    obj.parent=rig
    return rig,coords,weights,names


def clear_pose(rig):
    for bone in rig.pose.bones:
        bone.location=(0,0,0);bone.rotation_euler=(0,0,0);bone.scale=(1,1,1)


def create_action(rig,name,frames):
    action=bpy.data.actions.new(name)
    rig.animation_data_create();rig.animation_data.action=action
    animated=('Chest','Neck','Head','EarUpright','EarFolded','TailBase','TailMid','TailTip')
    for frame in sorted(set(list(range(1,frames+1,4))+[frames])):
        clear_pose(rig)
        t=(frame-1)/(frames-1)
        if name=='Idle':
            wave=math.sin(2*math.pi*t)
            rig.pose.bones['Chest'].scale=(1+.006*wave,1+.004*wave,1+.008*wave)
            rig.pose.bones['Neck'].rotation_euler.x=math.radians(.12)*wave
            rig.pose.bones['Head'].rotation_euler.x=math.radians(.32)*wave
            for bone,amplitude in [('TailBase',.65),('TailMid',1.35),('TailTip',2.1)]:
                rig.pose.bones[bone].rotation_euler.y=math.radians(amplitude)*wave
            rig.pose.bones['EarUpright'].rotation_euler.z=math.radians(.5)*wave
        elif name=='Respond':
            nod=math.sin(math.pi*t)**2
            rig.pose.bones['Neck'].rotation_euler.x=math.radians(1.2)*nod
            rig.pose.bones['Head'].rotation_euler.x=math.radians(3.0)*nod
            rig.pose.bones['EarUpright'].rotation_euler.z=math.radians(-1.5)*nod
        else:
            listen=math.sin(math.pi*t)**2
            rig.pose.bones['Head'].rotation_euler.y=math.radians(6)*listen
            rig.pose.bones['Head'].rotation_euler.z=math.radians(-1.7)*listen
            rig.pose.bones['Neck'].rotation_euler.y=math.radians(1.0)*listen
            rig.pose.bones['EarUpright'].rotation_euler.x=math.radians(-2)*listen
            rig.pose.bones['EarFolded'].rotation_euler.z=math.radians(1.0)*listen
        for bone_name in animated:
            bone=rig.pose.bones[bone_name]
            for channel in ('rotation_euler','scale','location'):
                bone.keyframe_insert(data_path=channel,frame=frame,group=bone_name)
    action.use_fake_user=True
    return action


def evaluated_positions(obj):
    evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh=evaluated.to_mesh()
    result=np.empty(len(mesh.vertices)*3,np.float32)
    mesh.vertices.foreach_get('co',result)
    evaluated.to_mesh_clear()
    return result.reshape(-1,3)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--scene',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(args.scene.resolve()))
    obj=next(o for o in bpy.context.scene.objects if o.name.startswith('Diting reconstructed'))
    bpy.ops.object.select_all(action='DESELECT')
    rig,rest,weights,bones=create_rig(obj)
    scene=bpy.context.scene;scene.render.fps=30
    clips={name:create_action(rig,name,frames) for name,frames in [('Idle',145),('Respond',43),('Listen',97)]}
    foot=rest[:,2]<.20
    edges=np.empty(len(obj.data.edges)*2,np.int32)
    obj.data.edges.foreach_get('vertices',edges);edges=edges.reshape(-1,2)
    rest_lengths=np.linalg.norm(rest[edges[:,0]]-rest[edges[:,1]],axis=1)
    valid_edges=rest_lengths>1e-4
    audit=[]
    for name,action in clips.items():
        rig.animation_data.action=action
        frames=int(action.frame_range[1])
        starts=[]
        for frame in (1,frames//4,frames//2,3*frames//4,frames):
            scene.frame_set(frame);bpy.context.view_layer.update()
            current=evaluated_positions(obj)
            assert np.isfinite(current).all()
            displacement=np.linalg.norm(current-rest,axis=1)
            ratios=np.linalg.norm(current[edges[:,0]]-current[edges[:,1]],axis=1)[valid_edges]/rest_lengths[valid_edges]
            if frame in (1,frames):starts.append(current)
            audit.append({'clip':name,'frame':frame,'max_displacement':float(displacement.max()),
                          'max_planted_paw_displacement':float(displacement[foot].max()),
                          'edge_length_ratio_p01_p99':np.percentile(ratios,[1,99]).tolist()})
            assert displacement[foot].max()<1e-4,'Planted paws moved'
            assert np.percentile(ratios,99)<1.25,'Excessive local stretching'
        assert np.max(np.linalg.norm(starts[0]-starts[1],axis=1))<1e-4,'Clip does not return to rest'
    # NLA tracks preserve all three named clips in the interchange file.
    rig.animation_data.action=None
    for name,action in clips.items():
        track=rig.animation_data.nla_tracks.new();track.name=name
        strip=track.strips.new(name,1,action);strip.name=name;track.mute=True
    rig.animation_data.action=clips['Idle']
    scene.frame_start=1;scene.frame_end=145;scene.frame_set(1)
    source=bpy.data.texts.new('rig_source.py');source.write(Path(__file__).read_text(encoding='utf-8'))
    shutil.copyfile(__file__,out/'rig_source.py')
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'diting-rig-v4.blend'))
    bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);rig.select_set(True)
    bpy.context.view_layer.objects.active=rig
    bpy.ops.export_scene.gltf(filepath=str(out/'DitingRigV4.glb'),use_selection=True,export_format='GLB',
                             export_animations=True,export_animation_mode='ACTIONS',
                             export_force_sampling=True,export_skins=True,export_def_bones=True)
    data=(out/'DitingRigV4.glb').read_bytes();length=struct.unpack_from('<I',data,12)[0]
    gltf=json.loads(data[20:20+length])
    assert gltf.get('skins') and len(gltf.get('animations',[]))==3
    scene.render.resolution_x=840;scene.render.resolution_y=940;scene.cycles.samples=20
    for name,frame in [('Idle',37),('Respond',22),('Listen',49)]:
        rig.animation_data.action=clips[name];scene.frame_set(frame)
        scene.render.filepath=str(out/f'{name.lower()}-pose.png');bpy.ops.render.render(write_still=True)
    (out/'rig-report.json').write_text(json.dumps({'bones':bones,'bone_count':len(bones),
        'clips':[a.get('name') for a in gltf['animations']], 'fps':30,'vertices':len(rest),
        'triangles':len(obj.data.polygons),'maximum_influences':4,'all_vertices_weighted':True,
        'unchanged_rest_mesh_and_uv':True,'pose_audit':audit,'skin_count':len(gltf['skins']),
        'glb_bytes':len(data),'purpose':'first seated motion rig, not locomotion or facial rig'},indent=2),encoding='utf-8')


if __name__=='__main__':main()
