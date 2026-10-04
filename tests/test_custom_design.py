from pathlib import Path
import json
import subprocess
import sys

import numpy as np
import pytest
import trimesh
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'plugins/bambu-autoprep/mcp'))
from design import build_design, export_cadquery

POT={'name':'Pencil pot','shape':{'type':'difference','children':[
 {'type':'cylinder','radius':22,'height':60,'translate':[0,0,30]},
 {'type':'cylinder','radius':19,'height':60,'translate':[0,0,33]}]}}


@pytest.mark.parametrize('shape',[
 {'type':'box','size':[10,20,30]},
 {'type':'sphere','radius':10},
 {'type':'ellipsoid','radii':[10,15,20]},
 {'type':'cylinder','radius':5,'height':20},
 {'type':'cone','radius':5,'height':20},
 {'type':'torus','major_radius':12,'minor_radius':3},
 {'type':'extrude','points':[[0,0],[20,0],[20,20],[0,20]],'holes':[[[5,5],[5,15],[15,15],[15,5]]],'height':4},
 {'type':'revolve','profile':[[0,0],[10,0],[10,20],[7,20],[7,3],[0,3],[0,0]]},
 {'type':'sweep','points':[[-1,-1],[1,-1],[1,1],[-1,1]],'path':[[0,0,0],[0,0,10],[5,0,15]]},
 {'type':'text','text':'BO','size':12,'height':2},
 {'type':'organic','blobs':[{'center':[0,0,0],'radii':[10,10,10]},{'center':[0,0,10],'radii':[8,8,8]}]},
 {'type':'intersection','children':[{'type':'sphere','radius':10},{'type':'box','size':[20,20,10]}]},
])
def test_general_geometry_operations(shape):
 mesh,report=build_design({'shape':shape})
 assert mesh.is_volume and mesh.is_watertight
 assert mesh.bounds[0,2]==pytest.approx(0)
 assert np.isfinite(mesh.vertices).all()
 assert report['watertight']


def test_custom_pot_has_actual_base_and_opening():
 mesh,_=build_design(POT)
 assert mesh.extents==pytest.approx([44,44,60])
 # Hollow pot volume: outer cylinder minus inner cavity with a 3 mm base.
 expected=np.pi*22**2*60-np.pi*19**2*57
 assert mesh.volume==pytest.approx(expected,rel=.004)
 assert len(mesh.split())==1


def test_real_text_fuses_to_base_and_holes_are_retained():
 plate={'shape':{'type':'union','children':[{'type':'box','size':[45,20,3],'translate':[20,4,1.5]},
  {'type':'text','text':'BO','size':12,'height':2,'translate':[0,0,2.8]}]}}
 mesh,_=build_design(plate)
 assert mesh.extents[2]==pytest.approx(4.8)
 assert len(mesh.split())==1
 text,_=build_design({'shape':{'type':'text','text':'O','size':12,'height':2}})
 assert text.euler_number==0  # Letter O's hole is real, not filled by triangulation.


def test_multipart_bed_layout():
 mesh,report=build_design({'parts':[{'type':'box','size':[20,30,10]},{'type':'cylinder','radius':10,'height':20}]})
 components=mesh.split()
 assert len(components)==2
 assert all(c.bounds[0,2]==pytest.approx(0) for c in components)
 assert components[1].bounds[0,0]-components[0].bounds[1,0]==pytest.approx(8)
 with pytest.raises(ValueError,match='multiple print plates'):
  build_design({'parts':[{'type':'box','size':[240,240,5]}]*2})


@pytest.mark.parametrize('spec',[
 {'shape':{'type':'execute','code':'anything'}},
 {'shape':{'type':'box','size':[float('nan'),10,10]}},
 {'shape':{'type':'box','size':[-1,10,10]}},
 {'shape':{'type':'extrude','points':[[0,0],[10,10],[0,10],[10,0]],'height':2}},
 {'shape':{'type':'difference','children':[{'type':'box','size':[10,10,10]}]*2}},
 {'shape':{'type':'mesh','vertices':[[0,0,0],[1,0,0],[0,1,0]],'faces':[[0,1,99]]*4}},
 {'shape':{'type':'box','size':[10,10,10],'file':'secret'}},
 {'shape':{'type':'torus','major_radius':5,'minor_radius':6}},
 {'shape':{'type':'text','text':'','size':12,'height':2}},
])
def test_invalid_designs_fail(spec):
 with pytest.raises(ValueError):
  build_design(spec)


def test_custom_cli_returns_print_package_without_text_guide(tmp_path):
 spec=tmp_path/'pot.json';spec.write_text(json.dumps(POT))
 out=tmp_path/'output'
 result=subprocess.run([sys.executable,str(ROOT/'plugins/bambu-autoprep/mcp/unsliced.py'),
  '--design',str(spec),'--output-dir',str(out),'--use','functional','--presentation',
  json.dumps({'title':'Pencil pot','use_steps':['Place on your desk and store pencils upright.']})],check=True,capture_output=True,text=True)
 report=json.loads(result.stdout)
 assert report['settings_embedded'] and not report['printer_started']
 assert not (out/'PRINT_GUIDE.md').exists()
 for key in ['model_file','three_mf','preview_png','instruction_pdf','settings_summary']:
  assert Path(report[key]).is_file()
 mesh=trimesh.load(report['three_mf'],force='mesh')
 assert mesh.is_volume and mesh.extents==pytest.approx([44,44,60])
 assert 'store pencils upright' in '\n'.join(p.extract_text() for p in PdfReader(report['instruction_pdf']).pages)


def test_full_cad_and_step_export(tmp_path):
 cq=pytest.importorskip('cadquery')
 shape=cq.Workplane('XY').box(50,30,8).edges('|Z').fillet(3).faces('>Z').workplane().hole(8)
 result=export_cadquery(shape,str(tmp_path))
 from server import load_mesh
 mesh=load_mesh(Path(result['model_file']))
 assert mesh.is_volume and len(mesh.split())==1
 assert mesh.extents==pytest.approx([50,30,8])
 assert load_mesh(Path(result['step_file'])).is_volume
