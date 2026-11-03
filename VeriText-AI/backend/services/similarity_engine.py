"""
Similarity primitives: cosine similarity over embeddings + lexical comparison.

Cosine similarity
------------------
For two embedding vectors A and B:

    cos(A, B) = (A · B) / (||A|| · ||B||)

``EmbeddingService`` returns L2-normalised vectors, so ``||A|| = ||B|| = 1`` and
the cosine collapses to the dot product ``A · B``. That is why the matrix
multiplication below *is* the cosine similarity matrix — no approximation.

Memory note: a 4000 x 4000 float32 matrix is 64 MB. Instead of materialising the
full matrix we score it in row blocks and immediately reduce each block to the
top-k candidates, which keeps peak memory proportional to the block size.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any, Dict, List, Sequence, Tuple

import numpy as np

from config import Config

# The cosine search is evaluated in row blocks and reduced to top-k per block, so
# peak memory is O(BLOCK_ROWS x n_b) rather than O(n_a x n_b). That keeps a 4 GB
# GPU (or a small VM) from ever allocating the full sentence-by-sentence matrix.
BLOCK_ROWS = max(16, Config.SIMILARITY_BLOCK_ROWS)

# Cache surface-word -> stem mappings so display terms stay cheap.
_STEMMER_SURFACE: Dict[str, str] = {}


# --------------------------------------------------------------------------- #
# semantic similarity
# --------------------------------------------------------------------------- #
def _l2_normalise(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms


def cosine_similarity_matrix(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """
    Full cosine matrix: (A · B) / (||A|| · ||B||).

    Inputs are normalised explicitly so the function is correct for *any* vectors,
    not only for the unit-length vectors produced by the embedding service.
    Only use this for small inputs — the detection engine uses
    :func:`top_k_similarities`, which never materialises the full matrix.
    """
    if a.size == 0 or b.size == 0:
        return np.zeros((len(a), len(b)), dtype=np.float32)
    a_norm = _l2_normalise(np.asarray(a, dtype=np.float32))
    b_norm = _l2_normalise(np.asarray(b, dtype=np.float32))
    return np.asarray(a_norm @ b_norm.T, dtype=np.float32)


def top_k_similarities(
    a: np.ndarray,
    b: np.ndarray,
    k: int = 3,
) -> Dict[str, np.ndarray]:
    """
    For every row of ``a`` find the ``k`` most similar rows of ``b``.

    Returns
    -------
    best_score : (n_a,)            highest cosine per row of A
    top_indices: (n_a, k) int      indices into B, best first
    top_scores : (n_a, k) float    corresponding cosines
    row_max_j  : (n_a,) int        index of the best match
    """
    n_a = len(a)
    n_b = len(b)
    k = max(1, min(k, n_b)) if n_b else 1
    best_score = np.zeros(n_a, dtype=np.float32)
    top_indices = np.zeros((n_a, k), dtype=np.int32)
    top_scores = np.zeros((n_a, k), dtype=np.float32)
    if n_a == 0 or n_b == 0:
        return {
            "best_score": best_score,
            "top_indices": top_indices,
            "top_scores": top_scores,
            "row_max_j": np.zeros(n_a, dtype=np.int32),
        }

    for start in range(0, n_a, BLOCK_ROWS):
        stop = min(start + BLOCK_ROWS, n_a)
        block = a[start:stop] @ b.T                     # (rows, n_b) cosine scores
        if k < n_b:
            # argpartition is O(n) per row instead of a full sort
            candidate_idx = np.argpartition(-block, k - 1, axis=1)[:, :k]
        else:
            candidate_idx = np.tile(np.arange(n_b), (stop - start, 1))
        candidate_scores = np.take_along_axis(block, candidate_idx, axis=1)
        order = np.argsort(-candidate_scores, axis=1)   # sort the k candidates only
        candidate_idx = np.take_along_axis(candidate_idx, order, axis=1)
        candidate_scores = np.take_along_axis(candidate_scores, order, axis=1)

        top_indices[start:stop] = candidate_idx
        top_scores[start:stop] = candidate_scores
        best_score[start:stop] = candidate_scores[:, 0]

    return {
        "best_score": best_score,
        "top_indices": top_indices,
        "top_scores": top_scores,
        "row_max_j": top_indices[:, 0],
    }


# --------------------------------------------------------------------------- #
# lexical (exact / near-exact) similarity
# --------------------------------------------------------------------------- #
_TOKEN_SPLIT = re.compile(r"[a-z0-9']+")
_WORD_RE = re.compile(r"\b\w+\b")


def _norm_tokens(norm_text: str) -> List[str]:
    return _TOKEN_SPLIT.findall(norm_text or "")


def token_jaccard(tokens_a: Sequence[str], tokens_b: Sequence[str]) -> float:
    set_a, set_b = set(tokens_a), set(tokens_b)
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def sequence_ratio(tokens_a: Sequence[str], tokens_b: Sequence[str]) -> float:
    """
    Order-aware ratio on token sequences (difflib). 1.0 means the same tokens in
    the same order; this is the main near-exact signal and it distinguishes
    "the same sentence with two words changed" from a genuine paraphrase.
    """
    if not tokens_a or not tokens_b:
        return 0.0
    matcher = SequenceMatcher(None, list(tokens_a), list(tokens_b), autojunk=False)
    return float(matcher.ratio())


def lexical_comparison(
    norm_a: str,
    norm_b: str,
    content_a: Sequence[str],
    content_b: Sequence[str],
    terms_a: Sequence[str] | None = None,
    terms_b: Sequence[str] | None = None,
) -> Dict[str, Any]:
    """
    Lexical evidence for a sentence pair — completely independent of the
    embedding model. Used to separate exact copies from semantic paraphrases and
    to explain *which words* the two sentences share.
    """
    tokens_a = _norm_tokens(norm_a)
    tokens_b = _norm_tokens(norm_b)
    set_a, set_b = set(tokens_a), set(tokens_b)
    shared_tokens = set_a & set_b
    chars_a, chars_b = len(" ".join(tokens_a)), len(" ".join(tokens_b))

    content_shared = sorted(set(content_a) & set(content_b))
    content_union = sorted(set(content_a) | set(content_b))

    # Readable versions of the shared stems ("rapidli" -> "rapidly") for display.
    surface: Dict[str, str] = {}
    for term in list(terms_a or []) + list(terms_b or []):
        stem = _STEMMER_SURFACE.get(term)
        if stem is None:
            try:
                from nltk.stem import PorterStemmer

                stem = PorterStemmer().stem(term)
            except Exception:  # pragma: no cover
                stem = term
            _STEMMER_SURFACE[term] = stem
        surface.setdefault(stem, term)
    shared_display = [surface.get(stem, stem) for stem in content_shared]

    return {
        "is_exact_string": bool(norm_a) and norm_a == norm_b,
        "sequence_ratio": round(sequence_ratio(tokens_a, tokens_b), 4),
        "token_jaccard": round(token_jaccard(tokens_a, tokens_b), 4),
        "token_overlap_ratio": round(
            (2 * len(shared_tokens)) / max(1, len(set_a) + len(set_b)), 4
        ),
        "shared_token_count": len(shared_tokens),
        "shared_content_terms": content_shared[:30],
        "shared_terms_display": shared_display[:30],
        "content_overlap": round(
            len(content_shared) / max(1, min(len(set(content_a)), len(set(content_b)))), 4
        ) if content_shared else 0.0,
        "content_union_size": len(content_union),
        "length_ratio": round(min(chars_a, chars_b) / max(1, max(chars_a, chars_b)), 3),
    }


def longest_common_substring_words(text_a: str, text_b: str) -> Tuple[int, str]:
    """Longest run of words shared verbatim — useful evidence for reports."""
    words_a = _WORD_RE.findall((text_a or "").lower())
    words_b = _WORD_RE.findall((text_b or "").lower())
    if not words_a or not words_b:
        return 0, ""
    matcher = SequenceMatcher(None, words_a, words_b, autojunk=False)
    match = matcher.find_longest_match(0, len(words_a), 0, len(words_b))
    if match.size == 0:
        return 0, ""
    return match.size, " ".join(words_a[match.a:match.a + match.size])


# --------------------------------------------------------------------------- #
# thresholds / bands
# --------------------------------------------------------------------------- #
def similarity_band(score: float, config: Any) -> str:
    """Map a cosine score to an interpretable band (configurable in config.py)."""
    if score >= 0.90:
        return "very_high"
    if score >= config.HIGH_SIMILARITY:
        return "high"
    if score >= config.MODERATE_SIMILARITY:
        return "moderate"
    return "low"


BAND_LABELS = {
    "very_high": "Very high semantic similarity (90-100%)",
    "high": "High semantic similarity (80-89%)",
    "moderate": "Moderate semantic similarity (65-79%)",
    "low": "Low semantic similarity (below 65%)",
}

BAND_COLORS = {
    "very_high": "#b91c1c",
    "high": "#dc2626",
    "moderate": "#d97706",
    "low": "#15803d",
}
