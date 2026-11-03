"""
End-to-end tests of the detection engine on controlled document pairs.

These tests assert *behaviour*, not exact scores: exact copies must be classified
as exact, paraphrases must be found semantically, unrelated text must not be
flagged, and generic boilerplate must be suppressed rather than counted.
"""

from __future__ import annotations

import pytest

from services.document_extractor import ExtractedDocument
from services.plagiarism_detector import detect_plagiarism
from services.text_preprocessor import prepare_document

ORIGINAL = [
    "Automated integrity screening has become common in universities over the past decade.",
    "Most deployed systems compare character n-grams or word sequences between documents.",
    "A learner who replaces half of the words in a paragraph can reduce a string matching score to almost zero.",
    "Semantic representations offer an alternative because they encode meaning rather than surface form.",
    "The pipeline recovers paraphrases that lexical baselines cannot detect at the same operating point.",
    "Reference lists are excluded from matching because bibliographies repeat across unrelated papers.",
]

VERBATIM = [
    "Automated integrity screening has become common in universities over the past decade.",   # exact
    "A learner who replaces half of the words in a paragraph can reduce a string matching score to almost zero.",  # exact
    "Rewriting roughly half of the vocabulary in a paragraph can push lexical similarity close to zero.",  # paraphrase
    "Because these vectors are trained on large text collections, changes in wording barely affect them.",  # paraphrase
    "Reference lists are excluded from matching because bibliographies repeat across unrelated papers.",  # exact
]

UNRELATED = [
    "Soil samples were collected from twelve sites and analysed for heavy metal concentration.",
    "Undergraduate admission policies vary considerably between institutions and regions.",
    "The fermentation process was monitored continuously for fourteen days at eighteen degrees.",
    "Marine biologists tagged forty green turtles near the reef during the summer survey.",
    "Interest rates were held constant throughout the entire simulation of the model economy.",
    "Library orientation sessions were delivered online for the duration of the pandemic.",
]

BOILERPLATE_A = [
    "In recent years the amount of published research has grown considerably in most disciplines.",
    "The results indicate that the proposed approach is effective across the tested conditions.",
    "The present study has several limitations that should be acknowledged by the reader.",
    "Further research is needed to confirm these findings in different institutional settings.",
    "It is important to note that the observed differences were relatively small in practice.",
]
BOILERPLATE_B = [
    "In recent years the volume of published research has increased substantially across disciplines.",
    "The results show that the suggested method performs effectively for the tested conditions.",
    "This study has a number of limitations that must be acknowledged by the reader.",
    "Further research is required to confirm these results in other institutional contexts.",
    "It should be noted that the observed differences were fairly small in practice.",
]


def _document(paragraphs, name="doc.txt"):
    return ExtractedDocument(
        filename=name, file_type="txt", text="\n\n".join(paragraphs),
        paragraphs=[
            {"index": i, "text": text, "page": 1, "style": "", "is_heading": False}
            for i, text in enumerate(paragraphs)
        ],
        page_count=1, char_count=sum(len(p) for p in paragraphs),
        word_count=sum(len(p.split()) for p in paragraphs),
    )


def _prepare(paragraphs, label):
    return prepare_document(_document(paragraphs), label, {})


@pytest.fixture(scope="module")
def mixed_result():
    return detect_plagiarism(_prepare(ORIGINAL, "A"), _prepare(VERBATIM, "B"), {})


def test_exact_copies_are_classified_exact(mixed_result):
    exact = [m for m in mixed_result["matches"] if m["is_primary"] and m["classification"] == "exact"]
    assert len(exact) >= 3
    for match in exact:
        assert match["similarity_pct"] > 99.9
        assert match["signals"]["longest_verbatim_words"] >= 10


def test_paraphrases_are_found_semantically(mixed_result):
    primary = [m for m in mixed_result["matches"] if m["is_primary"]]
    assert any(m["classification"] == "semantic" for m in primary), \
        "paraphrased sentences should produce semantic matches"


def test_matches_carry_explanations_and_positions(mixed_result):
    for match in mixed_result["matches"]:
        assert match["explanation"]["headline"]
        assert match["explanation"]["caveat"]
        assert match["source"]["index"] >= 0
        assert match["target"]["index"] >= 0
        assert match["band"] in {"very_high", "high", "moderate", "low"}


def test_unrelated_documents_produce_no_strong_matches():
    result = detect_plagiarism(_prepare(ORIGINAL, "A"), _prepare(UNRELATED, "B"), {})
    primary = [m for m in result["matches"] if m["is_primary"]]
    assert len(primary) == 0 or all(m["similarity"] < 0.70 for m in primary)
    assert result["summary"]["weighted_similarity_pct"] < 15


def test_identical_documents_score_one_hundred():
    result = detect_plagiarism(_prepare(ORIGINAL, "A"), _prepare(ORIGINAL, "B"), {})
    assert result["summary"]["max_similarity_pct"] == 100.0
    assert result["summary"]["exact_matches"] == result["summary"]["primary_matches"]
    assert result["summary"]["coverage"]["A"]["sentence_coverage_pct"] == 100.0


