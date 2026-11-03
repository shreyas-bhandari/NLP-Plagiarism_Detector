"""
PDF report generation (reportlab / Platypus).

The report is a *similarity analysis report*: it presents measured evidence,
the methodology that produced it, and explicit limitations. It never calls the
result a plagiarism verdict or a certified check.
"""

from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    LongTable,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from config import Config

NAVY = colors.HexColor("#0F2540")
NAVY_SOFT = colors.HexColor("#1B3A5C")
ACCENT = colors.HexColor("#2563EB")
INK = colors.HexColor("#1F2937")
MUTED = colors.HexColor("#5B6B7F")
LINE = colors.HexColor("#D9E2EC")
SURFACE = colors.HexColor("#F5F8FC")
GREEN = colors.HexColor("#15803D")
AMBER = colors.HexColor("#B45309")
RED = colors.HexColor("#B91C1C")

BAND_COLORS = {
    "low": GREEN,
    "moderate": AMBER,
    "elevated": AMBER,
    "high": RED,
    "very_high": RED,
}


def _device_line(engine: Any) -> str:
    """Short, honest description of where the embeddings for this run were computed."""
    engine = engine or {}
    device = engine.get("device")
    batch = engine.get("batch_size")
    if not device:
        return "not recorded"
    label = {"cuda": "GPU (CUDA)", "mps": "Apple MPS", "cpu": "CPU"}.get(device, str(device))
    return f"{label} · embedding batch {batch}" if batch else label


def _esc(text: Any, limit: Optional[int] = None) -> str:
    value = "" if text is None else str(text)
    if limit and len(value) > limit:
        value = value[: limit - 1].rstrip() + "…"
    return escape(value)


class _Report(BaseDocTemplate):
    """A4 document with a title header and page-number footer."""

    def __init__(self, buffer: io.BytesIO, title: str, subtitle: str):
        super().__init__(
            buffer, pagesize=A4,
            leftMargin=18 * mm, rightMargin=18 * mm,
            topMargin=24 * mm, bottomMargin=18 * mm,
            title=title, author=Config.REPORT_PRODUCT,
            subject="Semantic similarity analysis report",
        )
        self.report_title = title
        self.report_subtitle = subtitle
        frame = Frame(
            self.leftMargin, self.bottomMargin,
            self.width, self.height, id="body",
        )
        self.addPageTemplates([
            PageTemplate(id="main", frames=[frame], onPage=self._decorate)
        ])

    def _decorate(self, canvas, doc):
        canvas.saveState()
        width, height = A4
        canvas.setFillColor(NAVY)
        canvas.rect(0, height - 16 * mm, width, 16 * mm, stroke=0, fill=1)
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica-Bold", 12)
        canvas.drawString(18 * mm, height - 10.5 * mm, Config.REPORT_PRODUCT)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#B6C7DB"))
        canvas.drawRightString(width - 18 * mm, height - 10.5 * mm, self.report_subtitle)
        canvas.setStrokeColor(LINE)
        canvas.setLineWidth(0.5)
        canvas.line(18 * mm, 14 * mm, width - 18 * mm, 14 * mm)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(
            18 * mm, 9.5 * mm,
            "Similarity analysis report — not a plagiarism verdict. Human review required.",
        )
        canvas.drawRightString(width - 18 * mm, 9.5 * mm, f"Page {doc.page}")
        canvas.restoreState()


