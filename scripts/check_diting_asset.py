"""Verify and render the exported static GLB after importing it back to Blender."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Vector


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--asset',type=Path,required=True)
    p.add_argument('--studio',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    data=args.asset.read_bytes()
    assert data[:4]==b'glTF'
    size,kind=struct.unpack_from('<II',data,12)
    assert kind==0x4E4F534A
    gltf=json.loads(data[20:20+size])
    assert len(gltf.get('images',[]))==1
    assert not gltf.get('skins') and not gltf.get('animations')
    assert all('uri' not in image and 'bufferView' in image for image in gltf['images'])
    assert all('uri' not in buffer for buffer in gltf['buffers'])
    bpy.ops.wm.open_mainfile(filepath=str(args.studio.resolve()))
    for obj in list(bpy.context.scene.objects):
        if obj.name.startswith('Diting reconstructed'):bpy.data.objects.remove(obj,do_unlink=True)
    bpy.ops.import_scene.gltf(filepath=str(args.asset.resolve()))
    imported=[obj for obj in bpy.context.selected_objects if obj.type=='MESH']
    assert len(imported)==1
    obj=imported[0]
    coordinates=np.empty(len(obj.data.vertices)*3,np.float32)
    obj.data.vertices.foreach_get('co',coordinates)
    assert np.isfinite(coordinates).all()
    spans=np.ptp(coordinates.reshape(-1,3),axis=0)
    assert (spans>.2).all()
    uv=np.empty(len(obj.data.uv_layers.active.data)*2,np.float32)
    obj.data.uv_layers.active.data.foreach_get('uv',uv)
    assert np.isfinite(uv).all()
    bm=bmesh.new();bm.from_mesh(obj.data)
    # glTF splits vertices at UV and normal seams. Weld positional duplicates
    # solely for the topology audit, leaving the actual imported object intact.
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.000001)
    boundary=sum(e.is_boundary for e in bm.edges)
    nonmanifold=sum(not e.is_manifold for e in bm.edges)
    bm.free()
    scene=bpy.context.scene
    scene.cycles.samples=24
    scene.render.resolution_x=840;scene.render.resolution_y=940
    camera=scene.camera
    for name,position in {'hero':(-5,-8,2.6),'back':(0,9,2.6)}.items():
        camera.location=position
        camera.rotation_euler=(Vector((0,0,1.9))-camera.location).to_track_quat('-Z','Y').to_euler()
        scene.render.filepath=str(out/f'glb-{name}.png')
        bpy.ops.render.render(write_still=True)
    report={'glb_sha256':hashlib.sha256(data).hexdigest(),'glb_bytes':len(data),
            'embedded_images':len(gltf['images']),'self_contained':True,
            'mesh_objects':len(imported),'imported_vertices':len(obj.data.vertices),
            'triangles':len(obj.data.polygons),'finite_positions':True,'finite_uv':True,
            'xyz_span':spans.tolist(),'boundary_edges_after_positional_weld':boundary,
            'nonmanifold_edges_after_positional_weld':nonmanifold,
            'rigged':False,'animated':False,'likeness_final_approved':False,
            'rendered_after_glb_reimport':True}
    (out/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')


if __name__=='__main__':main()