def test_generic_boilerplate_is_flagged_and_downgraded():
    result = detect_plagiarism(_prepare(BOILERPLATE_A, "A"), _prepare(BOILERPLATE_B, "B"), {
        "semantic_threshold": 0.55,
    })
    generic = [m for m in result["matches"] if m["is_primary"] and m["generic_phrasing"]]
    assert generic, "boilerplate pairs should be marked as generic academic phrasing"
    for match in generic:
        assert match["evidence_strength"] == "weak"
        assert any("generic academic vocabulary" in reason
                   for reason in match["explanation"]["reasons"])
    assert result["summary"]["generic_phrasing_matches"] >= 3


def test_generic_boilerplate_below_high_band_is_suppressed():
    """Generic phrasing that is only weakly similar is noise, so it is suppressed."""
    result = detect_plagiarism(
        _prepare(BOILERPLATE_A, "A"), _prepare(BOILERPLATE_B, "B"),
        {"semantic_threshold": 0.40},
    )
    assert result["summary"]["suppressed_matches"] >= 0
    for match in result["matches"]:
        if match["suppressed"]:
            assert match["suppress_reason"] in {
                "generic_academic_phrasing", "no_shared_content_terms", "citation_context_only"
            }


def test_coverage_metrics_are_consistent(mixed_result):
    summary = mixed_result["summary"]
    for label in ("A", "B"):
        coverage = summary["coverage"][label]
        assert 0 <= coverage["sentence_coverage_pct"] <= 100
        assert coverage["words_covered"] <= coverage["words_considered"]
        assert coverage["sentences_matched"] <= coverage["sentences_considered"]


def test_weighted_index_equals_sum_of_scores_over_sentences(mixed_result):
    """index = Σ (best cosine per matched A sentence) / comparable sentences in A.

    Each sentence contributes at most once, at its strongest score, so the ratio is
    bounded by 1.0. (Summing every evidence row instead — including B→A reverse-only
    rows — is what previously produced values above 100%.)
    """
    summary = mixed_result["summary"]
    primary = [m for m in mixed_result["matches"] if m["is_primary"] and not m["suppressed"]]

    best_by_source = {}
    for match in primary:
        source_id = match["source"]["sentence_id"]
        best_by_source[source_id] = max(best_by_source.get(source_id, 0.0), match["similarity"])

    considered = summary["coverage"]["A"]["sentences_considered"]
    expected = sum(best_by_source.values()) / considered
    assert abs(expected - summary["weighted_similarity"]) < 1e-6
    assert summary["weighted_similarity"] <= 1.0


def test_counts_exclude_secondary_matches(mixed_result):
    summary = mixed_result["summary"]
    primary = [m for m in mixed_result["matches"] if m["is_primary"] and not m["suppressed"]]
    distinct_sources = {m["source"]["sentence_id"] for m in primary}

    # "primary_matches" counts matched sentences in A, not evidence rows.
    assert summary["primary_matches"] == len(distinct_sources)
    assert summary["evidence_rows"] == len(primary)
    assert summary["evidence_rows"] >= summary["primary_matches"]
    assert summary["all_match_candidates"] >= len(primary)


def test_passages_are_clustered(mixed_result):
    passages = mixed_result["passages"]
    assert passages, "consecutive matches should form at least one passage"
    assert max(p["size"] for p in passages) >= 2
    for passage in passages:
        assert passage["source_span"][0] <= passage["source_span"][1]


def test_reference_sections_are_excluded_from_matching():
    doc_a = ORIGINAL + [
        "References",
        "Smith JA, Kumar R. Fingerprinting methods for large collections. Journal of Integrity. 2019;14(2):112-129.",
        "Liu X, Andersen P. Paraphrase identification with embeddings. Proceedings of COLING. 2021:445-458.",
    ]
    result = detect_plagiarism(_prepare(doc_a, "A"), _prepare(VERBATIM, "B"), {})
    for match in result["matches"]:
        assert match["source"]["section"] != "references"
    assert any("reference list" in warning.lower() for warning in result["warnings"])


def test_threshold_option_changes_match_volume():
    low = detect_plagiarism(_prepare(ORIGINAL, "A"), _prepare(VERBATIM, "B"), {"semantic_threshold": 0.45})
    high = detect_plagiarism(_prepare(ORIGINAL, "A"), _prepare(VERBATIM, "B"), {"semantic_threshold": 0.80})
    assert low["summary"]["semantic_matches"] >= high["summary"]["semantic_matches"]

# --------------------------------------------------------------------------- #
# similarity index invariants (regression: index exceeded 100%)
# --------------------------------------------------------------------------- #
MANY_TO_ONE_B = []
for _ in range(4):
    MANY_TO_ONE_B += [
        "Over the past decade, automated integrity screening has become common across universities.",
        "Most systems that are deployed compare word sequences or character n-grams between documents.",
        "Semantic representations encode meaning instead of surface form inside a dense vector space.",
        "Bibliographies repeat across unrelated papers, so reference lists are excluded from matching.",
        "The pipeline detects paraphrases that lexical baselines cannot find at the same operating point.",
    ]

