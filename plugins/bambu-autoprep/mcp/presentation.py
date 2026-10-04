"""Reference-matched layouts using the actual printable geometry and saved settings."""
from pathlib import Path
import tempfile
from xml.sax.saxutils import escape

from cad_preview import render_view

BG = '#F7F9F6'
INK = '#153F37'
MUTED = '#58716B'
TEAL = '#61AD99'
PALE = '#EAF3EE'


def metadata(value=None):
    value = {} if value is None else value
    if not isinstance(value, dict):
        raise ValueError('Presentation metadata must be an object')
    limits = {'title': 160, 'subtitle': 240, 'overview': 600,
              'requirements': 350, 'use_note': 500, 'use_heading': 100}
    if set(value) - (set(limits) | {'use_steps', 'guide_style'}):
        raise ValueError('Unknown presentation metadata field')
    for key, limit in limits.items():
        if key in value and (not isinstance(value[key], str) or len(value[key]) > limit):
            raise ValueError(f'{key} must be text of at most {limit} characters')
    steps = value.get('use_steps', [])
    if not isinstance(steps, list) or len(steps) > 4:
        raise ValueError('Supply at most four concise use steps')
    for step in steps:
        if isinstance(step, str) and len(step) <= 500:
            continue
        if isinstance(step, dict) and set(step) == {'heading', 'body'}:
            if all(isinstance(step[k], str) and len(step[k]) <= limit
                   for k, limit in [('heading', 100), ('body', 500)]):
                continue
        raise ValueError('A use step must be text or an object with heading and body')
    if value.get('guide_style', 'compact') not in ('compact', 'editorial'):
        raise ValueError('guide_style must be compact or editorial')
    return dict(value)


def font(size, bold=False):
    from PIL import ImageFont
    import matplotlib.font_manager as fm
    return ImageFont.truetype(fm.findfont(fm.FontProperties(
        family='DejaVu Sans', weight='bold' if bold else 'normal')), size)


def _wrapped(draw, value, width, face):
    lines = []
    for paragraph in value.splitlines() or ['']:
        line = ''
        for word in paragraph.split():
            candidate = (line + ' ' + word).strip()
            if draw.textlength(candidate, font=face) <= width:
                line = candidate
                continue
            if line:
                lines.append(line)
            line = ''
            for char in word:
                if draw.textlength(line + char, font=face) > width and line:
                    lines.append(line)
                    line = ''
                line += char
        lines.append(line)
    return lines


def text_block(draw, value, x, y, width, height, size, fill=INK, bold=False):
    for candidate in range(size, 14, -1):
        face = font(candidate, bold)
        lines = _wrapped(draw, value, width, face)
        leading = round(candidate*1.3)
        if len(lines)*leading <= height:
            for line in lines:
                draw.text((x, y), line, font=face, fill=fill)
                y += leading
            return y
    raise ValueError('Presentation text does not fit; use a shorter title or subtitle')


def render_poster(mesh, destination, details=None):
    from PIL import Image, ImageDraw
    info = metadata(details)
    canvas = Image.new('RGB', (1800, 1280), BG)
    draw = ImageDraw.Draw(canvas)
    title_bottom = text_block(draw, info.get('title', 'PRINTABLE MODEL').upper(),
                             75, 52, 1650, 135, 52, bold=True)
    subtitle = info.get('subtitle', 'Actual CAD geometry | Two views of the printable model')
    text_block(draw, subtitle, 75, title_bottom+8, 1650, 75, 28, MUTED)
    with tempfile.TemporaryDirectory() as tmp:
        for i, angle in enumerate((-65, 115)):
            path = Path(tmp) / f'view{i}.png'
            render_view(mesh, path, angle, size=780)
            with Image.open(path) as view:
                canvas.paste(view, (72+865*i, 246))
            draw.text((85+865*i, 1040), ('FRONT VIEW', 'REVERSE VIEW')[i], font=font(28, True), fill=INK)
            draw.text((85+865*i, 1085), 'Actual printable part. Colour is illustrative.', font=font(21), fill=MUTED)
    draw.line((75, 1155, 1725, 1155), fill='#D2E0D9', width=2)
    dimensions = ' × '.join(f'{float(v):.1f}' for v in mesh.extents) + ' mm | Model dimensions'
    draw.text((75, 1176), dimensions, font=font(27), fill=INK)
    draw.text((75, 1225), 'CAD render of actual geometry. Physical print, supports and toolpaths are not shown.', font=font(21), fill=MUTED)
    canvas.save(destination)


