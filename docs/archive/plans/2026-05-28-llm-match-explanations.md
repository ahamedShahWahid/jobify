# LLM Match Explanations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Gemini-backed `MatchExplainer` behind a Protocol, selectable by env var, shipping dark (default `templated`). Flipping to LLM is a one-line env change.

**Architecture:** New `kpa/scoring/explainer.py` defines `ExplainContext`, a `MatchExplainer` Protocol, and a `TemplatedExplainer` that wraps the existing pure-function `templated_explanation(...)`. New `kpa/scoring/llm_explainer.py` adds `GeminiMatchExplainer` (constructor-injected `google.genai` client, surfaced-only LLM gate, broad fallback to templated on any failure). A lazy singleton `get_match_explainer()` in `kpa/workers/celery_app.py` chooses the impl from `settings.match_explainer`. Both score workers replace their inline `templated_explanation(...)` call with `await get_match_explainer().explain(ctx)`. No DB migration, no new queue, no new worker.

**Tech Stack:** FastAPI 0.115+ / SQLAlchemy 2.0 async / structlog / `google-genai >=1.0,<2` / pydantic-settings / pytest + pytest-asyncio.

**Spec:** `docs/superpowers/specs/2026-05-28-llm-match-explanations-design.md`

---

## File Structure

**New files:**

- `api/src/kpa/scoring/explainer.py` — `ExplainContext` (frozen dataclass), `MatchExplainer` (Protocol), `TemplatedExplainer`, `_templated_from_ctx(ctx)` helper. **No `google.genai` import** — anything that needs only the templated impl can `from kpa.scoring.explainer import ...` without pulling genai.
- `api/src/kpa/scoring/llm_explainer.py` — `GeminiMatchExplainer`, `LLM_GENERATOR="llm"`, `LLM_GENERATOR_VERSION="1"`. Imports `google.genai`. Lives in its own module so `explainer.py` stays genai-free (mirrors `embeddings/__init__.py` not re-exporting `GeminiEmbeddingProvider`).
- `api/tests/unit/test_explainer.py` — Unit tests for `TemplatedExplainer`.
- `api/tests/unit/test_llm_explainer.py` — Unit tests for `GeminiMatchExplainer` with a fake genai client.
- `api/tests/integration/test_llm_explainer_wiring.py` — End-to-end wiring test: with fake explainer injected, a scored applicant produces a `matches.explanation["generator"] == "fake-llm"` row.

**Modified files:**

- `api/src/kpa/settings.py` — Add `match_explainer` (str, default `"templated"`) and `match_explainer_model` (str, default `"gemini-2.5-flash"`) fields + validator.
- `api/src/kpa/workers/celery_app.py` — Add `_match_explainer` module-level cache + `get_match_explainer()` factory (mirrors `get_embedding_provider` / `get_email_channel`).
- `api/src/kpa/workers/tasks/score_applicant.py` — Replace the local `from kpa.scoring.explain import templated_explanation` import + inline call with `from kpa.scoring.explainer import ExplainContext` + `from kpa.workers.celery_app import get_match_explainer` + `await get_match_explainer().explain(ctx)`.
- `api/src/kpa/workers/tasks/score_job.py` — Same replacement.
- `api/tests/unit/test_settings.py` — Add 3 tests covering the new settings.
- `api/tests/integration/conftest.py` — Add `FakeMatchExplainer` dataclass + `patched_match_explainer` fixture mirroring the embedding-provider one (patches in three places + seeds the cache).
- `api/.env.example` — Document `KPA_MATCH_EXPLAINER` and `KPA_MATCH_EXPLAINER_MODEL`.
- `api/CLAUDE.md` — Update the "Match explanations" subsection under "Architecture — non-obvious bits".

**Unchanged (callouts):**

- `api/src/kpa/scoring/explain.py` — `templated_explanation(...)` is the fallback; signature stays intact.
- `api/tests/unit/test_explain_templated.py` — keeps passing as-is.
- `api/src/kpa/db/models.py` — `matches.explanation` JSONB is already the right shape.

---

## Task 1: Settings — `match_explainer` + `match_explainer_model`

**Files:**
- Modify: `api/src/kpa/settings.py:117-131` (insert after scoring fields, before `# --- Notifications ---`)
- Modify: `api/tests/unit/test_settings.py` (append new tests after `test_notify_batch_size_out_of_range_rejected`)

- [ ] **Step 1: Write the failing tests**

Append to `api/tests/unit/test_settings.py`:

```python
# ---------------------------------------------------------------------------
# Match-explainer settings (from sub-project G)
# ---------------------------------------------------------------------------


def test_match_explainer_default_is_templated(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_minimum_env(monkeypatch)
    monkeypatch.delenv("KPA_MATCH_EXPLAINER", raising=False)
    s = Settings()
    assert s.match_explainer == "templated"


def test_match_explainer_llm_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_minimum_env(monkeypatch)
    monkeypatch.setenv("KPA_MATCH_EXPLAINER", "llm")
    s = Settings()
    assert s.match_explainer == "llm"


def test_match_explainer_invalid_value_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_minimum_env(monkeypatch)
    monkeypatch.setenv("KPA_MATCH_EXPLAINER", "openai")
    with pytest.raises(ValidationError, match="match_explainer"):
        Settings()


def test_match_explainer_model_default(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_minimum_env(monkeypatch)
    monkeypatch.delenv("KPA_MATCH_EXPLAINER_MODEL", raising=False)
    s = Settings()
    assert s.match_explainer_model == "gemini-2.5-flash"


def test_match_explainer_model_override(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_minimum_env(monkeypatch)
    monkeypatch.setenv("KPA_MATCH_EXPLAINER_MODEL", "gemini-2.5-pro")
    s = Settings()
    assert s.match_explainer_model == "gemini-2.5-pro"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd api && uv run pytest tests/unit/test_settings.py -k "match_explainer" -v
```

Expected: 5 FAILs with `AttributeError: 'Settings' object has no attribute 'match_explainer'` (or `AttributeError: ... match_explainer_model`).

- [ ] **Step 3: Add the settings fields + validator**

In `api/src/kpa/settings.py`, insert immediately after the `match_vector_weight` field (`api/src/kpa/settings.py:131`, before `# --- Notifications ---`):

```python
    match_explainer: str = Field(
        default="templated",
        alias="KPA_MATCH_EXPLAINER",
        description="Match-explanation generator: 'templated' (default) or 'llm' (Gemini).",
    )
    match_explainer_model: str = Field(
        default="gemini-2.5-flash",
        alias="KPA_MATCH_EXPLAINER_MODEL",
        description="Gemini text-generation model used when match_explainer='llm'.",
    )
```

Then add a `@field_validator` next to `_enforce_valid_email_channel` (around `api/src/kpa/settings.py:228`):

```python
    @field_validator("match_explainer")
    @classmethod
    def _enforce_valid_match_explainer(cls, v: str) -> str:
        if v not in ("templated", "llm"):
            raise ValueError(f"match_explainer must be 'templated' or 'llm', got {v!r}")
        return v
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd api && uv run pytest tests/unit/test_settings.py -k "match_explainer" -v
```

Expected: 5 PASS.

- [ ] **Step 5: Run mypy to confirm no regressions**

```bash
cd api && uv run mypy
```

Expected: `Success: no issues found`.

- [ ] **Step 6: Commit**

```bash
git add api/src/kpa/settings.py api/tests/unit/test_settings.py
git commit -m "feat(api): add KPA_MATCH_EXPLAINER + KPA_MATCH_EXPLAINER_MODEL settings"
```

---

## Task 2: `ExplainContext` + `MatchExplainer` Protocol + `TemplatedExplainer`

**Files:**
- Create: `api/src/kpa/scoring/explainer.py`
- Create: `api/tests/unit/test_explainer.py`

- [ ] **Step 1: Write the failing tests**

Create `api/tests/unit/test_explainer.py`:

```python
"""Unit tests for the ExplainContext + TemplatedExplainer."""

from __future__ import annotations

from decimal import Decimal

import pytest

from kpa.scoring.explain import templated_explanation
from kpa.scoring.explainer import ExplainContext, TemplatedExplainer


def _ctx(**overrides: object) -> ExplainContext:
    base: dict[str, object] = {
        "components": {"location": 1.0, "exp": 1.0, "ctc": 1.0},
        "vector": 0.9,
        "structured": 1.0,
        "total": 0.94,
        "threshold": 0.55,
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


@pytest.mark.asyncio
async def test_templated_explainer_matches_pure_function() -> None:
    """TemplatedExplainer.explain(ctx) must return exactly what
    templated_explanation(**fields) returns for the same fields."""
    ctx = _ctx()
    expected = templated_explanation(
        components=ctx.components,
        vector=ctx.vector,
        structured=ctx.structured,
        total=ctx.total,
        threshold=ctx.threshold,
        job_title=ctx.job_title,
        job_locations=ctx.job_locations,
        job_min_exp_years=ctx.job_min_exp_years,
        job_max_exp_years=ctx.job_max_exp_years,
        job_ctc_max=ctx.job_ctc_max,
        employer_name=ctx.employer_name,
        applicant_expected_ctc=ctx.applicant_expected_ctc,
        applicant_locations=ctx.applicant_locations,
    )
    out = await TemplatedExplainer().explain(ctx)
    assert out == expected
    assert out["generator"] == "templated"
    assert out["generator_version"] == "1"


def test_explain_context_is_frozen() -> None:
    """ExplainContext is a frozen dataclass — mutation must raise."""
    ctx = _ctx()
    with pytest.raises((AttributeError, TypeError)):
        ctx.total = 0.1  # type: ignore[misc]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd api && uv run pytest tests/unit/test_explainer.py -v
```

