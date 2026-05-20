"""Unit tests for vector cosine similarity."""

from __future__ import annotations

import math

import pytest

from kpa.scoring.vector import cosine_similarity, vector_score


def test_cosine_identical_vectors_is_one() -> None:
    assert math.isclose(cosine_similarity([1.0, 0.0, 0.0], [1.0, 0.0, 0.0]), 1.0)


def test_cosine_orthogonal_is_zero() -> None:
    assert cosine_similarity([1.0, 0.0, 0.0], [0.0, 1.0, 0.0]) == 0.0


def test_cosine_dim_mismatch_raises() -> None:
    with pytest.raises(ValueError):
        cosine_similarity([1.0, 0.0], [1.0, 0.0, 0.0])


def test_vector_score_clips_negative_to_zero() -> None:
    assert vector_score([1.0, 0.0], [-1.0, 0.0]) == 0.0


def test_vector_score_zero_norm_returns_zero() -> None:
    assert cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0
