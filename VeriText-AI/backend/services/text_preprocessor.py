"""
Text pre-processing and segmentation for VeriText AI.

Design notes
------------
1. We normalise *text presentation* (whitespace, control characters, unicode
   width) but we never destroy the original sentence string — the UI and the
   PDF report show exactly what the author wrote.
2. We deliberately do **not** remove stop words, and we do **not** stem or
   lemmatise before creating embeddings. Sentence-Transformers rely on full
   context; aggressive cleaning would damage the meaning signal. A separate
   *stemmed content-token* view is produced only for the lexical (exact /
   near-exact) comparison path.
3. Sentence segmentation uses a rule-based splitter with abbreviation and
   decimal-number protection. It runs offline (no NLTK data download needed)
   and is deterministic, which matters for reproducible sentence indexes.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Optional, Sequence, Tuple

try:  # NLTK's Porter stemmer needs no downloaded corpora; used for lexical view only
    from nltk.stem import PorterStemmer

    _STEMMER: Optional[PorterStemmer] = PorterStemmer()
except Exception:  # pragma: no cover - graceful degradation
    _STEMMER = None

from config import Config
from utils.text import plural

# --------------------------------------------------------------------------- #
# constants
# --------------------------------------------------------------------------- #
STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "then", "than", "that", "this", "these", "those",
    "of", "in", "on", "at", "to", "for", "with", "by", "from", "as", "is", "are", "was", "were",
    "be", "been", "being", "it", "its", "we", "our", "us", "they", "their", "them", "he", "she",
    "his", "her", "i", "you", "your", "not", "no", "nor", "so", "such", "which", "who", "whom",
    "what", "when", "where", "why", "how", "can", "could", "should", "would", "may", "might",
    "must", "will", "shall", "do", "does", "did", "has", "have", "had", "also", "very", "more",
    "most", "some", "any", "all", "each", "both", "other", "into", "over", "under", "about",
    "between", "within", "there", "here", "however", "therefore", "thus", "hence", "while",
    "because", "although", "though", "upon", "per", "via", "using", "used", "use", "one", "two",
}

ABBREVIATIONS = {
    "e.g", "e.g.", "i.e", "i.e.", "et al", "et al.", "al", "fig", "fig.", "figs", "figs.",
    "eq", "eq.", "eqs", "eqs.", "no", "no.", "nos", "vs", "vs.", "dr", "dr.", "prof", "prof.",
    "mr", "mr.", "mrs", "mrs.", "ms", "ms.", "ph.d", "ph.d.", "cf", "cf.", "approx", "approx.",
    "inc", "inc.", "ltd", "ltd.", "pp", "pp.", "p", "p.", "vol", "vol.", "sec", "sec.", "ch",
    "ch.", "ref", "ref.", "refs", "refs.", "ca", "ca.", "st", "st.", "jr", "jr.", "sr", "sr.",
    "u.s", "u.s.", "u.k", "u.k.", "etc", "etc.", "ibid", "ibid.", "resp", "resp.", "figs",
    "tab", "tab.", "tabs", "tabs.", "tab", "dept", "univ", "assoc", "coll", "inst", "natl",
}

REFERENCE_HEADINGS = {
    "references", "reference", "bibliography", "works cited", "literature cited",
    "references and notes", "citations", "reference list", "sources",
}
APPENDIX_HEADINGS = {"appendix", "appendices", "supplementary material", "supplementary materials"}
ACK_HEADINGS = {"acknowledgements", "acknowledgments", "acknowledgement", "acknowledgment"}

_WS_RE = re.compile(r"\s+")
_CONTROL_RE = re.compile(r"[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]")
_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9'’\-]*")
_TERMINAL = ".!?…"


# --------------------------------------------------------------------------- #
# normalisation helpers
# --------------------------------------------------------------------------- #
def normalize_display(text: str) -> str:
    """Collapse whitespace / control characters but keep the readable wording."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = _CONTROL_RE.sub(" ", text)
    text = text.replace("\u00ad", "")
    return _WS_RE.sub(" ", text).strip()


def normalize_for_match(text: str) -> str:
    """
    Aggressive normalisation used *only* to decide whether two sentences are the
    same string (exact matching): lowercase, unify quotes/dashes, strip punctuation.
    """
    text = unicodedata.normalize("NFKC", text or "").lower()
    text = text.replace("’", "'").replace("“", '"').replace("”", '"').replace("–", "-").replace("—", "-")
    text = re.sub(r"[^a-z0-9'\s]", " ", text)
    return _WS_RE.sub(" ", text).strip()