Expected: FAILs (`ModuleNotFoundError: No module named 'kpa.scoring.explainer'`).

- [ ] **Step 3: Create the explainer module**

Create `api/src/kpa/scoring/explainer.py`:

```python
"""Match-explanation Protocol + frozen context + templated impl.

Wraps the pure-function ``templated_explanation`` from ``kpa.scoring.explain`` in
an async Protocol so the score workers can route between templated and LLM impls
behind a single call site. The LLM impl lives in ``kpa.scoring.llm_explainer``
so importing this module does not pull in ``google.genai``.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol, runtime_checkable

from kpa.scoring.explain import templated_explanation


@dataclass(frozen=True, slots=True)
class ExplainContext:
    """Frozen bundle of the 13 fields ``templated_explanation`` accepts.

    Workers build this once per match between the score computation and the
    UPSERT, then hand it to whichever ``MatchExplainer`` is configured.
    """

    components: dict[str, float]
    vector: float
    structured: float
    total: float
    threshold: float
    job_title: str
    job_locations: list[str]
    job_min_exp_years: int
    job_max_exp_years: int
    job_ctc_max: Decimal | None
    employer_name: str
    applicant_expected_ctc: Decimal | None
    applicant_locations: list[str]


@runtime_checkable
class MatchExplainer(Protocol):
    """Returns the 4-key explanation dict stored on matches.explanation."""

    async def explain(self, ctx: ExplainContext) -> dict[str, str]: ...


def _templated_from_ctx(ctx: ExplainContext) -> dict[str, str]:
    """Shared helper — both TemplatedExplainer and the LLM impl's fallback call this."""
    return templated_explanation(
        components=ctx.components,
        vector=ctx.vector,
        structured=ctx.structured,
        total=ctx.total,
        threshold=ctx.threshold,
        job_title=ctx.job_title,
        job_locations=ctx.job_locations,
        job_min_exp_years=ctx.job_min_exp_years,
        job_max_exp_years=ctx.job_max_exp_years,
        job_ctc_max=ctx.job_ctc_max,
        employer_name=ctx.employer_name,
        applicant_expected_ctc=ctx.applicant_expected_ctc,
        applicant_locations=ctx.applicant_locations,
    )


class TemplatedExplainer:
    """Async wrapper over the pure templated_explanation function.

    The ``async`` is interface uniformity; the body is sync.
    """

    async def explain(self, ctx: ExplainContext) -> dict[str, str]:
        return _templated_from_ctx(ctx)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd api && uv run pytest tests/unit/test_explainer.py -v
```

Expected: 2 PASS.

- [ ] **Step 5: Run the existing templated-explanation tests to confirm no regressions**

```bash
cd api && uv run pytest tests/unit/test_explain_templated.py -v
```

Expected: all PASS (this module is untouched but the new code depends on it).

- [ ] **Step 6: Mypy check**

```bash
cd api && uv run mypy
```

Expected: `Success: no issues found`.

- [ ] **Step 7: Commit**

```bash
git add api/src/kpa/scoring/explainer.py api/tests/unit/test_explainer.py
git commit -m "feat(api): ExplainContext + MatchExplainer protocol + TemplatedExplainer"
```

---

## Task 3: `GeminiMatchExplainer` with constructor-injected client

**Files:**
- Create: `api/src/kpa/scoring/llm_explainer.py`
- Create: `api/tests/unit/test_llm_explainer.py`

**Pre-implementation check:** This is the first text-generation call against `google-genai` in the repo. Before writing the implementation in Step 3, verify the structured-output API shape against context7:

```
mcp__plugin_context7_context7__resolve-library-id "google-genai"
mcp__plugin_context7_context7__query-docs <id>  "GenerateContentConfig response_schema response_mime_type system_instruction aio.models.generate_content"
```

