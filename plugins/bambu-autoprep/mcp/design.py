"""General, bounded declarative CAD/mesh generation; never executes supplied code."""
from pathlib import Path
import json
import math
import numpy as np
import trimesh

MAX_NODES = 256
MAX_FACES = 250_000


def number(value, low=-1000, high=1000):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'Expected a finite number between {low} and {high}')
    return float(value)


def vector(value, length=3, positive=False):
    if not isinstance(value, list) or len(value) != length:
        raise ValueError(f'Expected a {length}-element vector')
    return [number(v, .01 if positive else -1000, 1000) for v in value]


def points(value, width=2):
    if not isinstance(value, list) or not 3 <= len(value) <= 2000:
        raise ValueError('Expected 3 to 2000 profile points')
    return np.array([vector(p, width) for p in value])


def closed(mesh):
    if not isinstance(mesh, trimesh.Trimesh) or not len(mesh.faces) or len(mesh.faces) > MAX_FACES:
        raise ValueError('Design is empty or exceeds mesh complexity limit')
    mesh.remove_unreferenced_vertices()
    trimesh.repair.fix_normals(mesh, multibody=True)
    if not np.isfinite(mesh.vertices).all() or not mesh.is_watertight or not mesh.is_volume:
        raise ValueError('Design must be a finite, closed, positive-volume mesh')
    return mesh


def _polygon(node):
    from shapely.geometry import Polygon
    holes = node.get('holes', [])
    if not isinstance(holes, list) or len(holes) > 100:
        raise ValueError('Too many polygon holes')
    polygon = Polygon(points(node['points']), [points(h) for h in holes])
    if not polygon.is_valid or polygon.area <= 0:
        raise ValueError('Sketch polygon is self-intersecting, empty or invalid')
    return polygon


def _text(node):
    from matplotlib.textpath import TextPath
    from matplotlib.font_manager import FontProperties
    from shapely.geometry import Polygon
    text = node.get('text')
    if not isinstance(text, str) or not text.strip() or len(text) > 80:
        raise ValueError('Text must contain 1 to 80 characters')
    path = TextPath((0, 0), text, size=number(node.get('size', 12), .5, 200),
                    prop=FontProperties(family='DejaVu Sans', weight='bold'))
    shape = None
    for ring in path.to_polygons():
        p = Polygon(ring)
        if not p.is_valid:
            p = p.buffer(0)
        if p.area:
            shape = p if shape is None else shape.symmetric_difference(p)
    if shape is None or shape.is_empty:
        raise ValueError('Text has no printable outlines')
    polygons = [shape] if shape.geom_type == 'Polygon' else list(shape.geoms)
    return trimesh.util.concatenate([trimesh.creation.extrude_polygon(p,
        number(node.get('height', 1), .05, 100), engine='earcut') for p in polygons])


def _organic(node):
    from skimage.measure import marching_cubes
    blobs = node.get('blobs', [])
    if not isinstance(blobs, list) or not 1 <= len(blobs) <= 40:
        raise ValueError('Organic shape needs 1 to 40 ellipsoidal blobs')
    centers = np.array([vector(b['center']) for b in blobs])
    radii = np.array([vector(b['radii'], positive=True) for b in blobs])
    low = (centers - radii*2).min(axis=0); high = (centers + radii*2).max(axis=0)
    resolution = int(number(node.get('resolution', 64), 24, 96))
    grid = np.meshgrid(*(np.linspace(a, b, resolution) for a, b in zip(low, high)), indexing='ij')
    field = np.zeros((resolution,)*3)
    for center, radius in zip(centers, radii):
        q = sum(((grid[i]-center[i])/radius[i])**2 for i in range(3))
        field += np.exp(-2*q)
    verts, faces, _, _ = marching_cubes(field, level=number(node.get('level', .3), .05, .9),
                                      spacing=(high-low)/(resolution-1))
    # marching_cubes winding is fixed by the closed-volume validator below.
    return trimesh.Trimesh(vertices=verts+low, faces=faces, process=True)


