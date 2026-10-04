"""Report exporters (Epic 16: Export - PDF, Excel, CSV).

All three render the same format-neutral document produced by reports/builders.py.
"""

import csv
import io
import re
from pathlib import Path

from django.utils import timezone

ACCENT = '#7c3aed'
ACCENT_LIGHT = '#f3eefe'
MUTED = '#6b6375'
INK = '#1f1a2e'

_FONT_CACHE = {}


def _register_fonts():
    """Prefer a Unicode TTF (₹, accented names, Indian scripts render) over Helvetica,
    falling back silently when none can be loaded."""
    if _FONT_CACHE:
        return _FONT_CACHE['regular'], _FONT_CACHE['bold']

    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    candidates = [
        ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'),
        ('C:/Windows/Fonts/arial.ttf', 'C:/Windows/Fonts/arialbd.ttf'),
        ('C:/Windows/Fonts/segoeui.ttf', 'C:/Windows/Fonts/segoeuib.ttf'),
        ('/System/Library/Fonts/Supplemental/Arial.ttf', '/System/Library/Fonts/Supplemental/Arial Bold.ttf'),
    ]
    for regular_path, bold_path in candidates:
        if Path(regular_path).exists():
            try:
                pdfmetrics.registerFont(TTFont('ReportSans', regular_path))
                pdfmetrics.registerFont(TTFont('ReportSans-Bold', bold_path if Path(bold_path).exists() else regular_path))
                _FONT_CACHE.update(regular='ReportSans', bold='ReportSans-Bold')
                return 'ReportSans', 'ReportSans-Bold'
            except Exception:  # noqa: BLE001 - try the next candidate
                continue
    _FONT_CACHE.update(regular='Helvetica', bold='Helvetica-Bold')
    return 'Helvetica', 'Helvetica-Bold'


def _cell_text(value):
    if value is None:
        return ''
    if isinstance(value, float):
        return f'{value:,.2f}'
    if isinstance(value, int):
        return f'{value:,}'
    return str(value)


def _escape(text):
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


# ------------------------------------------------------------------ PDF

def to_pdf(document):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    regular, bold = _register_fonts()
    widest = max([len(s.get('columns', [])) for s in document.get('sections', [])] or [0])
    pagesize = landscape(A4) if widest > 6 else A4
    buffer = io.BytesIO()
    margin = 16 * mm
    doc = SimpleDocTemplate(
        buffer, pagesize=pagesize, leftMargin=margin, rightMargin=margin, topMargin=margin, bottomMargin=margin,
        title=document.get('title', 'Report'), author='Creativo AI',
    )
    width = pagesize[0] - 2 * margin

    styles = {
        'title': ParagraphStyle('title', fontName=bold, fontSize=20, leading=24, textColor=colors.HexColor(INK)),
        'subtitle': ParagraphStyle('subtitle', fontName=regular, fontSize=10, leading=14, textColor=colors.HexColor(MUTED)),
        'h2': ParagraphStyle('h2', fontName=bold, fontSize=13, leading=17, textColor=colors.HexColor(INK), spaceBefore=6),
        'desc': ParagraphStyle('desc', fontName=regular, fontSize=9, leading=12, textColor=colors.HexColor(MUTED)),
        'cell': ParagraphStyle('cell', fontName=regular, fontSize=8, leading=10, alignment=TA_LEFT, textColor=colors.HexColor(INK)),
        'head': ParagraphStyle('head', fontName=bold, fontSize=8, leading=10, textColor=colors.HexColor(ACCENT)),
        'kpi_label': ParagraphStyle('kpi_label', fontName=regular, fontSize=8, leading=10, textColor=colors.HexColor(MUTED)),
        'kpi_value': ParagraphStyle('kpi_value', fontName=bold, fontSize=15, leading=19, textColor=colors.HexColor(INK)),
        'kpi_hint': ParagraphStyle('kpi_hint', fontName=regular, fontSize=7, leading=9, textColor=colors.HexColor(MUTED)),
    }

    story = [
        Paragraph(_escape(document.get('title', 'Report')), styles['title']),
        Spacer(1, 3),
        Paragraph(_escape(f'{document.get("subtitle", "")} · Generated {timezone.localtime():%d %b %Y %H:%M}'), styles['subtitle']),
        Spacer(1, 12),
    ]

    kpis = document.get('kpis', [])
    if kpis:
        per_row = 3 if pagesize == A4 else 4
        cells = []
        for kpi in kpis:
            block = [Paragraph(_escape(kpi['label']), styles['kpi_label']),
                     Paragraph(_escape(_cell_text(kpi['value'])), styles['kpi_value'])]
            if kpi.get('hint'):
                block.append(Paragraph(_escape(kpi['hint']), styles['kpi_hint']))
            cells.append(block)
        while len(cells) % per_row:
            cells.append('')
        rows = [cells[i:i + per_row] for i in range(0, len(cells), per_row)]
        kpi_table = Table(rows, colWidths=[width / per_row] * per_row)
        kpi_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor(ACCENT_LIGHT)),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.white),
            ('INNERGRID', (0, 0), (-1, -1), 4, colors.white),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 7), ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ]))
        story += [kpi_table, Spacer(1, 14)]

    for section in document.get('sections', []):
        story.append(Paragraph(_escape(section['title']), styles['h2']))
        if section.get('description'):
            story.append(Paragraph(_escape(section['description']), styles['desc']))
        story.append(Spacer(1, 5))
        columns = section.get('columns', [])
        rows = section.get('rows', [])
        if not rows:
            story += [Paragraph('No data for this period.', styles['desc']), Spacer(1, 10)]
            continue
        data = [[Paragraph(_escape(str(c)), styles['head']) for c in columns]]
        for row in rows:
            data.append([Paragraph(_escape(_cell_text(v)), styles['cell']) for v in row])
        # Wider share for text-heavy columns (topics, links, errors).
        weights = []
        for index, column in enumerate(columns):
            sample = max((len(_cell_text(r[index])) for r in rows[:50] if index < len(r)), default=0)
            weights.append(max(min(max(sample, len(str(column))), 60), 6))
        total = sum(weights) or 1
        table = Table(data, colWidths=[width * w / total for w in weights], repeatRows=1)
        style = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(ACCENT_LIGHT)),
            ('LINEBELOW', (0, 0), (-1, 0), 0.8, colors.HexColor(ACCENT)),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]
        for index in range(1, len(data)):
            if index % 2 == 0:
                style.append(('BACKGROUND', (0, index), (-1, index), colors.HexColor('#faf8fe')))
        table.setStyle(TableStyle(style))
        story += [table, Spacer(1, 14)]

    def _footer(canvas, doc_):
        canvas.saveState()
        canvas.setFont(regular, 7)
        canvas.setFillColor(colors.HexColor(MUTED))
        canvas.drawString(margin, 9 * mm, document.get('generated_for', ''))
        canvas.drawRightString(pagesize[0] - margin, 9 * mm, f'Page {doc_.page}')
        canvas.restoreState()

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buffer.getvalue()


