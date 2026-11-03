"""
The VeriText AI detection engine.

Pipeline
--------
sentence segmentation (text_preprocessor)
        -> sentence embeddings (embedding_service, all-MiniLM-L6-v2)
        -> cosine similarity + top-k candidate retrieval (similarity_engine)
        -> lexical evidence (exact / near-exact / shared distinctive terms)
        -> classification + safeguards + explanation
        -> coverage & distribution metrics
        -> paragraph-level view

Important conceptual rules encoded here
---------------------------------------
* A cosine score measures **semantic closeness, not misconduct**. Every match
  carries a caveat and the top-level result carries a disclaimer.
* Exact, near-exact and semantic matches are *different kinds of evidence* and
  are counted separately.
* Reference lists, headings and very short fragments never enter the comparison.
* Pairs whose only shared content is generic academic phrasing are suppressed
  (kept in the payload with a reason, excluded from the headline metrics).
* Counts are based on *primary* (best) matches per sentence, so one sentence
  matching six others cannot inflate the result; alternatives are kept as
  secondary evidence for the viewer.
* The document-level number is a coverage-weighted similarity index
  (Σ best cosine of matched sentences / comparable sentences). It is explicitly
  **not** "percentage plagiarised", and the raw mean of all pairwise cosines is
  never reported as such.
"""

from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from config import Config
from services.embedding_service import get_embedding_service
from services.similarity_engine import (
    BAND_LABELS,
    longest_common_substring_words,
    lexical_comparison,
    similarity_band,
    top_k_similarities,
)
from services.text_preprocessor import content_tokens
from utils.text import plural

# --------------------------------------------------------------------------- #
# domain knowledge used by the safeguards
# --------------------------------------------------------------------------- #
GENERIC_ACADEMIC_PHRASES = [
    "further research is needed", "further research is required", "in recent years",
    "has gained significant attention", "plays an important role", "plays a crucial role",
    "the results show that", "the results indicate that", "this paper presents",
    "this study investigates", "this study aims to", "the purpose of this study",
    "it is important to note", "it should be noted", "on the other hand", "as a result",
    "due to the fact that", "state of the art", "a wide range of", "in terms of",
    "with respect to", "there is a growing body of", "significant differences between",
    "in conclusion", "in summary", "the present study", "according to the",
    "these findings suggest", "is one of the most", "has been widely used",
    "have been proposed", "in the field of", "the concept of", "with the development of",
    "recent studies have shown", "a number of studies", "in the context of",
    "the proposed method", "the experimental results", "on the basis of",
    "as well as the", "it is well known that", "the fact that the",
    "data were collected", "data were gathered", "the proposed approach",
    "consists of three main", "main stages", "main components",
]

# Curated list of vocabulary that is generic to academic writing rather than
# specific to a claim: methodology nouns, reporting verbs and evaluation terms.
# A matched pair whose *only* shared content words come from this list is weak
# evidence — anything can share "study", "method" and "results".
GENERIC_ACADEMIC_VOCABULARY = [
    "study", "studies", "paper", "article", "research", "researcher", "work",
    "method", "methods", "methodology", "approach", "technique", "framework",
    "result", "results", "finding", "findings", "outcome", "data", "dataset",
    "analysis", "analyses", "experiment", "experiments", "experimental",
    "evaluation", "evaluate", "measure", "measurement", "metric", "score",
    "performance", "accuracy", "precision", "recall", "baseline", "comparison",
    "model", "models", "system", "systems", "algorithm", "task", "process",
    "propose", "proposed", "present", "presented", "show", "showed", "shown",
    "indicate", "suggest", "demonstrate", "observe", "observed", "report",
    "reported", "describe", "described", "examine", "investigate", "consider",
    "provide", "achieve", "improve", "increase", "decrease", "reduce", "require",
    "significant", "significantly", "important", "relevant", "effective", "efficient",
    "limitation", "limitations", "future", "further", "additional", "furthermore",
    "however", "therefore", "moreover", "conclusion", "introduction", "background",
    "related", "literature", "review", "survey", "participant", "sample", "group",
    "condition", "factor", "variable", "value", "level", "type", "kind", "form",
    "number", "large", "small", "high", "low", "current", "existing", "previous",
    "novel", "new", "main", "key", "various", "different", "similar", "common",
    "widely", "generally", "typically", "usually", "often", "well", "also",
]
GENERIC_STEMS = (
    {stem for phrase in GENERIC_ACADEMIC_PHRASES for stem in content_tokens(phrase)}
    | {stem for word in GENERIC_ACADEMIC_VOCABULARY for stem in content_tokens(word)}
)