def _value(value, default='Vendor default'):
    if isinstance(value, list):
        return ', '.join(str(v) for v in value) if value else default
    return default if value is None or value == '' else str(value)


def _enabled(value):
    if isinstance(value, list):
        value = value[0] if value else None
    if str(value).lower() in ('true', '1', 'on'):
        return 'On'
    if str(value).lower() in ('false', '0', 'off'):
        return 'Off'
    return 'Vendor default'


def guide_data(summary):
    """Normalize both exporters; never describe recommendations as saved settings."""
    settings = summary.get('effective_process') or summary.get('recommended_settings') or {}
    profiles = summary.get('embedded_profiles') or {}
    hardware = summary.get('requested_hardware') or {}
    printer = profiles.get('printer_profile') or hardware.get('printer') or summary.get('machine_profile')
    nozzle = profiles.get('nozzle_mm') or hardware.get('nozzle_mm') or summary.get('nozzle_mm')
    filament = profiles.get('filament_profile') or hardware.get('filament') or summary.get('filament_profile')
    material = _value(filament, 'Confirm material').split(' @')[0]
    plate = _value(hardware.get('plate') or summary.get('plate'), 'Confirm plate')
    nozzle_text = f'{_value(nozzle)} mm' if nozzle is not None else 'Confirm nozzle'
    layer = _value(settings.get('layer_height'))
    if 'layer_height' in settings:
        layer += ' mm'
    walls = _value(settings.get('wall_loops'))
    infill = _value(settings.get('sparse_infill_density'))+' / '+_value(settings.get('sparse_infill_pattern'))
    shells = _value(settings.get('top_shell_layers'))+' / '+_value(settings.get('bottom_shell_layers'))
    supports = _enabled(settings.get('enable_support'))
    brim = _value(settings.get('brim_type')).replace('_', ' ')
    seam = _value(settings.get('seam_position')).replace('_', ' ')
    status = summary.get('status', 'unsliced')
    embedded = bool(summary.get('settings_embedded', status == 'sliced'))
    rows = [('Printer / nozzle', _value(printer, 'Confirm printer')+' / '+nozzle_text),
            ('Material', material), ('Build plate', plate), ('Layer height', layer),
            ('Walls', walls), ('Infill', infill), ('Top / bottom', shells),
            ('Supports', supports), ('Brim', brim), ('Seam', seam)]
    wide_rows = [('Printer / nozzle', rows[0][1]), ('Material / plate', material+' / '+plate),
                 ('Layer / walls / infill', layer+' / '+walls+' walls / '+infill),
                 ('Top / bottom layers', shells), ('Supports / brim', supports+' / '+brim), ('Seam', seam)]
    if not embedded:
        opening = 'Open '+project_name_placeholder()+' in Bambu Studio. This is a geometry-only file: choose matching hardware profiles and apply the recommendations in settings_summary.json before slicing.'
    else:
        opening = 'Open '+project_name_placeholder()+' in Bambu Studio as a PROJECT to load its saved settings. Keep the intended scale and orientation.'
    review = 'Confirm printer, nozzle, filament and plate. Choose the correct spool or AMS slot. If hardware or material changes, select matching profiles and slice again.'
    if status == 'sliced':
        final_step = ('Review the sliced plate', 'Inspect first-layer contact, walls, supports and the saved toolpaths. Slice again after any changes. Start the physical print manually only after review.')
        status_note = 'Sliced project: toolpaths are included. Review them in Bambu Studio before manually starting the print.'
    else:
        final_step = ('Slice plate, then review', 'Click Slice plate. Inspect the first layer, walls, supports and toolpaths. Start the physical print manually only after review.')
        status_note = ('Unsliced Bambu project: print settings are saved. Slice plate on your computer before printing.' if embedded else
                       'Geometry-only 3MF: settings are recommendations, not saved in this file. Apply them before slicing.')
    return {'rows': rows, 'wide_rows': wide_rows, 'embedded': embedded, 'status': status,
            'material': material, 'plate': plate, 'status_note': status_note,
            'steps': [('Open the project' if embedded else 'Open and apply settings', opening),
                      ('Confirm your equipment', review), final_step]}


