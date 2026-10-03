from pathlib import Path
import json
import sys
import zipfile
import pytest
import trimesh

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'plugins/bambu-autoprep/mcp'))
import server
from bambu_project import TEMPLATE


def test_native_project_keeps_vendor_and_applies_settings(tmp_path):
    model = tmp_path / 'input.stl'
    trimesh.creation.box([20, 30, 40]).export(model)
    result = server.prepare_unsliced_3mf(str(model), str(tmp_path / 'package'), use='functional')
    assert result['settings_embedded'] and result['requires_manual_slicing']
    assert result['printer_started'] is False
    with zipfile.ZipFile(TEMPLATE) as template:
        base = json.loads(template.read('Metadata/project_settings.config'))
    with zipfile.ZipFile(result['three_mf']) as archive:
        data = json.loads(archive.read('Metadata/project_settings.config'))
        assert not any(n.endswith('.gcode') for n in archive.namelist())
        assert data['printer_settings_id'] == 'Bambu Lab P2S 0.4 nozzle'
        assert data['filament_settings_id'] == ['Bambu PLA Basic @BBL P2S']
        assert data['curr_bed_type'] == 'Textured PEI Plate'
        assert data['wall_loops'] == '4'
        assert data['sparse_infill_density'] == '25%'
        assert data['sparse_infill_pattern'] == 'gyroid'
        for key in ('machine_start_gcode', 'machine_end_gcode', 'nozzle_temperature',
                    'filament_flow_ratio', 'machine_max_acceleration_x'):
            assert data[key] == base[key]
    mesh = trimesh.load(result['three_mf'], force='mesh')
    assert mesh.is_watertight and mesh.is_volume
    assert mesh.extents == pytest.approx([20, 30, 40])
    assert mesh.bounds[0, 2] == pytest.approx(0)
    assert mesh.bounds[:, :2].mean(axis=0) == pytest.approx([128, 128])
    summary = json.loads(Path(result['settings_summary']).read_text())
    assert summary['settings_embedded']
    assert summary['embedded_profiles']['effective_settings']['wall_loops'] == '4'


@pytest.mark.parametrize('choices', [{'filament': 'PETG'}, {'nozzle_mm': 0.6}, {'printer': 'Bambu Lab A1'}])
def test_no_silent_hardware_substitution(tmp_path, choices):
    model = tmp_path / 'input.stl'
    trimesh.creation.box([10, 10, 10]).export(model)
    with pytest.raises(ValueError, match='does not match template'):
        server.prepare_unsliced_3mf(str(model), str(tmp_path / 'package'), **choices)


def test_native_project_rejects_oversize(tmp_path):
    model = tmp_path / 'input.stl'
    trimesh.creation.box([270, 10, 10]).export(model)
    with pytest.raises(ValueError, match='build volume'):
        server.prepare_unsliced_3mf(str(model), str(tmp_path / 'package'))


def test_vendor_include_fragments_are_preserved(tmp_path):
    (tmp_path / 'parent.json').write_text(json.dumps({'name': 'parent', 'wall_loops': '2'}))
    (tmp_path / 'fragment.json').write_text(json.dumps({'name': 'fragment', 'machine_start_gcode': '; vendor code'}))
    child = tmp_path / 'child.json'
    child.write_text(json.dumps({'name': 'child', 'inherits': 'parent', 'include': ['fragment'], 'wall_loops': '3'}))
    result = server.flatten_profile(child, tmp_path)
    assert result['machine_start_gcode'] == '; vendor code'
    assert result['wall_loops'] == '3'
    assert result['name'] == 'child'
    assert 'inherits' not in result and 'include' not in result