def _node(node, budget, depth=0):
    if not isinstance(node, dict) or depth > 16:
        raise ValueError('Invalid or deeply nested design node')
    budget[0] += 1
    if budget[0] > MAX_NODES:
        raise ValueError('Design exceeds operation limit')
    kind = node.get('type')
    fields = {
        'box': {'size'}, 'sphere': {'radius'}, 'ellipsoid': {'radii'},
        'cylinder': {'radius','height'}, 'cone': {'radius','height'},
        'torus': {'major_radius','minor_radius'},
        'extrude': {'points','holes','height'}, 'revolve': {'profile'},
        'sweep': {'points','holes','path'}, 'text': {'text','size','height'},
        'organic': {'blobs','resolution','level'},
        'mesh': {'vertices','faces'},
        'union': {'children'}, 'difference': {'children'}, 'intersection': {'children'},
    }
    if kind not in fields or set(node)-fields[kind]-{'type','translate','rotate','scale'}:
        raise ValueError('Unknown design operation or parameter')
    if kind == 'box':
        mesh = trimesh.creation.box(vector(node['size'], positive=True))
    elif kind in ('sphere','ellipsoid'):
        mesh = trimesh.creation.icosphere(subdivisions=3,
            radius=number(node.get('radius', 1), .01, 1000))
        if kind == 'ellipsoid':
            mesh.apply_scale(vector(node['radii'], positive=True))
    elif kind in ('cylinder','cone'):
        method = trimesh.creation.cylinder if kind == 'cylinder' else trimesh.creation.cone
        mesh = method(radius=number(node['radius'], .01, 1000), height=number(node['height'], .01, 1000), sections=64)
    elif kind == 'torus':
        major = number(node['major_radius'], .01, 1000); minor = number(node['minor_radius'], .01, 1000)
        if minor >= major:
            raise ValueError('Torus minor radius must be smaller than major radius')
        mesh = trimesh.creation.torus(major_radius=major, minor_radius=minor, major_sections=64, minor_sections=32)
    elif kind == 'extrude':
        mesh = trimesh.creation.extrude_polygon(_polygon(node), number(node['height'], .01, 1000), engine='earcut')
    elif kind == 'revolve':
        profile = points(node['profile'])
        if (profile[:,0] < 0).any():
            raise ValueError('Revolved radii must be nonnegative')
        mesh = trimesh.creation.revolve(profile, sections=96)
    elif kind == 'sweep':
        mesh = trimesh.creation.sweep_polygon(_polygon(node), points(node['path'], 3), engine='earcut')
    elif kind == 'text':
        mesh = _text(node)
    elif kind == 'organic':
        mesh = _organic(node)
    elif kind == 'mesh':
        vertices = points(node['vertices'],3)
        faces = node['faces']
        if not isinstance(faces,list) or not 4 <= len(faces) <= MAX_FACES:
            raise ValueError('Invalid triangle count')
        if any(not isinstance(f,list) or len(f)!=3 or any(type(i)!=int or not 0 <= i < len(vertices) for i in f) for f in faces):
            raise ValueError('Invalid triangle indices')
        mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=True)
    else:
        children = node.get('children', [])
        if not isinstance(children,list) or not 2 <= len(children) <= 100:
            raise ValueError('Boolean operations need 2 to 100 children')
        meshes = [_node(c, budget, depth+1) for c in children]
        mesh = getattr(trimesh.boolean, kind)(meshes, engine='manifold')
    mesh = closed(mesh)
    if 'scale' in node:
        mesh.apply_scale(vector(node['scale'], positive=True))
    if 'rotate' in node:
        angles = np.deg2rad(vector(node['rotate']))
        mesh.apply_transform(trimesh.transformations.euler_matrix(*angles, axes='sxyz'))
    if 'translate' in node:
        mesh.apply_translation(vector(node['translate']))
    return closed(mesh)