Confirm: `client.aio.models.generate_content(model=..., contents=..., config=types.GenerateContentConfig(system_instruction=..., response_mime_type="application/json", response_schema=<Schema>, temperature=..., max_output_tokens=...))` and that the response exposes `.text` (a JSON string when `response_mime_type="application/json"`). If the API differs, adapt **Step 3** accordingly; **Steps 1–2 (tests)** stay valid because they assert via a fake client.

- [ ] **Step 1: Write the failing tests**

Create `api/tests/unit/test_llm_explainer.py`:

```python
"""Unit tests for GeminiMatchExplainer — genai client fully faked, no network."""

from __future__ import annotations

import json
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from kpa.scoring.explainer import ExplainContext
from kpa.scoring.llm_explainer import (
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
    assert "fit" in out and out["fit"]


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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd api && uv run pytest tests/unit/test_llm_explainer.py -v
```

Expected: FAILs (`ModuleNotFoundError: No module named 'kpa.scoring.llm_explainer'`).

- [ ] **Step 3: Implement `GeminiMatchExplainer`**

Create `api/src/kpa/scoring/llm_explainer.py`:

```python
"""Gemini-backed MatchExplainer — surfaced-only LLM call with templated fallback.

This module imports ``google.genai`` at module load time. Anything that only
needs the templated explainer should import from ``kpa.scoring.explainer``,
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

from kpa.scoring.explainer import ExplainContext, _templated_from_ctx

if TYPE_CHECKING:
    from google.genai import Client as GenaiClient

_log = structlog.get_logger(__name__)

LLM_GENERATOR = "llm"
LLM_GENERATOR_VERSION = "1"

_SYSTEM_INSTRUCTION = (
    "You are KPA's match explainer. Given a candidate-to-job match summary, "
    "produce a one-sentence 'fit' (<=25 words, concrete, no fluff) and an "
    "optional one-sentence 'caveat' (<=25 words, only if there is a real "
    "concern). Return JSON: {\"fit\": str, \"caveat\": str}. "
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
    ``kpa.workers.celery_app.get_match_explainer``.
    """

    def __init__(self, *, client: GenaiClient, model: str) -> None:
        self._client = client
        self._model = model

    async def explain(self, ctx: ExplainContext) -> dict[str, str]:
        # Surfaced-only gate — no LLM call below threshold.
        if ctx.total < ctx.threshold:
            return _templated_from_ctx(ctx)

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
            _log.warning("explain.llm-failed", exc_info=True)
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd api && uv run pytest tests/unit/test_llm_explainer.py -v
```

Expected: 7 PASS.

- [ ] **Step 5: Mypy check**

```bash
cd api && uv run mypy
```

Expected: `Success: no issues found`.

- [ ] **Step 6: Commit**

```bash
git add api/src/kpa/scoring/llm_explainer.py api/tests/unit/test_llm_explainer.py
git commit -m "feat(api): GeminiMatchExplainer with surfaced-only LLM call and templated fallback"
```

---

## Task 4: `get_match_explainer()` factory in `celery_app.py`

**Files:**
- Modify: `api/src/kpa/workers/celery_app.py` (add module-level cache + factory after `get_email_channel`, end of file)

This task has no tests of its own — Task 1 already covers settings validation, and Task 7's integration test verifies that workers honor the factory. Unit-testing the factory in isolation would just exercise `if/elif/else`, which the integration test covers end-to-end.

- [ ] **Step 1: Add the import-time TYPE_CHECKING entry**

In `api/src/kpa/workers/celery_app.py`, add to the existing `if TYPE_CHECKING:` block (currently at lines 25-29):

```python
if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

    from kpa.integrations.embeddings.gemini import GeminiEmbeddingProvider
    from kpa.integrations.notifications.base import EmailChannel
    from kpa.scoring.explainer import MatchExplainer
```

- [ ] **Step 2: Append the cache + factory at the end of the file**

Append to `api/src/kpa/workers/celery_app.py` (after `get_email_channel`, which ends near line 160):

```python


# --- Per-worker match explainer ---

_match_explainer: MatchExplainer | None = None


def get_match_explainer() -> MatchExplainer:
    """Return the worker's match explainer, building it lazily.

    Reads ``settings.match_explainer`` to choose the implementation:
    - ``"templated"`` — ``TemplatedExplainer`` (default; deterministic, no network).
    - ``"llm"``       — ``GeminiMatchExplainer`` wrapping ``genai.Client``.

    Like ``get_embedding_provider``, the explainer is built on first call so
    that eager-mode tests can monkeypatch before the factory is invoked. The
    LLM branch defers ``from google import genai`` so the templated path never
    pays the import cost.
    """
    global _match_explainer
    if _match_explainer is None:
        if settings.match_explainer == "templated":
            from kpa.scoring.explainer import TemplatedExplainer

            _match_explainer = TemplatedExplainer()
        elif settings.match_explainer == "llm":
            from google import genai

            from kpa.scoring.llm_explainer import GeminiMatchExplainer

            _match_explainer = GeminiMatchExplainer(
                client=genai.Client(api_key=settings.gemini_api_key.get_secret_value()),
                model=settings.match_explainer_model,
            )
        else:
            raise ValueError(f"unknown match_explainer: {settings.match_explainer!r}")
    return _match_explainer
```

