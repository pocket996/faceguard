"""Clean disconnected reconstruction specks and render fixed material guides."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

import bpy
import bmesh
from mathutils import Vector
import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scene', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--analysis-python', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(args.scene.resolve()))
    obj = next(o for o in bpy.context.scene.objects if o.name.startswith('Diting reconstructed'))
    edge_indices = np.empty(len(obj.data.edges) * 2, dtype=np.int32)
    obj.data.edges.foreach_get('vertices', edge_indices)
    np.savez(out / 'connectivity-input.npz', edges=edge_indices.reshape(-1, 2), count=len(obj.data.vertices))
    # SciPy stays in the external Python runtime, never imported into Blender.
    analysis = """
import json,sys,numpy as np
from pathlib import Path
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
p=Path(sys.argv[1]); a=np.load(p/'connectivity-input.npz'); e=a['edges']; n=int(a['count'])
g=coo_matrix((np.ones(len(e),np.uint8),(e[:,0],e[:,1])),shape=(n,n)).tocsr()
count,labels=connected_components(g,directed=False); sizes=np.bincount(labels)
keep=sizes[labels]>=300
np.save(p/'keep-vertices.npy',keep)
(p/'components.json').write_text(json.dumps({'components':int(count),'largest_component_sizes':sorted(sizes.tolist(),reverse=True)[:20],'removed_vertices':int((~keep).sum()),'threshold_vertices':300},indent=2),encoding='utf-8')
"""
    subprocess.run([str(args.analysis_python), '-c', analysis, str(out)], check=True)
    keep = np.load(out / 'keep-vertices.npy')
    before = len(obj.data.vertices)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    removed = [v for v in bm.verts if not keep[v.index]]
    bmesh.ops.delete(bm, geom=removed, context='VERTS')
    # Remove degenerate edges without changing the sculpture's silhouette.
    bmesh.ops.dissolve_degenerate(bm, dist=.000001, edges=list(bm.edges))
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    boundary_edges = sum(e.is_boundary for e in bm.edges)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()

    scene = bpy.context.scene
    camera = scene.camera
    target = Vector((0, 0, 1.9))
    clay = obj.data.materials[0]
    saved_materials = list(obj.data.materials)
    indices = np.empty(len(obj.data.polygons), dtype=np.int32)
    obj.data.polygons.foreach_get('material_index', indices)
    obj.data.polygons.foreach_set('material_index', np.zeros(len(indices), np.int32))
    scene.cycles.samples = 20
    scene.render.resolution_x = 840
    scene.render.resolution_y = 940
    views = {'left':(-9,0,2.6), 'right':(9,0,2.6), 'back':(0,9,2.6)}
    cameras = {}
    for view, location in views.items():
        camera.location = location
        camera.rotation_euler = (target-camera.location).to_track_quat('-Z','Y').to_euler()
        bpy.context.view_layer.update()
        cameras[view] = {'position':list(location), 'target':list(target), 'ortho_scale':camera.data.ortho_scale,
                         'resolution':[840,940]}
        scene.render.filepath = str(out / f'{view}-guide.png')
        bpy.ops.render.render(write_still=True)
    obj.data.polygons.foreach_set('material_index', indices)
    camera.location = (-5,-8,2.6)
    camera.rotation_euler = (target-camera.location).to_track_quat('-Z','Y').to_euler()
    scene.render.resolution_x = 1000
    scene.render.resolution_y = 1120
    source = bpy.data.texts.new('surface_refinement_source.py')
    source.write(Path(__file__).read_text(encoding='utf-8'))
    bpy.ops.wm.save_as_mainfile(filepath=str(out / 'diting-cleaned.blend'))
    report = json.loads((out/'components.json').read_text())
    report.update(vertices_before=before, vertices_after=len(obj.data.vertices),
                  faces_after=len(obj.data.polygons), boundary_edges_after=boundary_edges,
                  watertight=(boundary_edges==0), cameras=cameras, rigged=False,
                  production_asset_replaced=False)
    (out/'cleanup-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')


if __name__ == '__main__':
    main()