# Sentence pairs that both read as a definition ("X is the ...", "X refers to ...")
# legitimately score very high. They are still reported (verbatim definitions can be
# copied), but the explanation says why the score should be read with care.
_DEFINITION_PATTERNS = re.compile(
    r"\b(is|are|refers to|is defined as|means|denotes|describes|is called)\b\s+(a|an|the|defined)?",
    re.IGNORECASE,
)

_CITATION_PATTERNS = (
    r"\([^()]*\b(19|20)\d{2}[a-z]?\b[^()]*\)",     # (Smith, 2019)
    r"\[[0-9,\s\-\u2013]+\]",                        # [12], [3-5]
    r"\bet al\.?",                                   # et al.
)

DISCLAIMER = (
    "Similarity is measured, misconduct is not. VeriText AI reports semantic and lexical "
    "overlap between two documents that the user supplied. Overlap can be legitimate "
    "(quotation, common definitions, standard methodology wording, shared data description). "
    "A high score is a prompt for human review, never a finding of plagiarism."
)

CLASSIFICATION_LABELS = {
    "exact": "Exact textual match",
    "near_exact": "Near-exact textual match",
    "semantic": "Semantic similarity",
}
SUBTYPE_LABELS = {
    "paraphrase": "Likely paraphrase — rewritten wording, close meaning",
    "shared_wording": "Close meaning plus substantial shared wording",
}

DOCUMENT_BANDS = [
    (0.0, 0.10, "low", "Low overlap", "Little measurable overlap between the two documents."),
    (0.10, 0.25, "moderate", "Moderate overlap",
     "Some shared passages or closely related wording; review the flagged matches."),
    (0.25, 0.45, "elevated", "Elevated overlap",
     "A substantial share of comparable sentences is closely related. Careful human review is advised."),
    (0.45, 1.01, "high", "High overlap",
     "Large portions of the documents are semantically close. Check quotations and provenance before drawing conclusions."),
]


def _document_band(score: float) -> Dict[str, str]:
    for low, high, level, label, description in DOCUMENT_BANDS:
        if low <= score < high:
            return {"level": level, "label": label, "description": description}
    return {"level": "low", "label": "Low overlap", "description": ""}


def _strip_citations(text: str) -> str:
    stripped = text
    for pattern in _CITATION_PATTERNS:
        stripped = re.sub(pattern, " ", stripped)
    return stripped


def _sentence_payload(sentence: Dict[str, Any]) -> Dict[str, Any]:
    """Compact, serialisable view of a sentence (no embeddings, no internals)."""
    return {
        "sentence_id": sentence["id"],
        "index": sentence["index"],
        "text": sentence["text"],
        "page": sentence.get("page", 0),
        "paragraph": sentence.get("paragraph", 0),
        "section": sentence.get("section", "body"),
        "word_count": sentence["word_count"],
        "start": sentence.get("start"),
        "end": sentence.get("end"),
        "is_quoted": sentence.get("is_quoted", False),
    }


# --------------------------------------------------------------------------- #
# pair classification
# --------------------------------------------------------------------------- #
def _classify_pair(
    source: Dict[str, Any],
    target: Dict[str, Any],
    cosine: float,
    lexical: Dict[str, Any],
    config: Any = Config,
) -> Dict[str, Any]:
    """
    Decide what *kind* of overlap a candidate pair shows, and whether it carries
    enough distinctive evidence to be counted.
    """
    shared_terms = lexical["shared_content_terms"]
    # "Distinctive" = shared content words that are specific to the claim rather than
    # generic academic vocabulary. Two sentences that only share words like
    # "method", "results" or "study" have not demonstrated reuse.
    distinctive_terms = [
        term for term in shared_terms
        if not (set(content_tokens(term)) & GENERIC_STEMS)
    ]
    generic_only = bool(shared_terms) and not distinctive_terms

    # A sentence is "formulaic" when most of its content words come from generic
    # academic vocabulary; two formulaic sentences that share wording are almost
    # always standard phrasing rather than copied argument.
    def generic_ratio(sentence: Dict[str, Any]) -> float:
        tokens = sentence.get("content_tokens") or []
        if not tokens:
            return 1.0
        return sum(1 for t in tokens if t in GENERIC_STEMS) / len(tokens)

    ratio_source, ratio_target = generic_ratio(source), generic_ratio(target)
    formulaic = min(ratio_source, ratio_target) >= 0.5
    generic_phrasing = generic_only or formulaic

    if lexical["is_exact_string"]:
        classification, subtype = "exact", None
    elif lexical["sequence_ratio"] >= config.NEAR_EXACT_LEXICAL:
        classification, subtype = "near_exact", None
    elif cosine >= config.SEMANTIC_THRESHOLD:
        classification = "semantic"
        # A paraphrase rewrites the wording: little lexical overlap but strong meaning
        # overlap. When the word overlap is high as well, the pair shows both signals
        # (a lightly edited sentence), which is stronger evidence than meaning alone.
        if lexical["content_overlap"] < 0.34 and lexical["token_jaccard"] < 0.45:
            subtype = "paraphrase"
        else:
            subtype = "shared_wording"
    else:
        classification, subtype = None, None

    suppressed = False
    suppress_reason = None

    if classification in ("exact", "near_exact"):
        # Verbatim/near-verbatim strings are reported even if the wording is generic:
        # the user can judge; we never hide literal copying.
        pass
    elif classification == "semantic":
        if config.SUPPRESS_COMMON_PHRASES and generic_phrasing and cosine < config.HIGH_SIMILARITY:
            suppressed = True
            suppress_reason = (
                "generic_academic_phrasing" if shared_terms else "no_shared_content_terms"
            )
        else:
            # Citations can make two unrelated literature-review sentences look close.
            src_wo = content_tokens(_strip_citations(source["text"]))
            tgt_wo = content_tokens(_strip_citations(target["text"]))
            if not (set(src_wo) & set(tgt_wo)) and len(src_wo) >= 2 and len(tgt_wo) >= 2:
                suppressed = True
                suppress_reason = "citation_context_only"

    return {
        "classification": classification,
        "subtype": subtype,
        "suppressed": suppressed,
        "suppress_reason": suppress_reason,
        "generic_only": generic_only,
        "generic_phrasing": generic_phrasing,
        "formulaic": formulaic,
        "generic_ratio": round(min(ratio_source, ratio_target), 3),
        "distinctive_terms": distinctive_terms,
    }


