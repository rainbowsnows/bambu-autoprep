from pathlib import Path
import json
import sys
import zipfile
import pytest
import trimesh
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'plugins/bambu-autoprep/mcp'))
import server
from geometry import build_model

@pytest.mark.parametrize('template',['ghost','cable-holder','phone-stand'])
def test_real_geometry(template,tmp_path):
    result=server.generate_model(template,str(tmp_path))
    mesh=trimesh.load(result['model_file'],force='mesh')
    assert mesh.is_watertight and mesh.is_volume
    assert len(mesh.split())==1
    assert mesh.bounds[0,2]==pytest.approx(0)
    with Image.open(result['preview_png']) as im:
        assert im.width>400 and im.height>400
    assert result['analysis']['bed_contact_area_mm2']>0


def test_invalid_dimensions():
    with pytest.raises(ValueError): build_model('ghost',{'height':float('nan')})
    with pytest.raises(ValueError): build_model('cable-holder',{'cable_diameter':100})


def test_no_fuzzy_nozzle_substitution(tmp_path):
    (tmp_path/'machine').mkdir()
    (tmp_path/'machine/wrong.json').write_text(json.dumps({'name':'Bambu Lab P2S 0.2 nozzle'}))
    with pytest.raises(FileNotFoundError):
        server.find_profile_file(tmp_path,'machine','Bambu Lab P2S 0.4 nozzle')


def test_inheritance_cycle(tmp_path):
    a=tmp_path/'a.json';b=tmp_path/'b.json'
    a.write_text('{"name":"a","inherits":"b"}')
    b.write_text('{"name":"b","inherits":"a"}')
    with pytest.raises(ValueError,match='Cyclic'):server.flatten_profile(a,tmp_path)

@pytest.mark.parametrize('overrides',[{'machine_start_gcode':'x'},{'layer_height':-1},{'brim_width':float('inf')},{'wall_loops':{}}])
def test_override_boundary(overrides):
    with pytest.raises(ValueError): server.safe_apply_process_overrides({},overrides)


def test_unsliced_export_rejected(tmp_path):
    p=tmp_path/'bad.3mf'
    with zipfile.ZipFile(p,'w') as z:
        z.writestr('[Content_Types].xml','x');z.writestr('3D/3dmodel.model','x')
    with pytest.raises(ValueError,match='no sliced G-code'):server.validate_sliced_3mf(p)

@pytest.fixture
def installation(tmp_path,monkeypatch):
    profiles=tmp_path/'BBL'
    data={'machine':{'name':'Test Printer 0.4 nozzle','nozzle_diameter':['0.4'],'printable_area':['0x0','256x0','256x256','0x256'],'printable_height':'256'},
          'process':{'name':'Test Standard','layer_height':'0.2','wall_loops':'2','compatible_printers':['Test Printer 0.4 nozzle']},
          'filament':{'name':'Test PLA','compatible_printers':['Test Printer 0.4 nozzle']}}
    for category,profile in data.items():
        (profiles/category).mkdir(parents=True)
        (profiles/category/'profile.json').write_text(json.dumps(profile))
    exe=tmp_path/'fixture-slicer'
    exe.write_text('#!/usr/bin/env python3\nimport sys,zipfile\np=sys.argv[sys.argv.index("--export-3mf")+1]\nwith zipfile.ZipFile(p,"w") as z:\n z.writestr("[Content_Types].xml","<Types/>")\n z.writestr("3D/3dmodel.model","<model/>")\n z.writestr("Metadata/plate_1.gcode","; fixture only\\nG1 X0 Y0")\n')
    exe.chmod(0o755)
    cfg={'bambu_studio_path':str(exe),'profile_root':str(profiles),'defaults':{'machine_profile':'Test Printer 0.4 nozzle','process_profile_hint':'Test Standard','filament_profile':'Test PLA'}}
    monkeypatch.setattr(server,'load_config',lambda:cfg)
    model=tmp_path/'input.stl';trimesh.creation.box([10,10,10]).export(model)
    return exe,model


def test_complete_package_without_printer(installation,tmp_path):
    exe,model=installation
    out=tmp_path/'out'
    result=server.prepare_print(str(model),str(out))
    assert result['ok'] and not result['printer_started']
    assert result['preview_source']=='input_geometry_not_toolpaths'
    for key in ('three_mf','preview_png','print_guide','settings_summary'): assert Path(result[key]).is_file()
    summary=json.loads(Path(result['settings_summary']).read_text())
    assert summary['effective_process']['wall_loops']=='3'
    exe.write_text('#!/usr/bin/env python3\n')
    with pytest.raises(RuntimeError):server.prepare_print(str(model),str(out))


def test_oversize_model(installation,tmp_path):
    exe,model=installation
    trimesh.creation.box([300,10,10]).export(model)
    with pytest.raises(ValueError,match='build volume'):server.prepare_print(str(model),str(tmp_path/'out'))


def test_output_traversal(installation,tmp_path):
    _,model=installation
    with pytest.raises(ValueError): server.prepare_3mf(str(model),str(tmp_path),'x','y','z',output_name='../escape.3mf')
