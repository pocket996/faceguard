"""Blender facial geometry study: real recessed eyes, deformable lids and nose.

Works on the existing approved character, preserving its body mesh and atlas.
Eyeballs and lid surfaces are geometry; no replacement character image is used.
"""
import argparse
import json
import math
from pathlib import Path
import sys

import bpy
import bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree
import numpy as np


def material(name,color,roughness=.35,coat=.15):
    m=bpy.data.materials.new(name);m.use_nodes=True
    shader=m.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value=(*color,1)
    shader.inputs['Roughness'].default_value=roughness
    shader.inputs['Coat Weight'].default_value=coat
    return m


def mesh(name,vertices,faces,mat):
    data=bpy.data.meshes.new(name);data.from_pydata(vertices,[],faces);data.update()
    obj=bpy.data.objects.new(name,data);bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    for face in obj.data.polygons:face.use_smooth=True
    return obj


def full_weight(obj,bone):
    obj.vertex_groups.new(name=bone).add(list(range(len(obj.data.vertices))),1,'REPLACE')


def eye_point(center,right,up,normal,x,z,radius,offset=0):
    depth=math.sqrt(max(.00001,radius*radius-x*x-z*z))
    return center+right*x+up*z+normal*(depth+offset)


def make_eye(body,label,hit,normal,materials,width,height,radius,atlas):
    # Keep the lid opening anchored to the approved eye placement and expression.
    normal=Vector((normal.x,normal.y,0)).normalized()
    right=Vector((1,0,0));right=(right-normal*right.dot(normal)).normalized()
    up=normal.cross(right).normalized()
    if up.z<0:right=-right;up=-up
    center=hit-normal*(radius+.025)
    face_tree=BVHTree.FromObject(body,bpy.context.evaluated_depsgraph_get())
    eye_bone='Eye'+label;lid_bone='Lid'+label;bulge_bone='LidDepth'+label
    # Almond-shaped closed cutter, extruded through the front of the face only.
    outline=[]
    for i in range(65):
        t=i/64*2*math.pi
        # Remove the old painted orbital outline too; otherwise it remains an
        # open-eye-shaped dark ring around the moving, closed ivory lid.
        x=width*.5*1.18*math.cos(t)
        z=height*.5*1.24*math.copysign(abs(math.sin(t))**1.7,math.sin(t))
        # The outer corner rises slightly, preserving a mature tiger eye.
        z+=.04*x
        outline.append((x,z))
    cutter_vertices=[hit+right*x+up*z+normal*d for d in (-.32,.24) for x,z in outline]
    count=len(outline)
    cutter_faces=[tuple(range(count-1,-1,-1)),tuple(range(count,count*2))]
    cutter_faces += [(i,(i+1)%count,(i+1)%count+count,i+count) for i in range(count)]
    cutter=mesh('Orbit cutter '+label,cutter_vertices,cutter_faces,materials['socket'])
    # Only the visible spherical front surface is needed. Clip it to the
    # almond opening instead of letting an entire sphere protrude through the
    # imperfect reconstructed orbit. Pigment remains actual curved geometry.
    iris_radius=width*.30
    columns,rows=64,32
    vertices=[];colors=[]
    for row in range(rows+1):
        for column in range(columns+1):
            x=(column/columns-.5)*width
            shape=max(0,1-(2*x/width)**2)**.85
            z=(row/rows-.5)*height*shape+.04*x
            vertices.append(eye_point(center,right,up,normal,x,z,radius,.001))
            f=math.sqrt(x*x+z*z)/iris_radius;a=math.atan2(z,x)
            if f>1:color=(.66,.59,.43)
            elif f<.40:color=(.006,.003,.002)
            elif f>.91:color=(.045,.019,.009)
            else:
                grain=.83+.15*math.sin(a*47+f*18)+.06*math.sin(a*79-f*13)
                warm=1+.16*math.sin(f*math.pi*3)
                color=(.13*grain*warm,.052*grain,.015*grain)
            colors.append((*color,1))
    faces=[]
    for row in range(rows):
        for column in range(columns):
            a=row*(columns+1)+column
            faces.append((a,a+1,a+columns+2,a+columns+1))
    iris=mesh('EyeSurface'+label,vertices,faces,materials['iris'])
    attr=iris.data.color_attributes.new(name='IrisPigment',type='FLOAT_COLOR',domain='POINT')
    attr.data.foreach_set('color',np.array(colors,np.float32).ravel())
    iris.data.color_attributes.render_color_index=0
    full_weight(iris,eye_bone)
    sampled={}
    def face_sample(x,z):
        if (x,z) in sampled:return sampled[x,z]
        source=hit+right*x+up*z+normal*.45
        point,n,index,_=face_tree.ray_cast(source,-normal,.85)
        color=np.array((.68,.63,.52))
        if point is not None:
            polygon=body.data.polygons[index]
            loops=list(polygon.loop_indices)[:3]
            verts=[body.data.vertices[body.data.loops[i].vertex_index] for i in loops]
            a,b,c=[v.co for v in verts]
            v0,v1,v2=b-a,c-a,point-a
            d00,d01,d11,d20,d21=v0.dot(v0),v0.dot(v1),v1.dot(v1),v2.dot(v0),v2.dot(v1)
            denominator=d00*d11-d01*d01
            if abs(denominator)>1e-12:
                v=(d11*d20-d01*d21)/denominator;w=(d00*d21-d01*d20)/denominator
                weights=(1-v-w,v,w)
                uv=sum((body.data.uv_layers.active.data[i].uv*weight for i,weight in zip(loops,weights)),Vector((0,0)))
                row=int(np.clip(uv.y*(atlas.shape[0]-1),0,atlas.shape[0]-1));column=int(np.clip(uv.x*(atlas.shape[1]-1),0,atlas.shape[1]-1))
                srgb=atlas[row,column,:3]
                color=np.where(srgb<=.04045,srgb/12.92,((srgb+.055)/1.055)**2.4)
                n=sum((vertex.normal*weight for vertex,weight in zip(verts,weights)),Vector((0,0,0))).normalized()
            point+=normal*.004
        else:point=hit+right*x+up*z;n=normal
        sampled[x,z]=(point,n,color)
        return sampled[x,z]
    skin_color=max([face_sample(x,height*.5+.09)[2] for x in (-width*.45,0,width*.45)],key=lambda c:float(c.sum()))
    def blended_skin(color,r):
        # The source atlas still contains the painted iris and black outline.
        # Sample surrounding skin, but never carry those old eye pixels onto a
        # moving eyelid or it acquires a second, fixed dark ring.
        if float(color@np.array((.2126,.7152,.0722)))<.18:color=skin_color
        return (*(skin_color*r+color*(1-r)),1)
    def skin_finish(obj,colors,normals):
        attr=obj.data.color_attributes.new(name='SkinPigment',type='FLOAT_COLOR',domain='POINT')
        attr.data.foreach_set('color',np.asarray(colors,np.float32).ravel())
        # Open bands must wind toward the face front. Double-sided rendering
        # flips back-face shading, including custom normals; a reversed band
        # otherwise becomes an unlit black crescent despite ivory pigment.
        for polygon in obj.data.polygons:
            if polygon.normal.dot(normal)<0:polygon.flip()
        obj.data.update()
        obj.data.normals_split_custom_set_from_vertices([n if n.dot(normal)>=0 else -n for n in normals])
    # Anchor the outer lid edge to the existing facial surface, rather than
    # building a visible pale spherical patch around the eye.
    vertices=[];faces=[];weights=[];colors=[];normals=[]
    columns,rows=64,10
    for row in range(rows+1):
        r=1-row/rows
        for column in range(columns+1):
            theta=column/columns*math.pi
            inner_x=math.cos(theta)*width*.5
            f=abs(math.sin(theta))**1.7
            inner_z=height*.5*f+.04*inner_x
            outer_x=inner_x*1.30
            outer_z=inner_z+.065*abs(math.sin(theta))+.003
            inner_point=eye_point(center,right,up,normal,inner_x,inner_z,radius,.0045)
            outer_point,n,color=face_sample(outer_x,outer_z)
            vertices.append(inner_point*r+outer_point*(1-r))
            colors.append(blended_skin(color,r));normals.append(n)
            vertical=f*r;depth=.45*r*(1-r)*f
            weights.append((1-vertical-depth,vertical,depth))
    for row in range(rows):
        for column in range(columns):
            a=row*(columns+1)+column
            faces.append((a,a+1,a+columns+2,a+columns+1))
    lid=mesh('UpperLid'+label,vertices,faces,materials['skin']);skin_finish(lid,colors,normals)
    for bone,index in [('Head',0),(lid_bone,1),(bulge_bone,2)]:
        group=lid.vertex_groups.new(name=bone)
        for i,w in enumerate(weights):
            if w[index]>.00001:group.add([i],w[index],'REPLACE')
    lower_vertices=[];lower_faces=[];colors=[];normals=[]
    for row in range(rows+1):
        r=1-row/rows
        for column in range(columns+1):
            theta=math.pi+column/columns*math.pi
            inner_x=math.cos(theta)*width*.5
            inner_z=-height*.5*abs(math.sin(theta))**1.7+.04*inner_x
            inner_point=eye_point(center,right,up,normal,inner_x,inner_z,radius,.0045)
            outer_point,n,color=face_sample(inner_x*1.30,inner_z-.050*abs(math.sin(theta))-.003)
            lower_vertices.append(inner_point*r+outer_point*(1-r))
            colors.append(blended_skin(color,r));normals.append(n)
    for row in range(rows):
        for column in range(columns):
            a=row*(columns+1)+column
            lower_faces.append((a,a+1,a+columns+2,a+columns+1))
    lower=mesh('LowerLid'+label,lower_vertices,lower_faces,materials['skin']);full_weight(lower,'Head');skin_finish(lower,colors,normals)
    # Fine upper/lower liner geometry follows the actual eyelid boundary.
    for upper in (True,False):
        vertices=[];faces=[];closing=[]
        for i in range(columns+1):
            x=(i/columns-.5)*width
            f=max(0,1-(2*x/width)**2)**.85
            z=(1 if upper else -1)*height*.5*f+.04*x
            for dz in (-.004,.004):vertices.append(eye_point(center,right,up,normal,x,z+dz,radius,.005))
            closing.extend([f,f])
        for i in range(columns):faces.append((i*2,i*2+1,i*2+3,i*2+2))
        liner=mesh(('UpperLiner' if upper else 'LowerLiner')+label,vertices,faces,materials['liner'])
        if upper:
            a=liner.vertex_groups.new(name='Head');b=liner.vertex_groups.new(name=lid_bone)
            for i,w in enumerate(closing):
                if w<1:a.add([i],1-w,'REPLACE')
                if w>0:b.add([i],w,'REPLACE')
        else:full_weight(liner,'Head')
    bpy.context.view_layer.objects.active=body
    modifier=body.modifiers.new('Recessed eye orbit '+label,'BOOLEAN')
    modifier.operation='DIFFERENCE';modifier.solver='EXACT';modifier.object=cutter
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    bpy.data.objects.remove(cutter,do_unlink=True)
    return {'label':label,'center':list(center),'normal':list(normal),'right':list(right),'up':list(up),
            'opening_width':width,'opening_height':height,'radius':radius,
            'eye_bone':eye_bone,'lid_bone':lid_bone,'bulge_bone':bulge_bone}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--scene',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--sculpt-nose',action='store_true',help='Optional nose study; keep the approved nose by default')
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(args.scene.resolve()))
    body=next(o for o in bpy.context.scene.objects if o.name.startswith('Diting reconstructed'))
    scene=bpy.context.scene;cam=scene.camera
    basis=cam.rotation_euler.to_matrix();right,up,forward=[basis@Vector(a) for a in [(1,0,0),(0,1,0),(0,0,-1)]]
    tree=BVHTree.FromObject(body,bpy.context.evaluated_depsgraph_get())
    landmarks={}
    for name,(px,py) in {'Near':(564,251),'Far':(679,265),'Nose':(650,285)}.items():
        origin=cam.location+right*((px/840-.5)*cam.data.ortho_scale*840/940)+up*((.5-py/940)*cam.data.ortho_scale)
        hit,normal,_,_=tree.ray_cast(origin,forward)
        if hit is None:raise RuntimeError('Missing facial landmark '+name)
        landmarks[name]=(hit,normal)
    materials={
        'socket':material('Eye socket shadow',(.055,.032,.019),.65),
        'sclera':material('Warm ivory sclera',(.66,.59,.43),.22,.35),
        'iris':material('Amber iris and pupil',(1,1,1),.23,.65),
        'lid':material('Ivory jade eyelid',(.78,.70,.55),.38,.2),
        'skin':material('Continuous facial skin',(1,1,1),.43,.12),
        'liner':material('Dark brown lid margin',(.027,.012,.008),.38,.1),
        'nose':material('Sculpted warm brown nose',(.15,.064,.035),.29,.3),
        'nostril':material('Nostril recess',(.012,.006,.004),.65,.05),
    }
    iris_color=materials['iris'].node_tree.nodes.new('ShaderNodeVertexColor');iris_color.layer_name='IrisPigment'
    materials['iris'].node_tree.links.new(iris_color.outputs['Color'],materials['iris'].node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
    skin_color=materials['skin'].node_tree.nodes.new('ShaderNodeVertexColor');skin_color.layer_name='SkinPigment'
    materials['skin'].node_tree.links.new(skin_color.outputs['Color'],materials['skin'].node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
    atlas_image=next(n.image for n in body.data.materials[0].node_tree.nodes if n.type=='TEX_IMAGE')
    atlas=np.empty(atlas_image.size[0]*atlas_image.size[1]*4,np.float32);atlas_image.pixels.foreach_get(atlas)
    atlas=atlas.reshape(atlas_image.size[1],atlas_image.size[0],4)
    # Remove thin reconstructed whisker fragments in front of the muzzle.
    thin=[]
    for vertex in body.data.vertices:
        x,y,z=vertex.co
        if not (x>0 and y<-1.0 and 2.38<z<2.98):continue
        if ((x-.34)/.23)**2+((z-2.72)/.16)**2<1:continue
        hit,_,_,distance=tree.ray_cast(vertex.co-vertex.normal*.0005,-vertex.normal,.10)
        if hit is not None and .0004<distance<.055:thin.append(vertex.index)
    bm=bmesh.new();bm.from_mesh(body.data);bm.verts.ensure_lookup_table()
    bmesh.ops.delete(bm,geom=[bm.verts[i] for i in thin],context='VERTS')
    boundary=[e for e in bm.edges if e.is_boundary]
    fill=bmesh.ops.holes_fill(bm,edges=boundary,sides=32)
    body.data.materials.append(materials['lid'])
    for face in fill.get('faces',[]):face.material_index=len(body.data.materials)-1
    bm.to_mesh(body.data);bm.free();body.data.update()
    eyes=[]
    for label,width,height,radius in [('Near',.255,.125,.155),('Far',.175,.090,.130)]:
        eyes.append(make_eye(body,label,*landmarks[label],materials,width,height,radius,atlas))
    # Replace the ambiguous projected nose tip with a compact actual nose cap.
    hit,_=landmarks['Nose'];normal=Vector((.23,-.97,.05)).normalized()
    tangent=Vector((normal.y,-normal.x,0)).normalized();vertical=normal.cross(tangent).normalized()
    if vertical.z<0:tangent=-tangent;vertical=-vertical
    if args.sculpt_nose:
        outline=[(-.120,.036),(-.090,.073),(0,.085),(.090,.073),(.120,.036),(.090,-.012),(0,-.075),(-.090,-.012)]
        vertices=[];faces=[];segments=len(outline);rings=8
        for ring in range(rings+1):
            r=ring/rings
            vertices += [hit+tangent*(x*r)+vertical*(z*r)+normal*(.010+.042*(1-r*r)) for x,z in outline]
        for ring in range(rings):
            for i in range(segments):
                a=ring*segments+i;b=ring*segments+(i+1)%segments
                faces.append((a,b,b+segments,a+segments))
        vertices.append(hit-normal*.018)
        faces += [(len(vertices)-1,rings*segments+(i+1)%segments,rings*segments+i) for i in range(segments)]
        nose=mesh('SculptedNose',vertices,faces,materials['nose']);full_weight(nose,'Head')
        for side in (-1,1):
            center_nose=hit+tangent*(side*.062)+vertical*.012+normal*.046
            ring=[center_nose]+[center_nose+tangent*(.017*math.cos(a*2*math.pi/32))+vertical*(.009*math.sin(a*2*math.pi/32)) for a in range(32)]
            nostril=mesh('Nostril'+str(side),ring,[(0,i+1,(i+1)%32+1) for i in range(32)],materials['nostril']);full_weight(nostril,'Head')
    for side in (-1,1):
        for k in range(3):
            start=hit+tangent*(side*.115)+vertical*(-.075-k*.025)+normal*.005
            end=start+tangent*(side*(.36+.04*k))+vertical*(-.015-.035*k)+normal*.04
            curve=bpy.data.curves.new('Fine whisker','CURVE');curve.dimensions='3D';curve.bevel_depth=.0022;curve.bevel_resolution=2;curve.resolution_u=12
            spline=curve.splines.new('BEZIER');spline.bezier_points.add(2)
            for point,co,r in zip(spline.bezier_points,[start,start.lerp(end,.48)+vertical*.025,end],[1,.7,.08]):
                point.co=co;point.radius=r;point.handle_left_type=point.handle_right_type='AUTO'
            whisker=bpy.data.objects.new('FineWhisker',curve);bpy.context.collection.objects.link(whisker);whisker.data.materials.append(materials['lid'])
            bpy.ops.object.select_all(action='DESELECT');whisker.select_set(True);bpy.context.view_layer.objects.active=whisker
            bpy.ops.object.convert(target='MESH');full_weight(whisker,'Head')
    for obj in bpy.context.scene.objects:
        if obj.type=='MESH' and obj!=body and obj.vertex_groups:obj['facial_geometry']=True
    body['facial_base_body']=True
    metadata={'eyes':eyes,'removed_thin_whisker_vertices':len(thin),'landmarks':{k:list(v[0]) for k,v in landmarks.items()},
              'source_scene':str(args.scene.resolve()),'sculpted_nose_enabled':args.sculpt_nose,'purpose':'facial geometry candidate; inspect before integration'}
    (out/'face-report.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    source=bpy.data.texts.new('face_source.py');source.write(Path(__file__).read_text(encoding='utf-8'))
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'diting-face-v5.blend'))
    scene.render.resolution_x=840;scene.render.resolution_y=940;scene.cycles.samples=24
    scene.render.filepath=str(out/'face-hero.png');bpy.ops.render.render(write_still=True)
    cam.location=(-3.6,-7.5,3.6);target=Vector((.4,-.65,3.05));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=1.8
    scene.render.resolution_x=1000;scene.render.resolution_y=760
    scene.render.filepath=str(out/'face-close.png');bpy.ops.render.render(write_still=True)


if __name__=='__main__':main()
