"""Blender-only, reproducible static geometry study; never replaces UI assets.

blender --background --factory-startup --python-exit-code 1
  --python scripts/build_diting_study.py -- --output outputs/diting-3d/rebuild
"""
import argparse
import json
import math
from pathlib import Path
import random
import sys

import bpy
from mathutils import Vector

RNG = random.Random(20261030)


def material(name, color, roughness=.3, metallic=0, jade=False):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    shader = nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (*color, 1)
    shader.inputs['Roughness'].default_value = roughness
    shader.inputs['Metallic'].default_value = metallic
    shader.inputs['Coat Weight'].default_value = .22
    if jade:
        shader.inputs['Subsurface Weight'].default_value = .04
        shader.inputs['Subsurface Radius'].default_value = (.35, .6, .4)
        noise = nodes.new('ShaderNodeTexNoise')
        noise.inputs['Scale'].default_value = 6
        noise.inputs['Detail'].default_value = 3
        ramp = nodes.new('ShaderNodeValToRGB')
        ramp.color_ramp.elements[0].position = .15
        ramp.color_ramp.elements[0].color = (*(v * .8 for v in color), 1)
        ramp.color_ramp.elements[1].position = .85
        ramp.color_ramp.elements[1].color = (*(min(1, v * 1.12) for v in color), 1)
        mat.node_tree.links.new(noise.outputs['Fac'], ramp.inputs[0])
        mat.node_tree.links.new(ramp.outputs[0], shader.inputs['Base Color'])
    return mat


def register(obj, name, mat):
    obj.name = name
    if mat:
        obj.data.materials.append(mat)
    if obj.type == 'MESH':
        for poly in obj.data.polygons:
            poly.use_smooth = True
    return obj


def oval(name, center, scale, mat, rotation=None):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=40, ring_count=24, location=center)
    obj = register(bpy.context.object, name, mat)
    obj.scale = scale
    if rotation:
        obj.rotation_euler = rotation
    return obj


def mesh(name, vertices, faces, mat):
    data = bpy.data.meshes.new(name)
    data.from_pydata(vertices, [], faces)
    data.update()
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    return register(obj, name, mat)


def tube(name, points, radius, mat, taper=None):
    curve = bpy.data.curves.new(name, 'CURVE')
    curve.dimensions = '3D'
    curve.resolution_u = 16
    curve.bevel_depth = radius
    curve.bevel_resolution = 3
    curve.use_fill_caps = True
    spline = curve.splines.new('BEZIER')
    spline.bezier_points.add(len(points) - 1)
    for i, (point, value) in enumerate(zip(spline.bezier_points, points)):
        point.co = value
        point.handle_left_type = point.handle_right_type = 'AUTO'
        if taper:
            point.radius = taper[i]
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    return register(obj, name, mat)


def curl(center, radius, mat, phase=0, thickness=.075, depth=.12, yaw=0):
    # Sweep a tapered, fluted sculptural lock through an S-shaped curl.
    # Unlike the previous radial disks, this has a flowing root and pointed tip.
    controls=[Vector(p) for p in [(0,.85),(.23,.55),(.30,.15),(.10,-.35),(-.30,-.67),(-.65,-.54),(-.70,-.18),(-.42,.02),(-.15,-.16),(-.25,-.37),(-.43,-.32)]]
    path=[]
    for i in range(len(controls)-1):
        p0=controls[max(0,i-1)]; p1=controls[i]
        p2=controls[i+1]; p3=controls[min(len(controls)-1,i+2)]
        for j in range(7):
            t=j/7
            p=.5*((2*p1)+(-p0+p2)*t+(2*p0-5*p1+4*p2-p3)*t*t+(-p0+3*p1-3*p2+p3)*t*t*t)
            path.append(Vector((math.cos(phase)*p.x-math.sin(phase)*p.y,math.sin(phase)*p.x+math.cos(phase)*p.y)))
    path.append(Vector((math.cos(phase)*controls[-1].x-math.sin(phase)*controls[-1].y,math.sin(phase)*controls[-1].x+math.cos(phase)*controls[-1].y)))
    vertices,faces=[],[]
    sides=40
    for i,p in enumerate(path):
        t=i/(len(path)-1)
        tangent=(path[min(len(path)-1,i+1)]-path[max(0,i-1)]).normalized()
        across=Vector((-tangent.y,tangent.x))
        profile=(.5+.5*math.sin(min(1,t/.6)*math.pi*.8))*max(.025,(1-t)**.6)*min(1,(t/.13)**.7)
        for j in range(sides):
            a=j*math.tau/sides
            fluting=1+.16*math.cos(5*a)
            width=radius*.50*profile*math.cos(a)*fluting
            height=radius*.44*profile*math.sin(a)*fluting
            px=((p.x+.12)*radius*1.20+across.x*width)
            pz=(p.y*radius*1.20+across.y*width)
            py=-radius*.3*math.sin(t*math.pi)-height
            vertices.append((center[0]+math.cos(yaw)*px-math.sin(yaw)*py,center[1]+math.sin(yaw)*px+math.cos(yaw)*py,center[2]+pz))
            if i:
                current=i*sides+j; nxt=i*sides+(j+1)%sides
                faces.append((current-sides,nxt-sides,nxt,current))
    faces.extend([tuple(reversed(range(sides))),tuple(range((len(path)-1)*sides,len(path)*sides))])
    return mesh('Swept sculpted hair lock',vertices,faces,mat)