def tokenize(text: str) -> List[str]:
    return [t.lower().replace("’", "'") for t in _TOKEN_RE.findall(text or "")]


def content_terms(text: str) -> List[str]:
    """
    Surface content words of a sentence (lowercased, stop words removed, *not*
    stemmed). These are shown to users in explanations; comparing them is done on
    the stemmed view from :func:`content_tokens`.
    """
    terms: List[str] = []
    for token in tokenize(text):
        if token in STOPWORDS or len(token) < 3 or token.isdigit():
            continue
        terms.append(token)
    return terms


def content_tokens(text: str) -> List[str]:
    """
    Content words of a sentence (stop words removed, Porter stems applied).

    Used **only** for explainable lexical overlap ("shared distinctive terms"),
    never for the embedding that drives semantic similarity.
    """
    stems: List[str] = []
    for token in tokenize(text):
        if token in STOPWORDS or len(token) < 3 or token.isdigit():
            continue
        stems.append(_STEMMER.stem(token) if _STEMMER else token)
    return stems


def content_token_set(text: str) -> set[str]:
    return set(content_tokens(text))


# --------------------------------------------------------------------------- #
# sentence segmentation
# --------------------------------------------------------------------------- #
def split_sentences(text: str) -> List[Tuple[str, int, int]]:
    """
    Split a paragraph into sentences, returning ``(sentence, start, end)`` with
    offsets relative to ``text``.

    Boundary rule: terminal punctuation (``.``/``!``/``?``/``…``) optionally
    followed by a closing quote/bracket, then whitespace, then a token that
    starts with an uppercase letter, a digit or an opening quote/bracket.
    Abbreviations ("et al.", "e.g.", "Fig."), single-letter initials ("J. Smith")
    and decimal numbers ("3.14") do not create boundaries.
    """
    if not text:
        return []

    n = len(text)
    boundaries: List[int] = []
    i = 0
    while i < n:
        char = text[i]
        if char not in _TERMINAL:
            i += 1
            continue

        # consume runs like "?!" or "..." and optional closing quotes/brackets
        end = i + 1
        while end < n and (text[end] in _TERMINAL + "\"')]’”"):
            end += 1
        # must be followed by whitespace (or end of text)
        if end < n and not text[end].isspace():
            i = end
            continue

        prev_chunk = text[:i]
        # find the token immediately before the punctuation
        match = re.search(r"([A-Za-z0-9][A-Za-z0-9.'’\-]*)$", prev_chunk)
        token = (match.group(1) if match else "").lower()

        is_boundary = True
        if char == ".":
            if token in ABBREVIATIONS:
                is_boundary = False
            elif re.fullmatch(r"[a-z]", token):           # single initial: "J. Smith"
                is_boundary = False
            elif re.fullmatch(r"\d+", token) and end < n and text[end:end + 1].isdigit():
                is_boundary = False                       # "3. 14" style numbering
            elif re.fullmatch(r"\d+\.\d+", token):
                is_boundary = False
        if is_boundary:
            # look ahead to what starts the next sentence
            rest = text[end:]
            stripped = rest.lstrip()
            if stripped:
                first = stripped[0]
                if first.islower() or first in ",;:)":
                    is_boundary = False
        if is_boundary and end < n:
            boundaries.append(end)

        i = end

    sentences: List[Tuple[str, int, int]] = []
    start = 0
    for boundary in boundaries:
        chunk = text[start:boundary]
        if chunk.strip():
            offset = len(chunk) - len(chunk.lstrip())
            sentences.append((chunk.strip(), start + offset, boundary))
        start = boundary
    tail = text[start:]
    if tail.strip():
        offset = len(tail) - len(tail.lstrip())
        sentences.append((tail.strip(), start + offset, n))
    return sentences


# --------------------------------------------------------------------------- #
# section detection
# --------------------------------------------------------------------------- #
def _heading_key(text: str) -> str:
    key = re.sub(r"[^a-z\s]", "", normalize_display(text).lower())
    return _WS_RE.sub(" ", key).strip()