def _explain(
    source: Dict[str, Any],
    target: Dict[str, Any],
    cosine: float,
    lexical: Dict[str, Any],
    verdict: Dict[str, Any],
    verbatim_words: int,
    verbatim_text: str,
) -> Dict[str, Any]:
    """
    Human-readable justification for a flagged pair — the part that turns a score
    into something a reviewer can act on.
    """
    classification = verdict["classification"]
    reasons: List[str] = []
    pct = round(cosine * 100, 1)

    if classification == "exact":
        headline = "Identical wording after normalisation (case and punctuation ignored)."
        reasons.append("Both sentences reduce to the same word sequence.")
    elif classification == "near_exact":
        changed = max(0, max(source["word_count"], target["word_count"]) - verbatim_words)
        headline = (
            f"Almost identical wording: {lexical['sequence_ratio'] * 100:.0f}% of the token "
            f"sequence matches, with about {plural(changed, 'word')} changed or reordered."
        )
        if verbatim_words:
            reasons.append(f"{verbatim_words} consecutive words are identical verbatim.")
    elif verdict["subtype"] == "paraphrase":
        headline = (
            f"Meaning is close (cosine {pct}%) although the wording was rewritten — "
            "only "
            f"{plural(len(lexical['shared_content_terms']), 'distinctive term')} "
            f"{'is' if len(lexical['shared_content_terms']) == 1 else 'are'} shared."
        )
        reasons.append("Low word-level overlap combined with high embedding similarity is the "
                       "classic signature of paraphrasing.")
    else:
        headline = (
            f"Sentences are about the same content (cosine {pct}%) and share "
            f"{plural(len(lexical['shared_content_terms']), 'distinctive term')}."
        )

    display_terms = lexical.get("shared_terms_display") or lexical["shared_content_terms"]
    if display_terms:
        reasons.append("Shared distinctive terms: " + ", ".join(display_terms[:10]) + ".")
    if classification == "semantic":
        reasons.append(
            f"Lexical overlap is {lexical['token_jaccard'] * 100:.0f}% (Jaccard), "
            f"a contiguous verbatim run of {plural(verbatim_words, 'word')}."
        )
    if cosine < Config.HIGH_SIMILARITY and classification == "semantic":
        reasons.append("Similarity is below the high-similarity band, so this may reflect a "
                       "shared topic or standard phrasing rather than copying.")
    definition_like = bool(
        _DEFINITION_PATTERNS.search(source["text"]) and _DEFINITION_PATTERNS.search(target["text"])
    )
    if verdict.get("generic_phrasing"):
        reasons.append(
            "Most of the shared wording is generic academic vocabulary "
            f"({verdict['generic_ratio'] * 100:.0f}% of the content words are generic). "
            "Standard phrasing of this type recurs across unrelated documents, so this is "
            "weak evidence of reuse even when the similarity is high."
        )
    if definition_like:
        reasons.append(
            "Both sentences follow a definition pattern ('X is …' / 'X refers to …'). "
            "Textbook definitions are frequently phrased almost identically without any "
            "copying, so treat a definition-shaped match as weak evidence."
        )

    return {
        "headline": headline,
        "reasons": reasons,
        "definition_like": definition_like,
        "shared_terms": (lexical.get("shared_terms_display") or lexical["shared_content_terms"])[:10],
        "verbatim_run": verbatim_text,
        "verbatim_words": verbatim_words,
        "caveat": (
            "This flag describes textual/semantic overlap only. Verify with the original "
            "sources and citation practice before drawing any conclusion."
        ),
    }



