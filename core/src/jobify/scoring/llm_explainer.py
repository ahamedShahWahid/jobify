"""Gemini-backed MatchExplainer — surfaced-only LLM call with templated fallback.

This module imports ``google.genai`` at module load time. Anything that only
needs the templated explainer should import from ``jobify.scoring.explainer``,
which deliberately does NOT pull in genai (mirrors the embeddings package).

Behavior:
- Below-threshold matches return the templated explanation without an LLM call.
- Above-threshold matches call ``client.aio.models.generate_content`` with a
  JSON response schema. Any failure (provider exception, empty response,
  malformed JSON, non-dict JSON) is logged at WARNING and falls back to the
  templated explanation. ``explain()`` never raises.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import structlog
from google.genai import types

from jobify.scoring.explainer import ExplainContext, _templated_from_ctx

if TYPE_CHECKING:
    from google.genai import Client as GenaiClient

_log = structlog.get_logger(__name__)

LLM_GENERATOR = "llm"
LLM_GENERATOR_VERSION = "1"

_SYSTEM_INSTRUCTION = (
    "You are Jobify's match explainer. Given a candidate-to-job match summary, "
    "produce a one-sentence 'fit' (<=25 words, concrete, no fluff) and an "
    "optional one-sentence 'caveat' (<=25 words, only if there is a real "
    'concern). Return JSON: {"fit": str, "caveat": str}. '
    "Do not mention scores or thresholds."
)

_RESPONSE_SCHEMA = types.Schema(
    type=types.Type.OBJECT,
    properties={
        "fit": types.Schema(type=types.Type.STRING),
        "caveat": types.Schema(type=types.Type.STRING),
    },
    required=["fit"],
)


class GeminiMatchExplainer:
    """Constructor-injected genai client + model.

    Tests pass a MagicMock(); production wires this via
    ``jobify.workers.celery_app.get_match_explainer``.
    """

    def __init__(self, *, client: GenaiClient, model: str) -> None:
        self._client = client
        self._model = model

    async def explain(self, ctx: ExplainContext) -> dict[str, str]:
        # Surfaced-only gate — no LLM call below threshold.
        if ctx.total < ctx.threshold:
            return _templated_from_ctx(ctx)

        text: str | None = None
        try:
            prompt = _build_prompt(ctx)
            resp = await self._client.aio.models.generate_content(
                model=self._model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=_SYSTEM_INSTRUCTION,
                    response_mime_type="application/json",
                    response_schema=_RESPONSE_SCHEMA,
                    temperature=0.3,
                    max_output_tokens=200,
                    # gemini-2.5 thinks by default and thought tokens count
                    # against max_output_tokens: with the 200 cap the model
                    # burned ~190 tokens thinking, finished MAX_TOKENS, and
                    # emitted an unparsable preamble — every explain silently
                    # fell back to templated. This is a two-sentence JSON task;
                    # thinking buys nothing.
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                ),
            )
            text = getattr(resp, "text", None)
            if not text:
                raise ValueError("empty response text")
            parsed: Any = json.loads(text)
            if not isinstance(parsed, dict):
                raise ValueError(f"expected object, got {type(parsed).__name__}")
            fit = parsed.get("fit")
            if not isinstance(fit, str) or not fit:
                raise ValueError("missing or empty 'fit' field")
            caveat_raw = parsed.get("caveat", "")
            caveat = caveat_raw if isinstance(caveat_raw, str) else ""
            return {
                "fit": fit,
                "caveat": caveat,
                "generator": LLM_GENERATOR,
                "generator_version": LLM_GENERATOR_VERSION,
            }
        except Exception:
            # raw_text is the diagnosis handle — the templated fallback makes
            # this failure invisible everywhere else.
            _log.warning("explain.llm-failed", raw_text=(text or "")[:200], exc_info=True)
            return _templated_from_ctx(ctx)


def _build_prompt(ctx: ExplainContext) -> str:
    """Compact prompt — concrete facts only, no scores."""
    job_loc = ", ".join(ctx.job_locations) if ctx.job_locations else "unspecified"
    applicant_loc = ", ".join(ctx.applicant_locations) if ctx.applicant_locations else "unspecified"
    ctc_max = f"{ctx.job_ctc_max}" if ctx.job_ctc_max is not None else "unspecified"
    applicant_ctc = (
        f"{ctx.applicant_expected_ctc}" if ctx.applicant_expected_ctc is not None else "unspecified"
    )
    return (
        f"Role: {ctx.job_title} at {ctx.employer_name}.\n"
        f"Job locations: {job_loc}. Applicant locations: {applicant_loc}.\n"
        f"Experience band required: {ctx.job_min_exp_years}-{ctx.job_max_exp_years} years.\n"
        f"Job CTC max: {ctc_max}. Applicant expected CTC: {applicant_ctc}.\n"
        f"Component fits (0-1): location={ctx.components.get('location', 0.5):.2f}, "
        f"experience={ctx.components.get('exp', 0.5):.2f}, "
        f"compensation={ctx.components.get('ctc', 0.5):.2f}."
    )
