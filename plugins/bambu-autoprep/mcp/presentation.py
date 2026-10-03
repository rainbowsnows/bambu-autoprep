"""Reference-inspired CAD posters and illustrated PDF guides from actual geometry."""
from pathlib import Path
import math
import textwrap
import tempfile
from xml.sax.saxutils import escape

BG = '#F7F9F6'
INK = '#153F37'
MUTED = '#58716B'
TEAL = '#61AD99'
PALE = '#EAF3EE'


def metadata(value=None):
    value = value or {}
    if not isinstance(value, dict):
        raise ValueError('Presentation metadata must be an object')
    allowed = {'title', 'subtitle', 'use_steps', 'use_note', 'guide_style'}
    if set(value) - allowed:
        raise ValueError('Unknown presentation metadata field')
    for key in ('title', 'subtitle', 'use_note'):
        if key in value and (not isinstance(value[key], str) or len(value[key]) > 500):
            raise ValueError(f'{key} must be text of at most 500 characters')
    steps = value.get('use_steps', [])
    if not isinstance(steps, list) or len(steps) > 4 or any(not isinstance(s, str) or len(s) > 500 for s in steps):
        raise ValueError('Supply at most four use steps, each at most 500 characters')
    if value.get('guide_style', 'compact') not in ('compact', 'editorial'):
        raise ValueError('guide_style must be compact or editorial')
    return value


def render_view(mesh, path, azimuth=-65):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    import numpy as np
    fig = plt.figure(figsize=(6, 6), facecolor=BG)
    ax = fig.add_axes([0, 0, 1, 1], projection='3d', facecolor=BG)
    # Use every triangle: face sampling can create false holes in a preview.
    ax.add_collection3d(Poly3DCollection(mesh.triangles, facecolors=TEAL,
        linewidths=0, shade=True, zsort='average'))
    low, high = mesh.bounds
    center = (low + high) / 2
    half = max(float(np.max(high-low)) * .56, .001)
    for setter, c in zip((ax.set_xlim, ax.set_ylim, ax.set_zlim), center):
        setter(c-half, c+half)
    ax.set_box_aspect((1, 1, 1))
    ax.set_proj_type('ortho')
    ax.view_init(elev=26, azim=azimuth)
    ax.set_axis_off()
    fig.savefig(path, dpi=150, facecolor=BG)
    plt.close(fig)


def font(size, bold=False):
    from PIL import ImageFont
    import matplotlib.font_manager as fm
    return ImageFont.truetype(fm.findfont(fm.FontProperties(family='DejaVu Sans', weight='bold' if bold else 'normal')), size)


def fitted_text(draw, xy, value, max_width, size, fill=INK, bold=False):
    while size > 15 and draw.textlength(value, font=font(size, bold)) > max_width:
        size -= 1
    draw.text(xy, value, font=font(size, bold), fill=fill)


def render_poster(mesh, destination, details=None):
    from PIL import Image, ImageDraw
    info = metadata(details)
    canvas = Image.new('RGB', (1800, 1280), BG)
    draw = ImageDraw.Draw(canvas)
    fitted_text(draw, (75, 55), info.get('title', 'PRINTABLE MODEL').upper(), 1650, 52, bold=True)
    subtitle = info.get('subtitle', 'Actual CAD geometry | Two views of the printable model')
    fitted_text(draw, (75, 140), subtitle, 1650, 28, MUTED)
    with tempfile.TemporaryDirectory() as tmp:
        for i, angle in enumerate((-65, 115)):
            path = Path(tmp) / f'view{i}.png'
            render_view(mesh, path, angle)
            with Image.open(path) as view:
                canvas.paste(view.resize((800, 800)), (65 + 865*i, 220))
            draw.text((85 + 865*i, 1040), ('FRONT VIEW', 'REVERSE VIEW')[i], font=font(28, True), fill=INK)
            draw.text((85 + 865*i, 1085), 'Same printable geometry. Colour is illustrative.', font=font(21), fill=MUTED)
    draw.line((75, 1155, 1725, 1155), fill='#D2E0D9', width=2)
    dimensions = ' × '.join(f'{float(v):.1f}' for v in mesh.extents) + ' mm | Model dimensions'
    draw.text((75, 1176), dimensions, font=font(27), fill=INK)
    draw.text((75, 1225), 'CAD render of actual geometry. Physical print, supports and toolpaths are not shown.', font=font(21), fill=MUTED)
    canvas.save(destination)