def _styles() -> Dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("t", parent=base["Title"], fontName="Helvetica-Bold",
                                fontSize=19, leading=22, textColor=NAVY, spaceAfter=2,
                                alignment=TA_LEFT),
        "tagline": ParagraphStyle("tg", parent=base["Normal"], fontName="Helvetica-Oblique",
                                  fontSize=9, textColor=ACCENT, spaceAfter=10),
        "h1": ParagraphStyle("h1", parent=base["Heading1"], fontName="Helvetica-Bold",
                             fontSize=12.5, leading=15, textColor=NAVY,
                             spaceBefore=14, spaceAfter=5),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontName="Helvetica-Bold",
                             fontSize=10, leading=12, textColor=NAVY_SOFT,
                             spaceBefore=8, spaceAfter=3),
        "body": ParagraphStyle("b", parent=base["Normal"], fontName="Helvetica", fontSize=8.8,
                               leading=12.2, textColor=INK),
        "small": ParagraphStyle("s", parent=base["Normal"], fontName="Helvetica", fontSize=7.6,
                                leading=10, textColor=MUTED),
        "quote": ParagraphStyle("q", parent=base["Normal"], fontName="Helvetica",
                                fontSize=8.2, leading=11, textColor=INK,
                                leftIndent=6, borderPadding=2),
        "cell": ParagraphStyle("c", parent=base["Normal"], fontName="Helvetica", fontSize=7.8,
                               leading=10, textColor=INK),
        "cellbold": ParagraphStyle("cb", parent=base["Normal"], fontName="Helvetica-Bold",
                                   fontSize=7.8, leading=10, textColor=INK),
        "cellmuted": ParagraphStyle("cm", parent=base["Normal"], fontName="Helvetica",
                                    fontSize=7.2, leading=9.2, textColor=MUTED),
    }


def _metric_table(rows: List[List[Any]], widths: List[float], header: bool = False) -> Table:
    table = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
    style = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]
    if header:
        style += [
            ("BACKGROUND", (0, 0), (-1, 0), SURFACE),
            ("LINEBELOW", (0, 0), (-1, 0), 0.8, NAVY_SOFT),
        ]
    table.setStyle(TableStyle(style))
    return table


def _distribution_chart(histogram: List[Dict[str, Any]], styles: Dict[str, ParagraphStyle]) -> Drawing:
    """Simple, honest horizontal bar chart built with reportlab primitives."""
    width, row_height = 460, 15
    height = row_height * len(histogram) + 12
    drawing = Drawing(width, height)
    maximum = max([h["count"] for h in histogram] + [1])
    bar_area = width - 150
    for index, bucket in enumerate(histogram):
        y = height - (index + 1) * row_height + 2
        drawing.add(String(0, y + 3, bucket["range"], fontName="Helvetica", fontSize=7.5,
                           fillColor=MUTED))
        bar_width = (bucket["count"] / maximum) * (bar_area - 40)
        lower = bucket["lower"]
        # Colour follows the product palette: high similarity needs attention (red),
        # moderate is amber, low similarity is neutral.
        color = RED if lower >= 0.8 else (AMBER if lower >= 0.6 else colors.HexColor("#94A3B8"))
        drawing.add(Rect(52, y + 1, max(bar_width, 0.6), 8, fillColor=color, strokeColor=None))
        drawing.add(String(52 + bar_width + 5, y + 3, f"{bucket['count']}", fontName="Helvetica",
                           fontSize=7.5, fillColor=INK))
    return drawing


