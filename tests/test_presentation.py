"""Exercise actual rendered posters/PDFs and metadata/layout boundaries."""
from pathlib import Path
import sys
import json

import pytest
import trimesh
import numpy as np
from PIL import Image
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'plugins/bambu-autoprep/mcp'))
from presentation import create_guide, metadata, render_poster, guide_data
from cad_preview import render_view


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
    assert len(r.pages) == (3 if style == 'editorial' else 2)
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
    steps = [{'heading':f'Inspection {i}', 'body':('Inspect the actual part and check fit without forcing. '*8)+f' End {i}.'} for i in range(4)]
    create_guide(mesh,path,{},'model.3mf', {'use_steps':steps})
    pages = PdfReader(path).pages
    assert len(pages) >= 3
    text = '\n'.join(p.extract_text() for p in pages)
    for i in range(4):
        assert f'End {i}.' in text
    assert f'{len(pages)} / {len(pages)}' in pages[-1].extract_text()
    for data in ({'guide_style':'unknown'}, {'use_steps':['step']*5}, {'use_steps':'bad'}, {'title':123}, {'unknown':'field'}):
        with pytest.raises(ValueError):
            metadata(data)


def test_hidden_surfaces_do_not_depend_on_triangle_order(tmp_path):
    from design import build_design
    mesh, _ = build_design({'shape': {'type':'difference', 'children':[
        {'type':'box','size':[40,40,30]},
        {'type':'box','size':[34,34,30],'translate':[0,0,3]}]}})
    shuffled = trimesh.Trimesh(mesh.vertices, mesh.faces[::-1], process=False)
    render_view(mesh, tmp_path/'a.png', size=240)
    render_view(shuffled, tmp_path/'b.png', size=240)
    a = np.asarray(Image.open(tmp_path/'a.png')).astype(int)
    b = np.asarray(Image.open(tmp_path/'b.png')).astype(int)
    assert np.max(np.abs(a-b)) <= 1
    # The object fills most of the frame and is not an empty or hole-riddled render.
    occupied = np.any(a != [247,249,246], axis=2)
    assert .35 < occupied.mean() < .85


def test_guide_distinguishes_sliced_unsliced_and_geometry_only(tmp_path):
    base = {'effective_process': {'enable_support':'0'}, 'machine_profile':'Actual Printer',
            'nozzle_mm':.6, 'filament_profile':'PETG', 'plate':'Smooth PEI Plate'}
    for status, embedded in [('sliced',True), ('unsliced',True), ('unsliced',False)]:
        summary = dict(base, status=status, settings_embedded=embedded)
        data = guide_data(summary)
        assert dict(data['rows'])['Supports'] == 'Off'
        assert '0.6 mm' in dict(data['rows'])['Printer / nozzle']
        path=tmp_path/f'{status}-{embedded}.pdf'
        create_guide(trimesh.creation.box([10,20,30]), path, summary, 'actual.3mf')
        text='\n'.join(p.extract_text() for p in PdfReader(path).pages)
        if not embedded:
            assert 'not saved in this file' in text
            assert 'as a PROJECT to load its saved settings' not in text
        elif status == 'sliced':
            assert 'toolpaths are included' in text
            assert 'Click Slice plate' not in text
        else:
            assert 'Click Slice plate' in text


@pytest.mark.parametrize('style', ['compact','editorial'])
def test_long_headings_and_descriptions_are_wrapped(tmp_path, style):
    path=tmp_path/'long.pdf'
    details={'title':'Large storage organizer for a collection of small objects and craft supplies',
             'subtitle':'A purpose-built arrangement of compartments with a separate lid and an easy-to-clean flat base.',
             'overview':'The object keeps small pieces separated. '*12,
             'requirements':'Use the printed base and lid. '*10,
             'guide_style':style,'use_steps':[{'heading':'Final check', 'body':'Set on a flat surface. FINAL-MARKER'}]}
    create_guide(trimesh.creation.box([60,80,20]), path, {}, 'actual.3mf', details)
    assert 'FINAL-MARKER' in '\n'.join(p.extract_text() for p in PdfReader(path).pages)
    render_poster(trimesh.creation.box([60,80,20]), tmp_path/'long.png', details)