def loft(name, centers, radii, mat, sides=24):
    vertices, faces = [], []
    for i, (center, radius) in enumerate(zip(centers, radii)):
        center = Vector(center)
        tangent = Vector(centers[min(i + 1, len(centers) - 1)]) - Vector(centers[max(0, i - 1)])
        tangent.normalize()
        axis = Vector((0, 1, 0))
        if abs(tangent.dot(axis)) > .95:
            axis = Vector((1, 0, 0))
        u = tangent.cross(axis).normalized()
        v = tangent.cross(u).normalized()
        for j in range(sides):
            angle = j * math.tau / sides
            vertices.append(center + radius * (u * math.cos(angle) + v * math.sin(angle)))
            if i:
                a = i * sides + j
                b = i * sides + (j + 1) % sides
                faces.append((a - sides, b - sides, b, a))
    faces.extend([tuple(reversed(range(sides))), tuple(range((len(centers) - 1) * sides, len(centers) * sides))])
    return mesh(name, vertices, faces, mat)


def shield(center, normal, width, height, jade, gold):
    c, n = Vector(center), Vector(normal).normalized()
    u = Vector((0, 0, 1)).cross(n).normalized()
    v = n.cross(u).normalized()
    outline = [(-.46,.35),(-.5,.05),(-.38,-.24),(0,-.61),(.38,-.24),(.5,.05),(.46,.35),(0,.5)]
    rim = [c + u * x * width + v * y * height for x, y in outline]
    vertices = rim + [c + n * .065]
    obj = mesh('Overlapping jade scale', vertices, [(8, i, (i + 1) % 8) for i in range(8)], jade)
    solid = obj.modifiers.new('Scale depth', 'SOLIDIFY')
    solid.thickness = .018
    bevel = obj.modifiers.new('Scale rounded edge', 'BEVEL')
    bevel.width = .025
    bevel.segments = 3
    tube('Restrained gold scale rim', rim + [rim[0]], .009, gold)