# --------------------------------------------------------------------------- #
# passage clustering
# --------------------------------------------------------------------------- #
def _cluster_matches(matches: List[Dict[str, Any]], config: Any = Config) -> List[Dict[str, Any]]:
    """
    Group primary matches into *passages*.

    Real reused material produces runs of consecutive matching sentences, whereas
    boilerplate and shared definitions tend to appear as isolated matches scattered
    in unrelated contexts. Grouping is therefore both a usability feature (the UI
    can show "passage of 4 sentences") and an evidence-strength signal.
    """
    ordered = sorted(matches, key=lambda m: m["source"]["index"])
    clusters: List[Dict[str, Any]] = []
    for match in ordered:
        attached = False
        for cluster in clusters:
            last = cluster["members"][-1]
            source_gap = match["source"]["index"] - last["source"]["index"]
            target_gap = abs(match["target"]["index"] - last["target"]["index"])
            if 0 < source_gap <= 2 and target_gap <= 2:
                cluster["members"].append(match)
                attached = True
                break
        if not attached:
            clusters.append({"members": [match]})

    for number, cluster in enumerate(clusters, start=1):
        members = cluster["members"]
        best = max(m["similarity"] for m in members)
        for match in members:
            match["cluster"] = {
                "cluster_id": f"PS{number}",
                "size": len(members),
                "similarity_max": round(best, 4),
            }
        cluster["cluster_id"] = f"PS{number}"
        cluster["size"] = len(members)
        cluster["similarity_max"] = round(best, 4)

    # Evidence strength per match: verbatim evidence and clustered passages are
    # stronger than a single isolated semantic hit.
    for match in ordered:
        if match.get("generic_phrasing") and match["classification"] == "semantic":
            # Meaning-only overlap between formulaic sentences is never strong evidence.
            strength = "weak"
        elif match["classification"] in ("exact", "near_exact"):
            strength = "strong"
        elif match["cluster"]["size"] >= 2 or match["similarity"] >= config.HIGH_SIMILARITY:
            strength = "strong"
        elif match["similarity"] >= config.MODERATE_SIMILARITY:
            strength = "moderate"
        else:
            strength = "weak"
        match["evidence_strength"] = strength
    return clusters


