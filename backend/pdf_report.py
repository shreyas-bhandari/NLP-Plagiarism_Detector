"""PDF report generator for VeriText AI.

Produces a polished, 3-page executive report:
  Page 1 — Executive result
  Page 2 — Detected similarities (evidence)
  Page 3 — How VeriText works + technical details
"""
import io
import copy

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, white
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from nlp_engine import MODEL_NAME, EMBEDDING_SIZE, SEMANTIC_THRESHOLD

from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, PageBreak,
    Table, TableStyle, HRFlowable, KeepTogether,
)

PAGE_W, PAGE_H = A4
MARGIN = 20 * mm

# ---------- palette ----------
INK = HexColor('#0f172a')          # near-black slate
PRIMARY = HexColor('#3730a3')      # indigo
PRIMARY_DARK = HexColor('#2e2a8a')
ACCENT = HexColor('#6366f1')       # violet
LIGHT = HexColor('#f1f5f9')        # slate-100
CARD_BG = HexColor('#ffffff')
BORDER = HexColor('#e2e8f0')
TEXT_MUTED = HexColor('#64748b')
TEXT_BODY = HexColor('#334155')

HIGH_COLOR = HexColor('#15803d')      # green
HIGH_BG = HexColor('#ecfdf5')
MOD_COLOR = HexColor('#b45309')       # amber
MOD_BG = HexColor('#fffbeb')
LOW_COLOR = HexColor('#b91c1c')       # red
LOW_BG = HexColor('#fef2f2')


def _score_color(score):
    if score >= 70:
        return HIGH_COLOR, HIGH_BG
    if score >= 50:
        return MOD_COLOR, MOD_BG
    return LOW_COLOR, LOW_BG


# ---------- styles ----------
def st(name, **kw):
    base = dict(fontName='Helvetica', fontSize=10, leading=14, textColor=TEXT_BODY)
    base.update(kw)
    return ParagraphStyle(name, **base)


S_TITLE = st('title', fontName='Helvetica-Bold', fontSize=27, leading=32,
             textColor=INK, alignment=TA_LEFT)
S_SUBTITLE = st('subtitle', fontSize=13, leading=18, textColor=TEXT_MUTED)
S_H2 = st('h2', fontName='Helvetica-Bold', fontSize=15, leading=20,
          textColor=PRIMARY_DARK, spaceAfter=6)
S_H3 = st('h3', fontName='Helvetica-Bold', fontSize=11, leading=15,
          textColor=INK, spaceAfter=4)
S_BODY = st('body', fontSize=9.5, leading=14, spaceAfter=5)
S_SMALL = st('small', fontSize=8, leading=11, textColor=TEXT_MUTED)
S_SMALL_B = st('smallb', fontName='Helvetica-Bold', fontSize=8, leading=11,
               textColor=TEXT_MUTED)
S_SCORE = st('score', fontName='Helvetica-Bold', fontSize=38, leading=42,
             textColor=PRIMARY_DARK)
S_LABEL = st('label', fontName='Helvetica-Bold', fontSize=13, leading=17,
             textColor=INK)
S_META = st('meta', fontSize=9, leading=13, textColor=TEXT_MUTED)
S_CARD_NUM = st('cardNum', fontName='Helvetica-Bold', fontSize=20, leading=24,
                textColor=PRIMARY_DARK)
S_CARD_LBL = st('cardLbl', fontSize=8.5, leading=11, textColor=TEXT_MUTED)
S_EVIDENCE_SCORE = st('evScore', fontName='Helvetica-Bold', fontSize=12,
                      leading=15, textColor=INK)
S_DOC_LABEL = st('docLabel', fontName='Helvetica-Bold', fontSize=8,
                 leading=11, textColor=TEXT_MUTED)
S_QUOTE = st('quote', fontSize=10, leading=15, textColor=INK)
S_PIPE = st('pipe', fontName='Helvetica-Bold', fontSize=9, leading=13,
            textColor=PRIMARY_DARK, alignment=TA_CENTER)
