"""Embedding providers and profile canonicalization.

Public surface: ``EmbeddingProvider`` Protocol with two implementations
(currently only Gemini), an ``EmbeddingTask`` enum that distinguishes document
vs query encoding, and the ``canonicalize_profile`` helper that produces the
deterministic text + sha256 used as the idempotency key on
``applicant_embeddings.canonicalized_text_hash``.

``GeminiEmbeddingProvider`` is intentionally not imported here — it is deferred
to the point of use (in ``celery_app.get_embedding_provider()``) so that
``google.genai`` and its dependencies are not loaded for worker processes
that don't consume the ``embed`` queue.
"""

from jobify.integrations.embeddings.base import (
    EmbeddingProvider,
    EmbeddingProviderError,
    EmbeddingResult,
    EmbeddingTask,
    TransientEmbeddingError,
)
from jobify.integrations.embeddings.canonicalize import canonicalize_profile

__all__ = [
    "EmbeddingProvider",
    "EmbeddingProviderError",
    "EmbeddingResult",
    "EmbeddingTask",
    "TransientEmbeddingError",
    "canonicalize_profile",
]
