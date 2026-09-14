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

from jobify.integrations.gemini_thinking import no_thinking_config
from jobify.observability.external import observe_external_call
from jobify.scoring.explainer import ExplainContext, _templated_from_ctx

if TYPE_CHECKING:
    from google.genai import Client as GenaiClient

_log = structlog.get_logger(__name__)

LLM_GENERATOR = "llm"
LLM_GENERATOR_VERSION = "2"

_NO_CAVEAT_PLACEHOLDERS = frozenset({"none", "null", "n/a", "na", "-", "—", "no caveat"})

_SYSTEM_INSTRUCTION = (
    "You are Jobify's match explainer. Given a candidate-to-job match summary, "
    "produce a one-sentence 'fit' (<=25 words, concrete, no fluff) and an "
    "optional one-sentence 'caveat' (<=25 words, only if there is a real "
    'concern). Return JSON: {"fit": str, "caveat": str}. '
    "Do not mention scores or thresholds."
)

_HINDI_DIRECTIVE = (
    " Respond in Hindi (Devanagari script). Keep the same JSON shape and the "
    "same length limits. Job titles, company names, and city names stay in "
    "their original script."
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
    ``jobify_worker.runtime.get_match_explainer``.
    """

    generator_version = LLM_GENERATOR_VERSION

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
            if ctx.language == "hi":
                instruction = _SYSTEM_INSTRUCTION + _HINDI_DIRECTIVE
            else:
                instruction = _SYSTEM_INSTRUCTION
            with observe_external_call("gemini", "explain_match", log_traceback=False):
                resp = await self._client.aio.models.generate_content(
                    model=self._model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=instruction,
                        response_mime_type="application/json",
                        response_schema=_RESPONSE_SCHEMA,
                        temperature=0.3,
                        max_output_tokens=200,
                        # Gemini thinks by default and thought tokens count
                        # against max_output_tokens: with the 200 cap the model
                        # burned ~190 tokens thinking, finished MAX_TOKENS, and
                        # emitted an unparsable preamble — every explain silently
                        # fell back to templated. This is a two-sentence JSON task;
                        # thinking buys nothing. The knob differs per model family.
                        thinking_config=no_thinking_config(self._model),
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
            caveat = caveat_raw.strip() if isinstance(caveat_raw, str) else ""
            # The model sometimes spells "no caveat" as a literal placeholder
            # ("None", "N/A", "-") — seen live 2026-09-08 on gemini-2.5-flash.
            # That is an empty caveat, not one to render.
            if caveat.casefold().strip(".") in _NO_CAVEAT_PLACEHOLDERS:
                caveat = ""
            return {
                "fit": fit,
                "caveat": caveat,
                "generator": LLM_GENERATOR,
                "generator_version": LLM_GENERATOR_VERSION,
            }
        except Exception as exc:  # noqa: BLE001 — explain() NEVER raises; any failure degrades to templated
            # Shape only: the model's raw output can restate the applicant's
            # profile, and provider errors can echo the prompt (core/CLAUDE.md).
            _log.warning(
                "explain.llm-failed",
                error_type=type(exc).__name__,
                raw_length=len(text) if text is not None else None,
            )
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