def _looks_like_reference_entry(text: str) -> bool:
    """
    Heuristic detector for a single bibliographic entry.

    Reference lists are full of author names, journal titles and years that repeat
    across papers, so comparing them produces meaningless "matches". When a
    document has no explicit "References" heading (common in poorly structured
    DOCX files) we still want to keep those lines out of the comparison.
    """
    value = text.strip()
    if len(value) < 25 or len(value) > 400:
        return False
    has_year = bool(re.search(r"\b(19|20)\d{2}[a-z]?\b", value))
    if not has_year:
        return False
    signals = 0
    if re.search(r"\bet al\b", value, re.I):
        signals += 1
    if re.search(r"\b(19|20)\d{2}[;:,)]", value):
        signals += 1
    if re.search(r"\b(pp?\.|vol\.|no\.|doi|https?://|ISBN|ISSN)\b", value, re.I):
        signals += 1
    if re.search(r"^[A-Z][A-Za-z\-']+,?\s+[A-Z]{1,3}[.,]", value):   # "Smith, J. A."
        signals += 1
    if re.search(r"[A-Za-z]+\.\s*(19|20)\d{2}", value):              # "Journal. 2019"
        signals += 1
    # An entry is usually one dense line without sentence-final punctuation.
    if value.count(".") >= 2 and not re.search(r"[.!?]\s+[A-Z]", value):
        signals += 1
    return signals >= 2


def detect_reference_start(paragraphs: Sequence[Dict[str, Any]]) -> Optional[int]:
    """
    Return the paragraph index where the bibliography starts, if the document has
    one (explicit heading, or a run of bibliographic entries in the last third).
    """
    if not paragraphs:
        return None
    total = len(paragraphs)

    for para in paragraphs:
        key = _heading_key(para.get("text", ""))
        if not key or len(key.split()) > 4:
            continue
        if key in REFERENCE_HEADINGS and para["index"] >= total * 0.35:
            return para["index"]

    # Fallback: three consecutive reference-like paragraphs late in the document.
    for para in paragraphs[max(0, int(total * 0.55)):]:
        index = para["index"]
        window = [p for p in paragraphs if index <= p["index"] < index + 3]
        if len(window) >= 2 and all(_looks_like_reference_entry(p["text"]) for p in window):
            return index
    return None


def assign_sections(paragraphs: Sequence[Dict[str, Any]]) -> None:
    """Annotate each paragraph with a section label (in place)."""
    ref_start = detect_reference_start(paragraphs)
    section = "body"
    for para in paragraphs:
        idx = para["index"]
        key = _heading_key(para.get("text", ""))
        if ref_start is not None and idx >= ref_start:
            if key in APPENDIX_HEADINGS or (para.get("is_heading") and "appendix" in key):
                section = "appendix"
            elif section != "appendix":
                section = "references"
        elif key in ACK_HEADINGS:
            section = "acknowledgements"
        para["section"] = section


# --------------------------------------------------------------------------- #
# document preparation
# --------------------------------------------------------------------------- #
def _is_quoted(text: str) -> bool:
    stripped = text.strip()
    if len(stripped) < 24:
        return False
    pairs = [('"', '"'), ("“", "”"), ("'", "'")]
    return any(stripped.startswith(a) and stripped.endswith(b) for a, b in pairs)


