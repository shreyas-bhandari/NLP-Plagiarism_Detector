"""
Document text extraction for VeriText AI.

Supported formats
-----------------
* PDF   -> PyMuPDF (``pymupdf`` / legacy ``fitz`` import name)
* DOCX  -> python-docx (body paragraphs *and* tables)
* TXT / Markdown -> plain decoding (convenience for testing and pasted notes)

The extractor returns a *position aware* representation: every paragraph keeps
its page number, its style (for DOCX headings) and its character offsets inside
the reconstructed full text. Those offsets are what let the frontend highlight
matched passages at the right place in the document.

Nothing is written to disk here and no uploaded content is ever executed.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

try:  # PyMuPDF >= 1.24 exposes the `pymupdf` module name
    import pymupdf as _pymupdf
except ImportError:  # pragma: no cover - fallback for older installs
    import fitz as _pymupdf  # type: ignore

from docx import Document as DocxDocument  # python-docx

from config import Config
from utils.text import plural


class ExtractionError(Exception):
    """Raised when a document cannot be turned into usable text."""

    def __init__(self, code: str, message: str, status_code: int = 422, hint: str = ""):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.hint = hint


@dataclass
class ExtractedDocument:
    filename: str
    file_type: str
    text: str
    paragraphs: List[Dict[str, Any]] = field(default_factory=list)
    page_count: int = 0
    char_count: int = 0
    word_count: int = 0
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "filename": self.filename,
            "file_type": self.file_type,
            "page_count": self.page_count,
            "char_count": self.char_count,
            "word_count": self.word_count,
            "paragraph_count": len(self.paragraphs),
            "warnings": list(self.warnings),
            "metadata": self.metadata,
        }


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
_CONTROL_CHARS = re.compile(r"[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]")
_MULTI_NEWLINE = re.compile(r"\n{3,}")
_MULTI_SPACE = re.compile(r"[ \t\u00a0]{2,}")


def clean_block_text(raw: str) -> str:
    """Normalise a raw extracted text block without destroying its wording."""
    if not raw:
        return ""
    text = unicodedata.normalize("NFKC", raw)
    text = text.replace("\u00ad", "")            # soft hyphen
    text = _CONTROL_CHARS.sub("", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\t", " ")
    # De-hyphenate words that were split across PDF lines: "detec-\ntion" -> "detection"
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    text = re.sub(r"[ \t]*\n[ \t]*", " ", text)   # single newline = soft wrap inside a block
    text = _MULTI_SPACE.sub(" ", text)
    return text.strip()


def _looks_like_heading(text: str, style: str = "") -> bool:
    """Heuristic section-heading detector (used to keep headings out of matching)."""
    lowered = (style or "").lower()
    if lowered.startswith("heading") or lowered in {"title", "subtitle"}:
        return True
    value = (text or "").strip()
    if not value or len(value) > 100:
        return False
    if value[-1] in ".?!;,":
        return False                      # sentences end with punctuation, headings do not
    words = value.split()
    if len(words) > 14:
        return False
    # "1. Introduction", "3.2 Experimental Setup", "IV. Results"
    if re.match(r"^(\d+(\.\d+)*[.)]?|[IVXLC]{1,5}[.)])\s+[A-Z]", value):
        return True
    letters = [c for c in value if c.isalpha()]
    if len(letters) < 3:
        return False
    upper_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
    if upper_ratio > 0.75:                # ALL CAPS heading
        return True
    capitalised = sum(1 for w in words if w[:1].isupper()) / len(words)
    return len(words) <= 8 and capitalised >= 0.6


def _build_result(
    filename: str,
    file_type: str,
    paragraphs: List[Dict[str, Any]],
    page_count: int,
    warnings: List[str],
    metadata: Optional[Dict[str, Any]] = None,
) -> ExtractedDocument:
    """Assemble the full text and fill in character offsets for each paragraph."""
    parts: List[str] = []
    cursor = 0
    for para in paragraphs:
        text = para["text"]
        para["start"] = cursor
        para["end"] = cursor + len(text)
        parts.append(text)
        cursor = para["end"] + 2  # paragraphs are joined with "\n\n"
    full_text = "\n\n".join(parts)

    char_count = len(full_text)
    word_count = len(re.findall(r"\b\w+\b", full_text))
    return ExtractedDocument(
        filename=filename,
        file_type=file_type,
        text=full_text,
        paragraphs=paragraphs,
        page_count=page_count,
        char_count=char_count,
        word_count=word_count,
        warnings=warnings,
        metadata=metadata or {},
    )


# --------------------------------------------------------------------------- #
# PDF
# --------------------------------------------------------------------------- #
def _extract_pdf(path: Path) -> ExtractedDocument:
    try:
        pdf = _pymupdf.open(str(path))
    except Exception as exc:  # corrupted / encrypted / not really a PDF
        raise ExtractionError(
            "pdf_open_failed",
            "The PDF could not be opened. It may be corrupted, password protected "
            "or not a valid PDF file.",
            hint=str(exc)[:200],
        ) from exc

    warnings: List[str] = []
    metadata: Dict[str, Any] = {}
    try:
        if pdf.needs_pass:
            raise ExtractionError(
                "pdf_encrypted",
                "This PDF is password protected, so its text cannot be extracted.",
                hint="Upload an unprotected copy of the document.",
            )
        doc_meta = pdf.metadata or {}
        metadata = {
            "title": (doc_meta.get("title") or "").strip()[:200],
            "author": (doc_meta.get("author") or "").strip()[:200],
            "producer": (doc_meta.get("producer") or "").strip()[:120],
        }

        pages_blocks: List[List[str]] = []
        for page in pdf:
            blocks = page.get_text("blocks") or []
            # block tuple: (x0, y0, x1, y1, text, block_no, block_type); type 0 == text
            text_blocks = [
                b for b in blocks if len(b) >= 7 and b[6] == 0 and str(b[4]).strip()
            ]
            text_blocks.sort(key=lambda b: (round(b[1], 1), round(b[0], 1)))
            cleaned = [clean_block_text(str(b[4])) for b in text_blocks]
            pages_blocks.append([c for c in cleaned if c])

        page_count = len(pages_blocks)

        # Repeated header/footer suppression: a line that appears on most pages is
        # page furniture (running title, journal name), not document content.
        if page_count >= 4:
            from collections import Counter

            counter: Counter = Counter()
            for blocks in pages_blocks:
                for candidate in (blocks[0] if blocks else None, blocks[-1] if blocks else None):
                    if candidate and len(candidate) < 120:
                        counter[candidate.strip().lower()] += 1
            threshold = max(3, int(page_count * 0.6))
            furniture = {t for t, n in counter.items() if n >= threshold}
            if furniture:
                removed = 0
                for blocks in pages_blocks:
                    for i in range(len(blocks) - 1, -1, -1):
                        if blocks[i].strip().lower() in furniture:
                            blocks.pop(i)
                            removed += 1
                if removed:
                    warnings.append(
                        f"Removed {plural(removed, 'repeated page header/footer line', 'repeated page header/footer lines')} "
                        "before analysis."
                    )

        paragraphs: List[Dict[str, Any]] = []
        for page_index, blocks in enumerate(pages_blocks, start=1):
            for block in blocks:
                paragraphs.append(
                    {
                        "index": len(paragraphs),
                        "text": block,
                        "page": page_index,
                        "style": "",
                        "is_heading": _looks_like_heading(block),
                    }
                )

        total_chars = sum(len(p["text"]) for p in paragraphs)
        if total_chars < 120 or (page_count and total_chars / page_count < 40):
            raise ExtractionError(
                "scanned_pdf",
                "No selectable text could be extracted from this PDF. It looks like a "
                "scanned (image-only) document, which requires OCR before it can be analysed.",
                status_code=422,
                hint="Run OCR (e.g. Tesseract) on the PDF, or upload the original DOCX/text version.",
            )
        if total_chars < 600:
            warnings.append("Very little text was extracted — results may not be representative.")

        return _build_result(
            filename=path.name,
            file_type="pdf",
            paragraphs=paragraphs,
            page_count=page_count,
            warnings=warnings,
            metadata=metadata,
        )
    finally:
        pdf.close()


# --------------------------------------------------------------------------- #
# DOCX
# --------------------------------------------------------------------------- #
def _extract_docx(path: Path) -> ExtractedDocument:
    try:
        document = DocxDocument(str(path))
    except Exception as exc:
        raise ExtractionError(
            "docx_open_failed",
            "The DOCX file could not be opened. It may be corrupted or not a valid "
            "Word document.",
            hint=str(exc)[:200],
        ) from exc

    warnings: List[str] = []
    paragraphs: List[Dict[str, Any]] = []

    for para in document.paragraphs:
        text = clean_block_text(para.text)
        if not text:
            continue
        style_name = ""
        try:
            style_name = para.style.name or ""
        except Exception:  # pragma: no cover - malformed styles
            style_name = ""
        paragraphs.append(
            {
                "index": len(paragraphs),
                "text": text,
                "page": 0,  # DOCX has no fixed pagination
                "style": style_name,
                "is_heading": _looks_like_heading(text, style_name),
            }
        )

    # Tables often contain results and definitions worth analysing.
    table_cells = 0
    for table in document.tables:
        for row in table.rows:
            seen: set[str] = set()
            for cell in row.cells:
                text = clean_block_text(cell.text)
                if not text or text in seen:
                    continue
                seen.add(text)
                if len(text.split()) < 3:
                    continue
                table_cells += 1
                paragraphs.append(
                    {
                        "index": len(paragraphs),
                        "text": text,
                        "page": 0,
                        "style": "Table cell",
                        "is_heading": False,
                    }
                )
    if table_cells:
        warnings.append(
            f"Extracted {plural(table_cells, 'table cell')} in addition to body paragraphs."
        )

    if not paragraphs:
        raise ExtractionError(
            "docx_empty",
            "No readable text was found in this DOCX file.",
            hint="The document may contain only images or embedded objects.",
        )

    metadata = {}
    try:
        props = document.core_properties
        metadata = {
            "title": (props.title or "")[:200],
            "author": (props.author or "")[:200],
        }
    except Exception:  # pragma: no cover
        pass

    return _build_result(
        filename=path.name,
        file_type="docx",
        paragraphs=paragraphs,
        page_count=0,
        warnings=warnings,
        metadata=metadata,
    )


# --------------------------------------------------------------------------- #
# plain text
# --------------------------------------------------------------------------- #
def _extract_text_file(path: Path) -> ExtractedDocument:
    raw_bytes = path.read_bytes()
    text = ""
    for encoding in ("utf-8", "utf-16", "cp1252", "latin-1"):
        try:
            text = raw_bytes.decode(encoding)
            break
        except (UnicodeDecodeError, LookupError):
            continue
    text = unicodedata.normalize("NFKC", text).replace("\r\n", "\n").replace("\r", "\n")

    # Split into paragraphs on blank lines, but also treat a standalone short,
    # punctuation-free line (e.g. "2. Related Work") as its own paragraph even when
    # the author did not leave a blank line after it. Without this, headings get
    # glued to the first sentence of the section.
    raw_chunks: List[str] = []
    buffer: List[str] = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            if buffer:
                raw_chunks.append(" ".join(buffer))
                buffer = []
            continue
        looks_heading = (
            len(stripped) <= 80
            and not stripped.endswith((".", "!", "?", ",", ";", ":"))
            and len(stripped.split()) <= 12
            and re.match(r"^(\d+[.)]\s+)?[A-Z0-9]", stripped) is not None
        )
        if looks_heading and buffer:
            raw_chunks.append(" ".join(buffer))
            buffer = [stripped]
            raw_chunks.append(" ".join(buffer))
            buffer = []
            continue
        if looks_heading and not buffer:
            raw_chunks.append(stripped)
            continue
        buffer.append(stripped)
    if buffer:
        raw_chunks.append(" ".join(buffer))

    chunks = [clean_block_text(chunk) for chunk in raw_chunks]
    paragraphs = [
        {
            "index": i,
            "text": chunk,
            "page": 0,
            "style": "",
            "is_heading": _looks_like_heading(chunk),
        }
        for i, chunk in enumerate(c for c in chunks if c)
    ]
    if not paragraphs:
        raise ExtractionError("empty_document", "The uploaded text file is empty.")
    return _build_result(
        filename=path.name,
        file_type=path.suffix.lstrip(".").lower(),
        paragraphs=paragraphs,
        page_count=0,
        warnings=[],
        metadata={},
    )


# --------------------------------------------------------------------------- #
# public API
# --------------------------------------------------------------------------- #
def extract_document(path: str | Path, original_filename: Optional[str] = None) -> ExtractedDocument:
    """
    Extract text from a document on disk.

    ``original_filename`` is used for display only; the returned structure never
    exposes the server-side path.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise ExtractionError("file_missing", "The uploaded file could not be found.", 400)

    suffix = file_path.suffix.lower().lstrip(".")
    if suffix not in Config.ALLOWED_EXTENSIONS:
        raise ExtractionError(
            "unsupported_type",
            f"Unsupported file type '.{suffix}'. Allowed types: "
            f"{', '.join(sorted(Config.ALLOWED_EXTENSIONS))}.",
            status_code=415,
        )

    if suffix == "pdf":
        doc = _extract_pdf(file_path)
    elif suffix == "docx":
        doc = _extract_docx(file_path)
    else:
        doc = _extract_text_file(file_path)

    if original_filename:
        doc.filename = original_filename

    if doc.char_count > Config.MAX_DOCUMENT_CHARS:
        raise ExtractionError(
            "document_too_large",
            f"Extracted text is {doc.char_count:,} characters, above the "
            f"{Config.MAX_DOCUMENT_CHARS:,} character analysis limit. Split the document "
            "into chapters and analyse them separately.",
            status_code=413,
        )
    if doc.word_count < 20:
        raise ExtractionError(
            "document_too_short",
            "The document contains too little text (fewer than 20 words) to compare meaningfully.",
        )
    return doc
