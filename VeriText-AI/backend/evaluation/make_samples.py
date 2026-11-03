#!/usr/bin/env python3
"""
Build the PDF and DOCX sample documents from the plain-text sources.

    cd backend && python evaluation/make_samples.py

This gives the application realistic inputs for demos and end-to-end tests:
``source_article`` is the original article, ``student_submission`` reuses parts of
it verbatim, parts with light edits and parts as paraphrases, and adds two
sections that are entirely original (a useful negative control).
"""

from __future__ import annotations

import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from docx import Document  # noqa: E402
from docx.shared import Pt  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle  # noqa: E402
from reportlab.lib.units import mm  # noqa: E402
from reportlab.lib.enums import TA_JUSTIFY  # noqa: E402
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer  # noqa: E402

SAMPLES = BASE.parent / "sample_documents"


def read_blocks(path: Path) -> list[tuple[str, bool]]:
    """Return (paragraph, is_heading) pairs from a plain-text source."""
    blocks: list[tuple[str, bool]] = []
    for chunk in path.read_text(encoding="utf-8").split("\n\n"):
        text = " ".join(chunk.split())
        if not text:
            continue
        words = text.split()
        heading = (
            len(words) <= 12
            and not text.endswith((".", "?", "!", ";", ",", ":"))
            and (text.split(".")[0].strip().isdigit() or text.isupper() or len(words) <= 8)
        )
        blocks.append((text, heading))
    return blocks


def write_pdf(source: Path, target: Path) -> None:
    styles = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=styles["BodyText"], fontName="Times-Roman",
                          fontSize=10.5, leading=15, alignment=TA_JUSTIFY, spaceAfter=7)
    heading = ParagraphStyle("heading", parent=body, fontName="Times-Bold", fontSize=12,
                             spaceBefore=10, spaceAfter=4)
    title = ParagraphStyle("title", parent=body, fontName="Times-Bold", fontSize=15,
                           alignment=0, spaceAfter=10)

    document = SimpleDocTemplate(
        str(target), pagesize=A4,
        leftMargin=22 * mm, rightMargin=22 * mm, topMargin=20 * mm, bottomMargin=20 * mm,
        title=source.stem.replace("_", " ").title(), author="VeriText AI sample corpus",
    )
    story = []
    for index, (text, is_heading) in enumerate(read_blocks(source)):
        if index == 0:
            story.append(Paragraph(text, title))
        elif is_heading:
            story.append(Paragraph(text, heading))
        else:
            story.append(Paragraph(text, body))
        if is_heading:
            story.append(Spacer(1, 2))
    document.build(story)
    print(f"  wrote {target.relative_to(SAMPLES.parent)}")


def write_docx(source: Path, target: Path) -> None:
    document = Document()
    document.styles["Normal"].font.name = "Calibri"
    document.styles["Normal"].font.size = Pt(11)
    for index, (text, is_heading) in enumerate(read_blocks(source)):
        if index == 0:
            document.add_heading(text, level=0)
        elif is_heading:
            document.add_heading(text, level=1)
        else:
            document.add_paragraph(text)
    document.save(str(target))
    print(f"  wrote {target.relative_to(SAMPLES.parent)}")


def main() -> int:
    sources = sorted(SAMPLES.glob("*.txt"))
    if not sources:
        print("No .txt sample sources found.")
        return 1
    print("Building sample documents:")
    for source in sources:
        write_pdf(source, source.with_suffix(".pdf"))
        write_docx(source, source.with_suffix(".docx"))
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
