"""Blender multiview projection, UV baking, and static GLB material study.

Preserves the approved primary texture. Supplemental views fill surfaces that
the primary reference does not see. These are static candidates, not a rig.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import time

import bpy
from mathutils import Vector
import numpy as np

TARGET = Vector((0, 0, 1.9))
CAMERAS = {'hero':(-5,-8,2.6), 'angle':(-3.2,-8,2.6),
           'front':(0,-9,2.6), 'left':(-9,0,2.6), 'right':(9,0,2.6), 'back':(0,9,2.6)}


def camera_view(scene, name):
    cam = scene.camera
    cam.location = CAMERAS[name]
    cam.rotation_euler = (TARGET-cam.location).to_track_quat('-Z','Y').to_euler()
    bpy.context.view_layer.update()


def render_views(scene, out, names):
    scene.render.resolution_x = 840
    scene.render.resolution_y = 940
    scene.render.resolution_percentage = 100
    scene.cycles.samples = 24
    for name in names:
        camera_view(scene, name)
        scene.render.filepath = str(out / f'{name}.png')
        bpy.ops.render.render(write_still=True)
    camera_view(scene, 'hero')


def image_data(path):
    image = bpy.data.images.load(str(path.resolve()), check_existing=True)
    width,height = image.size
    pixels = np.empty(width*height*4, np.float32)
    image.pixels.foreach_get(pixels)
    pixels = pixels.reshape(height,width,4)
    yy,xx = np.where(pixels[:,:,3]>.5)
    low = np.array((xx.min()/width, yy.min()/height))
    high = np.array(((xx.max()+1)/width, (yy.max()+1)/height))
    image.pack()
    return image,pixels,low,high


def repair_projection_alpha(obj):
    """Composite transparent projection borders over ivory instead of black."""
    fallback=obj.data.color_attributes.get('UnseenSurfaceFallback')
    if fallback:
        values=np.empty((len(fallback.data),4),np.float32)
        values[:]=(.62,.54,.40,1)
        fallback.data.foreach_set('color',values.ravel())
    material=obj.data.materials[0]
    nodes,links=material.node_tree.nodes,material.node_tree.links
    base=nodes.new('ShaderNodeVertexColor');base.layer_name='UnseenSurfaceFallback'
    for tex in list(nodes):
        if tex.type!='TEX_IMAGE':continue
        existing=list(tex.outputs['Color'].links)
        if not existing:continue
        mix=nodes.new('ShaderNodeMixRGB');mix.blend_type='MIX'
        links.new(base.outputs['Color'],mix.inputs[1])
        links.new(tex.outputs['Alpha'],mix.inputs[0])
        links.new(tex.outputs['Color'],mix.inputs[2])
        for link in existing:links.new(mix.outputs[0],link.to_socket)


def visibility(projected, depth, tolerance=.028):
    low, high = projected.min(0), projected.max(0)
    coords = np.clip((projected-low)/(high-low)*1023,0,1023).astype(np.int32)
    z = np.full((1024,1024),-1e6,np.float32)
    np.maximum.at(z, (coords[:,1],coords[:,0]),depth)
    expanded = z.copy()
    for y in range(-1,2):
        for x in range(-1,2):
            expanded = np.maximum(expanded,np.roll(np.roll(z,y,axis=0),x,axis=1))
    return depth >= expanded[coords[:,1],coords[:,0]]-tolerance


def build_projection(obj, scene, reference, materials, out):
    vertices = np.empty(len(obj.data.vertices)*3,np.float32)
    normals = np.empty_like(vertices)
    obj.data.vertices.foreach_get('co',vertices)
    obj.data.vertices.foreach_get('normal',normals)
    vertices,normals = vertices.reshape(-1,3),normals.reshape(-1,3)
    loops = np.empty(len(obj.data.loops),np.int32)
    obj.data.loops.foreach_get('vertex_index',loops)
    original_uv = np.empty(len(loops)*2,np.float32)
    obj.data.uv_layers.active.data.foreach_get('uv',original_uv)
    original_vertex_uv = np.zeros((len(vertices),2),np.float32)
    original_vertex_uv[loops] = original_uv.reshape(-1,2)
    scores, textures, uv_names, stats = [],[],[],[]
    for index,name in enumerate(('hero','left','right','back')):
        camera_view(scene,name)
        basis = scene.camera.rotation_euler.to_matrix()
        right,up = np.array(basis@Vector((1,0,0))),np.array(basis@Vector((0,1,0)))
        direction = np.array((scene.camera.location-TARGET).normalized())
        projected = np.column_stack((vertices@right,vertices@up))
        depth = vertices@direction
        image,pixels,low,high = image_data(reference if name=='hero' else materials/f'{name}.png')
        if name=='hero':
            vertex_uv = original_vertex_uv
            uv_name = obj.data.uv_layers.active.name
        else:
            vertex_uv = low+(projected-projected.min(0))/np.ptp(projected,axis=0)*(high-low)
            uv_layer = obj.data.uv_layers.new(name=f'PaintProjection_{name}')
            uv_layer.data.foreach_set('uv',vertex_uv[loops].astype(np.float32).ravel())
            uv_name = uv_layer.name
        pixel_uv = np.clip(vertex_uv,0,1)
        xx = np.minimum((pixel_uv[:,0]*pixels.shape[1]).astype(np.int32),pixels.shape[1]-1)
        yy = np.minimum((pixel_uv[:,1]*pixels.shape[0]).astype(np.int32),pixels.shape[0]-1)
        alpha = pixels[yy,xx,3]
        visible = visibility(projected,depth)
        cosine = np.maximum(normals@direction,0)
        score = visible.astype(np.float32)*alpha**2*cosine**(2 if name=='hero' else 5)
        scores.append(score)
        textures.append(image)
        uv_names.append(uv_name)
        stats.append({'view':name,'image':image.filepath,'image_sha256':hashlib.sha256(Path(image.filepath).read_bytes()).hexdigest(),
                      'visible_vertex_fraction':float(visible.mean())})
    raw = np.column_stack(scores)
    front = np.clip((raw[:,0]*9-.06)/.30,0,1)
    sides = raw[:,1:]
    side_total = sides.sum(1)
    weights = np.zeros((len(vertices),4),np.float32)
    weights[:,0] = front
    weights[:,1:] = sides/np.maximum(side_total[:,None],1e-8)*(1-front[:,None])
    # Where no supplemental camera sees the surface, retain the valid primary.
    no_side = side_total < 1e-8
    weights[no_side & (raw[:,0]>0),0] = 1
    attr = obj.data.color_attributes.new(name='MultiViewWeights',type='FLOAT_COLOR',domain='POINT')
    attr.data.foreach_set('color',weights.ravel())
    fallback = np.empty((len(vertices),4),np.float32)
    fallback[:] = (.23,.37,.30,1)
    fallback[vertices[:,2]>2.3] = (.62,.54,.40,1)
    attr_fallback = obj.data.color_attributes.new(name='UnseenSurfaceFallback',type='FLOAT_COLOR',domain='POINT')
    attr_fallback.data.foreach_set('color',fallback.ravel())
    material = bpy.data.materials.new('Diting multiview painted surface')
    material.use_nodes = True
    nodes,links = material.node_tree.nodes,material.node_tree.links
    bsdf = nodes.get('Principled BSDF')
    bsdf.inputs['Roughness'].default_value = .43
    bsdf.inputs['Coat Weight'].default_value = .12
    colors = nodes.new('ShaderNodeVertexColor'); colors.layer_name = attr.name
    separate = nodes.new('ShaderNodeSeparateColor'); links.new(colors.outputs['Color'],separate.inputs[0])
    channels = [separate.outputs['Red'],separate.outputs['Green'],separate.outputs['Blue'],colors.outputs['Alpha']]
    total_color,total_weight = None,None
    for image,uv_name,channel in zip(textures,uv_names,channels):
        uv = nodes.new('ShaderNodeUVMap'); uv.uv_map = uv_name
        tex = nodes.new('ShaderNodeTexImage'); tex.image = image; tex.extension = 'EXTEND'
        links.new(uv.outputs[0],tex.inputs[0])
        scale = nodes.new('ShaderNodeVectorMath'); scale.operation = 'SCALE'
        links.new(tex.outputs['Color'],scale.inputs[0]); links.new(channel,scale.inputs['Scale'])
        if total_color is None:
            total_color,total_weight = scale.outputs['Vector'],channel
        else:
            add = nodes.new('ShaderNodeVectorMath'); add.operation = 'ADD'
            links.new(total_color,add.inputs[0]); links.new(scale.outputs['Vector'],add.inputs[1]);total_color=add.outputs[0]
            weight_sum = nodes.new('ShaderNodeMath'); weight_sum.operation = 'ADD'
            links.new(total_weight,weight_sum.inputs[0]);links.new(channel,weight_sum.inputs[1]);total_weight=weight_sum.outputs[0]
    residual = nodes.new('ShaderNodeMath'); residual.operation='SUBTRACT';residual.inputs[0].default_value=1
    links.new(total_weight,residual.inputs[1])
    base = nodes.new('ShaderNodeVertexColor');base.layer_name=attr_fallback.name
    scale = nodes.new('ShaderNodeVectorMath');scale.operation='SCALE'
    links.new(base.outputs['Color'],scale.inputs[0]);links.new(residual.outputs[0],scale.inputs['Scale'])
    add = nodes.new('ShaderNodeVectorMath');add.operation='ADD'
    links.new(total_color,add.inputs[0]);links.new(scale.outputs[0],add.inputs[1])
    links.new(add.outputs[0],bsdf.inputs['Base Color'])
    obj.data.materials.clear();obj.data.materials.append(material)
    obj.data.polygons.foreach_set('material_index',np.zeros(len(obj.data.polygons),np.int32))
    repair_projection_alpha(obj)
    return {'views':stats,'fallback_vertex_fraction':float((weights.sum(1)<.01).mean()),
            'vertices':len(vertices),'faces':len(obj.data.polygons),'rigged':False,
            'source':'original primary image plus imagegen supplemental material references',
            'production_asset_replaced':False}


def bake_atlas(obj,scene,out,face_target,size):
    bpy.ops.object.select_all(action='DESELECT');obj.select_set(True)
    bpy.context.view_layer.objects.active=obj
    triangles_before = len(obj.data.polygons)
    modifier=obj.modifiers.new('Static study mesh reduction','DECIMATE')
    modifier.ratio=min(1,face_target/triangles_before)
    modifier.use_collapse_triangulate=True
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    uv=obj.data.uv_layers.new(name='DitingAlbedoAtlas')
    uv_name=uv.name
    obj.data.uv_layers.active=uv
    uv.active_render=True
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(66),island_margin=.003,area_weight=.2,correct_aspect=True,scale_to_bounds=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    material=obj.data.materials[0]
    nodes,links=material.node_tree.nodes,material.node_tree.links
    bsdf=nodes.get('Principled BSDF');output=nodes.get('Material Output')
    source_color=bsdf.inputs['Base Color'].links[0].from_socket
    emission=nodes.new('ShaderNodeEmission');links.new(source_color,emission.inputs['Color'])
    links.new(emission.outputs[0],output.inputs['Surface'])
    atlas=bpy.data.images.new('Diting baked albedo',width=size,height=size,alpha=False)
    atlas.colorspace_settings.name='sRGB'
    texture=nodes.new('ShaderNodeTexImage');texture.image=atlas
    nodes.active=texture
    scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=1
    scene.render.bake.use_selected_to_active=False
    scene.render.bake.margin=12
    bpy.ops.object.bake(type='EMIT')
    atlas.filepath_raw=str(out/'diting-albedo.png');atlas.file_format='PNG';atlas.save();atlas.pack()
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'diting-bake-checkpoint.blend'))
    # The runtime material has one atlas and one standard BSDF, no view shaders.
    nodes.clear()
    output=nodes.new('ShaderNodeOutputMaterial')
    bsdf=nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.inputs['Roughness'].default_value=.43;bsdf.inputs['Coat Weight'].default_value=.12
    texture=nodes.new('ShaderNodeTexImage');texture.image=atlas
    coord=nodes.new('ShaderNodeUVMap');coord.uv_map=uv_name
    links.new(coord.outputs[0],texture.inputs[0]);links.new(texture.outputs['Color'],bsdf.inputs['Base Color'])
    links.new(bsdf.outputs[0],output.inputs[0])
    # Export only the atlas UV. The four camera projection UVs stay in the high scene.
    # Collection mutations invalidate Blender RNA element references. Reacquire
    # each element by its copied name instead of retaining a list of RNA objects.
    for name in [layer.name for layer in obj.data.uv_layers]:
        if name!=uv_name:obj.data.uv_layers.remove(obj.data.uv_layers[name])
    for name in [attr.name for attr in obj.data.color_attributes]:
        obj.data.color_attributes.remove(obj.data.color_attributes[name])
    camera_view(scene,'hero')
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'diting-material-study.blend'))
    bpy.ops.export_scene.gltf(filepath=str(out/'diting-material-study.glb'),use_selection=True,export_format='GLB',export_animations=False)
    return {'triangles_before':triangles_before,'triangles_after':len(obj.data.polygons),
            'vertices_after':len(obj.data.vertices),'atlas_size':[size,size],
            'glb_bytes':(out/'diting-material-study.glb').stat().st_size,
            'rigged':False,'production_asset_replaced':False}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--scene',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--reference',type=Path);p.add_argument('--materials',type=Path)
    p.add_argument('--stage',choices=['project','repair','bake'],default='project')
    p.add_argument('--faces',type=int,default=300000);p.add_argument('--size',type=int,default=4096)
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    started=time.monotonic()
    bpy.ops.wm.open_mainfile(filepath=str(args.scene.resolve()))
    scene=bpy.context.scene
    obj=next(o for o in scene.objects if o.name.startswith('Diting reconstructed'))
    if args.stage in ('project','repair'):
        if args.stage=='project':
            if not args.reference or not args.materials:p.error('project requires --reference and --materials')
            report=build_projection(obj,scene,args.reference,args.materials,out)
        else:
            repair_projection_alpha(obj)
            report={'kind':'projection alpha border repair','rigged':False,'production_asset_replaced':False}
        source=bpy.data.texts.new('multiview_material_source.py');source.write(Path(__file__).read_text(encoding='utf-8'))
        camera_view(scene,'hero')
        bpy.ops.wm.save_as_mainfile(filepath=str(out/'diting-multiview-high.blend'))
        render_views(scene,out,['hero','angle','back','right'])
    else:
        report=bake_atlas(obj,scene,out,args.faces,args.size)
        render_views(scene,out,['hero','angle','back','right','left','front'])
    report['elapsed_seconds']=time.monotonic()-started
    (out/f'{args.stage}-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')


if __name__=='__main__':main()