# ------------------------------------------------------------------ Excel

def _sheet_name(title, used):
    name = re.sub(r'[\[\]\*\?/\\:]', ' ', title)[:31].strip() or 'Sheet'
    base, n = name, 2
    while name in used:
        suffix = f' ({n})'
        name, n = base[:31 - len(suffix)] + suffix, n + 1
    used.add(name)
    return name


def to_xlsx(document):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    workbook = Workbook()
    summary = workbook.active
    summary.title = 'Summary'
    used = {'Summary'}
    header_fill = PatternFill('solid', fgColor='F3EEFE')
    header_font = Font(bold=True, color='7C3AED')

    summary['A1'] = document.get('title', 'Report')
    summary['A1'].font = Font(bold=True, size=14)
    summary['A2'] = document.get('subtitle', '')
    summary['A3'] = f'Generated {timezone.localtime():%d %b %Y %H:%M}'
    summary['A5'], summary['B5'], summary['C5'] = 'Metric', 'Value', 'Note'
    for cell in (summary['A5'], summary['B5'], summary['C5']):
        cell.fill, cell.font = header_fill, header_font
    for offset, kpi in enumerate(document.get('kpis', []), start=6):
        summary.cell(row=offset, column=1, value=kpi['label'])
        summary.cell(row=offset, column=2, value=kpi['value'])
        summary.cell(row=offset, column=3, value=kpi.get('hint', ''))
    summary.column_dimensions['A'].width = 32
    summary.column_dimensions['B'].width = 22
    summary.column_dimensions['C'].width = 40

    for section in document.get('sections', []):
        sheet = workbook.create_sheet(_sheet_name(section['title'], used))
        columns = section.get('columns', [])
        sheet.append(columns)
        for cell in sheet[1]:
            cell.fill, cell.font = header_fill, header_font
            cell.alignment = Alignment(vertical='top', wrap_text=True)
        for row in section.get('rows', []):
            sheet.append([v if isinstance(v, (int, float)) or v is None else str(v) for v in row])
        for index, column in enumerate(columns, start=1):
            longest = max([len(str(column))] + [len(str(r[index - 1])) for r in section.get('rows', [])[:200] if index - 1 < len(r)])
            sheet.column_dimensions[get_column_letter(index)].width = min(max(longest + 2, 10), 60)
        sheet.freeze_panes = 'A2'

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


# ------------------------------------------------------------------ CSV

def to_csv(document):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([document.get('title', 'Report')])
    writer.writerow([document.get('subtitle', '')])
    writer.writerow([])
    writer.writerow(['Metric', 'Value', 'Note'])
    for kpi in document.get('kpis', []):
        writer.writerow([kpi['label'], kpi['value'], kpi.get('hint', '')])
    for section in document.get('sections', []):
        writer.writerow([])
        writer.writerow([section['title']])
        writer.writerow(section.get('columns', []))
        for row in section.get('rows', []):
            writer.writerow(['' if v is None else v for v in row])
    # UTF-8 BOM so Excel opens non-ASCII text (₹, names) correctly.
    return ('\ufeff' + buffer.getvalue()).encode('utf-8')