def build():
    jade = material('Celadon satin jade', (.25,.43,.33), .29, jade=True)
    dark = material('Deep jade carving', (.035,.105,.08), .32, jade=True)
    ivory = material('Ivory cloud mane', (.72,.67,.51), .33, jade=True)
    gold = material('Antique gold inlay', (.55,.36,.12), .3, .72)
    inner = material('Warm ear interior', (.36,.25,.17), .48)
    amber = material('Amber brown iris', (.23,.095,.027), .16)
    pupil = material('Obsidian eyes', (.009,.013,.01), .1)
    white = material('Eye ivory', (.85,.86,.76), .2)
    nose = material('Warm dark nose', (.105,.069,.047), .3)

    oval('Seated dragon torso', (0,.33,1.67), (.82,.67,1.33), jade)
    oval('Ivory chest', (0,-.23,2.0), (.58,.45,.92), ivory)
    for side in (-1, 1):
        oval('Seated haunch', (side*.77,.4,.88), (.49,.62,.79), jade)
        oval('Rear paw', (side*.86,-.02,.22), (.40,.51,.22), jade)
        loft('Front leg', [(side*.48,-.05,2.33),(side*.51,-.24,1.65),(side*.54,-.42,.84),(side*.58,-.54,.32)], [.29,.25,.19,.23], jade)
        oval('Front qilin paw', (side*.58,-.7,.22), (.34,.43,.21), jade)
        for toe in (-1,0,1):
            x = side*.58 + toe*.18
            oval('Qilin toe', (x,-.92,.18), (.12,.22,.15), jade)
            loft('Carved claw', [(x,-1.02,.23),(x,-1.13,.14),(x,-1.16,.095)], [.077,.064,.004], dark, 16)
            tube('Claw gold edge', [(x+.055,-1.015,.22),(x+.052,-1.11,.16),(x,-1.16,.095)], .007, gold)
        curl((side*.59,-.71,.53), .23, ivory, phase=side, thickness=.07)
        curl((side*.62,-.57,.76), .16, ivory, phase=side+1, thickness=.055)

    # Fused head surfaces, rather than a stack of visible geometric primitives.
    face_before=set(bpy.context.scene.objects)
    parts = [oval('Head volume', (0,-.1,3.52), (.76,.62,.66), jade),
             oval('Broad tiger forehead', (0,-.42,3.79), (.63,.39,.38), jade),
             oval('Left cheek', (-.49,-.38,3.35), (.36,.37,.37), jade),
             oval('Right cheek', (.49,-.38,3.35), (.36,.37,.37), jade)]
    bpy.ops.object.select_all(action='DESELECT')
    for obj in parts:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bpy.ops.object.join()
    head = bpy.context.object
    head.name = 'Continuous tiger head surface'
    head.data.remesh_voxel_size = .035
    bpy.ops.object.voxel_remesh()
    smooth = head.modifiers.new('Sculpt surface smoothing', 'SMOOTH')
    smooth.factor = .7
    smooth.iterations = 5
    for polygon in head.data.polygons:
        polygon.use_smooth = True
    # Recess the eye sockets into the head instead of placing white globes
    # on top of its surface.
    for side in (-1,1):
        cutter=oval('Temporary orbital cutter',(side*.345,-.70,3.65),(.205,.16,.15),None)
        bpy.context.view_layer.objects.active=head
        cut=head.modifiers.new('Recessed feline orbit','BOOLEAN')
        cut.operation='DIFFERENCE'; cut.solver='EXACT'; cut.object=cutter
        bpy.ops.object.modifier_apply(modifier=cut.name)
        bpy.data.objects.remove(cutter,do_unlink=True)

    def marking(name,outline):
        bpy.context.view_layer.update()
        evaluated=head.evaluated_get(bpy.context.evaluated_depsgraph_get())
        inverse=head.matrix_world.inverted()
        controls=[Vector(p) for p in outline]
        samples=[]
        for i in range(len(controls)):
            p0,p1,p2,p3=[controls[(i+j)%len(controls)] for j in (-1,0,1,2)]
            for j in range(5):
                t=j/5
                samples.append(.5*((2*p1)+(-p0+p2)*t+(2*p0-5*p1+4*p2-p3)*t*t+(-p0+3*p1-3*p2+p3)*t*t*t))
        points=[]
        for x,z in samples:
            origin=inverse@Vector((x,-4,z))
            direction=(inverse.to_3x3()@Vector((0,1,0))).normalized()
            hit,location,normal,index=evaluated.ray_cast(origin,direction)
            if not hit:
                continue
            position=head.matrix_world@location
            position.y-=.007
            points.append(position)
        if len(points)>=3:
            return mesh(name,points,[tuple(range(len(points)))],dark)

    muzzle_parts=[]
    for side in (-1, 1):
        muzzle_parts.append(oval('Ivory muzzle', (side*.205,-.78,3.29), (.30,.29,.205), ivory))
        oval('Orbital dark lining', (side*.345,-.685,3.65), (.179,.10,.122), dark)
        oval('Almond eye', (side*.345,-.715,3.65), (.16,.078,.108), white,(0,-side*.1,0))
        oval('Amber iris', (side*.335,-.789,3.65), (.105,.025,.104), amber)
        oval('Pupil', (side*.335,-.811,3.65), (.055,.014,.076), pupil)
        oval('Eye catchlight', (side*.335-.024,-.830,3.684), (.016,.006,.016), white)
        for ray in range(28):
            a=ray*math.tau/28
            tube('Iris radial detail',[(side*.335+math.cos(a)*.067,-.813,3.65+math.sin(a)*.075),(side*.335+math.cos(a)*.094,-.804,3.65+math.sin(a)*.094)],.0018,gold,[.4,.1])
        tube('Upper jade eyelid', [(side*.18,-.78,3.67),(side*.30,-.806,3.747),(side*.43,-.77,3.75),(side*.51,-.70,3.72)], .038, jade, [.5,1,.9,.1])
        tube('Lower jade eyelid',[(side*.18,-.78,3.64),(side*.32,-.80,3.555),(side*.49,-.74,3.60)], .022,jade,[.25,1,.15])
        tube('Expressive tiger brow', [(side*.15,-.77,3.80),(side*.32,-.75,3.84),(side*.55,-.61,3.87)], .055, jade, [.45,1,.3])
        for row in range(2):
            z=3.53-row*.15
            marking('Surface-fitted tiger cheek marking',[(side*.66,z+.055),(side*.56,z+.075),(side*.48,z+.025),(side*.55,z-.01),(side*.65,z-.018),(side*.59,z+.025)])
        for whisker in range(4):
            z = 3.29 - whisker*.035
            tube('Fine ivory whisker', [(side*.2,-1.035,z),(side*.55,-1.02,z+.035),(side*(.86+whisker*.03),-.92,z+.10-whisker*.035)], .0035, ivory, [.7,.6,.02])
            oval('Whisker root', (side*(.15+whisker*.035),-1.047,z+.03), (.009,.006,.009), gold)
    muzzle_parts.append(oval('Chin', (0,-.69,3.08), (.34,.27,.145), ivory))
    bpy.ops.object.select_all(action='DESELECT')
    for part in muzzle_parts: part.select_set(True)
    bpy.context.view_layer.objects.active=muzzle_parts[0]
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    bpy.ops.object.join()
    muzzle=bpy.context.object
    muzzle.name='Continuous sculpted tiger muzzle'
    muzzle.data.remesh_voxel_size=.018
    bpy.ops.object.voxel_remesh()
    smoothing=muzzle.modifiers.new('Muzzle surface smoothing','SMOOTH')
    smoothing.factor=.6; smoothing.iterations=4
    for polygon in muzzle.data.polygons: polygon.use_smooth=True
    for side in (-1,1):
        oval('Nostril', (side*.087,-1.062,3.375), (.023,.009,.017), pupil)
    nose_vertices = [(-.15,-1.047,3.41),(.15,-1.047,3.41),(0,-1.105,3.25),(-.115,-.95,3.45),(.115,-.95,3.45),(0,-.98,3.25)]
    obj = mesh('Tiger nose', nose_vertices, [(0,1,2),(3,5,4),(0,3,4,1),(1,4,5,2),(2,5,3,0)], nose)
    bevel = obj.modifiers.new('Soft nose', 'BEVEL'); bevel.width=.045; bevel.segments=3
    tube('Mouth center', [(0,-1.08,3.29),(0,-1.065,3.16)], .013, nose)
    for side in (-1,1):
        tube('Quiet mouth contour', [(0,-1.065,3.16),(side*.14,-1.02,3.12),(side*.3,-.9,3.16)], .012, nose, [.9,1,.1])
    for side in (-1,1):
        marking('Surface-fitted forehead marking',[(side*.04,3.99),(side*.14,3.955),(side*.28,4.01),(side*.20,3.94),(side*.12,3.93)])
    ridges=[obj for obj in bpy.context.scene.objects if obj.name.startswith(('Expressive tiger brow','Upper jade eyelid','Lower jade eyelid'))]
    bpy.ops.object.select_all(action='DESELECT')
    head.select_set(True)
    for ridge in ridges: ridge.select_set(True)
    bpy.context.view_layer.objects.active=head
    bpy.ops.object.convert(target='MESH')
    bpy.ops.object.join()
    head=bpy.context.object
    head.data.remesh_voxel_size=.016
    bpy.ops.object.voxel_remesh()
    for polygon in head.data.polygons: polygon.use_smooth=True
    smooth=head.modifiers.new('Integrated orbital ridge smoothing','SMOOTH')
    smooth.factor=.3; smooth.iterations=2
    for part in set(bpy.context.scene.objects)-face_before:
        part.location.x*=1.075
        part.scale.x*=1.075

    # Curved single horn, with four restrained engraved bands.
    centers = [(0,-.26,4.03),(0,-.23,4.22),(0,-.15,4.45),(0,-.04,4.66),(0,.02,4.78)]
    loft('Single antique gold horn', centers, [.16,.145,.105,.05,.002], gold)
    for i in range(1,4):
        z = 4.12+i*.14; radius=.157-i*.027
        points=[(math.cos(a)*radius, -.22+(z-4.2)*.4+math.sin(a)*radius,z) for a in [j*math.tau/32 for j in range(33)]]
        tube('Horn engraved band', points, .009, dark)
    # Ear rims are rounded custom leaf surfaces, not cone ears.
    ears = [[(-.61,-.03,3.99),(-1.03,-.025,4.63),(-.9,.01,4.85),(-.63,-.02,4.61),(-.39,-.08,4.14)],
            [(.43,-.04,4.12),(.76,.025,4.39),(1.03,-.1,4.2),(.99,-.3,3.98),(.79,-.34,4.0)]]
    for outline in ears:
        controls=[Vector(p) for p in outline]
        contour=[]
        for i in range(len(controls)):
            p0,p1,p2,p3=[controls[(i+j)%len(controls)] for j in (-1,0,1,2)]
            for j in range(8):
                t=j/8
                contour.append(.5*((2*p1)+(-p0+p2)*t+(2*p0-5*p1+4*p2-p3)*t*t+(-p0+3*p1-3*p2+p3)*t*t*t))
        center=sum(controls,Vector())/len(controls)
        count=len(contour)
        faces=[(count,j,(j+1)%count) for j in range(count)]
        if (contour[0]-center).cross(contour[1]-center).y>0:
            faces=[tuple(reversed(face)) for face in faces]
        ear=mesh('Sculpted asymmetric canine ear',contour+[center+Vector((0,-.09,0))],faces,jade)
        solid=ear.modifiers.new('Ear thickness','SOLIDIFY'); solid.thickness=.07
        inset=[center+(p-center)*.78+Vector((0,-.10,0)) for p in contour]
        mesh('Ear warm interior',inset+[center+Vector((0,-.19,0))],faces,inner)
        tube('Ear gold rim',contour+[contour[0]],.018,gold)

    # Cloud mane: irregular overlapping curls, plus flowing cheek strands.
    for layer in range(2):
        for i in range(17):
            angle = .3+i*math.tau/17
            x = math.sin(angle)*(.78+layer*.16)
            z = 3.42+math.cos(angle)*(.67+layer*.13)
            y = -.10+layer*.21
            radius=RNG.uniform(.18,.29)
            oval('Cloud mane volume',(x,y+.07,z),(radius*1.1,.18,radius*1.27),ivory)
            curl((x,y-.12,z),radius,ivory,phase=angle+RNG.uniform(-.6,.6),thickness=RNG.uniform(.06,.092))
    for row in range(6):
        count=5 if row<3 else 4
        for col in range(count):
            x=(col-(count-1)/2)*(.29-row*.01)+RNG.uniform(-.07,.07)
            z=3.0-row*.19+RNG.uniform(-.07,.07)
            y=-.59-row*.025
            radius=RNG.uniform(.19,.27)
            oval('Solid sculpted chest cloud',(x,y+.08,z),(radius*1.14,.17,radius*1.08),ivory)
            curl((x,y-.065,z),radius,ivory,phase=(.4 if x<0 else -.4)+RNG.uniform(-.3,.3),thickness=.095)
    # Continue the mane around the head: this must have volume in profile,
    # not just a front-facing arrangement of cloud curls.
    for row in range(3):
        for i in range(11):
            yaw=math.radians(80+i*20+RNG.uniform(-8,8))
            radius=RNG.uniform(.21,.29)
            x=.76*math.sin(yaw)
            y=.16-.53*math.cos(yaw)
            z=3.12+row*.35+RNG.uniform(-.10,.10)
            oval('Cloud mane volume',(x,y,z),(radius,.20,radius*1.15),ivory,(0,0,yaw))
            curl((x+math.sin(yaw)*.13,y-math.cos(yaw)*.13,z),radius,ivory,phase=RNG.uniform(0,math.tau),thickness=.085,yaw=yaw)
    for side in (-1,1):
        for j in range(4):
            tube('Flowing sculpted mane',[(side*.63,-.3,3.5-j*.15),(side*.92,-.31,3.2-j*.2),(side*.78,-.4,2.94-j*.20),(side*.62,-.54,3.0-j*.23)], .09-j*.006, ivory, [.9,1,.7,.15])
        curl((side*.23,-.40,4.055),.16,ivory,phase=side*.8,thickness=.07)
        for z,radius in [(3.86,.19),(3.64,.23),(3.40,.22)]:
            curl((side*.72,-.62,z),radius,ivory,phase=side*.45,thickness=.07)
        curl((side*.35,-.60,4.02),.18,ivory,phase=side*.6,thickness=.06)

    for side in (-1,1):
        for row in range(7):
            z = .95+row*.205
            factor=math.sqrt(max(.05,1-((z-1.67)/1.33)**2))
            for col in range(5):
                angle=math.radians(43+col*20+(row%2)*8)
                x=side*.84*factor*math.sin(angle)
                y=.33+.70*factor*math.cos(angle)
                normal=(side*math.sin(angle),math.cos(angle),.15)
                shield((x,y,z),normal,.30,.31,dark,gold)
        for row in range(4):
            z=.5+row*.22
            for col in range(4):
                angle=math.radians(62+col*22+(row%2)*9)
                factor=math.sqrt(max(.1,1-((z-.88)/.79)**2))
                center=(side*(.77+.50*factor*math.sin(angle)),.4+.64*factor*math.cos(angle),z)
                shield(center,(side*math.sin(angle),math.cos(angle),.25),.25,.31,dark,gold)
    tail=[(-.56,.79,.64),(-1.15,.8,.7),(-1.69,.65,1.0),(-1.85,.55,1.65),(-1.58,.48,2.05),(-1.39,.47,1.84)]
    tube('Flexible lion tail',tail,.13,jade,[1.25,1.1,1,.88,.7,.6])
    for i in range(7):
        angle=i*math.tau/7
        oval('Solid cloud tail tuft',(-1.65+math.sin(angle)*.22,.5,2.1+math.cos(angle)*.24),(.22,.15,.24),ivory)
        curl((-1.65+math.sin(angle)*.22,.39,2.1+math.cos(angle)*.24),.20,ivory,phase=angle,thickness=.075)
    return [obj for obj in bpy.context.scene.objects if obj.type in {'MESH','CURVE'}]