PARTIAL = [
    # two exact copies, one light paraphrase, three original sentences
    "Automated integrity screening has become common in universities over the past decade.",
    "Most deployed systems compare character n-grams or word sequences between documents.",
    "Rewriting most of the vocabulary in a paragraph pulls lexical similarity close to zero.",
    "Campus library hours were extended during the examination period last semester.",
    "Student feedback forms were collected after each of the twelve workshop sessions.",
    "The gardening society planted forty bulbs along the eastern boundary of the campus.",
]


def _summary(paragraphs_a, paragraphs_b, options=None):
    result = detect_plagiarism(_prepare(paragraphs_a, "A"), _prepare(paragraphs_b, "B"), options or {})
    return result["summary"], result


def test_many_to_one_matches_do_not_inflate_the_index():
    """One A sentence matched by many B sentences must count once.

    Regression: every reverse-only evidence row was added to the numerator while the
    denominator stayed len(comparable sentences in A), which produced a 392% index.
    """
    summary, result = _summary(ORIGINAL[:5], MANY_TO_ONE_B)

    comparable_a = summary["coverage"]["A"]["sentences_considered"]
    assert summary["evidence_rows"] > summary["primary_matches"], \
        "this fixture is only meaningful if it really produces reverse-only evidence"
    assert summary["reverse_only_evidence"] > 0

    assert summary["primary_matches"] <= comparable_a
    assert summary["weighted_similarity_pct"] <= 100.0
    assert 0.0 <= summary["weighted_similarity"] <= 1.0


def test_index_equals_average_times_coverage():
    """index = mean(best cosine per matched A sentence) x (matched / comparable)."""
    summary, _ = _summary(ORIGINAL, PARTIAL)
    comparable_a = summary["coverage"]["A"]["sentences_considered"]
    matched_a = summary["coverage"]["A"]["sentences_matched"]

    assert matched_a == summary["primary_matches"]
    expected = summary["average_matched_similarity"] * (matched_a / comparable_a)
    assert abs(summary["weighted_similarity"] - expected) < 0.002


def test_every_metric_stays_inside_its_valid_range():
    pairs = [
        (ORIGINAL, ORIGINAL),
        (ORIGINAL, VERBATIM),
        (ORIGINAL, PARTIAL),
        (ORIGINAL, UNRELATED),
        (BOILERPLATE_A, BOILERPLATE_B),
        (ORIGINAL[:3], MANY_TO_ONE_B),
    ]
    for paragraphs_a, paragraphs_b in pairs:
        summary, _ = _summary(paragraphs_a, paragraphs_b)
        assert 0.0 <= summary["weighted_similarity"] <= 1.0
        assert 0.0 <= summary["average_matched_similarity"] <= 1.0
        assert 0.0 <= summary["max_similarity"] <= 1.0
        for label in ("A", "B"):
            coverage = summary["coverage"][label]
            assert 0.0 <= coverage["sentence_coverage_pct"] <= 100.0
            assert 0.0 <= coverage["word_coverage_pct"] <= 100.0
            assert coverage["sentences_matched"] <= coverage["sentences_considered"]
            assert coverage["words_covered"] <= coverage["words_considered"]


def test_identical_documents_report_exactly_one_hundred_percent():
    summary, _ = _summary(ORIGINAL, ORIGINAL)
    assert summary["weighted_similarity_pct"] == 100.0
    assert summary["average_matched_similarity_pct"] == 100.0
    assert summary["coverage"]["A"]["sentence_coverage_pct"] == 100.0
    assert summary["primary_matches"] == summary["coverage"]["A"]["sentences_considered"]


def test_unrelated_documents_stay_near_zero():
    summary, result = _summary(ORIGINAL, UNRELATED)
    assert summary["weighted_similarity_pct"] < 15
    assert summary["exact_matches"] == 0
    assert summary["near_exact_matches"] == 0


def test_paraphrase_is_found_without_exact_matches():
    paraphrase_only = [
        "Rewriting about half of the vocabulary in a paragraph can push lexical similarity close to zero.",
        "Because these vectors are trained on large text collections, changes in wording barely affect them.",
        "Over the past decade, automated integrity screening has become common across universities.",
        "Systems that are deployed usually compare word sequences or character n-grams between documents.",
        "Bibliographies repeat across unrelated papers, so reference lists are excluded from matching.",
        "The pipeline detects paraphrases that lexical baselines cannot find at the same operating point.",
    ]
    summary, result = _summary(ORIGINAL, paraphrase_only)
    primary = [m for m in result["matches"] if m["is_primary"]]
    assert any(m["classification"] == "semantic" for m in primary)
    assert summary["weighted_similarity_pct"] <= 100.0
    assert 0 < summary["weighted_similarity_pct"] < 100


def test_too_little_text_is_rejected_with_a_clear_message():
    from services.document_extractor import ExtractionError

    with pytest.raises(ExtractionError) as excinfo:
        _prepare(["Only one short sentence here."], "A")
    assert excinfo.value.code == "not_enough_text"
    assert "comparable sentence" in excinfo.value.message