S_TECH = st('tech', fontSize=8.5, leading=12, textColor=TEXT_BODY)
S_DISCLAIMER = st('disclaimer', fontSize=8, leading=11, textColor=TEXT_MUTED)


def _decorate(canvas, doc):
    """Header + footer drawn on every page."""
    canvas.saveState()
    # Header band
    canvas.setFillColor(PRIMARY)
    canvas.rect(0, PAGE_H - 14 * mm, PAGE_W, 14 * mm, stroke=0, fill=1)
    canvas.setFillColor(white)
    canvas.setFont('Helvetica-Bold', 15)
    canvas.drawString(MARGIN, PAGE_H - 9 * mm, 'VeriText AI')
    canvas.setFont('Helvetica', 9)
    canvas.drawRightString(PAGE_W - MARGIN, PAGE_H - 9 * mm,
                           'Semantic Similarity Report')
    canvas.setFillColor(HexColor('#818cf8'))
    canvas.rect(0, PAGE_H - 14.6 * mm, PAGE_W, 0.6 * mm, stroke=0, fill=1)

    # Footer
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN, 14 * mm, PAGE_W - MARGIN, 14 * mm)
    canvas.setFillColor(TEXT_MUTED)
    canvas.setFont('Helvetica', 7.5)
    total = getattr(doc, '_total_pages', 1)
    canvas.drawString(MARGIN, 10 * mm,
                      'Similarity does not prove plagiarism. Results should be reviewed by a human.')
    canvas.drawRightString(PAGE_W - MARGIN, 10 * mm, f'Page {doc.page} of {total}')
    canvas.restoreState()


def _badge_table(score, label_text, kind='score'):
    color, bg = _score_color(score)
    inner = [
        [Paragraph(f'{score}%', st('bscore', fontName='Helvetica-Bold',
                                     fontSize=15 if kind == 'score' else 12,
                                     leading=18, textColor=color))],
        [Paragraph(label_text, st('blbl', fontSize=7.5, leading=10,
                                  textColor=color, fontName='Helvetica-Bold'))],
    ]
    t = Table(inner, colWidths=[None])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), bg),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 7 if kind == 'score' else 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7 if kind == 'score' else 5),
        ('ROUNDEDCORNERS', [6, 6, 6, 6]),
        ('BOX', (0, 0), (-1, -1), 0.5, color),
    ]))
    return t


def _metric_card(number, label_text):
    inner = [
        [Paragraph(number, S_CARD_NUM)],
        [Paragraph(label_text, S_CARD_LBL)],
    ]
    t = Table(inner, colWidths=[None])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), LIGHT),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LINEBEFORE', (0, 0), (0, -1), 3, PRIMARY),
    ]))
    return t


def _quote_box(doc_label, quote):
    inner = [
        [Paragraph(doc_label, S_DOC_LABEL)],
        [Paragraph(quote, S_QUOTE)],
    ]
    t = Table(inner, colWidths=[None])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), LIGHT),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('BOX', (0, 0), (-1, -1), 0.7, BORDER),
    ]))
    return t