def _match_table(matches: List[Dict[str, Any]], styles: Dict[str, ParagraphStyle]) -> Table:
    rows = [[
        Paragraph("#", styles["cellbold"]),
        Paragraph("Similarity", styles["cellbold"]),
        Paragraph("Document A (source)", styles["cellbold"]),
        Paragraph("Document B (comparison)", styles["cellbold"]),
        Paragraph("Why it was flagged", styles["cellbold"]),
    ]]
    for index, match in enumerate(matches, start=1):
        rows.append([
            Paragraph(str(index), styles["cell"]),
            Paragraph(f"<b>{match['similarity_pct']}%</b><br/>{_esc(match['band'].replace('_', ' '))}",
                      styles["cell"]),
            Paragraph(
                f"<font color='#5B6B7F'>§{match['source']['index'] + 1}"
                + (f" · p.{match['source']['page']}" if match['source'].get('page') else "")
                + "</font><br/>" + _esc(match["source"]["text"], 320),
                styles["cell"],
            ),
            Paragraph(
                f"<font color='#5B6B7F'>§{match['target']['index'] + 1}"
                + (f" · p.{match['target']['page']}" if match['target'].get('page') else "")
                + "</font><br/>" + _esc(match["target"]["text"], 320),
                styles["cell"],
            ),
            Paragraph(
                f"<b>{_esc(match['classification_label'])}</b><br/>"
                + _esc(match["explanation"]["headline"], 260),
                styles["cellmuted"],
            ),
        ])
    table = LongTable(rows, colWidths=[16, 46, 150, 150, 152], repeatRows=1)
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (-1, 0), SURFACE),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, NAVY_SOFT),
        ("LINEBELOW", (0, 1), (-1, -1), 0.35, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def generate_pdf_report(
    analysis_id: str,
    result: Dict[str, Any],
    created_at: Optional[str] = None,
) -> bytes:
    """Build the PDF and return it as bytes (never written to a public path)."""
    styles = _styles()
    buffer = io.BytesIO()
    timestamp = created_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        pretty_date = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).strftime(
            "%d %B %Y, %H:%M UTC"
        )
    except ValueError:
        pretty_date = timestamp

    doc = _Report(buffer, Config.REPORT_TITLE, "Semantic similarity analysis report")
    summary = result["summary"]
    docs = result["documents"]
    engine = result["engine"]
    story: List[Any] = []

    # ------------------------------------------------------------------ header
    story.append(Paragraph(Config.REPORT_TITLE, styles["title"]))
    story.append(Paragraph(Config.REPORT_TAGLINE, styles["tagline"]))
    story.append(_metric_table([
        [Paragraph("<b>Analysis ID</b>", styles["cell"]), Paragraph(_esc(analysis_id), styles["cell"]),
         Paragraph("<b>Generated</b>", styles["cell"]), Paragraph(_esc(pretty_date), styles["cell"])],
        [Paragraph("<b>Engine</b>", styles["cell"]), Paragraph(_esc(engine["version"]), styles["cell"]),
         Paragraph("<b>Embedding model</b>", styles["cell"]), Paragraph(_esc(engine["model"]), styles["cell"]),
         Paragraph("<b>Inference device</b>", styles["cell"]),
         Paragraph(_esc(_device_line(engine)), styles["cell"])],
    ], [26 * mm, 62 * mm, 26 * mm, 60 * mm]))

    # --------------------------------------------------------------- documents
    story.append(Paragraph("1. Documents analysed", styles["h1"]))
    story.append(_metric_table([
        [Paragraph("", styles["cell"]), Paragraph("<b>Document A</b>", styles["cell"]),
         Paragraph("<b>Document B</b>", styles["cell"])],
        [Paragraph("File name", styles["cell"]), Paragraph(_esc(docs["A"]["filename"]), styles["cell"]),
         Paragraph(_esc(docs["B"]["filename"]), styles["cell"])],
        [Paragraph("Type", styles["cell"]), Paragraph(_esc(docs["A"]["file_type"].upper()), styles["cell"]),
         Paragraph(_esc(docs["B"]["file_type"].upper()), styles["cell"])],
        [Paragraph("Words", styles["cell"]), Paragraph(f"{docs['A']['word_count']:,}", styles["cell"]),
         Paragraph(f"{docs['B']['word_count']:,}", styles["cell"])],
        [Paragraph("Sentences", styles["cell"]),
         Paragraph(f"{docs['A']['sentence_count']:,} ({docs['A']['eligible_sentence_count']:,} compared)", styles["cell"]),
         Paragraph(f"{docs['B']['sentence_count']:,} ({docs['B']['eligible_sentence_count']:,} compared)", styles["cell"])],
        [Paragraph("Pages", styles["cell"]), Paragraph(str(docs["A"]["page_count"] or "n/a"), styles["cell"]),
         Paragraph(str(docs["B"]["page_count"] or "n/a"), styles["cell"])],
    ], [30 * mm, 72 * mm, 72 * mm], header=True))

    # ----------------------------------------------------------------- summary
    story.append(Paragraph("2. Summary", styles["h1"]))
    band = summary["band"]
    story.append(_metric_table([
        [Paragraph("<b>Coverage-weighted similarity index</b>", styles["cell"]),
         Paragraph(f"<font size=12 color='#{BAND_COLORS.get(band['level'], NAVY).hexval()[2:]}'>"
                   f"<b>{summary['weighted_similarity_pct']}%</b></font> "
                   f"— {_esc(band['label'])}", styles["cell"])],
        [Paragraph("Average similarity of matched sentences", styles["cell"]),
         Paragraph(f"{summary['average_matched_similarity_pct']}%", styles["cell"])],
        [Paragraph("Highest single sentence similarity", styles["cell"]),
         Paragraph(f"{summary['max_similarity_pct']}%", styles["cell"])],
        [Paragraph("Exact textual matches", styles["cell"]),
         Paragraph(str(summary["exact_matches"]), styles["cell"])],
        [Paragraph("Near-exact textual matches", styles["cell"]),
         Paragraph(str(summary["near_exact_matches"]), styles["cell"])],
        [Paragraph("Semantic matches (paraphrase detected: %d)" % summary["paraphrase_matches"], styles["cell"]),
         Paragraph(str(summary["semantic_matches"]), styles["cell"])],
        [Paragraph("Suppressed low-evidence matches", styles["cell"]),
         Paragraph(str(summary["suppressed_matches"]), styles["cell"])],
        [Paragraph("Matched sentences in Document A (primary evidence)", styles["cell"]),
         Paragraph(str(summary["primary_matches"]), styles["cell"])],
    ], [82 * mm, 92 * mm]))
    story.append(Spacer(1, 4))
    story.append(Paragraph(_esc(band["description"]), styles["body"]))
    story.append(Paragraph(_esc(summary["explanation_of_weighted_index"]), styles["small"]))

    # ---------------------------------------------------------------- coverage
    story.append(Paragraph("3. Match coverage", styles["h1"]))
    coverage_rows = [[
        Paragraph("Document", styles["cellbold"]), Paragraph("Sentences compared", styles["cellbold"]),
        Paragraph("Sentences with a match", styles["cellbold"]), Paragraph("Sentence coverage", styles["cellbold"]),
        Paragraph("Word coverage", styles["cellbold"]),
    ]]
    for label in ("A", "B"):
        cov = summary["coverage"][label]
        coverage_rows.append([
            Paragraph(f"Document {label}", styles["cell"]),
            Paragraph(str(cov["sentences_considered"]), styles["cell"]),
            Paragraph(str(cov["sentences_matched"]), styles["cell"]),
            Paragraph(f"{cov['sentence_coverage_pct']}%", styles["cell"]),
            Paragraph(f"{cov['word_coverage_pct']}% ({cov['words_covered']:,}/{cov['words_considered']:,} words)", styles["cell"]),
        ])
    story.append(_metric_table(coverage_rows, [26 * mm, 32 * mm, 36 * mm, 30 * mm, 50 * mm], header=True))

    # ------------------------------------------------------------ distribution
    story.append(Paragraph("4. Similarity distribution (best match per sentence in Document A)", styles["h1"]))
    story.append(_distribution_chart(summary["distribution"], styles))
    story.append(Paragraph(
        "Bars show how many comparable sentences in Document A have a best-match cosine score in each "
        "range. Sentences below the flag threshold are shown so the shape of the comparison stays visible.",
        styles["small"],
    ))

    # ----------------------------------------------------------------- matches
    primary = [m for m in result["matches"] if m["is_primary"]]
    sections = [
        ("5. Exact textual matches", "exact", "Sentences that are identical after case, punctuation and whitespace normalisation."),
        ("6. Near-exact textual matches", "near_exact", "Sentences whose word sequence is almost identical (minor edits, insertions or deletions)."),
        ("7. Semantic matches (paraphrasing)", "semantic", "Sentences with closely related meaning but different wording — the cases exact matching cannot see."),
    ]
    for title, classification, blurb in sections:
        subset = [m for m in primary if m["classification"] == classification]
        story.append(Paragraph(f"{title} ({len(subset)})", styles["h1"]))
        story.append(Paragraph(_esc(blurb), styles["small"]))
        story.append(Spacer(1, 3))
        if not subset:
            story.append(Paragraph("No matches of this type were detected.", styles["body"]))
            continue
        limited = sorted(subset, key=lambda m: -m["similarity"])[:18]
        story.append(_match_table(limited, styles))
        if len(subset) > len(limited):
            story.append(Paragraph(
                f"Showing the {len(limited)} highest-scoring of {len(subset)} matches. "
                "The full list is available in the VeriText AI web interface.",
                styles["small"],
            ))

    # -------------------------------------------------------- paragraph level
    paragraph_matches = result.get("paragraph_matches", [])
    if paragraph_matches:
        story.append(Paragraph("8. Paragraph-level similarities", styles["h1"]))
        rows = [[
            Paragraph("Similarity", styles["cellbold"]),
            Paragraph("Document A paragraph", styles["cellbold"]),
            Paragraph("Document B paragraph", styles["cellbold"]),
        ]]
        for match in paragraph_matches[:10]:
            rows.append([
                Paragraph(f"{match['similarity_pct']}%", styles["cell"]),
                Paragraph(f"<font color='#5B6B7F'>¶{match['source']['paragraph_index'] + 1}</font><br/>"
                          + _esc(match["source"]["text"], 300), styles["cell"]),
                Paragraph(f"<font color='#5B6B7F'>¶{match['target']['paragraph_index'] + 1}</font><br/>"
                          + _esc(match["target"]["text"], 300), styles["cell"]),
            ])
        story.append(_metric_table(rows, [18 * mm, 78 * mm, 78 * mm], header=True))

    # -------------------------------------------------------- methodological
    story.append(Paragraph("9. Methodology", styles["h1"]))
    story.append(Paragraph(
        "VeriText AI extracts text with PyMuPDF (PDF) and python-docx (DOCX), segments it into sentences with an "
        "abbreviation-aware rule-based splitter, and encodes every sentence with the pretrained transformer "
        f"<b>{_esc(engine['model'])}</b>. The encoder maps each sentence to a 384-dimensional vector; vectors are "
        "L2-normalised, so the cosine similarity between two sentences is their dot product. Cosine similarity is "
        "computed as (A·B)/(‖A‖‖B‖) = A·B for unit vectors.", styles["body"]))
    story.append(Paragraph(
        "For every comparable sentence the engine retrieves the top-k most similar sentences in the other document. "
        "Each candidate is then classified using two independent signals: (a) the embedding cosine, which captures "
        "meaning, and (b) lexical evidence — normalised string equality, token-sequence ratio and shared distinctive "
        "terms — which captures copying of words. Exact, near-exact and semantic matches are therefore reported "
        "separately. Headings, very short fragments and (by default) reference lists are excluded from matching. "
        "Sentence pairs whose only overlap is generic academic phrasing or citation context are suppressed and "
        "excluded from the headline metrics.", styles["body"]))
    story.append(Paragraph(
        f"Thresholds in this run: semantic flag ≥ {engine['thresholds']['semantic_min']:.2f} cosine, "
        f"high-similarity band ≥ {engine['thresholds']['high']:.2f}, moderate band ≥ "
        f"{engine['thresholds']['moderate']:.2f}, near-exact token ratio ≥ "
        f"{engine['thresholds']['near_exact_lexical']:.2f}. These are configurable operating points calibrated on a "
        "labelled evaluation set; they are not scientifically validated plagiarism boundaries.", styles["body"]))

    # ---------------------------------------------------------- warnings
    if result.get("warnings"):
        story.append(Paragraph("10. Processing notes", styles["h1"]))
        for warning in result["warnings"]:
            story.append(Paragraph("• " + _esc(warning), styles["body"]))

    # ------------------------------------------------- limitations
    story.append(Paragraph("11. Limitations", styles["h1"]))
    for line in [
        "The comparison covers only the two documents supplied by the user. VeriText AI does not search the web or "
        "any external corpus, so copied material from an unsupplied source cannot be detected.",
        "Sentence embeddings compress meaning into 384 dimensions; irony, negation subtleties, discipline-specific "
        "jargon and very short sentences can be scored inaccurately.",
        "Paraphrase detection is probabilistic. Legitimate similarity (shared definitions, standard method "
        "descriptions, common terminology, quotations with citation) produces high scores, and sophisticated "
        "paraphrasing can produce low scores.",
        "Similarity scores depend on the segmentation of both documents: different sentence boundaries can move a "
        "score up or down by several points.",
        "Scanned PDFs need OCR before analysis; tables, figures, footnotes and equations are extracted imperfectly.",
        "The similarity index is a triage aid. It is not a plagiarism percentage, and it is not evidence of intent.",
    ]:
        story.append(Paragraph("• " + _esc(line), styles["body"]))

    story.append(Paragraph("12. Disclaimer", styles["h1"]))
    story.append(Paragraph(_esc(result["disclaimer"]), styles["body"]))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        f"Prepared by {Config.REPORT_PRODUCT} · {Config.REPORT_TAGLINE} · Analysis ID {_esc(analysis_id)} · "
        f"{_esc(pretty_date)}",
        styles["small"],
    ))

    doc.build(story)
    return buffer.getvalue()
