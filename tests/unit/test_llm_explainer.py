"""Unit tests for GeminiMatchExplainer — genai client fully faked, no network."""

from __future__ import annotations

import json
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from prometheus_client import REGISTRY

from jobify.scoring.explainer import ExplainContext
from jobify.scoring.llm_explainer import (
    LLM_GENERATOR,
    LLM_GENERATOR_VERSION,
    GeminiMatchExplainer,
)


def _external_calls(service: str, operation: str, outcome: str) -> float:
    labels = {"service": service, "operation": operation, "outcome": outcome}
    return REGISTRY.get_sample_value("jobify_external_calls_total", labels) or 0.0


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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
async def test_generation_config_uses_thinking_level_on_3x_models() -> None:
    """3.x rejects thinking_budget=0 (400 INVALID_ARGUMENT); the explainer
    must send the family's knob or every explain silently falls back to
    templated after a model bump."""
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, MagicMock

    from jobify.scoring.llm_explainer import GeminiMatchExplainer

    client = MagicMock()
    gc_mock = AsyncMock(return_value=SimpleNamespace(text='{"fit": "Solid match."}'))
    client.aio.models.generate_content = gc_mock
    explainer = GeminiMatchExplainer(client=client, model="gemini-3.5-flash-lite")

    await explainer.explain(_ctx())

    config = gc_mock.await_args.kwargs["config"]
    from google.genai import types

    assert config.thinking_config.thinking_budget is None
    assert config.thinking_config.thinking_level == types.ThinkingLevel.MINIMAL


@pytest.mark.asyncio
async def test_parse_failure_logs_shape_not_model_text() -> None:
    """The model's raw output can restate the applicant's profile — the
    failure log must carry shape (length, error type) only, never the text
    itself."""
    from structlog.testing import capture_logs

    explainer, gc_mock = _make_explainer()
    gc_mock.return_value = SimpleNamespace(text="Here is the JSON requested:\n")

    with capture_logs() as logs:
        out = await explainer.explain(_ctx())

    assert out["generator"] == "templated"
    (failed,) = (e for e in logs if e.get("event") == "explain.llm-failed")
    assert "raw_text" not in failed
    assert failed["raw_length"] == len("Here is the JSON requested:\n")
    assert failed["error_type"] == "JSONDecodeError"
    assert all("Here is the JSON" not in str(value) for value in failed.values())


@pytest.mark.asyncio
async def test_explain_call_is_observed() -> None:
    """A failed generate_content call bumps the (gemini, explain_match, error) counter."""
    explainer, gc_mock = _make_explainer()
    gc_mock.side_effect = RuntimeError("down")
    before = _external_calls("gemini", "explain_match", "error")

    out = await explainer.explain(_ctx())

    assert out["generator"] == "templated"
    assert _external_calls("gemini", "explain_match", "error") == before + 1


@pytest.mark.asyncio
async def test_llm_explainer_hindi_appends_language_directive() -> None:
    """The generate_content call's system_instruction mentions Hindi when ctx.language='hi'."""
    explainer, gc_mock = _make_explainer()
    gc_mock.return_value = SimpleNamespace(text='{"fit": "अच्छा मेल"}')

    await explainer.explain(_ctx(language="hi", total=0.9, threshold=0.5))

    config = gc_mock.await_args.kwargs["config"]
    assert "Hindi" in config.system_instruction


@pytest.mark.asyncio
async def test_llm_explainer_english_instruction_unchanged() -> None:
    """English context should not have Hindi directive in system instruction."""
    explainer, gc_mock = _make_explainer()
    gc_mock.return_value = SimpleNamespace(text='{"fit": "good match"}')

    await explainer.explain(_ctx(total=0.9, threshold=0.5))

    config = gc_mock.await_args.kwargs["config"]
    assert "Hindi" not in config.system_instruction


@pytest.mark.asyncio
async def test_llm_failure_falls_back_to_hindi_templated_for_hindi_ctx() -> None:
    """On LLM failure with Hindi context, fallback should return Hindi templated."""
    gc_mock = AsyncMock(side_effect=RuntimeError("503"))
    client = MagicMock()
    client.aio.models.generate_content = gc_mock
    explainer = GeminiMatchExplainer(client=client, model="m")

    result = await explainer.explain(_ctx(language="hi", total=0.9, threshold=0.5))

    assert result["generator"] == "templated"
    # Check for Devanagari script presence (Hindi text should contain Devanagari characters)
    assert any("ऀ" <= ch <= "ॿ" for ch in result["fit"])


@pytest.mark.asyncio
async def test_generator_version_bumped() -> None:
    """LLM_GENERATOR_VERSION should be '2' after the Hindi update."""
    assert LLM_GENERATOR_VERSION == "2"


@pytest.mark.asyncio
@pytest.mark.parametrize("placeholder", ["None", "none.", "N/A", "-", " null "])
async def test_placeholder_caveat_is_treated_as_empty(placeholder: str) -> None:
    """Seen live 2026-09-08: gemini-2.5-flash returned caveat "None" (the
    string) for a clean match. Rendering that as a caveat is wrong; it is the
    absence of one."""
    import json

    explainer, gc_mock = _make_explainer()
    gc_mock.return_value = SimpleNamespace(
        text=json.dumps({"fit": "Great fit at Acme.", "caveat": placeholder})
    )

    out = await explainer.explain(_ctx())

    assert out["caveat"] == ""
    assert out["generator"] == "llm"
