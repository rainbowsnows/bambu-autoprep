from pathlib import Path
import io
import json
import subprocess
import sys
import zipfile

import numpy as np
import pytest
import trimesh
from PIL import Image
from defusedxml import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'plugins/bambu-autoprep/mcp'))
import server
from unsliced import CORE, REL, export_unsliced


def test_unsliced_roundtrip_without_bambu(tmp_path, monkeypatch):
    # Initialize font discovery before blocking subprocesses used by slicing.
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot
    def forbidden(*args, **kwargs):
        raise AssertionError('Offline export must not invoke Bambu or subprocesses')
    monkeypatch.setattr(server, 'find_bambu_executable', forbidden)
    monkeypatch.setattr(server.subprocess, 'run', forbidden)
    model = tmp_path / 'source.stl'
    mesh = trimesh.creation.box([12.3, 24.6, 8.2])
    mesh.apply_translation([17, 13, 50])
    mesh.export(model)
    original = model.read_bytes()
    result = server.prepare_unsliced_3mf(str(model), str(tmp_path / 'package'), use='functional')
    assert result['status'] == 'unsliced' and result['requires_manual_slicing']
    assert not result['settings_embedded'] and not result['printer_started']
    assert model.read_bytes() == original
    with zipfile.ZipFile(result['three_mf']) as archive:
        assert archive.testzip() is None
        assert not any(n.endswith(('.gcode', '.config')) for n in archive.namelist())
        root = ET.fromstring(archive.read('3D/3dmodel.model'))
        assert root.attrib['unit'] == 'millimeter'
        assert root.find(f'{{{CORE}}}build/{{{CORE}}}item').attrib['objectid'] == '1'
        links = ET.fromstring(archive.read('_rels/.rels'))
        for link in links.findall(f'{{{REL}}}Relationship'):
            assert link.attrib['Target'].lstrip('/') in archive.namelist()
        with Image.open(io.BytesIO(archive.read('Metadata/thumbnail.png'))) as image:
            image.verify()
    loaded = trimesh.load(result['three_mf'], force='mesh')
    assert loaded.is_watertight and loaded.is_volume
    assert np.allclose(loaded.extents, [12.3, 24.6, 8.2], atol=1e-5)
    assert loaded.bounds[0, 2] == pytest.approx(0)
    assert len(loaded.faces) == len(mesh.faces)
    settings = json.loads(Path(result['settings_summary']).read_text())
    assert settings['recommended_settings']['wall_loops'] == 4
    assert settings['settings_embedded'] is False
    assert 'Slice plate' in Path(result['print_guide']).read_text()
    with pytest.raises(ValueError, match='no sliced G-code'):
        server.validate_sliced_3mf(Path(result['three_mf']))


def test_offline_cli_generates_ghost(tmp_path):
    result = subprocess.run([sys.executable, str(ROOT / 'plugins/bambu-autoprep/mcp/unsliced.py'),
                             '--template', 'ghost', '--output-dir', str(tmp_path)],
                            capture_output=True, text=True, check=True)
    report = json.loads(result.stdout)
    loaded = trimesh.load(report['three_mf'], force='mesh')
    assert loaded.is_watertight and loaded.is_volume
    assert loaded.extents[2] == pytest.approx(40)
    for key in ('model_file', 'three_mf', 'preview_png', 'settings_summary', 'print_guide'):
        assert Path(report[key]).is_file()


def test_unsliced_rejects_bad_input_and_output(tmp_path):
    model = tmp_path / 'source.stl'
    mesh = trimesh.creation.box([10, 10, 10])
    mesh.export(model)
    for kwargs in ({'output_name': '../escape.3mf'}, {'nozzle_mm': float('nan')}, {'use': 'unknown'}):
        with pytest.raises(ValueError):
            server.prepare_unsliced_3mf(str(model), str(tmp_path / 'out'), **kwargs)
    protected = tmp_path / 'printable_model.stl'
    mesh.export(protected)
    with pytest.raises(ValueError, match='overwrite'):
        server.prepare_unsliced_3mf(str(protected), str(tmp_path))
    opened = trimesh.Trimesh(vertices=mesh.vertices, faces=mesh.faces[:2])
    with pytest.raises(ValueError, match='closed'):
        export_unsliced(opened, tmp_path / 'invalid.3mf')
