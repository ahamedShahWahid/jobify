"""Embedding provider interface.

Task is encoded via prompt-prefix at the impl layer; call sites pass the
``EmbeddingTask`` enum and the impl formats accordingly. Keeps a future
Voyage/Cohere swap a single-file change.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class EmbeddingTask(StrEnum):
    DOCUMENT = "document"  # applicant profile (or job description, in P2)
    QUERY = "query"  # recruiter-side query (in P2)


@dataclass(frozen=True)
class EmbeddingResult:
    values: list[float]
    model_name: str
    input_tokens: int


class EmbeddingProviderError(Exception):
    """Permanent failure — bad input, malformed response, etc. No retry."""


class TransientEmbeddingError(Exception):
    """Transient failure — rate limit, 5xx, network blip. Celery autoretries."""


class EmbeddingProvider(Protocol):
    async def encode(
        self,
        *,
        text: str,
        task: EmbeddingTask,
        title: str | None = None,
    ) -> EmbeddingResult: ...