- [ ] **Step 3: Run the full unit + integration suite that already exists to confirm no regression**

```bash
cd api && uv run pytest tests/unit -v
```

Expected: all PASS (no behavioral change yet; new symbol just exists).

```bash
cd api && uv run pytest tests/integration -v -m integration -k "score or embed"
```

Expected: all PASS (workers still call `templated_explanation` directly; we wire them in Tasks 5–6).

- [ ] **Step 4: Mypy check**

```bash
cd api && uv run mypy
```

Expected: `Success: no issues found`.

- [ ] **Step 5: Commit**

```bash
git add api/src/kpa/workers/celery_app.py
git commit -m "feat(api): get_match_explainer() lazy-singleton factory"
```

---

## Task 5: Wire `score_applicant.py` to use `get_match_explainer().explain(ctx)`

**Files:**
- Modify: `api/src/kpa/workers/tasks/score_applicant.py:141-185` (the compute step)

- [ ] **Step 1: Replace the local import + inline templated call**

In `api/src/kpa/workers/tasks/score_applicant.py`:

**Delete** the line at `api/src/kpa/workers/tasks/score_applicant.py:141`:

```python
    from kpa.scoring.explain import templated_explanation
```

**Replace** with these two local imports (at the same spot, inside the `async def` so eager-mode patching works):

```python
    from kpa.scoring.explainer import ExplainContext
    from kpa.workers.celery_app import get_match_explainer

    _explainer = get_match_explainer()
```

**Replace** the existing `explanation = templated_explanation(...)` block (`api/src/kpa/workers/tasks/score_applicant.py:170-184`) with:

```python
        ctx = ExplainContext(
            components=ms.components,
            vector=ms.vector,
            structured=ms.structured,
            total=ms.total,
            threshold=_settings.match_surface_threshold,
            job_title=job_title,
            job_locations=job_locs,
            job_min_exp_years=job_min_exp,
            job_max_exp_years=job_max_exp,
            job_ctc_max=job_ctc_max,
            employer_name=employer_name,
            applicant_expected_ctc=applicant_ctc,
            applicant_locations=applicant_locs,
        )
        explanation = await _explainer.explain(ctx)
```

The surrounding `for ... in scored_inputs` loop, `score_match(...)` call, and `scores.append((job_id, ms, job_emb_model, explanation))` stay unchanged.

- [ ] **Step 2: Run the score_applicant integration suite**

```bash
cd api && uv run pytest tests/integration/test_score_applicant_worker.py -v -m integration
```

Expected: all PASS. The existing assertions (`row.explanation["generator"] == "templated"`) still hold because `settings.match_explainer` defaults to `"templated"`.

- [ ] **Step 3: Mypy check**

```bash
cd api && uv run mypy
```

Expected: `Success: no issues found`.

- [ ] **Step 4: Commit**

```bash
git add api/src/kpa/workers/tasks/score_applicant.py
git commit -m "refactor(api): score_applicant uses get_match_explainer() instead of inline templated"
```

---

## Task 6: Wire `score_job.py` similarly

**Files:**
- Modify: `api/src/kpa/workers/tasks/score_job.py:132-172` (the compute step)

- [ ] **Step 1: Apply the same swap to `score_job.py`**

In `api/src/kpa/workers/tasks/score_job.py`:

**Delete** the line at `api/src/kpa/workers/tasks/score_job.py:132`:

```python
    from kpa.scoring.explain import templated_explanation
```

**Replace** with:

```python
    from kpa.scoring.explainer import ExplainContext
    from kpa.workers.celery_app import get_match_explainer

    _explainer = get_match_explainer()
```

**Replace** the `explanation = templated_explanation(...)` block (`api/src/kpa/workers/tasks/score_job.py:157-171`) with:

```python
        ctx = ExplainContext(
            components=ms.components,
            vector=ms.vector,
            structured=ms.structured,
            total=ms.total,
            threshold=_settings.match_surface_threshold,
            job_title=job_title,
            job_locations=job_locs,
            job_min_exp_years=job_min_exp,
            job_max_exp_years=job_max_exp,
            job_ctc_max=job_ctc_max,
            employer_name=job_employer_name,
            applicant_expected_ctc=applicant_ctc,
            applicant_locations=applicant_locs,
        )
        explanation = await _explainer.explain(ctx)
```

