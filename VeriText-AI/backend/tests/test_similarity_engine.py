"""Tests that the similarity maths matches the definition it claims to implement."""

from __future__ import annotations

import numpy as np
import pytest
from sklearn.metrics.pairwise import cosine_similarity as sklearn_cosine

from services.embedding_service import get_embedding_service
from services.similarity_engine import (
    cosine_similarity_matrix,
    lexical_comparison,
    longest_common_substring_words,
    similarity_band,
    top_k_similarities,
)
from config import Config


def test_cosine_matrix_matches_sklearn():
    rng = np.random.default_rng(seed=7)
    a = rng.normal(size=(12, 16)).astype(np.float32)
    b = rng.normal(size=(9, 16)).astype(np.float32)
    ours = cosine_similarity_matrix(a, b)
    reference = sklearn_cosine(a, b)
    assert np.allclose(ours, reference, atol=1e-5)


def test_normalised_vectors_give_dot_product_equal_to_cosine():
    embedder = get_embedding_service()
    vectors = embedder.encode([
        "The experiment produced a stable result.",
        "Results from the experiment were stable.",
        "Photosynthesis converts light into chemical energy.",
    ])
    norms = np.linalg.norm(vectors, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-5)
    dot = float(vectors[0] @ vectors[1])
    cos = float(cosine_similarity_matrix(vectors[0:1], vectors[1:2])[0, 0])
    assert abs(dot - cos) < 1e-6


def test_related_sentences_score_higher_than_unrelated():
    embedder = get_embedding_service()
    vectors = embedder.encode([
        "Neural networks require large training corpora.",
        "Deep models need big annotated datasets to train.",
        "The museum acquired nineteenth century maps.",
    ])
    related = float(vectors[0] @ vectors[1])
    unrelated = float(vectors[0] @ vectors[2])
    assert related > unrelated + 0.2


def test_top_k_returns_sorted_candidates():
    a = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
    b = np.array([[0.9, 0.1], [0.1, 0.9], [0.7, 0.7]], dtype=np.float32)
    b = b / np.linalg.norm(b, axis=1, keepdims=True)
    result = top_k_similarities(a, b, k=2)
    assert result["top_indices"].shape == (2, 2)
    assert result["top_indices"][0][0] == 0
    assert result["top_indices"][1][0] == 1
    scores = result["top_scores"][0]
    assert scores[0] >= scores[1]


def test_top_k_handles_k_larger_than_columns():
    a = np.eye(3, 4, dtype=np.float32)
    b = np.eye(2, 4, dtype=np.float32)
    result = top_k_similarities(a, b, k=5)
    assert result["top_indices"].shape == (3, 2)


def test_lexical_comparison_detects_exact_and_near_exact():
    exact = lexical_comparison(
        "the model performs well", "the model performs well", ["model", "perform"], ["model", "perform"]
    )
    assert exact["is_exact_string"] is True
    assert exact["sequence_ratio"] == 1.0

    near = lexical_comparison(
        "the model performs very well on this dataset",
        "the model performs extremely well on this dataset",
        ["model", "perform", "well", "dataset"], ["model", "perform", "well", "dataset"],
    )
    assert near["is_exact_string"] is False
    assert near["sequence_ratio"] > 0.8
    assert near["shared_content_terms"]


def test_longest_verbatim_run_is_detected():
    size, text = longest_common_substring_words(
        "We exclude reference lists from matching because bibliographies repeat",
        "Reference lists are excluded from matching because bibliographies repeat",
    )
    assert size >= 3
    assert "because bibliographies repeat" in text


@pytest.mark.parametrize(
    "score,expected",
    [(0.95, "very_high"), (0.85, "high"), (0.70, "moderate"), (0.30, "low")],
)
def test_similarity_bands(score, expected):
    assert similarity_band(score, Config) == expected