# --------------------------------------------------------------------------- #
# main entry point
# --------------------------------------------------------------------------- #
def detect_plagiarism(
    prep_a: Dict[str, Any],
    prep_b: Dict[str, Any],
    options: Optional[Dict[str, Any]] = None,
    config: Any = Config,
) -> Dict[str, Any]:
    """
    Compare two prepared documents and return a fully explainable result object.
    This function performs real embedding + real cosine computation on the
    supplied text; nothing in the result is randomly generated.
    """
    options = dict(options or {})
    started = time.perf_counter()
    embedder = get_embedding_service()

    top_k = int(options.get("top_k", config.TOP_K_PER_SENTENCE))
    semantic_threshold = float(options.get("semantic_threshold", config.SEMANTIC_THRESHOLD))
    paragraph_threshold = float(options.get("paragraph_threshold", config.PARAGRAPH_THRESHOLD))

    eligible_a = [s for s in prep_a["sentences"] if s["eligible"]]
    eligible_b = [s for s in prep_b["sentences"] if s["eligible"]]

    # ------------------------------------------------------------- embeddings
    t0 = time.perf_counter()
    emb_a = embedder.encode([s["text"] for s in eligible_a], progress_label="document A")
    emb_b = embedder.encode([s["text"] for s in eligible_b], progress_label="document B")
    embed_seconds = time.perf_counter() - t0

    # ------------------------------------------------------- candidate pairs
    t0 = time.perf_counter()
    forward = top_k_similarities(emb_a, emb_b, k=top_k)     # A -> B
    backward = top_k_similarities(emb_b, emb_a, k=top_k)    # B -> A (for coverage of B)
    match_seconds = time.perf_counter() - t0

    matches: List[Dict[str, Any]] = []
    counter = {"value": 0}

    def build_match(i: int, j: int, cosine: float, is_primary: bool, rank: int) -> Dict[str, Any]:
        source, target = eligible_a[i], eligible_b[j]
        lexical = lexical_comparison(
            source["norm_text"], target["norm_text"],
            source["content_tokens"], target["content_tokens"],
            source.get("content_terms"), target.get("content_terms"),
        )
        verdict = _classify_pair(source, target, cosine, lexical, config)
        verbatim_words, verbatim_text = longest_common_substring_words(source["text"], target["text"])
        explanation = _explain(source, target, cosine, lexical, verdict, verbatim_words, verbatim_text)
        counter["value"] += 1
        return {
            "id": f"M{counter['value']}",
            "is_primary": is_primary,
            "rank_in_source": rank,
            "classification": verdict["classification"] or "below_threshold",
            "classification_label": CLASSIFICATION_LABELS.get(verdict["classification"] or "", "Below threshold"),
            "subtype": verdict["subtype"],
            "subtype_label": SUBTYPE_LABELS.get(verdict["subtype"] or "", ""),
            "similarity": round(float(cosine), 4),
            "similarity_pct": round(float(cosine) * 100, 1),
            "band": similarity_band(float(cosine), config),
            "band_label": BAND_LABELS[similarity_band(float(cosine), config)],
            "source": _sentence_payload(source),
            "target": _sentence_payload(target),
            "signals": {
                "cosine": round(float(cosine), 4),
                "sequence_ratio": lexical["sequence_ratio"],
                "token_jaccard": lexical["token_jaccard"],
                "content_overlap": lexical["content_overlap"],
                "shared_content_terms": lexical.get("shared_terms_display", lexical["shared_content_terms"]),
                "shared_token_count": lexical["shared_token_count"],
                "longest_verbatim_words": verbatim_words,
            },
            "explanation": explanation,
            "suppressed": verdict["suppressed"],
            "suppress_reason": verdict["suppress_reason"],
            "generic_phrasing": verdict["generic_phrasing"],
            "generic_ratio": verdict["generic_ratio"],
            "mutual_best": bool(
                forward["row_max_j"][i] == j and backward["row_max_j"][j] == i
            ),
        }

    def qualifies(match: Dict[str, Any]) -> bool:
        if match["classification"] == "below_threshold":
            return False
        if match["classification"] in ("exact", "near_exact"):
            return True
        return match["similarity"] >= semantic_threshold

    # Primary matches: best qualifying neighbour for each sentence of A.
    # Secondary matches: the remaining top-k neighbours, kept as alternatives
    # (they never change headline counts — that prevents many-to-one inflation).
    primary_by_source: Dict[int, Dict[str, Any]] = {}
    for i in range(len(eligible_a)):
        for rank, (j, score) in enumerate(
            zip(forward["top_indices"][i], forward["top_scores"][i])
        ):
            candidate = build_match(i, int(j), float(score), rank == 0, rank + 1)
            if not qualifies(candidate):
                continue
            if i not in primary_by_source:
                # Best qualifying neighbour -> primary evidence for this sentence.
                candidate["is_primary"] = True
                primary_by_source[i] = candidate
            else:
                # Alternative candidate -> secondary evidence (never inflates counts).
                candidate["is_primary"] = False
            matches.append(candidate)

    # Reverse direction: sentences in B that had no forward partner still count
    # toward B's coverage (asymmetry is normal — B may contain extra sources).
    matched_targets = {m["target"]["sentence_id"] for m in primary_by_source.values()}
    reverse_primary: Dict[int, Dict[str, Any]] = {}
    for j in range(len(eligible_b)):
        target_id = eligible_b[j]["id"]
        if target_id in matched_targets:
            continue
        for rank, (i, score) in enumerate(zip(backward["top_indices"][j], backward["top_scores"][j])):
            candidate = build_match(int(i), j, float(score), rank == 0, rank + 1)
            if not qualifies(candidate):
                continue
            if j not in reverse_primary:
                candidate["is_primary"] = True
                candidate["reverse_only"] = True
                reverse_primary[j] = candidate
                matches.append(candidate)
            break

    # ------------------------------------------------------------- safeguards
    suppressed_count = 0
    counted: List[Dict[str, Any]] = []
    for match in matches:
        if not match["is_primary"]:
            continue
        if match["suppressed"]:
            suppressed_count += 1
            continue
        counted.append(match)

    # ------------------------------------------------- one row per A sentence
    # `counted` holds one row per primary match, which includes *reverse-only* rows:
    # a B sentence with no forward partner whose best match is an A sentence that
    # may already carry a forward match. Those rows are genuine evidence for B's
    # coverage, but they must not enter A's numerator a second time. Summing every
    # row while dividing by the number of comparable sentences in A is what allowed
    # the index to exceed 100% (392% on a many-to-one pair, ~102% on the reported
    # document pair).
    #
    # Authoritative primary evidence for A = at most ONE row per comparable sentence
    # in A: the strongest (highest cosine) row across all of that sentence's evidence.
    # Hence 0 <= Σ best cosine <= number of comparable sentences and the index is
    # bounded by 1.0 by construction, not by clipping.
    primary_by_source: Dict[str, Dict[str, Any]] = {}
    for match in counted:
        source_id = match["source"]["sentence_id"]
        current = primary_by_source.get(source_id)
        if current is None or match["similarity"] > current["similarity"]:
            primary_by_source[source_id] = match
    primary_evidence_a: List[Dict[str, Any]] = sorted(
        primary_by_source.values(), key=lambda m: m["source"]["index"]
    )
    reverse_only_evidence = [m for m in counted if m.get("reverse_only")]

    counts = {"exact": 0, "near_exact": 0, "semantic": 0, "paraphrase": 0}
    for match in primary_evidence_a:
        counts[match["classification"]] = counts.get(match["classification"], 0) + 1
        if match["subtype"] == "paraphrase":
            counts["paraphrase"] += 1

    # ------------------------------------------------- passage-level grouping
    # Clustered over one row per A sentence, so duplicated evidence cannot create
    # or break a passage run.
    clusters = _cluster_matches(primary_evidence_a)
    passage_clusters = [c for c in clusters if c["size"] >= 2]
    for cluster in passage_clusters:
        first, last = cluster["members"][0], cluster["members"][-1]
        cluster["source_span"] = [first["source"]["index"], last["source"]["index"]]
        cluster["target_span"] = [min(m["target"]["index"] for m in cluster["members"]),
                                  max(m["target"]["index"] for m in cluster["members"])]
        cluster["similarity_max"] = round(max(m["similarity"] for m in cluster["members"]), 4)
        cluster["classification"] = (
            "exact" if any(m["classification"] == "exact" for m in cluster["members"])
            else "near_exact" if any(m["classification"] == "near_exact" for m in cluster["members"])
            else "semantic"
        )

    # --------------------------------------------------------------- coverage
    def coverage(prepared: Dict[str, Any], eligible: List[Dict[str, Any]],
                 matched_ids: set[str]) -> Dict[str, Any]:
        matched = [s for s in eligible if s["id"] in matched_ids]
        words_total = sum(s["word_count"] for s in eligible)
        words_matched = sum(s["word_count"] for s in matched)
        return {
            "sentences_considered": len(eligible),
            "sentences_matched": len(matched),
            "sentence_coverage_pct": round(100 * len(matched) / max(1, len(eligible)), 1),
            "words_considered": words_total,
            "words_covered": words_matched,
            "word_coverage_pct": round(100 * words_matched / max(1, words_total), 1),
        }

    matched_a = {m["source"]["sentence_id"] for m in primary_evidence_a}
    matched_b = {m["target"]["sentence_id"] for m in counted}
    coverage_a = coverage(prep_a, eligible_a, matched_a)
    coverage_b = coverage(prep_b, eligible_b, matched_b)

    # Per-sentence best cosine for A (0..1 each, at most one per comparable sentence).
    best_of_a = np.array([m["similarity"] for m in primary_evidence_a], dtype=np.float32)
    all_evidence = np.array([m["similarity"] for m in counted], dtype=np.float32)

    average_matched = float(best_of_a.mean()) if len(best_of_a) else 0.0
    max_similarity = float(all_evidence.max()) if len(all_evidence) else 0.0

    # Coverage-weighted similarity index:
    #     Σ (best cosine of each MATCHED sentence in A, counted once)
    #     ---------------------------------------------------------
    #              number of comparable sentences in A
    # Unmatched comparable sentences contribute 0. Because every term is at most
    # 1.0 and there is at most one term per comparable sentence, the index cannot
    # exceed 1.0. The clamp below is a defensive guard against float error only.
    comparable_a = max(1, len(eligible_a))
    weighted_index = float(best_of_a.sum() / comparable_a) if len(best_of_a) else 0.0
    weighted_index = min(1.0, max(0.0, weighted_index))

    # Distribution of the *best* cosine per comparable sentence in A (all bands,
    # so the chart shows how much of the document sits below the threshold too).
    buckets = [0, 0.2, 0.4, 0.6, 0.7, 0.8, 0.9, 1.0001]
    best_scores = forward["best_score"]
    histogram = []
    for lower, upper in zip(buckets[:-1], buckets[1:]):
        count = int(np.sum((best_scores >= lower) & (best_scores < upper)))
        histogram.append({
            "range": f"{int(lower * 100)}–{min(100, int(round(upper * 100)))}%",
            "lower": round(lower, 2),
            "upper": round(min(1.0, upper), 2),
            "count": count,
        })

    # --------------------------------------------------------- many-to-one
    groups: Dict[str, Dict[str, Any]] = {}
    for match in counted:  # all evidence rows, so alternatives stay visible
        key = match["target"]["sentence_id"]
        group = groups.setdefault(key, {
            "group_id": f"G{len(groups) + 1}",
            "target_sentence_id": key,
            "target_index": match["target"]["index"],
            "target_text": match["target"]["text"],
            "source_sentence_ids": [],
            "match_ids": [],
            "max_similarity": 0.0,
        })
        group["source_sentence_ids"].append(match["source"]["sentence_id"])
        group["match_ids"].append(match["id"])
        group["max_similarity"] = max(group["max_similarity"], match["similarity"])
    many_to_one = [
        g for g in groups.values() if len(g["source_sentence_ids"]) > 1
    ]

    # ------------------------------------------------------ paragraph level
    paragraph_matches = _paragraph_level(
        prep_a, prep_b, eligible_a, eligible_b, emb_a, emb_b,
        threshold=paragraph_threshold, top_k=5,
    )

    # ------------------------------------------------------------ warnings
    warnings: List[str] = []
    for prepared, label in ((prep_a, "Document A"), (prep_b, "Document B")):
        for warning in prepared["warnings"]:
            warnings.append(f"{label}: {warning}")
    if suppressed_count:
        warnings.append(
            f"{suppressed_count} low-evidence match(es) were suppressed (generic academic "
            "phrasing or citation-only overlap). They remain visible in the detailed list."
        )
    if prep_a["eligible_word_count"] < 150 or prep_b["eligible_word_count"] < 150:
        warnings.append(
            "One of the documents contains fewer than 150 comparable words, so coverage "
            "percentages are unstable and should be read as indicative only."
        )
    if len(eligible_a) > 1500 or len(eligible_b) > 1500:
        warnings.append(
            "Large document pair: candidate retrieval uses top-k scoring, so extremely "
            "unusual matches outside each sentence's best neighbours may not be listed."
        )

    duration_ms = int((time.perf_counter() - started) * 1000)
    band = _document_band(weighted_index)

    return {
        "engine": {
            "name": "VeriText semantic comparison engine",
            "version": config.ENGINE_VERSION,
            "model": config.MODEL_NAME,
            "embedding_dimension": embedder.dimension,
            "similarity_metric": "cosine similarity on L2-normalised sentence embeddings",
            # Where the embeddings were actually computed for this run (GPU or CPU).
            "device": embedder.device,
            "batch_size": embedder.batch_size,
            "thresholds": {
                "semantic_min": semantic_threshold,
                "high": config.HIGH_SIMILARITY,
                "moderate": config.MODERATE_SIMILARITY,
                "near_exact_lexical": config.NEAR_EXACT_LEXICAL,
                "paragraph": paragraph_threshold,
            },
            "options": options,
            "timings": {
                "embedding_ms": int(embed_seconds * 1000),
                "matching_ms": int(match_seconds * 1000),
                "total_ms": duration_ms,
            },
        },
        "documents": {
            "A": _document_summary(prep_a),
            "B": _document_summary(prep_b),
        },
        "summary": {
            "weighted_similarity": round(weighted_index, 4),
            "weighted_similarity_pct": round(weighted_index * 100, 1),
            "average_matched_similarity": round(average_matched, 4),
            "average_matched_similarity_pct": round(average_matched * 100, 1),
            "max_similarity": round(max_similarity, 4),
            "max_similarity_pct": round(max_similarity * 100, 1),
            # Matched sentences in A (one row per sentence) — the evidence the
            # headline metrics are computed from.
            "primary_matches": len(primary_evidence_a),
            # Every qualifying evidence row, including reverse-only (B→A) rows that
            # contribute to B's coverage but not to A's index.
            "evidence_rows": len(counted),
            "reverse_only_evidence": len(reverse_only_evidence),
            "all_match_candidates": len(matches),
            "exact_matches": counts["exact"],
            "near_exact_matches": counts["near_exact"],
            "semantic_matches": counts["semantic"],
            "paraphrase_matches": counts["paraphrase"],
            "suppressed_matches": suppressed_count,
            "generic_phrasing_matches": sum(1 for m in primary_evidence_a if m["generic_phrasing"]),
            "many_to_one_groups": len(many_to_one),
            "passages_detected": len(passage_clusters),
            "largest_passage_sentences": max([c["size"] for c in passage_clusters], default=0),
            "strong_evidence_matches": sum(1 for m in primary_evidence_a if m["evidence_strength"] == "strong"),
            "moderate_evidence_matches": sum(1 for m in primary_evidence_a if m["evidence_strength"] == "moderate"),
            "weak_evidence_matches": sum(1 for m in primary_evidence_a if m["evidence_strength"] == "weak"),
            "coverage": {"A": coverage_a, "B": coverage_b},
            "band": band,
            "distribution": histogram,
            "explanation_of_weighted_index": (
                "Coverage-weighted similarity index = the best cosine score of each matched "
                "sentence in Document A (each sentence counted once, so the same evidence is "
                "never added twice) summed and divided by the number of comparable sentences in "
                "Document A. Unmatched sentences contribute zero, so the value combines how much "
                "of the document overlapped with how closely it overlapped and always lies "
                "between 0% and 100%. It is a similarity indicator, not a plagiarism percentage."
            ),
        },
        "matches": sorted(matches, key=lambda m: (-m["is_primary"], -m["similarity"])),
        "paragraph_matches": paragraph_matches,
        "many_to_one_groups": many_to_one,
        "passages": sorted(passage_clusters, key=lambda c: (-c["size"], -c["similarity_max"])),
        "warnings": warnings,
        "disclaimer": DISCLAIMER,
    }


