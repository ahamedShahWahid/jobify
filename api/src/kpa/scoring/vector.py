"""Cosine similarity and clipped vector score for matching."""

from __future__ import annotations

import math


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Return cosine similarity in [-1, 1].

    Zero-norm vectors return 0.0 (no signal). Dim mismatch raises ValueError.
    """
    if len(a) != len(b):
        raise ValueError(f"dim mismatch: {len(a)} vs {len(b)}")
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(dot / (na * nb))


def vector_score(a: list[float], b: list[float]) -> float:
    """Cosine clipped to [0, 1]. Negative similarity → 0 (no anti-signal)."""
    return float(max(0.0, cosine_similarity(a, b)))