def compact_proportions(parts):
    """Shorten the seated lower body while preserving the head's proportions."""
    bpy.context.view_layer.update()
    def transform(point):
        result=point.copy()
        result.z=result.z*.81 if result.z<2.5 else result.z-.475
        return result
    for obj in parts:
        world=obj.matrix_world.copy()
        local=world.inverted()
        if obj.type=='MESH':
            for vertex in obj.data.vertices:
                vertex.co=local@transform(world@vertex.co)
            obj.data.update()
        elif obj.type=='CURVE':
            for spline in obj.data.splines:
                for point in spline.bezier_points:
                    point.co=local@transform(world@point.co)


def fuse_mane(parts):
    """Unify touching cloud masses so seams do not read as separate disks."""
    prefixes=('Carved solid cloud lock','Swept sculpted hair lock','Cloud mane volume','Solid sculpted chest cloud','Solid cloud tail tuft')
    locks=[obj for obj in parts if obj.type=='MESH' and obj.name.startswith(prefixes)]
    bpy.ops.object.select_all(action='DESELECT')
    for obj in locks: obj.select_set(True)
    bpy.context.view_layer.objects.active=locks[0]
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    bpy.ops.object.join()
    mane=bpy.context.object
    mane.name='Unified sculpted cloud mane and cuffs'
    mane.data.remesh_voxel_size=.010
    bpy.ops.object.voxel_remesh()
    for polygon in mane.data.polygons: polygon.use_smooth=True
    smoothing=mane.modifiers.new('Gentle carved surface smoothing','SMOOTH')
    smoothing.factor=.45; smoothing.iterations=6
    return [obj for obj in bpy.context.scene.objects if obj.type in {'MESH','CURVE'}]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--views',nargs='+',default=['hero','front','side'])
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    output=args.output.resolve(); output.mkdir(parents=True,exist_ok=True)
    source=Path(__file__).read_text(encoding='utf-8')
    (output/'build_source.py').write_text(source,encoding='utf-8')
    bpy.data.texts.new('build_source.py').write(source)
    bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
    parts=build()
    compact_proportions(parts)
    parts=fuse_mane(parts)
    root=bpy.data.objects.new('DITING_STATIC_STUDY_not_approved',None)
    bpy.context.collection.objects.link(root)
    for part in parts: part.parent=root
    scene=bpy.context.scene
    scene.render.engine='CYCLES'; scene.cycles.device='CPU'; scene.cycles.samples=24
    scene.cycles.use_denoising=True
    scene.render.resolution_x=900; scene.render.resolution_y=1000; scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG'; scene.render.image_settings.color_mode='RGBA'
    scene.render.film_transparent=True
    scene.world.use_nodes=True
    scene.world.node_tree.nodes.get('Background').inputs[0].default_value=(.75,.76,.7,1)
    scene.world.node_tree.nodes.get('Background').inputs[1].default_value=.2
    bpy.ops.mesh.primitive_plane_add(size=200)
    ground=bpy.context.object; ground.name='Studio ground'
    ground.is_shadow_catcher=True
    ground.data.materials.append(material('Warm jade white backdrop',(.86,.84,.77),.7))
    scene.use_nodes=True
    compositor=scene.node_tree
    compositor.nodes.clear()
    layers=compositor.nodes.new('CompositorNodeRLayers')
    backdrop=compositor.nodes.new('CompositorNodeAlphaOver')
    backdrop.inputs[1].default_value=(3.3,3.1,2.7,1)
    compositor.links.new(layers.outputs['Image'],backdrop.inputs[2])
    composite=compositor.nodes.new('CompositorNodeComposite')
    compositor.links.new(backdrop.outputs['Image'],composite.inputs['Image'])
    for name,location,power,size,color in [('Key',(-3,-5,8),1000,5,(1,.93,.8)),('Fill',(5,-2,5),250,4,(.83,.94,1)),('Rim',(0,4,7),650,4,(1,.95,.84))]:
        bpy.ops.object.light_add(type='AREA',location=location)
        light=bpy.context.object; light.name=name; light.data.energy=power; light.data.shape='DISK';light.data.size=size;light.data.color=color
        light.rotation_euler=(Vector((0,0,2.15))-light.location).to_track_quat('-Z','Y').to_euler()
    bpy.ops.object.camera_add(location=(-6,-11,4.5))
    camera=bpy.context.object; camera.name='Study camera';camera.data.type='ORTHO';camera.data.ortho_scale=5.4;scene.camera=camera
    camera.rotation_euler=(Vector((-.12,0,2.15))-camera.location).to_track_quat('-Z','Y').to_euler()
    bpy.ops.wm.save_as_mainfile(filepath=str(output/'diting-static-study.blend'))
    bpy.ops.object.select_all(action='DESELECT')
    for part in parts: part.select_set(True)
    root.select_set(True)
    bpy.ops.export_scene.gltf(filepath=str(output/'diting-static-study.glb'),export_format='GLB',use_selection=True,export_animations=False)
    report={'stage':'static geometry study; NOT approved likeness; NOT rigged','seed':20261030,'blender':bpy.app.version_string,'objects':len(parts),'views':args.views,'ui_replaced':False}
    (output/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    cameras={'hero':(-6,-11,4.5),'front':(0,-12,4.1),'side':(11,-.3,4.2)}
    for view in args.views:
        camera.location=cameras[view]
        camera.rotation_euler=(Vector((-.12,0,2.15))-camera.location).to_track_quat('-Z','Y').to_euler()
        scene.render.filepath=str(output/f'{view}.png')
        bpy.ops.render.render(write_still=True)
        print('RENDERED '+str(output/f'{view}.png'),flush=True)


if __name__=='__main__':
    main()
