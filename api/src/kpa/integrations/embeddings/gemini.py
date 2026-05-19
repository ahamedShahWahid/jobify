"""Gemini Developer API embedding provider — gemini-embedding-2 by default.

Task is encoded via prompt prefix (gemini-embedding-2 does NOT accept the
``task_type`` parameter; that was a gemini-embedding-001 thing).
"""

from __future__ import annotations

import structlog
from google import genai
from google.genai import errors, types

from kpa.integrations.embeddings.base import (
    EmbeddingProvider,
    EmbeddingProviderError,
    EmbeddingResult,
    EmbeddingTask,
    TransientEmbeddingError,
)

_log = structlog.get_logger(__name__)


class GeminiEmbeddingProvider(EmbeddingProvider):
    def __init__(self, *, api_key: str, model: str, output_dim: int) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._output_dim = output_dim

    async def encode(
        self,
        *,
        text: str,
        task: EmbeddingTask,
        title: str | None = None,
    ) -> EmbeddingResult:
        if task is EmbeddingTask.DOCUMENT:
            content = f"title: {title or 'none'} | text: {text}"
        elif task is EmbeddingTask.QUERY:
            content = f"task: search result | query: {text}"
        else:
            raise NotImplementedError(f"task type not supported by this provider: {task}")

        try:
            resp = await self._client.aio.models.embed_content(
                model=self._model,
                contents=[content],
                config=types.EmbedContentConfig(output_dimensionality=self._output_dim),
            )
        except errors.ServerError as exc:
            raise TransientEmbeddingError(str(exc)) from exc
        except errors.ClientError as exc:
            # 429 Too Many Requests → transient; all other 4xx → permanent
            if exc.code == 429:
                raise TransientEmbeddingError(str(exc)) from exc
            raise EmbeddingProviderError(str(exc)) from exc
        except errors.APIError as exc:
            raise EmbeddingProviderError(str(exc)) from exc

        if not resp.embeddings or not resp.embeddings[0].values:
            raise EmbeddingProviderError("empty embedding response")
        emb = resp.embeddings[0]
        if len(emb.values) != self._output_dim:
            raise EmbeddingProviderError(
                f"dim mismatch: got {len(emb.values)} expected {self._output_dim}"
            )
        return EmbeddingResult(
            values=list(emb.values),
            model_name=self._model,
            input_tokens=(
                int(emb.statistics.token_count)
                if emb.statistics and emb.statistics.token_count
                else 0
            ),
        )