Note: `employer_name=job_employer_name` here — the job-side worker's local variable is `job_employer_name`, not `employer_name` (compare `score_job.py:125`).

- [ ] **Step 2: Run the score_job integration suite**

```bash
cd api && uv run pytest tests/integration/test_score_job_worker.py -v -m integration
```

Expected: all PASS — same reasoning as Task 5 (default explainer is templated).

- [ ] **Step 3: Mypy check**

```bash
cd api && uv run mypy
```

Expected: `Success: no issues found`.

- [ ] **Step 4: Commit**

```bash
git add api/src/kpa/workers/tasks/score_job.py
git commit -m "refactor(api): score_job uses get_match_explainer() instead of inline templated"
```

---

## Task 7: `patched_match_explainer` fixture + integration wiring test

**Files:**
- Modify: `api/tests/integration/conftest.py` (add `FakeMatchExplainer` + fixture after the embedding-provider section, around line 130)
- Create: `api/tests/integration/test_llm_explainer_wiring.py`

- [ ] **Step 1: Add `FakeMatchExplainer` + `patched_match_explainer` fixture**

In `api/tests/integration/conftest.py`, after the `patched_embedding_provider` fixture (around line 130), append:

```python


@dataclass
class FakeMatchExplainer:
    """Test double: records every call, returns a marker dict so the wiring test
    can assert the worker actually routed through the configured explainer."""

    calls: list["ExplainContext"] = field(default_factory=list)
    fit: str = "fake-llm fit string"
    caveat: str = "fake-llm caveat string"

    async def explain(self, ctx: "ExplainContext") -> dict[str, str]:
        self.calls.append(ctx)
        return {
            "fit": self.fit,
            "caveat": self.caveat,
            "generator": "fake-llm",
            "generator_version": "test",
        }


@pytest.fixture
def match_explainer() -> FakeMatchExplainer:
    return FakeMatchExplainer()


@pytest.fixture
def patched_match_explainer(
    monkeypatch: pytest.MonkeyPatch,
    match_explainer: FakeMatchExplainer,
) -> FakeMatchExplainer:
    """Patch get_match_explainer() so eager-mode score workers use the fake.

    Mirrors patched_embedding_provider: three patch sites + the cache, because
    score_applicant.py and score_job.py do
    ``from kpa.workers.celery_app import get_match_explainer`` locally inside
    the async body. Each local import creates a separate reference; we patch
    both call sites plus the source module, then seed the module-level cache.
    """
    import kpa.workers.celery_app as cel
    import kpa.workers.tasks.score_applicant as sa_mod
    import kpa.workers.tasks.score_job as sj_mod

    monkeypatch.setattr(cel, "get_match_explainer", lambda: match_explainer)
    monkeypatch.setattr(sa_mod, "get_match_explainer", lambda: match_explainer, raising=False)
    monkeypatch.setattr(sj_mod, "get_match_explainer", lambda: match_explainer, raising=False)
    monkeypatch.setattr(cel, "_match_explainer", match_explainer)
    return match_explainer
```

Add the `ExplainContext` import to the top-of-file imports (after `from kpa.integrations.embeddings import EmbeddingResult, EmbeddingTask`):

```python
from kpa.scoring.explainer import ExplainContext
```

**Note on `raising=False`:** `score_applicant.py` and `score_job.py` import `get_match_explainer` **inside** the `async def` body (Task 5/6 chose local imports so this exact patching strategy works). On the first invocation during the test the name has not yet been bound on the module, so `monkeypatch.setattr(..., raising=False)` is necessary; the patched attribute then shadows the local import binding.

- [ ] **Step 2: Write the failing wiring test**

Create `api/tests/integration/test_llm_explainer_wiring.py`:

```python
"""Integration test: with a fake explainer injected, the score worker routes
the explanation through the factory and stores the fake's marker generator.

Confirms the wiring established in Tasks 5–6 (score_applicant.py and
score_job.py both call get_match_explainer().explain(ctx) instead of the
inline templated function)."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from kpa.db.models import (
    Applicant,
    ApplicantEmbedding,
    Employer,
    Job,
    JobEmbedding,
    Match,
    User,
    UserRole,
)
from kpa.workers.tasks.score_applicant import _score_applicant_async


def _make_sm(session: AsyncSession) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(bind=session.bind, expire_on_commit=False)


@pytest.mark.asyncio
async def test_score_applicant_routes_through_match_explainer_factory(
    session: AsyncSession,
    patched_match_explainer,  # noqa: ARG001 — fixture has side effect of patching
) -> None:
    """A scored applicant with a job that crosses threshold should produce a
    matches.explanation whose generator == 'fake-llm' (the fake's marker)."""
    user = User(email="wiring@example.com", role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()
    applicant = Applicant(
        user_id=user.id,
        full_name="Wiring Test",
        locations=["Bangalore"],
        years_experience=4,
    )
    session.add(applicant)
    await session.flush()
    session.add(
        ApplicantEmbedding(
            applicant_id=applicant.id,
            embedding=[1.0] * 1536,
            model_name="test-model",
            canonicalized_text_hash="a" * 64,
            input_tokens=10,
        )
    )
    employer = Employer(name="Acme", name_norm="acme")
    session.add(employer)
    await session.flush()
    job = Job(
        employer_id=employer.id,
        title="Engineer",
        description="x",
        locations=["Bangalore"],
        min_exp_years=1,
        max_exp_years=5,
    )
    session.add(job)
    await session.flush()
    session.add(
        JobEmbedding(
            job_id=job.id,
            embedding=[1.0] * 1536,  # parallel to applicant → vector score 1.0 → surfaces
            model_name="test-model",
            canonicalized_text_hash="b" * 64,
            input_tokens=10,
        )
    )
    await session.commit()

    await _score_applicant_async(applicant.id, sm=_make_sm(session))

    row = (
        await session.execute(
            select(Match).where(Match.applicant_id == applicant.id, Match.job_id == job.id)
        )
    ).scalar_one()
    assert row.explanation is not None
    assert row.explanation["generator"] == "fake-llm"
    assert row.explanation["fit"] == "fake-llm fit string"
    assert row.explanation["generator_version"] == "test"
```

- [ ] **Step 3: Run the wiring test**

```bash
cd api && uv run pytest tests/integration/test_llm_explainer_wiring.py -v -m integration
```

Expected: PASS. The fake explainer's marker hits `matches.explanation`.

- [ ] **Step 4: Re-run the full score-applicant + score-job integration suites to confirm the fixture doesn't break the default path**

```bash
cd api && uv run pytest tests/integration/test_score_applicant_worker.py tests/integration/test_score_job_worker.py -v -m integration
```