def build_pdf(output_path, data):
    score = float(data.get('similarity_score', 0))
    label = data.get('label', 'LOW SIMILARITY')
    counts = data.get('counts', {})
    coverage = data.get('coverage', {})
    matches = data.get('matches', []) or []
    passages = data.get('passages', []) or []
    para = data.get('paragraph_similarity', {}) or {}
    technical = data.get('technical', {}) or {}
    filename_a = (data.get('document_a') or {}).get('name', 'Document A')
    filename_b = (data.get('document_b') or {}).get('name', 'Document B')
    created_at = data.get('created_at', '')

    story = []

    # ================= PAGE 1 — EXECUTIVE RESULT =================
    story.append(Spacer(1, 1 * mm))
    story.append(Paragraph('VeriText AI', S_TITLE))
    story.append(Spacer(1, 1 * mm))
    story.append(Paragraph('Semantic Similarity Report', S_SUBTITLE))
    story.append(Spacer(1, 2 * mm))
    story.append(HRFlowable(width='100%', thickness=1, color=BORDER))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(
        f'<font name="Helvetica-Bold" size=10 color="#1e293b">{filename_a}</font> '
        f'<font name="Helvetica-Bold" size=10 color="#6366f1">&#8594;</font> '
        f'<font name="Helvetica-Bold" size=10 color="#1e293b">{filename_b}</font>',
        S_SUBTITLE,
    ))
    if created_at:
        story.append(Paragraph(f'Report generated: {created_at[:16]}', S_META))
        story.append(Spacer(1, 1 * mm))

    # Hero result card
    score_color, score_bg = _score_color(score)
    hero_inner = [
        [Paragraph('Similarity Result', st('hr1', fontSize=9, leading=12,
                                           textColor=TEXT_MUTED))],
        [Paragraph(f'{score}%', S_SCORE)],
        [Paragraph(label, S_LABEL)],
        [Paragraph(data.get('explanation', ''), S_META)],
    ]
    hero = Table(hero_inner, colWidths=[None])
    hero.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), LIGHT),
        ('LEFTPADDING', (0, 0), (-1, -1), 16),
        ('RIGHTPADDING', (0, 0), (-1, -1), 16),
        ('TOPPADDING', (0, 0), (-1, -1), 11),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 11),
        ('LINEBEFORE', (0, 0), (0, -1), 4, PRIMARY),
        ('BOX', (0, 0), (-1, -1), 0.8, BORDER),
    ]))
    story.append(hero)
    story.append(Spacer(1, 2 * mm))

    # Metric cards 2x2
    metric_grid = Table([
        [_metric_card(str(counts.get('semantic', 0)), 'Semantic Matches'),
         _metric_card(str(counts.get('exact', 0)), 'Exact Matches')],
        [_metric_card(str(counts.get('near_exact', 0)), 'Near-exact Matches'),
         _metric_card(f"{coverage.get('a', 0)}%", 'Document Coverage')],
    ], colWidths=[(PAGE_W - 2 * MARGIN - 10) / 2.0] * 2)
    metric_grid.setStyle(TableStyle([
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 1), (-1, 1), 0),
        ('LEFTPADDING', (1, 0), (1, -1), 5),
        ('RIGHTPADDING', (0, 0), (0, -1), 5),
    ]))
    story.append(metric_grid)
    story.append(Spacer(1, 4 * mm))

    # Key finding
    kf = Table([
        [Paragraph('Key Finding', S_H3)],
        [Paragraph(
            'The documents use different wording but contain several passages '
            'with similar meaning.', S_BODY)],
    ], colWidths=[None])
    kf.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), HexColor('#f8fafc')),
        ('BOX', (0, 0), (-1, -1), 0.8, BORDER),
        ('LEFTPADDING', (0, 0), (-1, -1), 14),
        ('RIGHTPADDING', (0, 0), (-1, -1), 14),
        ('TOPPADDING', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 9),
    ]))
    story.append(kf)
    story.append(Spacer(1, 3 * mm))

    # Strongest match — hero evidence
    strongest = matches[0] if matches else None
    if strongest:
        story.append(Paragraph('Strongest Match', S_H2))
        score_color, _ = _score_color(strongest['score'])
        badge = Paragraph(
            f'<font color="{score_color.hexval()}"><b>{strongest["score"]}%</b></font> '
            f'— <b>{strongest["label"]}</b>',
            S_EVIDENCE_SCORE,
        )
        left_card = _quote_box('Document A', strongest['sentence_a'])
        right_card = _quote_box('Document B', strongest['sentence_b'])
        cmp_row = Table([[badge, ''], [left_card, Paragraph('&#8595;', S_PIPE)],
                         [right_card, '']],
                        colWidths=[None, 6 * mm])
        cmp_row.setStyle(TableStyle([
            ('SPAN', (0, 0), (1, 0)),
            ('VALIGN', (0, 1), (0, 1), 'MIDDLE'),
            ('VALIGN', (0, 2), (0, 2), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))
        story.append(cmp_row)
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph(
            '<font color="#15803d"><b>Different wording. Similar meaning.</b></font> '
            'This is the core VeriText signal: meaning matched despite changed words.',
            S_BODY),
        )
    story.append(PageBreak())

    # ================= PAGE 2 — EVIDENCE =================
    story.append(Paragraph('Detected Similarities', S_H2))
    story.append(Paragraph(
        'The strongest sentence-level matches found between the two documents.',
        S_SMALL),
    )
    story.append(Spacer(1, 4 * mm))

    evidence_blocks = []
    for idx, m in enumerate(matches[:3], 1):
        color, bg = _score_color(m['score'])
        badge = Paragraph(
            f'<font color="{color.hexval() if hasattr(color, "hexval") else str(color)}"><b>'
            f'{m["score"]}%</b></font> — <b>{m["label"]}</b>',
            S_EVIDENCE_SCORE,
        )
        card = Table([
            [Paragraph(f'0{idx}', st(f'en{idx}', fontName='Helvetica-Bold',
                                     fontSize=13, leading=16, textColor=PRIMARY_DARK)),
             badge, ''],
            ['', '', ''],
            [_quote_box('Document A', m['sentence_a']),
             Paragraph('&#8595;', S_PIPE),
             _quote_box('Document B', m['sentence_b'])],
        ],
            colWidths=[None, 8 * mm, None])
        card.setStyle(TableStyle([
            ('SPAN', (1, 0), (2, 0)),
            ('SPAN', (1, 1), (2, 1)),
            ('BOX', (0, 0), (-1, -1), 0.8, BORDER),
            ('LINEBELOW', (0, 0), (-1, 1), 0.5, BORDER),
            ('BACKGROUND', (0, 2), (-1, 2), HexColor('#f8fafc')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        evidence_blocks.append(card)
        if idx < len(matches[:3]):
            evidence_blocks.append(Spacer(1, 5 * mm))

    for block in evidence_blocks:
        story.append(KeepTogether(block))
    story.append(Spacer(1, 6 * mm))

    note = Table([
        [Paragraph(
            '<font name="Helvetica-Bold" size=8 color="#64748b">Note:</font> '
            '<font size=8 color="#64748b">Matches are ordered by similarity. '
            'Only sentence-level evidence is shown here; full technical details '
            'are on page 3.</font>',
            S_DISCLAIMER)],
    ], colWidths=[None])
    note.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), LIGHT),
        ('BOX', (0, 0), (-1, -1), 0.6, BORDER),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
    ]))
    story.append(note)
    story.append(PageBreak())

    # ================= PAGE 3 — HOW IT WORKS =================
    story.append(Paragraph('How VeriText Works', S_H2))
    story.append(Paragraph(
        'VeriText goes beyond word matching to compare the meaning of two documents.',
        S_SMALL),
    )
    story.append(Spacer(1, 5 * mm))

    pipeline = [
        ('Documents', 'The two files uploaded for review.'),
        ('Extract Sentences', 'Each document is split into sentences.'),
        ('Understand Meaning', 'Sentences are converted into meaning vectors.'),
        ('Compare Similarity', 'Cosine similarity between sentence pairs.'),
        ('Find Matching Passages', 'Consecutive related sentences are grouped.'),
        ('Explain the Evidence', 'The strongest matches are presented side by side.'),
    ]
    pipe_rows = []
    for i, (title, desc) in enumerate(pipeline):
        cell = Table([
            [Paragraph(title, S_PIPE)],
            [Paragraph(desc, st('pd', fontSize=7.5, leading=10,
                                textColor=TEXT_MUTED, alignment=TA_CENTER))],
        ], colWidths=[None])
        cell.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), LIGHT),
            ('BOX', (0, 0), (-1, -1), 0.6, BORDER),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ]))
        pipe_rows.append(cell)
        if i < len(pipeline) - 1:
            pipe_rows.append(Paragraph('&#8595;', S_PIPE))

    # 6 pipeline cards + 5 arrows between them.
    arrow_w = 8 * mm
    cell_w = (PAGE_W - 2 * MARGIN - 5 * arrow_w) / 6.0
    widths = [arrow_w if i % 2 == 1 else cell_w for i in range(len(pipe_rows))]
    pipe_table = Table([pipe_rows], colWidths=widths)
    pipe_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(pipe_table)
    story.append(Spacer(1, 7 * mm))

    # Technology
    t_inner = Table([
        [Paragraph('Technology', S_H3)],
        [Paragraph('Python · Flask · PyTorch · Sentence Transformers', S_TECH)],
        [Spacer(1, 2 * mm)],
        [Paragraph('<b>Model:</b> all-MiniLM-L6-v2', S_TECH)],
        [Paragraph('<b>Embedding:</b> 384 dimensions', S_TECH)],
        [Paragraph('<b>Comparison:</b> Cosine similarity', S_TECH)],
    ], colWidths=[None])
    t_inner.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), LIGHT),
        ('BOX', (0, 0), (-1, -1), 0.6, BORDER),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
    ]))
    story.append(t_inner)
    story.append(Spacer(1, 5 * mm))

    # Disclaimer
    story.append(Paragraph(
        '<b>Similarity does not prove plagiarism.</b> Results should be reviewed by a human.',
        S_DISCLAIMER),
    )
    story.append(Spacer(1, 6 * mm))

    # Technical details (appendix)
    story.append(Paragraph('Technical Details', S_H2))
    story.append(Spacer(1, 2 * mm))
    tech_rows = [
        ['Model', technical.get('model', MODEL_NAME)],
        ['Embedding size', f"{technical.get('embedding_size', EMBEDDING_SIZE)} dimensions"],
        ['Device', technical.get('device', 'cpu').upper()],
        ['Comparison method', 'Cosine similarity'],
        ['Semantic threshold', f"{technical.get('semantic_threshold', SEMANTIC_THRESHOLD)}"],
        ['Classification', 'Exact / near-exact / semantic'],
        ['Lexical evidence', 'Normalized string + sequence matching'],
    ]
    tdata = [[Paragraph('<b>Property</b>', S_TECH), Paragraph('<b>Value</b>', S_TECH)]]
    for k, v in tech_rows:
        tdata.append([Paragraph(k, S_TECH), Paragraph(str(v), S_TECH)])
    ttech = Table(tdata, colWidths=[40 * mm, None])
    ttech.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PRIMARY_DARK),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, LIGHT]),
        ('BOX', (0, 0), (-1, -1), 0.6, BORDER),
        ('INNERGRID', (0, 0), (-1, -1), 0.4, BORDER),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(ttech)

    # Pass 1: count pages so the footer can show "Page X of Y".
    buf = io.BytesIO()
    doc1 = BaseDocTemplate(buf, pagesize=A4,
                           leftMargin=MARGIN, rightMargin=MARGIN,
                           topMargin=19 * mm, bottomMargin=17 * mm,
                           title='VeriText AI — Semantic Similarity Report',
                           author='VeriText AI')
    frame1 = Frame(MARGIN, 20 * mm, PAGE_W - 2 * MARGIN,
                   PAGE_H - 19 * mm - 17 * mm, id='main')
    doc1.addPageTemplates([PageTemplate(id='page', frames=[frame1],
                                        onPage=_decorate)])
    doc1.build(copy.deepcopy(story))
    total_pages = doc1.page

    # Pass 2: real build with the known page total.
    doc = BaseDocTemplate(output_path, pagesize=A4,
                          leftMargin=MARGIN, rightMargin=MARGIN,
                          topMargin=19 * mm, bottomMargin=17 * mm,
                          title='VeriText AI — Semantic Similarity Report',
                          author='VeriText AI')
    frame = Frame(MARGIN, 20 * mm, PAGE_W - 2 * MARGIN,
                  PAGE_H - 19 * mm - 17 * mm, id='main')

    def _decorate_total(canvas, doc):
        doc._total_pages = total_pages
        _decorate(canvas, doc)

    doc.addPageTemplates([PageTemplate(id='page', frames=[frame],
                                       onPage=_decorate_total)])
    doc.build(copy.deepcopy(story))