def _document_summary(prepared: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "filename": prepared["filename"],
        "file_type": prepared["file_type"],
        "page_count": prepared["page_count"],
        "word_count": prepared["word_count"],
        "char_count": prepared["char_count"],
        "sentence_count": prepared["sentence_count"],
        "eligible_sentence_count": prepared["eligible_sentence_count"],
        "eligible_word_count": prepared["eligible_word_count"],
        "paragraph_count": prepared["paragraph_count"],
        "sections_present": prepared["sections_present"],
    }


def _paragraph_level(
    prep_a: Dict[str, Any],
    prep_b: Dict[str, Any],
    eligible_a: Sequence[Dict[str, Any]],
    eligible_b: Sequence[Dict[str, Any]],
    emb_a: np.ndarray,
    emb_b: np.ndarray,
    threshold: float,
    top_k: int = 5,
    max_results: int = 25,
) -> List[Dict[str, Any]]:
    """
    Paragraph-level comparison.

    A paragraph vector is the L2-normalised mean of its sentences' embeddings
    (computed from the vectors we already have — no extra model passes). This
    surfaces passages whose *overall* meaning is aligned even when individual
    sentence pairs fall below the sentence threshold.
    """
    idx_a = {s["id"]: k for k, s in enumerate(eligible_a)}
    idx_b = {s["id"]: k for k, s in enumerate(eligible_b)}

    para_vecs_a, meta_a = [], []
    for para in prep_a["paragraphs"]:
        rows = [idx_a[sid] for sid in para["sentence_ids"] if sid in idx_a]
        if not rows:
            continue
        vec = emb_a[rows].mean(axis=0)
        norm = np.linalg.norm(vec)
        if norm == 0:
            continue
        para_vecs_a.append(vec / norm)
        meta_a.append(para)

    para_vecs_b, meta_b = [], []
    for para in prep_b["paragraphs"]:
        rows = [idx_b[sid] for sid in para["sentence_ids"] if sid in idx_b]
        if not rows:
            continue
        vec = emb_b[rows].mean(axis=0)
        norm = np.linalg.norm(vec)
        if norm == 0:
            continue
        para_vecs_b.append(vec / norm)
        meta_b.append(para)

    if not para_vecs_a or not para_vecs_b:
        return []

    matrix_a = np.vstack(para_vecs_a).astype(np.float32)
    matrix_b = np.vstack(para_vecs_b).astype(np.float32)
    top = top_k_similarities(matrix_a, matrix_b, k=min(top_k, len(matrix_b)))

    results: List[Dict[str, Any]] = []
    for i, para in enumerate(meta_a):
        for rank, (j, score) in enumerate(zip(top["top_indices"][i], top["top_scores"][i])):
            if float(score) < threshold:
                continue
            other = meta_b[int(j)]
            results.append({
                "id": f"P{len(results) + 1}",
                "similarity": round(float(score), 4),
                "similarity_pct": round(float(score) * 100, 1),
                "band": similarity_band(float(score), Config),
                "source": {
                    "paragraph_index": para["index"],
                    "page": para.get("page", 0),
                    "text": para["text"][:1200],
                    "word_count": len(para["text"].split()),
                },
                "target": {
                    "paragraph_index": other["index"],
                    "page": other.get("page", 0),
                    "text": other["text"][:1200],
                    "word_count": len(other["text"].split()),
                },
                "explanation": (
                    "Paragraph-level vector similarity: the aggregate meaning of these two "
                    "paragraphs is close. Individual sentences inside them may or may not be "
                    "flagged separately."
                ),
                "rank_in_source": rank + 1,
            })
        if len(results) >= max_results:
            break

    return sorted(results, key=lambda r: -r["similarity"])[:max_results]