def project_name_placeholder():
    return '{project_file}'


def create_guide(mesh, destination, summary, project_name, details=None):
    """Compact green two-page guide or white editorial three-page manual.

    Long task-specific text flows onto numbered continuation pages. The footer,
    paragraph and table measurements are shared to prevent clipping/overlap.
    """
    from reportlab.pdfgen import canvas
    from reportlab.lib.colors import HexColor
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Paragraph
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import matplotlib.font_manager as fm
    for face, weight in [('GuideSans', 'normal'), ('GuideSans-Bold', 'bold')]:
        if face not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(face, fm.findfont(fm.FontProperties(family='DejaVu Sans', weight=weight))))
    info = metadata(details)
    editorial = info.get('guide_style') == 'editorial'
    title = info.get('title') or 'Printable model'
    subtitle = info.get('subtitle') or 'Print and use guide | Actual printable geometry'
    overview = info.get('overview') or info.get('subtitle') or 'Use this model for the purpose described in your request. The illustrations show the actual geometry included in the download.'
    requirements = info.get('requirements') or 'The printed part or parts. Use additional hardware only when specified by the design.'
    use_steps = info.get('use_steps') or ['For an uploaded model with no usage description, assembly and use instructions require the design description.']
    use_steps = [(s['heading'], s['body']) if isinstance(s, dict) else
                 ('Use the model' if len(use_steps) == 1 else f'Use step {i+1}', s)
                 for i, s in enumerate(use_steps)]
    data = guide_data(summary)
    print_steps = [(h, b.replace(project_name_placeholder(), project_name)) for h, b in data['steps']]
    width, height = 595.28, 841.89
    ink, muted = HexColor(INK), HexColor(MUTED)
    paper = '#FFFFFF' if editorial else BG
    note_colour = '#F6ECD8' if editorial else PALE

    class NumberedCanvas(canvas.Canvas):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.frames = []
        def showPage(self):
            self.frames.append(dict(self.__dict__))
            self._startPage()
        def save(self):
            self.showPage()
            count = len(self.frames)
            for state in self.frames:
                self.__dict__.update(state)
                self.setStrokeColor(HexColor('#D2E0D9')); self.line(42, 40, 553, 40)
                self.setFillColor(muted); self.setFont('GuideSans', 7)
                self.drawString(42, 24, 'CAD illustrations. Physical print and fit have not been tested.')
                self.drawRightString(553, 24, f'{self._pageNumber} / {count}')
                super().showPage()
            super().save()

    c = NumberedCanvas(str(destination), pagesize=(width, height))
    c.setTitle(title+' - Print and use guide')
    c.setAuthor('3D Print')
    def paragraph(text, w, size=10, bold=False, colour=ink):
        style = ParagraphStyle('p', fontName='GuideSans-Bold' if bold else 'GuideSans',
                               fontSize=size, leading=size*1.38, textColor=colour)
        p = Paragraph(escape(str(text)), style)
        _, h = p.wrap(w, height*10)
        return p, h
    def para(text, x, top, w, size=10, bold=False, colour=ink):
        p, h = paragraph(text, w, size, bold, colour)
        if top-h < 53:
            raise ValueError('Guide text would overlap its footer')
        p.drawOn(c, x, top-h)
        return top-h
    def header(heading, sub=subtitle):
        c.setFillColor(HexColor(paper)); c.rect(0, 0, width, height, fill=1, stroke=0)
        c.setFillColor(muted); c.setFont('GuideSans-Bold', 7.5)
        c.drawString(42, 802, '3D PRINT / PRINT AND USE GUIDE')
        size = 25
        while paragraph(heading, 511, size, True)[1] > 92 and size > 17:
            size -= 1
        bottom = para(heading, 42, 780, 511, size, True)
        return para(sub, 42, bottom-8, 511, 10, colour=muted)-18
    def callout(text, top):
        p, h = paragraph(text, 483, 9)
        if top-h-24 < 53:
            raise ValueError('Guide note would overlap its footer')
        c.setFillColor(HexColor(note_colour)); c.roundRect(42, top-h-24, 511, h+24, 8, fill=1, stroke=0)
        p.drawOn(c, 56, top-h-12)
        return top-h-38
    def step_height(heading, body):
        return paragraph(heading, 477, 10, True)[1]+paragraph(body, 477, 9.5)[1]+19
    def step(number, heading, body, top):
        c.setFillColor(HexColor('#507E73' if editorial else INK)); c.circle(52, top-9, 10, fill=1, stroke=0)
        c.setFillColor(HexColor('#FFFFFF')); c.setFont('GuideSans-Bold', 9)
        c.drawCentredString(52, top-12, str(number))
        y = para(heading, 76, top, 477, 10, True)
        return para(body, 76, y-5, 477, 9.5)-14
    def ensure(top, needed, continuation):
        if top-needed < 58:
            c.showPage()
            return header(continuation, title+' | Continued')
        return top
    def steps(items, top, continuation):
        for i, (heading, body) in enumerate(items, 1):
            top = ensure(top, step_height(heading, body)+3, continuation)
            top = step(i, heading, body, top)
        return top
    def note(text, top, continuation):
        top = ensure(top, paragraph(text, 483, 9)[1]+30, continuation)
        return callout(text, top)
    def table(rows, x, top, w, ruled=False):
        label_w = w*(.41 if ruled else .40)
        for label, value in rows:
            size = 9 if ruled else 8.5
            h = max(paragraph(label, label_w-8, size)[1], paragraph(value, w-label_w, size, ruled)[1])
            para(label, x, top, label_w-8, size, colour=muted)
            para(value, x+label_w, top, w-label_w, size, ruled)
            top -= h+9
            if ruled:
                c.setStrokeColor(HexColor('#D2E0D9')); c.line(x, top+4, x+w, top+4)
        return top
    def table_height(rows, w, ruled=False):
        label_w = w*(.41 if ruled else .40)
        size = 9 if ruled else 8.5
        return sum(max(paragraph(k, label_w-8, size)[1], paragraph(v, w-label_w, size, ruled)[1])+9 for k, v in rows)
    def image(path, x, top, w, h):
        c.drawImage(ImageReader(str(path)), x, top-h, w, h, preserveAspectRatio=True, anchor='c', mask='auto')
    def pair(front, back, top, h=210):
        image(front, 42, top, 248, h); image(back, 305, top, 248, h)
        para('FRONT VIEW', 42, top-h-7, 248, 8.5, True)
        para('REVERSE VIEW', 305, top-h-7, 248, 8.5, True)
        return top-h-39

    default_note = 'Check the first physical print before use. Confirm material, dimensions and any fit requirements. No physical testing is claimed.'
    finish = 'Let the plate and model cool. Remove the print carefully, then remove supports, brim and loose strings if present. Inspect edges and weak areas; try fitted parts gently without forcing.'
    with tempfile.TemporaryDirectory() as tmp:
        front, back = Path(tmp)/'front.png', Path(tmp)/'back.png'
        render_view(mesh, front, size=620, background=paper)
        render_view(mesh, back, 115, size=620, background=paper)
        if editorial:
            y = header(title)
            y = callout(data['status_note'], y)
            y = pair(front, back, y, 222)
            y = para('How it works', 42, y, 511, 13, True)-8
            y = para(overview, 42, y, 511, 10)-20
            y = steps([('Check the size', 'The model dimensions are '+ ' × '.join(f'{float(v):.1f}' for v in mesh.extents)+' mm. Keep 100% scale for dimension-sensitive designs.'),
                       ('Keep the files together', 'Download the 3MF, printable model, preview PNG, settings summary and this PDF. The next page contains the print setup.')], y, 'Before printing')
            c.showPage()
            y = header('Your model. Ready to prepare.', 'The saved project and the settings to review before printing.')
            y = pair(front, back, y, 135)
            y = para('Bambu settings '+('included' if data['embedded'] else 'to apply'), 42, y, 511, 13, True)-12
            y = table(data['wide_rows'], 42, y, 511, True)-14
            y = steps(print_steps, y, 'Open, review and print')
            c.showPage()
            y = header(info.get('use_heading', 'Using the printed model'), title+' | Finish, assemble and use')
            y = pair(front, back, y, 210)
            y = para(finish, 42, y, 511, 9.5)-20
            y = steps(use_steps, y, 'Assemble and use')
            note(info.get('use_note', default_note), y, 'Use and care')
        else:
            y = header(title.upper())
            c.setFillColor(HexColor(PALE)); c.roundRect(42, y-53, 511, 53, 10, fill=1, stroke=0)
            for i, value in enumerate(mesh.extents):
                para(f'{float(value):.1f} mm', 58+167*i, y-9, 153, 16, True)
                para(('Width / X', 'Depth / Y', 'Height / Z')[i], 58+167*i, y-33, 150, 8.5, colour=muted)
            y -= 73
            block_h = max(238, table_height(data['rows'], 248)+25)
            image(front, 42, y, 245, min(block_h-18, 270))
            para('Actual printable geometry.', 42, y-block_h+12, 245, 8, colour=muted)
            para('PRINT SETUP'+(' INCLUDED' if data['embedded'] else ' / TO APPLY'), 305, y, 248, 11, True)
            table(data['rows'], 305, y-23, 248)
            y -= block_h+14
            y = para('OPEN, REVIEW, PRINT' if data['status']=='sliced' else 'OPEN, SLICE, PRINT', 42, y, 511, 12, True)-14
            y = steps(print_steps, y, 'Open, review and print')
            note(data['status_note']+' This plugin never sends or starts a physical print.', y, 'Project status')
            c.showPage()
            y = header(title.upper(), 'Use guide | '+info.get('use_heading', 'Finish, assemble and use'))
            top = y
            image(back, 42, top, 245, 260)
            y = para('WHAT YOU NEED', 310, y, 243, 11, True)-10
            y = para(requirements, 310, y, 243, 9.5)-20
            y = para('HOW IT WORKS', 310, y, 243, 11, True)-10
            y = para(overview, 310, y, 243, 9.5)-20
            y = para('SIZE AND MATERIAL', 310, y, 243, 11, True)-10
            size_text = ' × '.join(f'{float(v):.1f}' for v in mesh.extents)+' mm. '+data['material']+'. Dimensions describe the supplied geometry.'
            y = para(size_text, 310, y, 243, 9.5)
            y = min(y, top-260)-22
            y = ensure(y, 75, 'Finish, assemble and use')
            y = para('ASSEMBLE AND USE', 42, y, 511, 12, True)-12
            y = para(finish, 42, y, 511, 9.5)-18
            y = steps(use_steps, y, 'Assemble and use')
            note(info.get('use_note', default_note), y, 'Use and care')
        c.save()
