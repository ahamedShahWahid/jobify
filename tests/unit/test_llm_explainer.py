"""Unit tests for GeminiMatchExplainer — genai client fully faked, no network."""

from __future__ import annotations

import json
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from jobify.scoring.explainer import ExplainContext
from jobify.scoring.llm_explainer import (
    LLM_GENERATOR,
    LLM_GENERATOR_VERSION,
    GeminiMatchExplainer,
)


def _ctx(*, total: float = 0.9, threshold: float = 0.55, **overrides: object) -> ExplainContext:
    base: dict[str, object] = {
        "components": {"location": 1.0, "exp": 1.0, "ctc": 1.0},
        "vector": 0.9,
        "structured": 1.0,
        "total": total,
        "threshold": threshold,
        "job_title": "Senior Backend Engineer",
        "job_locations": ["Bangalore"],
        "job_min_exp_years": 5,
        "job_max_exp_years": 9,
        "job_ctc_max": Decimal("4200000"),
        "employer_name": "Acme",
        "applicant_expected_ctc": Decimal("3000000"),
        "applicant_locations": ["Bangalore"],
    }
    base.update(overrides)
    return ExplainContext(**base)  # type: ignore[arg-type]


def _make_explainer() -> tuple[GeminiMatchExplainer, AsyncMock]:
    """Return (explainer, generate_content_mock)."""
    gc_mock = AsyncMock()
    client = MagicMock()
    client.aio.models.generate_content = gc_mock
    explainer = GeminiMatchExplainer(client=client, model="gemini-2.5-flash")
    return explainer, gc_mock


@pytest.mark.asyncio
async def test_surfaced_match_calls_gemini_and_returns_llm_generator() -> None:
    """total >= threshold → Gemini called once, parsed JSON returned."""
    explainer, gc_mock = _make_explainer()
    gc_mock.return_value = SimpleNamespace(
        text=json.dumps({"fit": "Great fit at Acme.", "caveat": "Located in Bangalore only."})
    )

    out = await explainer.explain(_ctx(total=0.9, threshold=0.55))

    assert gc_mock.await_count == 1
    assert out["fit"] == "Great fit at Acme."
    assert out["caveat"] == "Located in Bangalore only."
    assert out["generator"] == LLM_GENERATOR == "llm"
    assert out["generator_version"] == LLM_GENERATOR_VERSION


@pytest.mark.asyncio
async def test_caveat_optional_defaults_to_empty_string() -> None:
    """If the model returns no caveat key, the explainer fills in ''."""
    explainer, gc_mock = _make_explainer()
    gc_mock.return_value = SimpleNamespace(text=json.dumps({"fit": "Strong match."}))

    out = await explainer.explain(_ctx(total=0.9))

    assert out["fit"] == "Strong match."
    assert out["caveat"] == ""
    assert out["generator"] == "llm"


@pytest.mark.asyncio
async def test_below_threshold_skips_gemini_and_returns_templated() -> None:
    """total < threshold → Gemini NOT called, templated returned."""
    explainer, gc_mock = _make_explainer()

    out = await explainer.explain(_ctx(total=0.3, threshold=0.55))

    assert gc_mock.await_count == 0
    assert out["generator"] == "templated"
    assert out["fit"] == "Lower-confidence match - surfaced for breadth."


@pytest.mark.asyncio
async def test_gemini_raises_falls_back_to_templated() -> None:
    """Any exception from the genai client → templated fallback, no raise."""
    explainer, gc_mock = _make_explainer()
    gc_mock.side_effect = RuntimeError("network exploded")

    out = await explainer.explain(_ctx(total=0.9))

    assert out["generator"] == "templated"
    assert out.get("fit")


@pytest.mark.asyncio
async def test_invalid_json_response_falls_back_to_templated() -> None:
    """Non-JSON / malformed response → templated fallback, no raise."""
    explainer, gc_mock = _make_explainer()
    gc_mock.return_value = SimpleNamespace(text="not json at all {{{")

    out = await explainer.explain(_ctx(total=0.9))

    assert out["generator"] == "templated"


@pytest.mark.asyncio
async def test_empty_response_text_falls_back_to_templated() -> None:
    """An empty or None .text on the response → templated fallback."""
    explainer, gc_mock = _make_explainer()
    gc_mock.return_value = SimpleNamespace(text="")

    out = await explainer.explain(_ctx(total=0.9))

    assert out["generator"] == "templated"


@pytest.mark.asyncio
async def test_non_dict_json_falls_back_to_templated() -> None:
    """JSON that parses to a list/str/etc. → templated fallback."""
    explainer, gc_mock = _make_explainer()
    gc_mock.return_value = SimpleNamespace(text=json.dumps(["fit", "caveat"]))

    out = await explainer.explain(_ctx(total=0.9))

    assert out["generator"] == "templated"


@pytest.mark.anyio
async def test_generation_config_disables_thinking() -> None:
    """gemini-2.5 thinking is ON by default and its tokens count against
    max_output_tokens — with the 200 cap the model burned ~190 tokens thinking
    and truncated (finish=MAX_TOKENS, text='Here is the JSON requested:\\n'),
    so every explain fell back to templated in production. Pin budget=0."""
    explainer, gc_mock = _make_explainer()
    gc_mock.return_value = SimpleNamespace(text='{"fit": "Solid match."}')

    await explainer.explain(_ctx())

    config = gc_mock.await_args.kwargs["config"]
    assert config.thinking_config is not None
    assert config.thinking_config.thinking_budget == 0
    assert config.max_output_tokens >= 200


@pytest.mark.anyio
async def test_parse_failure_logs_raw_text_snippet() -> None:
    """The fallback is silent by design — the warning must carry the raw
    model text or the failure mode is undiagnosable from logs."""
    from structlog.testing import capture_logs

    explainer, gc_mock = _make_explainer()
    gc_mock.return_value = SimpleNamespace(text="Here is the JSON requested:\n")

    with capture_logs() as logs:
        out = await explainer.explain(_ctx())

    assert out["generator"] == "templated"
    failed = [e for e in logs if e.get("event") == "explain.llm-failed"]
    assert len(failed) == 1
    assert "Here is the JSON requested" in failed[0]["raw_text"]