Expected: all PASS (these tests don't use `patched_match_explainer`, so the default `TemplatedExplainer` is built and they still see `generator == "templated"`).

- [ ] **Step 5: Mypy check**

```bash
cd api && uv run mypy
```

Expected: `Success: no issues found`.

- [ ] **Step 6: Commit**

```bash
git add api/tests/integration/conftest.py api/tests/integration/test_llm_explainer_wiring.py
git commit -m "test(api): patched_match_explainer fixture + score worker wiring test"
```

---

## Task 8: Documentation + `.env.example`

**Files:**
- Modify: `api/.env.example` (append a `# --- Match explainer ---` block before or after the scoring block)
- Modify: `api/CLAUDE.md` (update the "Match explanations (templated)" section under "Architecture — non-obvious bits")

- [ ] **Step 1: Document new env vars in `api/.env.example`**

Append to `api/.env.example` (after the existing scoring block at the bottom):

```
# --- Match explainer ---
# 'templated' (default; deterministic, no network) or 'llm' (Gemini text-gen).
KPA_MATCH_EXPLAINER=templated
# Gemini text model used when KPA_MATCH_EXPLAINER=llm. Ignored otherwise.
KPA_MATCH_EXPLAINER_MODEL=gemini-2.5-flash
```

- [ ] **Step 2: Update `api/CLAUDE.md`**

In `api/CLAUDE.md`, locate the `### Match explanations (templated)` section (under "Architecture — non-obvious bits"). Update it to reflect the now-shipped LLM provider:

Replace the existing section heading and body with:

```markdown
### Match explanations (templated + llm)

- **`matches.explanation` is JSONB** with shape `{fit, caveat, generator, generator_version}`. Nullable for backward compat with pre-P2.4 rows. Generated inline in both score workers' compute step (no separate worker).
- **`kpa.scoring.explainer.MatchExplainer` Protocol** routes between two impls. Workers call `await get_match_explainer().explain(ctx)`; the call site does not change between templated and LLM.
- **`TemplatedExplainer`** (`kpa/scoring/explainer.py`) — wraps the pure-function `templated_explanation(...)` from `kpa/scoring/explain.py`. Deterministic, no network. `generator="templated"`.
- **`GeminiMatchExplainer`** (`kpa/scoring/llm_explainer.py`) — uses `google.genai` to call the configured Gemini text model. Surfaced-only LLM call: if `ctx.total < ctx.threshold`, returns the templated explanation without calling Gemini. Any failure (provider exception, empty response, malformed JSON, non-dict JSON) logs `explain.llm-failed` (warning, `exc_info=True`) and falls back to templated. `explain()` **never raises** — scoring is never failed or retried by the explainer.
- **Selection via env.** `KPA_MATCH_EXPLAINER` is `"templated"` (default) or `"llm"`. `KPA_MATCH_EXPLAINER_MODEL` (default `"gemini-2.5-flash"`) is read only when the LLM branch is selected. `get_match_explainer()` in `celery_app.py` is the lazy-singleton factory (mirrors `get_embedding_provider` / `get_email_channel`).
- **`kpa/scoring/explainer.py` does NOT import `google.genai`.** The LLM impl lives in a separate module so the templated path never pays the genai import cost (mirrors the embeddings package's `__init__` not re-exporting `GeminiEmbeddingProvider`). The factory's LLM branch does `from google import genai` lazily.
- **Three modules need patching to intercept `get_match_explainer`** in tests (mirrors `get_embedding_provider`): `celery_app`, `score_applicant`, `score_job`. The integration conftest's `patched_match_explainer` fixture patches all three plus the `_match_explainer` cache.
- **The score worker's Txn 1 already loads `Employer.name`** alongside `Job` + `JobEmbedding` (added when the templated explainer first shipped). The LLM impl uses the same context.
- **`GENERATOR_VERSION` bumps when the templates or LLM prompt change semantically.** Reviewers should flag template/prompt edits as version-bump candidates. `LLM_GENERATOR_VERSION = "1"` is the initial release.
- **First text-gen call in the repo.** If the `google-genai` 1.x structured-output API changes shape, only `kpa/scoring/llm_explainer.py` needs to change; the Protocol, the factory, and the workers are insulated.
```

- [ ] **Step 3: Run the full test suite once to confirm everything is green before the docs commit**

```bash
cd api && uv run pytest tests/unit -v
cd api && uv run pytest tests/integration -v -m integration -k "score or embed or explain or settings or wiring"
```

Expected: all PASS.

- [ ] **Step 4: Lint + format check (full module sanity)**

```bash
cd api && uv run ruff check src/ tests/
cd api && uv run ruff format --check src/ tests/
cd api && uv run mypy
```

Expected: clean.

- [ ] **Step 5: Commit**

```bash
git add api/.env.example api/CLAUDE.md
git commit -m "docs(api): document KPA_MATCH_EXPLAINER + MatchExplainer architecture"
```

---

## Self-review summary

**Spec coverage:**

- Decision 1 (LLM scope = surfaced matches only) → Task 3 Step 3 surfaced-gate in `GeminiMatchExplainer.explain`, asserted by `test_below_threshold_skips_gemini_and_returns_templated`.
- Decision 2 (failure = fall back to templated, never raise) → Task 3 Step 3 broad `except Exception`, asserted by `test_gemini_raises_falls_back_to_templated`, `test_invalid_json_response_falls_back_to_templated`, `test_empty_response_text_falls_back_to_templated`, `test_non_dict_json_falls_back_to_templated`.
- `ExplainContext` (13 fields) → Task 2 Step 3.
- `MatchExplainer` Protocol → Task 2 Step 3.
- `TemplatedExplainer` wraps `templated_explanation` → Task 2 Step 3, asserted by `test_templated_explainer_matches_pure_function`.
- `GeminiMatchExplainer` with injectable client → Task 3 Step 3, used by all 7 unit tests.
- `get_match_explainer()` factory → Task 4.
- Both workers use the factory → Tasks 5 + 6.
- Config (`match_explainer`, `match_explainer_model` + validator) → Task 1.
- No migration → no task (called out explicitly).
- Unit tests (templated, llm, settings) → Tasks 1, 2, 3.
- `patched_match_explainer` fixture + integration wiring test → Task 7.

**Placeholder scan:** none. Every step shows the exact code, the exact command, and the expected output.

**Type consistency:** `ExplainContext`'s 13 fields match `templated_explanation`'s 13 keyword args exactly (cross-checked against `api/src/kpa/scoring/explain.py:22-37`). `MatchExplainer.explain(ctx)` signature is identical in the Protocol, `TemplatedExplainer`, `GeminiMatchExplainer`, and `FakeMatchExplainer`. The score-job worker uses `job_employer_name` (its local variable), not `employer_name`, in Task 6 (cross-checked against `api/src/kpa/workers/tasks/score_job.py:125`).
