"""Unit tests for cleaning, sentence segmentation and section detection."""

from __future__ import annotations

import pytest

from services.document_extractor import clean_block_text
from services.text_preprocessor import (
    content_tokens,
    detect_reference_start,
    normalize_for_match,
    prepare_document,
    split_sentences,
)
from services.document_extractor import ExtractedDocument


def test_whitespace_and_control_characters_are_cleaned():
    raw = "Deep   learning\tmodels\x00 require  large datasets.\n\n"
    cleaned = clean_block_text(raw)
    assert "\x00" not in cleaned
    assert "  " not in cleaned
    assert cleaned.startswith("Deep learning models")


def test_hyphenated_line_breaks_are_rejoined():
    assert clean_block_text("detec-\ntion of copied text") == "detection of copied text"


@pytest.mark.parametrize(
    "text,expected_count",
    [
        ("This is one sentence. This is another.", 2),
        ("Only a single sentence here.", 1),
        ("Results were mixed. However, accuracy improved.", 2),
        ("", 0),
    ],
)
def test_sentence_counts(text, expected_count):
    assert len(split_sentences(text)) == expected_count


def test_abbreviations_do_not_split_sentences():
    text = "The method of Smith et al. was used. We then compared results."
    sentences = [s for s, _, _ in split_sentences(text)]
    assert len(sentences) == 2
    assert "et al." in sentences[0]


def test_decimals_and_initials_do_not_split_sentences():
    text = "The threshold was 0.62 in this study. J. Smith reported 0.75 earlier."
    sentences = [s for s, _, _ in split_sentences(text)]
    assert len(sentences) == 2
    assert "0.62" in sentences[0]


def test_sentence_offsets_are_consistent():
    text = "First sentence here. Second sentence follows."
    for sentence, start, end in split_sentences(text):
        assert text[start:end].strip() == sentence


def test_normalize_for_match_ignores_case_and_punctuation():
    assert normalize_for_match("The Model performs Well!") == \
        normalize_for_match("the model, performs well")


def test_content_tokens_remove_stopwords_and_stem():
    tokens = content_tokens("The models were performing well on the datasets")
    assert "the" not in tokens
    assert any(token.startswith("model") for token in tokens)


def _document(paragraphs):
    return ExtractedDocument(
        filename="t.txt", file_type="txt", text="", paragraphs=paragraphs,
        page_count=0, char_count=0, word_count=0,
    )


def _paragraphs(texts):
    return [
        {"index": i, "text": t, "page": 1, "style": "", "is_heading": False, "start": 0, "end": 0}
        for i, t in enumerate(texts)
    ]


def test_reference_section_is_detected_and_excluded():
    paragraphs = _paragraphs([
        "The study compares two similarity approaches across annotated pairs of sentences.",
        "Results show a clear advantage for the embedding based method in most conditions.",
        "A human annotator reviewed every flagged pair before it entered the evaluation set.",
        "References",
        "Smith JA, Kumar R. Fingerprinting methods for large collections. 2019;14(2):112-129.",
        "Liu X, Andersen P. Paraphrase identification with embeddings. 2021:445-458.",
    ])
    assert detect_reference_start(paragraphs) == 3
    prepared = prepare_document(_document(paragraphs), "A", {"exclude_references": True})
    assert "references" in prepared["sections_present"]
    assert all(
        not s["eligible"] for s in prepared["sentences"] if s["section"] == "references"
    )


def test_short_fragments_are_kept_but_not_comparable():
    prepared = prepare_document(
        _document(_paragraphs([
            "This is a sufficiently long sentence for comparison purposes.",
            "Too short.",
            "Another sentence that is long enough to be compared with something else.",
            "A third sentence of adequate length to satisfy the minimum requirement.",
        ])),
        "A", {},
    )
    short = [s for s in prepared["sentences"] if s["exclude_reason"] == "too_short"]
    assert len(short) == 1
    assert short[0]["eligible"] is False


def test_prepare_document_requires_enough_comparable_text():
    from services.document_extractor import ExtractionError

    with pytest.raises(ExtractionError):
        prepare_document(_document(_paragraphs(["Too short."])), "A", {})
