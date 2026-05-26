from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import re


def texto_a_docx(texto: str, output_path: str):
    doc = Document()

    # Márgenes
    for section in doc.sections:
        section.top_margin = Cm(2.5)
        section.bottom_margin = Cm(2.5)
        section.left_margin = Cm(3)
        section.right_margin = Cm(2.5)

    # Estilo base
    style = doc.styles['Normal']
    style.font.name = 'Arial'
    style.font.size = Pt(11)
    style.paragraph_format.space_after = Pt(8)
    style.paragraph_format.line_spacing = Pt(14)

    lineas = texto.strip().split('\n')

    for linea in lineas:
        linea = linea.strip()
        if not linea:
            doc.add_paragraph()
            continue

        # Detectar viñeta (-, *, •, ❖, ✓)
        viñeta = re.match(r'^[-*•❖✓✔►]\s+(.+)', linea)
        # Detectar numerado (1. 2. etc)
        numerado = re.match(r'^\d+\.\s+(.+)', linea)
        # Detectar título de punto del orden del día (1.\tTítulo)
        titulo_punto = re.match(r'^(\d+)\.\t(.+)', linea)

        if titulo_punto:
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(12)
            run = p.add_run(f"{titulo_punto.group(1)}.\t{titulo_punto.group(2)}")
            run.bold = True
            run.font.size = Pt(11)

        elif viñeta:
            p = doc.add_paragraph(style='List Bullet')
            p.paragraph_format.left_indent = Cm(1.5)
            p.paragraph_format.space_after = Pt(4)
            aplicar_formato_inline(p, viñeta.group(1))

        elif numerado:
            p = doc.add_paragraph(style='List Number')
            p.paragraph_format.left_indent = Cm(1.5)
            p.paragraph_format.space_after = Pt(4)
            aplicar_formato_inline(p, numerado.group(1))

        else:
            p = doc.add_paragraph()
            p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            p.paragraph_format.first_line_indent = Cm(1.25)
            aplicar_formato_inline(p, linea)

    doc.save(output_path)


def aplicar_formato_inline(p, texto):
    # Detectar **negrita**
    partes = re.split(r'\*\*(.+?)\*\*', texto)
    for i, parte in enumerate(partes):
        if not parte:
            continue
        run = p.add_run(parte)
        run.font.name = 'Arial'
        run.font.size = Pt(11)
        if i % 2 == 1:
            run.bold = True