def create_guide(mesh, destination, summary, project_name, details=None):
    """Two A4 pages: real model/settings, then finishing and model-specific use."""
    from reportlab.pdfgen import canvas
    from reportlab.lib.colors import HexColor
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Paragraph
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import matplotlib.font_manager as fm
    for face, weight in [('GuideSans', 'normal'), ('GuideSans-Bold', 'bold')]:
        pdfmetrics.registerFont(TTFont(face, fm.findfont(fm.FontProperties(family='DejaVu Sans', weight=weight))))
    info = metadata(details)
    editorial = info.get('guide_style') == 'editorial'
    title = info.get('title', 'Printable model')
    use_steps = info.get('use_steps') or ['Use only for the purpose stated in your model request. For an uploaded model with no usage information, assembly and use instructions need the design description.']
    pages = 3 if len(use_steps) > 2 or sum(map(len, use_steps)) > 400 else 2
    c = canvas.Canvas(str(destination), pagesize=(595.28, 841.89))
    c.setTitle(title + ' - Print and use guide')
    width, height = 595.28, 841.89
    ink, muted = HexColor(INK), HexColor(MUTED)
    style = ParagraphStyle('body', fontName='GuideSans', fontSize=10, leading=14, textColor=ink)
    def para(text, x, top, w, size=10, bold=False):
        s = ParagraphStyle('p', parent=style, fontName='GuideSans-Bold' if bold else 'GuideSans', fontSize=size, leading=size*1.4)
        p = Paragraph(escape(str(text)), s)
        _, h = p.wrap(w, height)
        p.drawOn(c, x, top-h)
        return top-h
    def header(page, subtitle):
        c.setFillColor(HexColor('#FFFFFF' if editorial else BG)); c.rect(0, 0, width, height, fill=1, stroke=0)
        c.setFillColor(muted); c.setFont('GuideSans-Bold', 8)
        c.drawString(42, 800, '3D PRINT / PRINT AND USE GUIDE' if editorial else '3D PRINT')
        bottom = para(title if editorial else title.upper(), 42, 777, 511, 25, True)
        para(subtitle, 42, bottom-10, 511, 10)
        c.setStrokeColor(HexColor('#D2E0D9')); c.line(42, 40, 553, 40)
        c.setFillColor(muted); c.setFont('GuideSans', 8)
        c.drawString(42, 24, 'CAD illustrations. Physical print and fit have not been tested.')
        c.drawRightString(553, 24, f'{page} / {pages}')
    def callout(text, top):
        color = '#F6ECD8' if editorial else PALE
        p = Paragraph(escape(text), style); _, h = p.wrap(475, 1000)
        c.setFillColor(HexColor(color)); c.roundRect(42, top-h-22, 511, h+22, 8, fill=1, stroke=0)
        p.drawOn(c, 60, top-h-11)
        return top-h-22
    def step(number, heading, body, top):
        c.setFillColor(HexColor('#507E73' if editorial else INK)); c.circle(53, top-10, 10, fill=1, stroke=0)
        c.setFillColor(HexColor('#FFFFFF')); c.setFont('GuideSans-Bold', 10); c.drawCentredString(53, top-13.5, str(number))
        bottom = para(heading, 76, top, 475, 11, True)
        return para(body, 76, bottom-5, 475)-19
    settings = summary.get('recommended_settings') or summary.get('effective_process') or {}
    profiles = summary.get('embedded_profiles', {})
    hardware = summary.get('requested_hardware', {})
    rows = [('Layer height', str(settings.get('layer_height', 'Vendor default')) + ' mm'),
            ('Walls', str(settings.get('wall_loops', 'Vendor default'))),
            ('Infill', str(settings.get('sparse_infill_density', 'Vendor default')) + ' / ' + str(settings.get('sparse_infill_pattern', 'Vendor default'))),
            ('Top / bottom', str(settings.get('top_shell_layers', 'Vendor default')) + ' / ' + str(settings.get('bottom_shell_layers', 'Vendor default'))),
            ('Supports', ('On' if settings['enable_support'] else 'Off') if 'enable_support' in settings else 'Vendor default'),
            ('Brim', str(settings.get('brim_type', 'Vendor default')).replace('_', ' ')),
            ('Plate', str(hardware.get('plate') or summary.get('plate', 'See project'))),
            ('Material', str(profiles.get('filament_profile') or hardware.get('filament') or summary.get('filament_profile', 'See project')))]
    # Fixed regions with wrapped text prevent overlap for long profile identifiers.
    header(1, info.get('subtitle', 'Open the project. Review the setup. Slice and print manually.'))
    c.setFillColor(HexColor(PALE)); c.roundRect(42, 646, 511, 53, 10, fill=1, stroke=0)
    for i, value in enumerate(mesh.extents):
        para(f'{float(value):.1f} mm', 58+167*i, 685, 153, 16, True)
        para(('Width / X', 'Depth / Y', 'Height / Z')[i], 58+167*i, 663, 150, 9)
    with tempfile.TemporaryDirectory() as tmp:
        view = Path(tmp)/'actual.png'; render_view(mesh, view)
        c.drawImage(ImageReader(str(view)), 42, 400, 245, 245, preserveAspectRatio=True, mask='auto')
        para('PRINT SETUP' + (' INCLUDED' if summary.get('settings_embedded') else ' / REVIEW'), 305, 628, 248, 11, True)
        y = 599
        for label, value in rows:
            para(label, 305, y, 90, 9)
            bottom = para(value, 399, y, 154, 9)
            y = min(y-24, bottom-7)
        para('Actual model. Illustrative teal colour.', 42, 399, 245, 8)
        para('Time and material estimates are available after slicing. No estimates are invented.', 305, min(y, 393), 248, 9)
        para('OPEN, SLICE, PRINT', 42, 357, 511, 13, True)
        y = step(1, 'Open as a project', f'Open {project_name} in Bambu Studio as a PROJECT to load its saved settings. Geometry-only import discards settings.', 328)
        y = step(2, 'Confirm your equipment', 'Check printer, nozzle, filament and plate. Choose the correct spool or AMS slot. Changing hardware or material requires matching profiles and a fresh slice.', y)
        y = step(3, 'Slice and review before starting', 'Review scale, orientation, first-layer contact, walls and supports. Slice plate and inspect the toolpaths. Start the physical print manually.', y)
        callout('Prepared digitally. The model image shows geometry, not sliced supports or toolpaths. This plugin never sends or starts a physical print.', min(y, 120))
        c.showPage()
        header(2, 'Finish the print, check fit, then use it for its intended purpose.')
        c.drawImage(ImageReader(str(view)), 160, 443, 275, 275, preserveAspectRatio=True, mask='auto')
        para('ACTUAL PRINTABLE MODEL', 42, 441, 511, 11, True)
        para('The same geometry is shown here; no extra parts or assembly mechanisms are invented.', 42, 422, 511, 9)
        y = step(1, 'Cool and remove', 'Let the plate and model cool. Remove the model carefully, then remove any supports, brim and loose strings. Check edges and small details.', 382)
        y = step(2, 'Inspect the finished part', 'Check dimensions, cracks and weak areas. For fitted parts, try the fit gently without forcing. The first physical print still needs inspection.', y)
        if pages == 3:
            callout('Inspect the finished print before following the use and assembly steps on the next page.', min(y, 122))
            c.showPage()
            header(3, 'Model-specific use and assembly')
            y = 675
        for i, body in enumerate(use_steps):
            y = step(i+3, 'Use the model' if len(use_steps)==1 else f'Use step {i+1}', body, y)
        # Longer task-specific instructions continue into a compact note region only when they fit.
        if y < 105:
            raise ValueError('Use instructions exceed the guide layout; shorten the four use steps')
        callout(info.get('use_note', 'No physical testing is claimed. Confirm material and intended-use suitability before using the print. Follow any model-specific assembly and care instructions.'), min(y, 122))
        c.save()