def build_design(spec):
    """Generate any design expressible in this DSL; complex CAD uses host Python/CadQuery."""
    if not isinstance(spec,dict) or set(spec)-{'version','name','shape','parts','minimum_feature_mm'}:
        raise ValueError('Unknown design specification field')
    if spec.get('version',1) != 1 or ('shape' in spec) == ('parts' in spec):
        raise ValueError('Use version 1 and exactly one of shape or parts')
    if len(json.dumps(spec, allow_nan=False)) > 2_000_000:
        raise ValueError('Design specification exceeds size limit')
    if not isinstance(spec.get('name','Custom model'),str) or len(spec.get('name',''))>100:
        raise ValueError('Model name must be text of at most 100 characters')
    if 'minimum_feature_mm' in spec:
        number(spec['minimum_feature_mm'], .01, 100)
    budget = [0]
    if 'shape' in spec:
        mesh = _node(spec['shape'], budget)
        mesh.apply_translation([0,0,-mesh.bounds[0,2]])
    else:
        parts = spec['parts']
        if not isinstance(parts,list) or not 1 <= len(parts) <= 30:
            raise ValueError('Supply 1 to 30 part shapes')
        placed=[]; x=0.; y=0.; row=0.
        for part in parts:
            m=_node(part,budget)
            w,d,h=m.extents
            if max(w,d,h)>250:
                raise ValueError('Part exceeds standard print envelope; do not autoscale')
            if x+w>250:
                x=0.;y+=row+8.;row=0.
            if y+d>250:
                raise ValueError('Parts need multiple print plates; prepare separate packages')
            m.apply_translation([x-m.bounds[0,0],y-m.bounds[0,1],-m.bounds[0,2]])
            placed.append(m);x+=w+8.;row=max(row,d)
        mesh=trimesh.util.concatenate(placed)
    closed(mesh)
    if (mesh.extents>1000).any():
        raise ValueError('Model too large; specify intended dimensions')
    return mesh, {'name':spec.get('name','Custom model'), 'units':'mm', 'watertight':True,
        'connected_components':len(mesh.split()), 'dimensions_mm':mesh.extents.tolist(),
        'operations':budget[0], 'minimum_feature_mm_declared':spec.get('minimum_feature_mm'),
        'limitations':'Declared feature size is not a measured wall-thickness guarantee; fit/strength need review.'}


def generate_custom_model(design: dict, output_dir: str, presentation: dict | None = None) -> dict:
    """Create STL and actual preview from custom CAD/mesh spec, beyond preset templates."""
    from presentation import render_poster, metadata
    from server import analyze_model
    details=metadata(presentation)
    mesh, report=build_design(design)
    details.setdefault('title',report['name'])
    out=Path(output_dir).expanduser().resolve();out.mkdir(parents=True,exist_ok=True)
    model=out/'custom_model.stl';preview=out/'model_preview.png'
    mesh.export(model);render_poster(mesh,preview,details)
    (out/'design.json').write_text(json.dumps(design,indent=2))
    return {'model_file':str(model),'preview_png':str(preview),'report':report,
        'analysis':analyze_model(str(model)),'printer_started':False}


def export_cadquery(shape, output_dir):
    """Host-Python helper for unrestricted task-specific CAD; accepts an object, never code."""
    import cadquery as cq
    from server import load_mesh
    out=Path(output_dir).expanduser().resolve();out.mkdir(parents=True,exist_ok=True)
    if not isinstance(shape,(cq.Workplane,cq.Shape)):
        raise ValueError('Expected a CadQuery Workplane or Shape')
    stl=out/'custom_model.stl';step=out/'custom_model.step'
    cq.exporters.export(shape,str(stl),tolerance=.05,angularTolerance=.1)
    closed(load_mesh(stl))
    cq.exporters.export(shape,str(step))
    return {'model_file':str(stl),'step_file':str(step),'printer_started':False}
