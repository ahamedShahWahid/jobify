"""Unit tests for GeminiEmbeddingProvider — SDK fully mocked, no network.

Uses unittest.mock.AsyncMock to patch genai.Client so no real HTTP calls occur.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jobify.integrations.embeddings.base import (
    EmbeddingProviderError,
    EmbeddingTask,
    TransientEmbeddingError,
)
from jobify.integrations.embeddings.gemini import GeminiEmbeddingProvider

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_provider(output_dim: int = 3072) -> tuple[GeminiEmbeddingProvider, AsyncMock]:
    """Return (provider, embed_content_mock).

    The embed_content_mock is the AsyncMock wired to
    client.aio.models.embed_content. Configure its return_value / side_effect
    per test.
    """
    embed_mock = AsyncMock()

    mock_client = MagicMock()
    mock_client.aio.models.embed_content = embed_mock

    with patch("jobify.integrations.embeddings.gemini.genai.Client", return_value=mock_client):
        provider = GeminiEmbeddingProvider(
            api_key="test-key",
            model="gemini-embedding-2",
            output_dim=output_dim,
        )

    return provider, embed_mock


_DEFAULT_STATISTICS = SimpleNamespace(token_count=10.0)


def _make_response(
    values: list[float],
    statistics: SimpleNamespace | None = _DEFAULT_STATISTICS,
):
    """Build a fake SDK embed_content response with the expected shape.

    ``statistics`` mirrors ``ContentEmbeddingStatistics``. Pass
    ``SimpleNamespace(token_count=N)`` to exercise the token-count path;
    pass ``None`` to simulate a response with no statistics.
    """
    emb = SimpleNamespace(values=values, statistics=statistics)
    return SimpleNamespace(embeddings=[emb])


# ---------------------------------------------------------------------------
# Task formatting tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_document_task_formats_with_title_prefix() -> None:
    """DOCUMENT task + explicit title → prompt prefix includes 'title: Alice | text:'."""
    provider, embed_mock = _make_provider(output_dim=2)
    embed_mock.return_value = _make_response([0.1, 0.2])

    await provider.encode(text="foo", task=EmbeddingTask.DOCUMENT, title="Alice")

    assert embed_mock.call_args.kwargs["contents"] == ["title: Alice | text: foo"]


@pytest.mark.asyncio
async def test_document_task_with_none_title_uses_none_literal() -> None:
    """DOCUMENT task with title=None → prompt uses 'none' as the title literal."""
    provider, embed_mock = _make_provider(output_dim=2)
    embed_mock.return_value = _make_response([0.1, 0.2])

    await provider.encode(text="foo", task=EmbeddingTask.DOCUMENT, title=None)

    assert embed_mock.call_args.kwargs["contents"] == ["title: none | text: foo"]


@pytest.mark.asyncio
async def test_query_task_formats_with_search_result_prefix() -> None:
    """QUERY task → prompt prefix is 'task: search result | query:'."""
    provider, embed_mock = _make_provider(output_dim=2)
    embed_mock.return_value = _make_response([0.1, 0.2])

    await provider.encode(text="foo", task=EmbeddingTask.QUERY)

    assert embed_mock.call_args.kwargs["contents"] == ["task: search result | query: foo"]


# ---------------------------------------------------------------------------
# Error-mapping tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_5xx_maps_to_transient_error() -> None:
    """ServerError (5xx) from the SDK → TransientEmbeddingError."""
    from google.genai import errors

    provider, embed_mock = _make_provider()

    # Build a minimal fake response that satisfies APIError.__init__
    fake_response = MagicMock()
    fake_response.status_code = 500
    fake_response.json.return_value = {
        "message": "internal error",
        "status": "INTERNAL",
        "code": 500,
    }
    embed_mock.side_effect = errors.ServerError(500, fake_response)

    with pytest.raises(TransientEmbeddingError):
        await provider.encode(text="x", task=EmbeddingTask.DOCUMENT)


@pytest.mark.asyncio
async def test_429_maps_to_transient_error() -> None:
    """ClientError with code=429 (rate limit) → TransientEmbeddingError."""
    from google.genai import errors

    provider, embed_mock = _make_provider()

    fake_response = MagicMock()
    fake_response.status_code = 429
    fake_response.json.return_value = {
        "message": "rate limit",
        "status": "RESOURCE_EXHAUSTED",
        "code": 429,
    }
    embed_mock.side_effect = errors.ClientError(429, fake_response)

    with pytest.raises(TransientEmbeddingError):
        await provider.encode(text="x", task=EmbeddingTask.DOCUMENT)


@pytest.mark.asyncio
async def test_other_4xx_maps_to_permanent_error() -> None:
    """ClientError with code=400 (bad request) → EmbeddingProviderError."""
    from google.genai import errors

    provider, embed_mock = _make_provider()

    fake_response = MagicMock()
    fake_response.status_code = 400
    fake_response.json.return_value = {
        "message": "bad input",
        "status": "INVALID_ARGUMENT",
        "code": 400,
    }
    embed_mock.side_effect = errors.ClientError(400, fake_response)

    with pytest.raises(EmbeddingProviderError):
        await provider.encode(text="x", task=EmbeddingTask.DOCUMENT)


# ---------------------------------------------------------------------------
# Response validation tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dim_mismatch_is_permanent_error() -> None:
    """Response returning 768 values when output_dim=1536 → EmbeddingProviderError."""
    provider, embed_mock = _make_provider(output_dim=1536)
    embed_mock.return_value = _make_response([0.1] * 768)  # wrong dim

    with pytest.raises(EmbeddingProviderError, match="dim mismatch"):
        await provider.encode(text="x", task=EmbeddingTask.DOCUMENT)


@pytest.mark.asyncio
async def test_empty_response_is_permanent_error() -> None:
    """Response with no embeddings → EmbeddingProviderError."""
    provider, embed_mock = _make_provider()
    embed_mock.return_value = SimpleNamespace(embeddings=[])

    with pytest.raises(EmbeddingProviderError, match="empty embedding response"):
        await provider.encode(text="x", task=EmbeddingTask.DOCUMENT)


@pytest.mark.asyncio
async def test_input_tokens_extracted_from_statistics() -> None:
    """The SDK exposes token count under emb.statistics.token_count, not emb.input_tokens.

    This test ensures we read the correct field — otherwise cost-tracking
    dashboards (which consume EmbeddingResult.input_tokens) will be wrong.
    """
    provider, embed_mock = _make_provider(output_dim=2)
    embed_mock.return_value = _make_response(
        [0.1, 0.2],
        statistics=SimpleNamespace(token_count=42.0),
    )

    result = await provider.encode(text="hello", task=EmbeddingTask.DOCUMENT)

    assert result.input_tokens == 42


@pytest.mark.asyncio
async def test_input_tokens_zero_when_statistics_is_none() -> None:
    """When the SDK returns no statistics, input_tokens falls back to 0."""
    provider, embed_mock = _make_provider(output_dim=2)
    embed_mock.return_value = _make_response([0.1, 0.2], statistics=None)

    result = await provider.encode(text="hello", task=EmbeddingTask.DOCUMENT)

    assert result.input_tokens == 0