def prepare_document(
    doc: Any,
    label: str,
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Turn an :class:`ExtractedDocument` into the structure consumed by the NLP
    engine: a flat, ordered list of sentences (each with document position and
    section metadata) plus paragraph records for paragraph-level comparison.

    Sentences that must not be compared (headings, reference-list entries, very
    short fragments) are still returned — flagged with ``eligible=False`` and an
    ``exclude_reason`` — so the viewer can render the full document.
    """
    options = options or {}
    exclude_references = bool(options.get("exclude_references", True))
    exclude_headings = bool(options.get("exclude_headings", True))
    ignore_quotations = bool(options.get("ignore_quotations", False))
    min_words = int(options.get("min_sentence_words", Config.MIN_SENTENCE_WORDS))
    min_chars = int(options.get("min_sentence_chars", Config.MIN_SENTENCE_CHARS))

    paragraphs = []
    for position, raw in enumerate(doc.paragraphs):
        paragraph = dict(raw)
        paragraph.setdefault("index", position)
        paragraph.setdefault("page", 0)
        paragraph.setdefault("is_heading", False)
        paragraph.setdefault("start", 0)
        paragraph.setdefault("end", paragraph["start"] + len(paragraph["text"]))
        paragraphs.append(paragraph)
    assign_sections(paragraphs)

    sentences: List[Dict[str, Any]] = []
    paragraph_records: List[Dict[str, Any]] = []
    warnings: List[str] = list(doc.warnings)
    counts = {"references": 0, "headings": 0, "short": 0, "quoted": 0}

    for para in paragraphs:
        para_sentences: List[Dict[str, Any]] = []
        for sentence_text, local_start, local_end in split_sentences(para["text"]):
            display = normalize_display(sentence_text)
            if not display:
                continue
            words = display.split()
            reason = None
            if para.get("is_heading"):
                reason = "heading"
                counts["headings"] += 1
            elif para.get("section") == "references" and exclude_references:
                reason = "references"
                counts["references"] += 1
            elif len(words) < min_words or len(display) < min_chars:
                reason = "too_short"
                counts["short"] += 1
            elif ignore_quotations and _is_quoted(display):
                reason = "quotation"
                counts["quoted"] += 1

            sentence = {
                "id": f"{label}-{len(sentences)}",
                "doc": label,
                "index": len(sentences),
                "text": display,
                "norm_text": normalize_for_match(display),
                "start": para["start"] + local_start,
                "end": para["start"] + local_end,
                "page": para.get("page", 0),
                "paragraph": para["index"],
                "section": para.get("section", "body"),
                "is_heading": bool(para.get("is_heading")),
                "is_quoted": _is_quoted(display),
                "word_count": len(words),
                "char_count": len(display),
                "content_tokens": content_tokens(display),
                "content_terms": content_terms(display),
                "eligible": reason is None,
                "exclude_reason": reason,
            }
            if exclude_headings and sentence["is_heading"]:
                sentence["eligible"] = False
                sentence["exclude_reason"] = "heading"
            sentences.append(sentence)
            para_sentences.append(sentence)

        paragraph_records.append(
            {
                "id": f"{label}-p{para['index']}",
                "doc": label,
                "index": para["index"],
                "text": para["text"],
                "page": para.get("page", 0),
                "section": para.get("section", "body"),
                "is_heading": bool(para.get("is_heading")),
                "start": para["start"],
                "end": para["end"],
                "sentence_ids": [s["id"] for s in para_sentences],
                "eligible": any(s["eligible"] for s in para_sentences),
            }
        )

    if counts["references"]:
        warnings.append(
            f"{plural(counts['references'], 'sentence')} from the reference list "
            f"{'was' if counts['references'] == 1 else 'were'} excluded from matching "
            "(bibliographies repeat verbatim across papers and are not evidence)."
        )
    if counts["short"]:
        warnings.append(
            f"{plural(counts['short'], 'very short fragment', 'very short fragments')} "
            f"({min_words} words minimum) {'was' if counts['short'] == 1 else 'were'} kept for "
            "display but excluded from matching."
        )
    if counts["quoted"]:
        warnings.append(
            f"{plural(counts['quoted'], 'quoted sentence')} "
            f"{'was' if counts['quoted'] == 1 else 'were'} excluded (quotation option enabled)."
        )

    eligible = [s for s in sentences if s["eligible"]]
    if len(eligible) < 3:
        from services.document_extractor import ExtractionError

        raise ExtractionError(
            "not_enough_text",
            f"Only {plural(len(eligible), 'comparable sentence')} "
            f"{'was' if len(eligible) == 1 else 'were'} found in this document. "
            "At least 3 sentences with five or more words are required.",
        )
    if len(eligible) > Config.MAX_SENTENCES_PER_DOC:
        from services.document_extractor import ExtractionError

        raise ExtractionError(
            "too_many_sentences",
            f"The document contains {len(eligible):,} comparable sentences, above the "
            f"{Config.MAX_SENTENCES_PER_DOC:,} sentence analysis limit.",
            status_code=413,
        )

    word_total = sum(s["word_count"] for s in sentences)
    return {
        "label": label,
        "filename": doc.filename,
        "file_type": doc.file_type,
        "page_count": doc.page_count,
        "char_count": doc.char_count,
        "word_count": word_total,
        "paragraph_count": len(paragraph_records),
        "sentence_count": len(sentences),
        "eligible_sentence_count": len(eligible),
        "eligible_word_count": sum(s["word_count"] for s in eligible),
        "sentences": sentences,
        "paragraphs": paragraph_records,
        "warnings": warnings,
        "metadata": dict(getattr(doc, "metadata", {}) or {}),
        "sections_present": sorted({s["section"] for s in sentences}),
    }


def prepare_both(doc_a: Any, doc_b: Any, options: Optional[Dict[str, Any]] = None) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    return prepare_document(doc_a, "A", options), prepare_document(doc_b, "B", options)
