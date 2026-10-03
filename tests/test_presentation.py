"""Exercise actual rendered posters/PDFs and metadata/layout boundaries."""
from pathlib import Path
import sys
import json

import pytest
import trimesh
from PIL import Image
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'plugins/bambu-autoprep/mcp'))
from presentation import create_guide, metadata, render_poster


@pytest.mark.parametrize('style', ['compact', 'editorial'])
def test_illustrated_guides_have_actual_settings_and_usage(tmp_path, style):
    mesh = trimesh.creation.box([12, 24, 36])
    original = mesh.vertices.copy()
    summary = {'settings_embedded': True, 'recommended_settings': {
        'layer_height': .16, 'wall_loops': 4, 'sparse_infill_density': '25%',
        'sparse_infill_pattern': 'gyroid', 'enable_support': False},
        'requested_hardware': {'plate': 'Textured PEI Plate', 'filament': 'PLA'}}
    path = tmp_path/'guide.pdf'
    create_guide(mesh, path, summary, 'actual.3mf', {'title':'Desk holder', 'guide_style':style,
        'use_steps':['Place the holder on your desk.']})
    r = PdfReader(path)
    assert len(r.pages) == 2
    text = '\n'.join(p.extract_text() for p in r.pages)
    for value in ('actual.3mf', '0.16 mm', '25% / gyroid', 'Place the holder on your desk.', 'Physical print and fit have not been tested.'):
        assert value in text
    assert 'PRO' in text and 'manually' in text
    assert any('/FontFile2' in f.get_object()['/FontDescriptor'].get_object()
               for f in r.pages[0]['/Resources']['/Font'].values() if '/FontDescriptor' in f.get_object())
    assert (mesh.vertices == original).all()
    render_poster(mesh, tmp_path/'poster.png', {'title':'Desk holder'})
    with Image.open(tmp_path/'poster.png') as im:
        assert im.size == (1800,1280)
        assert im.getpixel((0,0)) == (247,249,246)


def test_long_use_guide_continues_and_invalid_metadata_rejected(tmp_path):
    mesh=trimesh.creation.box([10,10,10])
    path=tmp_path/'manual.pdf'
    create_guide(mesh,path,{},'model.3mf', {'use_steps':['Inspect the part.']*4})
    assert len(PdfReader(path).pages)==3
    assert '3 / 3' in PdfReader(path).pages[2].extract_text()
    for data in ({'guide_style':'unknown'}, {'use_steps':['step']*5}, {'use_steps':'bad'}, {'title':123}, {'unknown':'field'}):
        with pytest.raises(ValueError):
            metadata(data)
