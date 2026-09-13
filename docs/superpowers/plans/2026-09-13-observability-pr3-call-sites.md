# Observability PR 3 — Call Sites, External Calls, Task Signals Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every error path in the backend is logged with enough context to act on (without leaking PII), every external call has latency/outcome telemetry, every Celery task run is counted and timed, and a lint rule stops new blind `except Exception` blocks.

**Architecture:** A `observe_external_call(service, operation)` context manager in `core` times, counts and logs each Gemini / SES / S3 / Google-JWKS call. Celery `task_prerun`/`task_postrun`/`task_failure`/`task_retry` receivers in `jobify_worker/observability.py` bind task context (with token-based reset, so eager tasks inside a request don't wipe request context) and record `jobify_task_runs_total` + duration. The ~20 silent or traceback-losing `except` blocks found by the survey are fixed one by one, and ruff `BLE001` is enabled with a written reason on every remaining suppression.

**Tech Stack:** Python 3.12, structlog 24.4, prometheus-client 0.26, Celery 5.6, google-genai 1.75, boto3, httpx, FastAPI 0.115, pytest.

**Spec:** `docs/superpowers/specs/2026-09-13-backend-observability-foundation-design.md` ("Call-site remediation", "Worker — Task signals", "Rollout → PR 3").

## Global Constraints

- **Log shapes, never values.** No query strings, raw paths, bodies, tokens, emails, resume text, model output, or validation inputs in log fields.
- **Tracebacks vs. provider messages (rule for this PR):** an unexpected exception from *our own code or infrastructure* (DB, broker, storage) logs with a traceback (`_log.exception(...)` / `exc_info=`). An exception whose *message can carry request or user content* — provider API errors (SES, Gemini client/validation errors) and anything chained to a pydantic `ValidationError` over resume data — logs `error_type` (+ `http_status` when known) **without** `exc_info`, because the rendered traceback includes the message and its chained causes. Email scrubbing is a safety net, not a licence.
- **Every external call site uses `observe_external_call`** with literal `service`/`operation` strings from this closed set: `("gemini", "embed")`, `("gemini", "parse_resume")`, `("gemini", "explain_match")`, `("ses", "send_email")`, `("s3", "put_object")`, `("s3", "get_object")`, `("s3", "delete_object")`, `("google", "jwks_fetch")`.
- **Metric names/labels (verbatim from spec):** `jobify_external_calls_total{service,operation,outcome}` (counter), `jobify_external_call_duration_seconds{service,operation}` (histogram), `jobify_task_runs_total{task,outcome}` (counter), `jobify_task_duration_seconds{task}` (histogram). `outcome ∈ {success, error, retry, failure}`. Declared only in `core/src/jobify/observability/metrics.py`.
- **Task args/kwargs are never logged.**
- **Celery signals fire for eager tasks too** (verified in `celery/app/trace.py`): task receivers must restore the context they bound (`bind_contextvars` tokens → `reset_contextvars`), never `clear_contextvars()`.
- **Celery's `celery.app.trace` ERROR line is the canonical task-failure traceback** (already structured + redacted since PR 1); `task.failed` carries task context and `error_type`, not a second traceback.
- **ruff:** `BLE` is added to `[tool.ruff.lint] select` in **Task 1** (not Task 6): `RUF` is selected, so `RUF100` rejects a `# noqa: BLE001` while BLE is not enabled — every later task's lint gate depends on this ordering. Do NOT add `TRY400` — ruff cannot recognise structlog `_log` objects as loggers, so it would report nothing (documented in `core/CLAUDE.md`).
- **`# noqa: BLE001` only where BLE001 actually fires.** BLE001 does not flag a handler that re-raises (`raise`/`raise X from exc`), and `RUF100` flags an unused directive — so no noqa on re-raising arms, and when you narrow `except Exception` to specific types, delete the noqa on that line. Every suppression reads `# noqa: BLE001 — <why this boundary catches everything>`.
- Tests that assert on redaction/format use the real `configure_logging` chain + `capsys` (`tests/logging_helpers.py`); plain "event was logged with these fields" assertions may use `structlog.testing.capture_logs()`. Metric assertions are deltas via `REGISTRY.get_sample_value`.
- structlog only in `src`; modules without a logger get `import structlog` + `_log = structlog.get_logger(__name__)`.
- All commands from repo root; CI gate verbatim: `uv run ruff check core/src api/src worker/src tests` · `uv run ruff format --check core/src api/src worker/src tests` · `uv run mypy` · `uv run pytest -v -m "not integration and not eval"` · `uv run pytest -v -s -m eval` · `uv run pytest -v -m integration`.
- Commit trailer on every commit:
  ```
  Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01JSP8DPirBJicB72XTMVq3o
  ```
- Branch: `feat/observability-call-sites` off latest `origin/main` **after PR 2 has merged** (needs `jobify.observability.metrics`).

## File Structure

| File | Status | Responsibility |
|---|---|---|
| `core/src/jobify/observability/metrics.py` | modify | declare external-call + task metrics |
| `core/src/jobify/observability/external.py` | create | `observe_external_call`, `http_status_of` |
| `core/src/jobify/db/errors.py` | create | `constraint_name(IntegrityError) -> str \| None` |
| `core/src/jobify/observability/logging.py` | modify | pin noisy third-party loggers to WARNING |
| `core/src/jobify/integrations/embeddings/gemini.py` | modify | wrap `embed_content` |
| `core/src/jobify/integrations/parser/llm_parser.py` | modify | wrap `generate_content`; status in error; shape log WARNING |
| `core/src/jobify/integrations/parser/fallback.py` | modify | re-raise `TransientParserError`; shape-only degrade log |
| `core/src/jobify/integrations/parser/library.py` | modify | log `no_text_extracted` |
| `core/src/jobify/scoring/llm_explainer.py` | modify | wrap call only; drop `raw_text` log |
| `core/src/jobify/integrations/notifications/ses.py` | modify | wrap send; error_type-only result |
| `core/src/jobify/integrations/storage/s3.py` | modify | wrap put/get/delete |
| `api/src/jobify_api/auth/google_verifier.py` | modify | wrap JWKS fetch; token-rejection log |
| `api/src/jobify_api/routes/auth.py`, `routes/ready.py` | modify | log dependency failures |
| `api/src/jobify_api/employers/team_service.py`, `routes/invites.py`, `routes/employers/core.py` | modify | conflict logs via `constraint_name` |
| `api/src/jobify_api/middleware/error_handler.py` | modify | cap validation `loc` part length |
| `api/src/jobify_api/scripts/seed_jobs.py`, `scripts/grant_admin.py` | modify | tracebacks; no email in logs |
| `worker/src/jobify_worker/observability.py` | modify | task signal receivers |
| `worker/src/jobify_worker/tasks/embed.py`, `embed_job.py`, `sweep_outbox.py`, `sweep_notifications.py` | modify | error context |
| `pyproject.toml` | modify | ruff `BLE001` |
| `core/CLAUDE.md`, `api/CLAUDE.md`, `worker/CLAUDE.md` | modify | invariants |
| tests (per task) | create/modify | see tasks |

---

### Task 1: External-call helper + metrics declarations

**Files:**
- Modify: `core/src/jobify/observability/metrics.py` (append declarations)
- Create: `core/src/jobify/observability/external.py`
- Create: `tests/unit/test_observe_external_call.py`
- Modify: `pyproject.toml` (`[tool.ruff.lint] select` += `"BLE"`) and the 11 current BLE001 sites (reason comments only — no behavior change)

**Interfaces:**
- Consumes: PR 2's `jobify.observability.metrics` module.
- Produces:
  - `EXTERNAL_CALLS: Counter` labels `("service", "operation", "outcome")`; `EXTERNAL_CALL_DURATION: Histogram` labels `("service", "operation")`; `TASK_RUNS: Counter` labels `("task", "outcome")`; `TASK_DURATION: Histogram` labels `("task",)` — all in `jobify.observability.metrics`.
  - `jobify.observability.external.observe_external_call(service: str, operation: str, *, log_traceback: bool = True) -> Iterator[None]` (a `contextlib.contextmanager`).
  - `jobify.observability.external.http_status_of(exc: BaseException) -> int | None`.

- [ ] **Step 0: Enable BLE001 and annotate existing sites**

In root `pyproject.toml`: `select = ["E", "F", "I", "B", "UP", "N", "S", "RUF", "BLE"]`. Then add a reason comment on each current hit (verified 2026-09-13 on main @ 80bdf6b; confirm with `uv run ruff check core/src api/src worker/src tests --select BLE001 --output-format concise`):

| Site | Comment to append to the `except` line |
|---|---|
| `api/src/jobify_api/routes/metrics.py:44` | `# noqa: BLE001 — scrape must succeed even when the DB is down (reports jobify_async_metrics_up 0)` |
| `api/src/jobify_api/routes/ready.py:35`, `:46` | `# noqa: BLE001 — readiness boundary: any dependency error is a 503, not a 500` |
| `api/src/jobify_api/scripts/seed_jobs.py:316`, `:321` | `# noqa: BLE001 — CLI boundary: any failure maps to an exit code` |
| `core/src/jobify/integrations/notifications/ses.py:78` | `# noqa: BLE001 — channel contract: provider failures become ChannelResult.failed (sweep retries)` |
| `core/src/jobify/integrations/parser/fallback.py:39` | `# noqa: BLE001 — degradation boundary by design` |
| `core/src/jobify/scoring/llm_explainer.py:123` | `# noqa: BLE001 — explain() NEVER raises; any failure degrades to templated` |
| `worker/src/jobify_worker/tasks/sweep_notifications.py:124` | `# noqa: BLE001 — per-row isolation; the lease makes the row recoverable` |
| `worker/src/jobify_worker/tasks/sweep_notifications.py:282` | `# noqa: BLE001 — a channel crash is a failed attempt, retried with backoff` |
| `worker/src/jobify_worker/tasks/sweep_outbox.py:63` | `# noqa: BLE001 — per-event isolation: any failure is recorded on the row and retried` |

If `tests/**` trips BLE001, add `"BLE001"` to the existing `"tests/**" = ["S"]` per-file ignore. If line-length (100) forces it, shorten the reason, never drop it. Expected: `uv run ruff check core/src api/src worker/src tests` clean. Later tasks rewrite some of these arms and keep (or update) the reason next to the new code.

- [ ] **Step 1: Write the failing tests**

`tests/unit/test_observe_external_call.py`:

```python
"""observe_external_call: timing, outcome counter, one log line, never swallows."""

from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest
import structlog
from prometheus_client import REGISTRY
from structlog.testing import capture_logs

from jobify.observability.external import http_status_of, observe_external_call


def _calls(service: str, operation: str, outcome: str) -> float:
    labels = {"service": service, "operation": operation, "outcome": outcome}
    return REGISTRY.get_sample_value("jobify_external_calls_total", labels) or 0.0


def _durations(service: str, operation: str) -> float:
    labels = {"service": service, "operation": operation}
    return REGISTRY.get_sample_value("jobify_external_call_duration_seconds_count", labels) or 0.0


def test_success_counts_times_and_logs_debug() -> None:
    before, before_duration = _calls("t", "ok", "success"), _durations("t", "ok")

    with capture_logs() as logs, observe_external_call("t", "ok"):
        pass

    assert _calls("t", "ok", "success") == before + 1
    assert _durations("t", "ok") == before_duration + 1
    (line,) = [e for e in logs if e["event"] == "external.call"]
    assert line["log_level"] == "debug"
    assert line["service"] == "t" and line["operation"] == "ok" and line["outcome"] == "success"
    assert isinstance(line["duration_ms"], float)


def test_failure_reraises_counts_error_and_logs_warning_with_traceback() -> None:
    before = _calls("t", "boom", "error")

    with capture_logs() as logs, pytest.raises(RuntimeError), observe_external_call("t", "boom"):
        raise RuntimeError("provider down")

    assert _calls("t", "boom", "error") == before + 1
    (line,) = [e for e in logs if e["event"] == "external.call"]
    assert line["log_level"] == "warning"
    assert line["outcome"] == "error"
    assert line["error_type"] == "RuntimeError"
    assert line["exc_info"] is True


def test_log_traceback_false_omits_exc_info() -> None:
    with capture_logs() as logs, pytest.raises(ValueError), observe_external_call(
        "t", "quiet", log_traceback=False
    ):
        raise ValueError("message may carry an address")

    (line,) = [e for e in logs if e["event"] == "external.call"]
    assert "exc_info" not in line
    assert line["error_type"] == "ValueError"


def test_http_status_extracted_into_log() -> None:
    request = httpx.Request("GET", "https://example.test/jwks")
    error = httpx.HTTPStatusError("503", request=request, response=httpx.Response(503, request=request))

    with capture_logs() as logs, pytest.raises(httpx.HTTPStatusError), observe_external_call(
        "t", "status"
    ):
        raise error

    (line,) = [e for e in logs if e["event"] == "external.call"]
    assert line["http_status"] == 503


def test_http_status_of_known_shapes() -> None:
    request = httpx.Request("GET", "https://example.test")
    assert http_status_of(
        httpx.HTTPStatusError("x", request=request, response=httpx.Response(429, request=request))
    ) == 429
    assert http_status_of(SimpleNamespace(code=403)) == 403  # type: ignore[arg-type]  # google-genai APIError shape
    boto_like = RuntimeError("x")
    boto_like.response = {"ResponseMetadata": {"HTTPStatusCode": 400}}  # type: ignore[attr-defined]
    assert http_status_of(boto_like) == 400
    assert http_status_of(RuntimeError("no status")) is None
    assert http_status_of(SimpleNamespace(code="not-an-int")) is None  # type: ignore[arg-type]


def test_base_exceptions_are_not_counted_as_errors() -> None:
    before = _calls("t", "cancel", "error")

    with pytest.raises(KeyboardInterrupt), observe_external_call("t", "cancel"):
        raise KeyboardInterrupt

    assert _calls("t", "cancel", "error") == before
    structlog.contextvars.clear_contextvars()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_observe_external_call.py -v`
Expected: collection ERROR `ModuleNotFoundError: No module named 'jobify.observability.external'`.

- [ ] **Step 3: Declare the metrics**

Append to `core/src/jobify/observability/metrics.py` (after `VALIDATION_FAILURES`):

```python
_EXTERNAL_CALL_BUCKETS: Final[tuple[float, ...]] = (0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30)
_TASK_DURATION_BUCKETS: Final[tuple[float, ...]] = (0.1, 0.5, 1, 5, 10, 30, 60, 120, 300)

EXTERNAL_CALLS: Final[Counter] = Counter(
    "jobify_external_calls",
    "External provider calls by service, operation and outcome (success|error).",
    ("service", "operation", "outcome"),
)
EXTERNAL_CALL_DURATION: Final[Histogram] = Histogram(
    "jobify_external_call_duration_seconds",
    "External provider call duration by service and operation.",
    ("service", "operation"),
    buckets=_EXTERNAL_CALL_BUCKETS,
)
TASK_RUNS: Final[Counter] = Counter(
    "jobify_task_runs",
    "Celery task runs by registered task name and outcome (success|retry|failure|error).",
    ("task", "outcome"),
)
TASK_DURATION: Final[Histogram] = Histogram(
    "jobify_task_duration_seconds",
    "Celery task run duration by registered task name.",
    ("task",),
    buckets=_TASK_DURATION_BUCKETS,
)
```

(Match the existing constants' `Final[...]` annotation style in that file.)

- [ ] **Step 4: Implement the helper**

`core/src/jobify/observability/external.py`:

```python
"""Telemetry for calls to external providers (Gemini, SES, S3, Google JWKS).

    with observe_external_call("gemini", "embed"):
        resp = await client.aio.models.embed_content(...)

Records ``jobify_external_calls_total{service,operation,outcome}`` and
``jobify_external_call_duration_seconds{service,operation}``, and logs one
``external.call`` event: DEBUG on success, WARNING on failure. It NEVER swallows —
the exception propagates unchanged.

``service``/``operation`` must be literal strings from the closed set documented
in core/CLAUDE.md (metric cardinality). Pass ``log_traceback=False`` when the
provider's exception message can carry request/user content (e.g. SES errors
echo recipient addresses): the event then carries ``error_type`` and
``http_status`` only.

BaseExceptions (cancellation, KeyboardInterrupt) propagate without being
counted as provider errors.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from time import perf_counter
from typing import Any

import structlog

from jobify.observability.metrics import EXTERNAL_CALL_DURATION, EXTERNAL_CALLS

_log = structlog.get_logger(__name__)


def http_status_of(exc: BaseException) -> int | None:
    """Best-effort HTTP status from the provider exception shapes we use."""
    response: Any = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)  # httpx.HTTPStatusError
    if isinstance(status, int):
        return status
    if isinstance(response, dict):  # botocore ClientError
        metadata = response.get("ResponseMetadata")
        if isinstance(metadata, dict) and isinstance(metadata.get("HTTPStatusCode"), int):
            return int(metadata["HTTPStatusCode"])
    code = getattr(exc, "code", None)  # google.genai.errors.APIError
    return code if isinstance(code, int) and not isinstance(code, bool) else None


@contextmanager
def observe_external_call(
    service: str, operation: str, *, log_traceback: bool = True
) -> Iterator[None]:
    started_at = perf_counter()
    try:
        yield
    except Exception as exc:
        duration_seconds = max(perf_counter() - started_at, 0.0)
        EXTERNAL_CALLS.labels(service=service, operation=operation, outcome="error").inc()
        EXTERNAL_CALL_DURATION.labels(service=service, operation=operation).observe(
            duration_seconds
        )
        _log.warning(
            "external.call",
            service=service,
            operation=operation,
            outcome="error",
            error_type=type(exc).__name__,
            http_status=http_status_of(exc),
            duration_ms=round(duration_seconds * 1000, 1),
            **({"exc_info": True} if log_traceback else {}),
        )
        raise
    duration_seconds = max(perf_counter() - started_at, 0.0)
    EXTERNAL_CALLS.labels(service=service, operation=operation, outcome="success").inc()
    EXTERNAL_CALL_DURATION.labels(service=service, operation=operation).observe(duration_seconds)
    _log.debug(
        "external.call",
        service=service,
        operation=operation,
        outcome="success",
        duration_ms=round(duration_seconds * 1000, 1),
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_observe_external_call.py tests/unit/test_observability_metrics.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
uv run ruff check core/src api/src worker/src tests && uv run ruff format core/src api/src worker/src tests && uv run mypy
git add pyproject.toml core/src api/src worker/src tests/unit/test_observe_external_call.py
git commit -m "core: observe_external_call helper, external-call/task metrics, ruff BLE001 with reasons

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01JSP8DPirBJicB72XTMVq3o"
```

---

### Task 2: Wrap every external call

**Files:**
- Modify: `core/src/jobify/integrations/embeddings/gemini.py` (`encode`, the `embed_content` try block ~lines 54-68)
- Modify: `core/src/jobify/integrations/parser/llm_parser.py` (`parse_text` ~226-243; the three `_log.debug("parse.llm-output-rejected", ...)` calls ~266/276/284)
- Modify: `core/src/jobify/scoring/llm_explainer.py` (`explain` ~71-127)
- Modify: `core/src/jobify/integrations/notifications/ses.py` (`send` ~47-80)
- Modify: `core/src/jobify/integrations/storage/s3.py` (`save`/`read`/`delete` ~49-66)
- Modify: `api/src/jobify_api/auth/google_verifier.py` (`_refetch_locked` ~148-160)
- Modify tests: `tests/unit/test_gemini_provider.py`, `tests/unit/parser/test_llm_parser.py`, `tests/unit/test_llm_explainer.py`, `tests/unit/test_ses_email_channel.py`, `tests/unit/test_s3_storage.py`, `tests/unit/test_google_verifier.py`

**Interfaces:**
- Consumes: `observe_external_call`, `http_status_of` (Task 1).
- Produces: `LlmParserError` message format for provider failures becomes `"llm_call_failed: <ExceptionType>"` plus `" <code> <status>"` when the exception is a `google.genai.errors.APIError` (e.g. `"llm_call_failed: ClientError 429 RESOURCE_EXHAUSTED"`). SES `ChannelResult.failed` message becomes `"ses:<ExceptionType>"` (+ `":<http_status>"` when known) — no provider text.

Read each target function fully before editing; the line numbers are from a 2026-09-13 survey and may have drifted.

- [ ] **Step 1: Write the failing tests**

Add one test per wrapped call (each asserts the counter delta for its `(service, operation, outcome)`), and update the two tests whose contract changes. Use this helper at the top of each test module that needs it:

```python
from prometheus_client import REGISTRY


def _external_calls(service: str, operation: str, outcome: str) -> float:
    labels = {"service": service, "operation": operation, "outcome": outcome}
    return REGISTRY.get_sample_value("jobify_external_calls_total", labels) or 0.0
```

`tests/unit/test_gemini_provider.py` — add (reuse the module's existing fake-client construction used by `test_5xx_maps_to_transient_error` and the happy-path tests; mirror their setup exactly):

```python
async def test_embed_call_is_observed_on_success() -> None:
    before = _external_calls("gemini", "embed", "success")
    # ... existing happy-path arrange + `await provider.encode(...)` ...
    assert _external_calls("gemini", "embed", "success") == before + 1


async def test_embed_call_is_observed_on_provider_error() -> None:
    before = _external_calls("gemini", "embed", "error")
    # ... existing 5xx arrange; `with pytest.raises(TransientEmbeddingError): await provider.encode(...)` ...
    assert _external_calls("gemini", "embed", "error") == before + 1
```

`tests/unit/parser/test_llm_parser.py` — add:

```python
async def test_provider_api_error_message_keeps_http_status() -> None:
    from google.genai import errors

    # Build the parser exactly like test_provider_exception_wrapped_as_llm_error does,
    # but make generate_content raise a real APIError subclass:
    api_error = errors.ClientError(429, {"error": {"code": 429, "status": "RESOURCE_EXHAUSTED", "message": "quota"}})
    # ... AsyncMock(side_effect=api_error) on client.aio.models.generate_content ...
    before = _external_calls("gemini", "parse_resume", "error")
    with pytest.raises(LlmParserError) as info:
        await parser.parse_text("resume text")
    assert str(info.value) == "llm_call_failed: ClientError 429 RESOURCE_EXHAUSTED"
    assert _external_calls("gemini", "parse_resume", "error") == before + 1
```

(If `errors.ClientError`'s constructor signature differs in the installed google-genai 1.75, construct it the way `tests/unit/test_gemini_provider.py::test_429_maps_to_transient_error` does and keep the asserted message.)

Also add a test that an invalid model response logs `parse.llm-output-rejected` at **warning** (use `capture_logs`, arrange like `test_invalid_json_raises_llm_error`, assert `log_level == "warning"`).

`tests/unit/test_llm_explainer.py` — replace `test_parse_failure_logs_raw_text_snippet` with:

```python
async def test_parse_failure_logs_shape_not_model_text() -> None:
    explainer, gc_mock = _make_explainer()
    gc_mock.return_value = SimpleNamespace(text="Here is the JSON requested:\n")

    with capture_logs() as logs:
        out = await explainer.explain(_ctx())

    assert out["generator"] == "templated"
    (failed,) = [e for e in logs if e.get("event") == "explain.llm-failed"]
    assert "raw_text" not in failed
    assert failed["raw_length"] == len("Here is the JSON requested:\n")
    assert failed["error_type"] == "JSONDecodeError"
    assert all("Here is the JSON" not in str(value) for value in failed.values())
```

and add:

```python
async def test_explain_call_is_observed() -> None:
    explainer, gc_mock = _make_explainer()
    gc_mock.side_effect = RuntimeError("down")
    before = _external_calls("gemini", "explain_match", "error")

    out = await explainer.explain(_ctx())

    assert out["generator"] == "templated"
    assert _external_calls("gemini", "explain_match", "error") == before + 1
```

`tests/unit/test_ses_email_channel.py` — change `test_ses_channel_returns_failure_for_provider_error` to also assert `result.message == "ses:RuntimeError"` and that `"down"` is not in it, and add a success-path counter assertion (`("ses", "send_email", "success")`) to `test_ses_channel_sends_application_email`.

`tests/unit/test_s3_storage.py` — in `test_s3_storage_round_trip_calls_encrypted_object_api`, assert `("s3", "put_object", "success")`, `("s3", "get_object", "success")`, `("s3", "delete_object", "success")` each increased by 1.

`tests/unit/test_google_verifier.py` — in `test_jwks_unavailable_raises`, assert `("google", "jwks_fetch", "error")` increased by 1; in `test_verify_happy_path`, assert `("google", "jwks_fetch", "success")` increased by 1.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_gemini_provider.py tests/unit/parser/test_llm_parser.py tests/unit/test_llm_explainer.py tests/unit/test_ses_email_channel.py tests/unit/test_s3_storage.py tests/unit/test_google_verifier.py -v`
Expected: the new/changed assertions FAIL (counter deltas 0; old message formats; `raw_text` present; debug level).

- [ ] **Step 3: Implement the wraps**

**Gemini embeddings** (`gemini.py`): add `from jobify.observability.external import observe_external_call`; wrap only the provider call inside the existing try, keeping the except arms unchanged:

```python
        try:
            with observe_external_call("gemini", "embed", log_traceback=False):
                resp = await self._client.aio.models.embed_content(
                    model=self._model,
                    contents=content,
                    config=types.EmbedContentConfig(output_dimensionality=self._output_dim),
                )
        except errors.ServerError as exc:
            ...  # existing arms unchanged
```

(`log_traceback=False`: `APIError` messages include the response `details`, which can echo request content.)

**LLM parser** (`llm_parser.py`): add `from google.genai import errors` and the observe import. In `parse_text`:

```python
        try:
            with observe_external_call("gemini", "parse_resume", log_traceback=False):
                resp = await self._client.aio.models.generate_content(
                    model=self._model,
                    contents=text,
                    config=_generate_content_config(self._model),
                )
        except Exception as exc:  # re-raises, so BLE001 doesn't fire — no noqa (RUF100)
            # Degradation contract: ANY provider failure → LlmParserError (fallback parser takes over).
            detail = type(exc).__name__
            if isinstance(exc, errors.APIError):
                # code/status only — never exc.details/message (can echo the prompt).
                detail = f"{detail} {exc.code} {exc.status}"
            raise LlmParserError(f"llm_call_failed: {detail}") from exc
```

Change the three `_log.debug("parse.llm-output-rejected", **_raw_shape(raw))` calls to `_log.warning(...)` (same arguments — `_raw_shape` is already shape-only).

**LLM explainer** (`llm_explainer.py`): add the observe import; wrap only the `generate_content` await (inside the existing try) in `with observe_external_call("gemini", "explain_match", log_traceback=False):`. Replace the final except arm:

```python
        except Exception as exc:  # noqa: BLE001 — explain() NEVER raises; any failure degrades to templated
            # Shape only: the model's raw output can restate the applicant's
            # profile, and provider errors can echo the prompt (core/CLAUDE.md).
            _log.warning(
                "explain.llm-failed",
                error_type=type(exc).__name__,
                raw_length=len(text) if text is not None else None,
            )
            return _templated_from_ctx(ctx)
```

**SES** (`ses.py`): add `import structlog`? — not needed (the helper logs). Add the observe + `http_status_of` imports. Wrap the `await asyncio.to_thread(self._client.send_email, ...)` in `with observe_external_call("ses", "send_email", log_traceback=False):` and replace the except arm:

```python
        except Exception as exc:  # noqa: BLE001 — channel contract: provider failures become ChannelResult.failed (sweep retries)
            # Type + status only: SES error text can contain recipient addresses,
            # and this message is persisted to notifications.last_error.
            status = http_status_of(exc)
            suffix = f":{status}" if status is not None else ""
            return ChannelResult.failed(f"ses:{type(exc).__name__}{suffix}")
```

**S3** (`s3.py`): add the observe import; wrap each `asyncio.to_thread` call:

```python
    async def save(self, *, key: str, content: bytes, content_type: str) -> None:
        with observe_external_call("s3", "put_object"):
            await asyncio.to_thread(
                self._client.put_object,
                Bucket=self._bucket,
                Key=self._key(key),
                Body=content,
                ContentType=content_type,
                ServerSideEncryption="AES256",
            )

    async def read(self, key: str) -> bytes:
        with observe_external_call("s3", "get_object"):
            response = await asyncio.to_thread(
                self._client.get_object, Bucket=self._bucket, Key=self._key(key)
            )
            return await asyncio.to_thread(response["Body"].read)

    async def delete(self, key: str) -> None:
        with observe_external_call("s3", "delete_object"):
            await asyncio.to_thread(
                self._client.delete_object, Bucket=self._bucket, Key=self._key(key)
            )
```

(Tracebacks allowed: botocore errors for our own bucket carry bucket/key names — storage keys are opaque ids, not PII.)

**JWKS** (`google_verifier.py`): add the observe import; in `_refetch_locked`:

```python
        try:
            with observe_external_call("google", "jwks_fetch"):
                async with self._http_factory() as client:
                    resp = await client.get(self._jwks_url)
                    resp.raise_for_status()
                    body = resp.json()
        except (httpx.HTTPError, ValueError):
            # external.call (WARNING, with traceback) already recorded the failure.
            _log.warning("jwks-fetch-failed", serving_stale=bool(self._cache_keys))
            if self._cache_keys:
                # Serve stale on transient failure.
                return
            raise GoogleJwksUnavailableError() from None
```

This arm is a narrowed catch (no BLE001, no noqa). Keep `from exc`-style chaining if the original code used it: replace `from None` with binding `as exc` + `from exc` if the existing tests or type checks rely on `__cause__` (check `test_jwks_unavailable_raises`).

- [ ] **Step 4: Run tests to verify they pass**

Run the Step 2 command. Expected: all PASS. Then `uv run pytest -q -m "not integration and not eval"` and `uv run pytest -q -m integration` (the parse/embed/sweep integration tests exercise these providers through fakes).

- [ ] **Step 5: Commit**

```bash
uv run ruff check core/src api/src tests && uv run ruff format core/src api/src tests && uv run mypy
git add core/src/jobify/integrations core/src/jobify/scoring/llm_explainer.py api/src/jobify_api/auth/google_verifier.py tests/unit
git commit -m "core/api: observe every external provider call; stop logging model output and provider text

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01JSP8DPirBJicB72XTMVq3o"
```

---

### Task 3: Celery task signal receivers

**Files:**
- Modify: `worker/src/jobify_worker/observability.py`
- Create: `tests/unit/worker/test_task_signals.py`
- Modify: `worker/CLAUDE.md` ("## Worker runtime" bullets)

**Interfaces:**
- Consumes: `TASK_RUNS`, `TASK_DURATION` (Task 1).
- Produces receivers `bind_task_context` (`task_prerun`), `record_task_run` (`task_postrun`), `log_task_retry` (`task_retry`), `log_task_failure` (`task_failure`) in `jobify_worker.observability`.

- [ ] **Step 1: Write the failing tests**

`tests/unit/worker/test_task_signals.py`:

```python
"""Task lifecycle receivers, driven by sending the Celery signals directly."""

from __future__ import annotations

from types import SimpleNamespace

import structlog
from celery.signals import task_failure, task_postrun, task_prerun, task_retry
from prometheus_client import REGISTRY
from structlog.testing import capture_logs

import jobify_worker.observability  # noqa: F401  (connects the receivers)

_TASK = SimpleNamespace(name="jobify.test_task", request=SimpleNamespace(retries=2))


def _runs(outcome: str) -> float:
    return REGISTRY.get_sample_value(
        "jobify_task_runs_total", {"task": "jobify.test_task", "outcome": outcome}
    ) or 0.0


def _durations() -> float:
    return REGISTRY.get_sample_value(
        "jobify_task_duration_seconds_count", {"task": "jobify.test_task"}
    ) or 0.0


def _run(state: str, *, task_id: str = "t-1") -> None:
    task_prerun.send(sender=_TASK, task_id=task_id, task=_TASK, args=("secret-arg",), kwargs={})
    task_postrun.send(
        sender=_TASK, task_id=task_id, task=_TASK, args=("secret-arg",), kwargs={},
        retval=None, state=state,
    )


def test_prerun_binds_task_context_and_postrun_restores_outer_context() -> None:
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id="outer-request")
    seen: dict[str, object] = {}

    task_prerun.send(sender=_TASK, task_id="t-ctx", task=_TASK, args=(), kwargs={})
    seen.update(structlog.contextvars.get_contextvars())
    task_postrun.send(
        sender=_TASK, task_id="t-ctx", task=_TASK, args=(), kwargs={}, retval=None, state="SUCCESS"
    )

    assert seen["task_id"] == "t-ctx"
    assert seen["task_name"] == "jobify.test_task"
    assert seen["task_retries"] == 2
    assert seen["request_id"] == "outer-request"
    after = structlog.contextvars.get_contextvars()
    assert after == {"request_id": "outer-request"}  # eager task inside a request: context restored
    structlog.contextvars.clear_contextvars()


def test_postrun_records_outcome_and_duration_per_state() -> None:
    for state, outcome in (("SUCCESS", "success"), ("RETRY", "retry"), ("FAILURE", "failure"), ("REVOKED", "error")):
        before, before_duration = _runs(outcome), _durations()
        _run(state, task_id=f"t-{state}")
        assert _runs(outcome) == before + 1, state
        assert _durations() == before_duration + 1, state


def test_postrun_without_prerun_still_counts() -> None:
    before = _runs("success")
    task_postrun.send(
        sender=_TASK, task_id="never-started", task=_TASK, args=(), kwargs={}, retval=None, state="SUCCESS"
    )
    assert _runs("success") == before + 1


def test_retry_logs_warning_with_error_type_and_no_args() -> None:
    request = SimpleNamespace(id="t-r", task="jobify.test_task", retries=1, args=("secret-arg",))
    with capture_logs() as logs:
        task_retry.send(sender=_TASK, request=request, reason=TimeoutError("slow"), einfo=None)

    (line,) = [e for e in logs if e["event"] == "task.retry"]
    assert line["log_level"] == "warning"
    assert line["task_name"] == "jobify.test_task"
    assert line["error_type"] == "TimeoutError"
    assert "secret-arg" not in repr(line)


def test_failure_logs_error_without_second_traceback_or_args() -> None:
    with capture_logs() as logs:
        task_failure.send(
            sender=_TASK, task_id="t-f", exception=ValueError("bad"), args=("secret-arg",),
            kwargs={}, traceback=None, einfo=None,
        )

    (line,) = [e for e in logs if e["event"] == "task.failed"]
    assert line["log_level"] == "error"
    assert line["task_name"] == "jobify.test_task"
    assert line["task_id"] == "t-f"
    assert line["error_type"] == "ValueError"
    assert "exc_info" not in line
    assert "secret-arg" not in repr(line)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/worker/test_task_signals.py -v`
Expected: FAIL — no `task_id` in context (KeyError), counters unchanged, no `task.retry`/`task.failed` events.

- [ ] **Step 3: Implement the receivers**

In `worker/src/jobify_worker/observability.py`: extend the `celery.signals` import with `task_failure, task_postrun, task_prerun, task_retry`; add `from time import perf_counter`, `from contextvars import Token`, `from typing import Any`; add `TASK_DURATION, TASK_RUNS` to the metrics import. Add a module-docstring bullet: `- task_prerun/postrun/retry/failure → task context in logs, jobify_task_runs_total + jobify_task_duration_seconds; task args are never logged.` Then append:

```python
# Per-run state keyed by task id. Celery signals also fire for EAGER tasks (tests,
# and any code path that calls .apply()), possibly inside an API request — so
# receivers restore exactly the contextvars they bound instead of clearing.
_TASK_OUTCOMES = {"SUCCESS": "success", "RETRY": "retry", "FAILURE": "failure"}
# An entry leaks only if task_postrun never fires for a started task (hard-killed
# process — which discards this dict anyway); postrun fires on success, retry and failure.
_task_runs: dict[str, tuple[float, dict[str, Token[Any]]]] = {}


@task_prerun.connect  # type: ignore[untyped-decorator]
def bind_task_context(task_id: str, task: Any, **_kwargs: object) -> None:
    tokens = structlog.contextvars.bind_contextvars(
        task_id=task_id,
        task_name=task.name,
        task_retries=getattr(task.request, "retries", 0),
    )
    _task_runs[task_id] = (perf_counter(), dict(tokens))


@task_postrun.connect  # type: ignore[untyped-decorator]
def record_task_run(task_id: str, task: Any, state: str | None = None, **_kwargs: object) -> None:
    started_at, tokens = _task_runs.pop(task_id, (None, {}))
    outcome = _TASK_OUTCOMES.get(state or "", "error")
    TASK_RUNS.labels(task=task.name, outcome=outcome).inc()
    if started_at is not None:
        TASK_DURATION.labels(task=task.name).observe(max(perf_counter() - started_at, 0.0))
    if tokens:
        structlog.contextvars.reset_contextvars(**tokens)


@task_retry.connect  # type: ignore[untyped-decorator]
def log_task_retry(request: Any, reason: object = None, **_kwargs: object) -> None:
    _log.warning(
        "task.retry",
        task_id=getattr(request, "id", None),
        task_name=getattr(request, "task", None),
        retries=getattr(request, "retries", None),
        error_type=type(reason).__name__ if isinstance(reason, BaseException) else None,
    )


@task_failure.connect  # type: ignore[untyped-decorator]
def log_task_failure(
    sender: Any = None, task_id: str | None = None, exception: BaseException | None = None,
    **_kwargs: object,
) -> None:
    # celery.app.trace already logs the canonical ERROR line WITH the traceback
    # (structured + redacted since PR 1); this adds task context, no second copy.
    _log.error(
        "task.failed",
        task_id=task_id,
        task_name=getattr(sender, "name", None),
        error_type=type(exception).__name__ if exception is not None else None,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/worker/ -v` then `uv run pytest -q -m integration` (eager task tests now run the receivers).
Expected: all PASS.

- [ ] **Step 5: Document**

`worker/CLAUDE.md`, append to "## Worker runtime (shared by all tasks)":

```markdown
- **Task lifecycle signals** (`jobify_worker/observability.py`): `task_prerun` binds `task_id`/`task_name`/`task_retries` into log context, `task_postrun` records `jobify_task_runs_total{task,outcome}` (outcome from the final state) + duration and **resets exactly the tokens it bound** — signals fire for eager tasks too, possibly inside an API request, so never `clear_contextvars()` there. `task.failed`/`task.retry` log `error_type` and task context; `celery.app.trace` owns the traceback. Never log task args/kwargs.
```

- [ ] **Step 6: Commit**

```bash
uv run ruff check worker/src tests && uv run ruff format worker/src tests && uv run mypy
git add worker/src/jobify_worker/observability.py tests/unit/worker/test_task_signals.py worker/CLAUDE.md
git commit -m "worker: task lifecycle signals — task log context, run counters and durations

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01JSP8DPirBJicB72XTMVq3o"
```

---

### Task 4: API error paths — dependency failures, token rejections, conflicts, CLIs

**Files:**
- Create: `core/src/jobify/db/errors.py`, `tests/unit/test_db_errors.py`
- Modify: `api/src/jobify_api/routes/auth.py` (`_enforce_auth_limit` ~27-47)
- Modify: `api/src/jobify_api/routes/ready.py` (~21-57)
- Modify: `api/src/jobify_api/auth/google_verifier.py` (`verify` ~82-122)
- Modify: `api/src/jobify_api/employers/team_service.py` (~102-109, ~239-244), `api/src/jobify_api/routes/invites.py` (~182-191), `api/src/jobify_api/routes/employers/core.py` (~64-81)
- Modify: `api/src/jobify_api/middleware/error_handler.py` (`_handle_validation_error` fields)
- Modify: `api/src/jobify_api/scripts/seed_jobs.py` (`main` ~311-325), `api/src/jobify_api/scripts/grant_admin.py` (`main` ~94-116)
- Create/modify tests: `tests/unit/test_auth_rate_limit_unavailable.py`, `tests/unit/test_ready_logging.py`, `tests/unit/test_google_verifier.py`, `tests/integration/test_employer_team.py`, `tests/integration/test_employers_create.py`, `tests/unit/test_error_handler.py`

**Interfaces:**
- Consumes: `tests/logging_helpers.rebind_logging_per_request` / `json_log_lines` (PR 1) where real-chain output matters; `capture_logs` otherwise.
- Produces: `jobify.db.errors.constraint_name(exc: IntegrityError) -> str | None`.

- [ ] **Step 1: Write the failing tests**

`tests/unit/test_db_errors.py`:

```python
from __future__ import annotations

from sqlalchemy.exc import IntegrityError

from jobify.db.errors import constraint_name


class _UniqueViolationError(Exception):
    def __init__(self, constraint: str | None) -> None:
        super().__init__("duplicate key")
        self.constraint_name = constraint


def _wrapped(cause: BaseException | None) -> IntegrityError:
    orig = Exception("adapter error")
    orig.__cause__ = cause
    return IntegrityError("INSERT ...", {}, orig)


def test_constraint_name_walks_asyncpg_cause_chain() -> None:
    assert constraint_name(_wrapped(_UniqueViolationError("ix_employers_name_norm_live"))) == (
        "ix_employers_name_norm_live"
    )


def test_constraint_name_none_when_unknown() -> None:
    assert constraint_name(_wrapped(None)) is None
    assert constraint_name(_wrapped(_UniqueViolationError(None))) is None
```

`tests/unit/test_auth_rate_limit_unavailable.py`:

```python
"""A rate-limiter backend outage (Redis down) is logged, not just turned into a 503."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from structlog.testing import capture_logs

from jobify_api.app_factory import create_app


class _BrokenLimiter:
    async def hit(self, **_kwargs: object) -> None:
        raise ConnectionError("redis unavailable")


def test_rate_limiter_outage_logs_and_returns_503(monkeypatch: pytest.MonkeyPatch) -> None:
    app = create_app()
    app.state.rate_limiter = _BrokenLimiter()

    with TestClient(app) as client, capture_logs() as logs:
        response = client.post("/v1/auth/oauth/google", json={"id_token": "x"})

    assert response.status_code == 503
    (line,) = [e for e in logs if e["event"] == "auth.rate-limiter-unavailable"]
    assert line["log_level"] == "error"
    assert line["scope"] == "google"
    assert line["exc_info"] is True
```

`tests/unit/test_ready_logging.py`:

```python
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from structlog.testing import capture_logs

from jobify_api.app_factory import create_app


class _DownRedis:
    async def ping(self) -> None:
        raise ConnectionError("redis down")

    async def aclose(self) -> None:
        return None


def test_ready_logs_each_failed_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JOBIFY_DB_URL", "postgresql+asyncpg://u:p@127.0.0.1:1/d")
    app = create_app()
    app.state.redis = _DownRedis()

    with TestClient(app) as client, capture_logs() as logs:
        response = client.get("/ready")

    assert response.status_code == 503
    failed = {e["dependency"]: e for e in logs if e["event"] == "ready.dependency-failed"}
    assert set(failed) == {"db", "redis"}
    assert failed["redis"]["error_type"] == "ConnectionError"
    assert all(e["log_level"] == "warning" for e in failed.values())
```

`tests/unit/test_google_verifier.py` — add (reuse the module's token/JWKS builders from `test_verify_rejects_wrong_iss` / `test_verify_rejects_unknown_kid`):

```python
async def test_rejected_token_logs_reason_without_token() -> None:
    # ... arrange exactly like test_verify_rejects_wrong_iss ...
    with capture_logs() as logs, pytest.raises(InvalidGoogleTokenError):
        await verifier.verify(token)
    (line,) = [e for e in logs if e["event"] == "google.id-token-rejected"]
    assert line["reason"] == "issuer_invalid"
    assert token not in repr(line)
```

`tests/integration/test_employers_create.py` — in `test_create_employer_duplicate_name_returns_409`, wrap the duplicate request in `capture_logs()` and assert one `employer.create-conflict` event with `constraint == "ix_employers_name_norm_live"`.

`tests/integration/test_employer_team.py` — in `test_create_invite_duplicate_pending_409`, likewise assert one `team.invite-conflict` event (the `constraint` value is whatever `constraint_name` returns for the pending-invite unique index — assert it is a non-empty string).

`tests/unit/test_error_handler.py` — add a deterministic test: build a small local app in the test (mirror how the module's `json_app` fixture builds its app, including `rebind_logging_per_request`) with a NEW local model `class _Strict(BaseModel): model_config = ConfigDict(extra="forbid"); count: int` and a `POST /strict` route taking it (do not modify the shared `_Body`). Post `{"count": 1, "k" * 500: 1}`, then assert: exactly one `http.validation-failed` line; its `fields` contains an `extra_forbidden` entry; every `.`-separated `loc` part in it has `len(part) <= 64`; and the long part ends with `"…"`. No conditional asserts.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_db_errors.py tests/unit/test_auth_rate_limit_unavailable.py tests/unit/test_ready_logging.py tests/unit/test_google_verifier.py tests/unit/test_error_handler.py -v` and `uv run pytest tests/integration/test_employers_create.py tests/integration/test_employer_team.py -v`
Expected: new tests FAIL (import error / missing events / uncapped loc).

- [ ] **Step 3: Implement**

`core/src/jobify/db/errors.py`:

```python
"""Helpers for classifying DB errors without logging their text.

``IntegrityError`` text includes the violating row's values (e.g.
``Key (email)=(...)``) — log the constraint NAME, never the message.
"""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError


def constraint_name(exc: IntegrityError) -> str | None:
    """The violated constraint's name from asyncpg's cause chain, if present.

    SQLAlchemy wraps the adapter exception (``exc.orig``); asyncpg's
    ``UniqueViolationError`` (which carries ``constraint_name``) is at
    ``exc.orig.__cause__``.
    """
    orig = getattr(exc, "orig", None)
    for candidate in (getattr(orig, "__cause__", None), orig):
        name = getattr(candidate, "constraint_name", None)
        if isinstance(name, str) and name:
            return name
    return None
```

`routes/auth.py`: add `import structlog` + `_log = structlog.get_logger(__name__)`; in the second except arm:

```python
    except Exception as exc:  # re-raises as 503, so BLE001 doesn't fire — no noqa (RUF100)
        # Any limiter backend failure fails closed with 503.
        # The key embeds the client address + identity: log the scope only.
        _log.exception("auth.rate-limiter-unavailable", scope=scope)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="rate_limiter_unavailable",
        ) from exc
```

`routes/ready.py`: add the logger; in each failing arm add
`_log.warning("ready.dependency-failed", dependency="db", error_type=type(exc).__name__)` (and `dependency="redis"` for the Redis arm), (the two blind arms already carry `# noqa: BLE001 — readiness boundary…` from Task 1). No traceback: probes fire every few seconds while a dependency is down.

`auth/google_verifier.py` (`verify`): before each `raise InvalidGoogleTokenError()` add `_log.warning("google.id-token-rejected", reason=<slug>)` with slugs: header unparsable → `"header_invalid"`; no kid → `"kid_missing"`; key not found → `"kid_unknown"`; `pyjwt.decode` error → `"signature_or_claims_invalid"` plus `error_type=type(exc).__name__`; bad iss → `"issuer_invalid"`; missing email → `"email_missing"`; bad aud → `"audience_invalid"`. Never log the token or claims.

Conflicts — import `from jobify.db.errors import constraint_name` and log before each 409 raise:
- `team_service.add_member`: `_log.info("team.member-add-conflict", employer_id=str(employer_id), constraint=constraint_name(exc))`
- `team_service.create_invite`: `_log.info("team.invite-conflict", employer_id=str(employer_id), constraint=constraint_name(exc))`
- `routes/invites.accept_invite`: `_log.info("invite.accept-conflict", invite_id=str(invite.id), constraint=constraint_name(e))`
- `routes/employers/core.create_employer`: replace the inline cause-walk with `name = constraint_name(e)`; `if name == "ix_employers_name_norm_live": _log.info("employer.create-conflict", constraint=name); ...409`; keep the bare `raise` for any other constraint. (Use the function's existing variable names for employer/invite ids; read the function first.)

`middleware/error_handler.py`: add a module constant `_MAX_LOC_PART_CHARS: Final = 64` and a helper, and use it in the `fields` comprehension:

```python
def _loc_part(part: object) -> str:
    # extra="forbid" models put the CLIENT's unknown key name in loc — bound it.
    text = str(part)
    return text if len(text) <= _MAX_LOC_PART_CHARS else text[: _MAX_LOC_PART_CHARS - 1] + "…"
```

`{"loc": ".".join(_loc_part(part) for part in error["loc"]), "type": error["type"]}`

`scripts/seed_jobs.py` `main`: replace `_log.error("seed.validation-failed", error=str(exc))` with `_log.exception("seed.validation-failed")` and `_log.error("seed.db-failed", error=str(exc))` with `_log.exception("seed.db-failed")`; drop the now-unused `as exc` bindings; keep the Task 1 `# noqa: BLE001 — CLI boundary…` comments.

`scripts/grant_admin.py` `main`: remove `email=email` from all three log calls; the not-found call becomes `_log.error("grant-admin.user-not-found")` (the operator typed the email; the exit code + event are enough).

- [ ] **Step 4: Run tests to verify they pass**

Run the Step 2 commands. Expected: all PASS. Then full unit + integration suites.

- [ ] **Step 5: Document**

`api/CLAUDE.md` "## Error handling" paragraph — append: `Validation log \`loc\` parts are capped at 64 chars (\`extra="forbid"\` echoes the client's key names). Dependency/infra failures that map to a status code still log (\`auth.rate-limiter-unavailable\`, \`ready.dependency-failed\`); 409s from IntegrityError log the constraint name via \`jobify.db.errors.constraint_name\`, never the error text.`

- [ ] **Step 6: Commit**

```bash
uv run ruff check core/src api/src tests && uv run ruff format core/src api/src tests && uv run mypy
git add core/src/jobify/db/errors.py api/src/jobify_api tests/unit tests/integration api/CLAUDE.md
git commit -m "api: log dependency outages, token rejections and 409 conflicts; no emails in CLI logs

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01JSP8DPirBJicB72XTMVq3o"
```

---

### Task 5: Parser + worker error paths

**Files:**
- Modify: `core/src/jobify/integrations/parser/fallback.py` (`parse` ~31-41)
- Modify: `core/src/jobify/integrations/parser/library.py` (`parse` ~66-78)
- Modify: `worker/src/jobify_worker/tasks/embed.py` (~115-120), `embed_job.py` (~109-114)
- Modify: `worker/src/jobify_worker/tasks/sweep_outbox.py` (`_record_failure` ~163-187, batch loop ~62-63)
- Modify: `worker/src/jobify_worker/tasks/sweep_notifications.py` (~124, ~272-326)
- Modify tests: `tests/unit/parser/test_fallback_parser.py`, `tests/unit/test_parser_library.py`, `tests/integration/test_embed_job_worker.py`, `tests/integration/test_sweep_outbox.py`, `tests/integration/test_sweep_notifications.py`, `tests/unit/test_logging_email_channel.py`

**Interfaces:**
- Consumes: `http_status_of` (Task 1); real-chain helpers from `tests/logging_helpers.py`.
- Produces: `FallbackResumeParser.parse` re-raises `TransientParserError` (Celery retry) instead of degrading.

- [ ] **Step 1: Write the failing tests**

`tests/unit/parser/test_fallback_parser.py` — add (build primary/fallback fakes the way the existing tests do):

```python
async def test_transient_extraction_error_propagates_for_retry() -> None:
    # primary.parse raises TransientParserError("storage hiccup"); fallback must NOT be called
    ...
    with pytest.raises(TransientParserError):
        await parser.parse(content=b"x", content_type="application/pdf")
    assert fallback_called is False


async def test_llm_degrade_logs_class_without_message_or_traceback() -> None:
    # primary.parse raises LlmParserError("llm_output_invalid: validation failed on ['name']")
    ...
    with capture_logs() as logs:
        await parser.parse(content=b"x", content_type="application/pdf")
    (line,) = [e for e in logs if e["event"] == "parse.llm-failed"]
    assert line["error_class"] == "LlmParserError"
    assert line["reason"] == "llm_output_invalid: validation failed on ['name']"
    assert "exc_info" not in line


async def test_unexpected_degrade_logs_class_only() -> None:
    # primary.parse raises RuntimeError("contains alice@example.com and resume text")
    ...
    (line,) = [e for e in logs if e["event"] == "parse.llm-failed"]
    assert line["error_class"] == "RuntimeError"
    assert "reason" not in line and "exc_info" not in line
```

`tests/unit/test_parser_library.py` — in `test_parse_empty_resume_returns_valid_parsed_resume`, wrap the call in `capture_logs()` and assert one `parse.no-text-extracted` warning with `content_type` set.

`tests/integration/test_embed_job_worker.py` — in `test_embed_job_permanent_error_does_not_retry`, wrap the call in `capture_logs()` and assert one `embed.job-permanent-failure` event with `error_type` equal to the fake's exception class name, and no `error` key (provider text).

`tests/integration/test_sweep_outbox.py` — in `test_record_failure_schedules_retry_with_backoff`, wrap `_record_failure(...)` in `capture_logs()` and assert the `outbox.event-failed` event has `task_name` (from the seeded event's payload, or `None` for non-task events) and `exc_info` set to the passed exception.

`tests/integration/test_sweep_notifications.py` — add a test where the fake email channel's `send` **raises** `RuntimeError("smtp says bob@example.com bounced")`: after one sweep, the row is PENDING with `last_error == "RuntimeError"`, and the logs contain a `sweep.dispatch-failed` warning with `error_type == "RuntimeError"`, `channel` set, and no occurrence of `"bob@example.com"` in any captured event. In `test_sweep_retries_on_failed_channel`, assert the `sweep.max-attempts-reached` event has no `last_error` key.

`tests/unit/test_logging_email_channel.py` — add a real-chain test:

```python
async def test_logging_email_channel_output_redacts_recipient_and_payload(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(LogSettings())
    capsys.readouterr()
    await LoggingEmailChannel().send(_make_notification(), recipient="applicant@example.com")

    output = capsys.readouterr().out
    (line,) = [x for x in json_log_lines(output) if x["event"] == "email.sent"]
    assert line["recipient"] == "[REDACTED]"
    assert line["payload"] == "[REDACTED]"
    assert "applicant@example.com" not in output
```

(Keep the existing `capture_logs` tests: they pin what the dev channel *emits*; this pins what reaches output.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/parser/test_fallback_parser.py tests/unit/test_parser_library.py tests/unit/test_logging_email_channel.py -v` and `uv run pytest tests/integration/test_embed_job_worker.py tests/integration/test_sweep_outbox.py tests/integration/test_sweep_notifications.py -v`
Expected: new assertions FAIL (transient error degrades; `error` key present; no `sweep.dispatch-failed`; etc.). The redaction test may already PASS (PR 1 masks `recipient`/`payload`) — that is expected; it pins the contract.

- [ ] **Step 3: Implement**

`fallback.py` — import `TransientParserError`; replace the try/except:

```python
        try:
            return await self._primary.parse(content=content, content_type=content_type)
        except TransientParserError:
            # Transient extraction/storage failure: let Celery retry the whole
            # parse (LLM path included) instead of silently degrading.
            raise
        except LlmParserError as exc:
            # Our own slug messages are PII-free; no traceback — the chained
            # cause can be a ValidationError whose text is the resume itself.
            _log.warning("parse.llm-failed", error_class=type(exc).__name__, reason=str(exc))
        except ParserError:
            # Extraction failure — permanent for the fallback too; re-raise.
            raise
        except Exception as exc:  # noqa: BLE001 — degradation boundary by design
            _log.warning("parse.llm-failed", error_class=type(exc).__name__)
        return await self._fallback.parse(content=content, content_type=content_type)
```

`library.py` — add the logger; in the `no_text_extracted` branch, before `return`: `_log.warning("parse.no-text-extracted", content_type=content_type)`.

`embed.py` / `embed_job.py` — in the `EmbeddingProviderError` arms, replace `error=str(exc)` with `error_type=type(exc).__name__, http_status=http_status_of(exc.__cause__) if exc.__cause__ is not None else None` (import `http_status_of`); no traceback (provider message).

`sweep_outbox.py` — in `_record_failure`, read the task name before clearing the claim: `task_name = event.payload.get("task_name") if isinstance(event.payload, dict) else None`, and extend the warning with `task_name=task_name, exc_info=exc` (logged outside the except, so pass the exception object). Mark the batch loop arm `# noqa: BLE001 — per-event isolation: any failure is recorded on the row and retried`.

`sweep_notifications.py`:
- line ~124 arm: `# noqa: BLE001 — per-row isolation; the lease makes the row recoverable` (it already logs with traceback).
- dispatch arm (~282):

```python
    except Exception as exc:  # noqa: BLE001 — a channel crash is a failed attempt, retried with backoff
        # Type only: provider text can contain the recipient address and is
        # persisted to notifications.last_error.
        _log.warning(
            "sweep.dispatch-failed",
            notification_id=str(notification_id),
            channel=str(channel),
            error_type=type(exc).__name__,
        )
        result = ChannelResult.failed(type(exc).__name__)
```

- `sweep.max-attempts-reached`: remove `last_error=result.message`, add `channel=n.channel`.
- `sweep.retry-scheduled`: add `channel=n.channel`.

- [ ] **Step 4: Run tests to verify they pass**

Run the Step 2 commands; expected all PASS. Then full unit + integration suites.

- [ ] **Step 5: Commit**

```bash
uv run ruff check core/src worker/src tests && uv run ruff format core/src worker/src tests && uv run mypy
git add core/src/jobify/integrations/parser worker/src/jobify_worker/tasks tests/unit tests/integration
git commit -m "core/worker: retry transient parse errors; error context without provider text in embed/outbox/notification paths

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01JSP8DPirBJicB72XTMVq3o"
```

---

### Task 6: Lint guard, third-party logger levels, docs, CI gate + smoke

**Files:**
- Modify: `pyproject.toml` (`[tool.ruff.lint] select`)
- Modify: `core/src/jobify/observability/logging.py` + `tests/unit/test_logging.py`
- Modify: any remaining `BLE001` sites (`api/src/jobify_api/routes/metrics.py` etc.)
- Modify: `core/CLAUDE.md`

**Interfaces:**
- Consumes: everything above.
- Produces: a verified branch ready for PR 3.

- [ ] **Step 1: Pin noisy third-party loggers (test first)**

Add to `tests/unit/test_logging.py`:

```python
def test_third_party_loggers_pinned_to_warning() -> None:
    configure_logging(LogSettings(log_level="DEBUG"))

    for name in ("httpx", "httpcore", "botocore", "boto3", "urllib3", "google_genai"):
        assert logging.getLogger(name).level == logging.WARNING, name
```

Run it (FAIL), then in `configure_logging` add, after the uvicorn block:

```python
    # Third-party clients log full outbound URLs at INFO (httpx) and signed request
    # headers inside message text at DEBUG (botocore) — key-based redaction can't
    # see either. Pin them to WARNING regardless of JOBIFY_LOG_LEVEL.
    for name in _PINNED_THIRD_PARTY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
```

with `_PINNED_THIRD_PARTY_LOGGERS: Final[tuple[str, ...]] = ("httpx", "httpcore", "botocore", "boto3", "urllib3", "google_genai")`.

Root `tests/conftest.py` `_restore_global_logging_state` currently snapshots only `handlers` + `propagate` for `_NAMED_LOGGERS_TO_RESTORE = ("uvicorn", "uvicorn.error", "uvicorn.access")` (verified 2026-09-13). Extend it: add the six names to `_NAMED_LOGGERS_TO_RESTORE`, and snapshot/restore `level` as well (`saved_named = [(lg.handlers[:], lg.propagate, lg.level) ...]`, restore with `lg.setLevel(level)`), and update its docstring in one sentence. Run the test (PASS).

- [ ] **Step 2: Verify BLE001 coverage**

BLE was enabled in Task 1. Run `uv run ruff check core/src api/src worker/src tests --select BLE001,RUF100 --output-format concise` → no hits, and `grep -rn "noqa: BLE001" core/src api/src worker/src` → every line carries `— <reason>`.

- [ ] **Step 3: Document**

`core/CLAUDE.md` "## Logging + redaction" — append bullets:

```markdown
- **Tracebacks vs provider text.** Unexpected exceptions from our code/infra log WITH traceback. Exceptions whose message can carry request/user content — provider API errors (SES, Gemini), anything chained to a `ValidationError` over resume data — log `error_type` (+ `http_status`) WITHOUT `exc_info`: the rendered traceback includes the message and its causes.
- **External calls go through `observe_external_call(service, operation)`** (`observability/external.py`) — closed set: gemini/embed, gemini/parse_resume, gemini/explain_match, ses/send_email, s3/put_object, s3/get_object, s3/delete_object, google/jwks_fetch. It never swallows.
- **Blind `except Exception` needs a reason** — ruff `BLE001` is on; every suppression is `# noqa: BLE001 — <why this boundary catches everything>`. `TRY400` is deliberately NOT enabled: ruff can't see structlog `_log` objects as loggers.
- **Third-party loggers** (`httpx`, `httpcore`, `botocore`, `boto3`, `urllib3`, `google_genai`) are pinned to WARNING in `configure_logging`.
- **LLM output is never logged** — parser and explainer log shapes (`_raw_shape`, `raw_length`) only.
```

- [ ] **Step 4: Run the CI gate verbatim**

```bash
uv run ruff check core/src api/src worker/src tests
uv run ruff format --check core/src api/src worker/src tests
uv run mypy
uv run pytest -v -m "not integration and not eval"
uv run pytest -v -s -m eval
uv run pytest -v -m integration
```

Expected: all green.

- [ ] **Step 5: Live smoke**

**Guard (mandatory, check immediately before running):** if ANY local service is already up — a live pid in `var/run/*.pid`, or a listener on :8000/:8080/:5173/:9101, or `pgrep -f "uvicorn|celery|flutter"` matches — do NOT run `start-all.sh`/`stop-all.sh`; skip this step and report "smoke skipped: stack in use". The user runs the stack from this same checkout.

```bash
scripts/start-all.sh
# poll http://localhost:8000/health (≤60s)
curl -s -o /dev/null -X POST http://localhost:8000/v1/auth/oauth/google -H 'content-type: application/json' -d '{"id_token":"not-a-jwt"}'
sleep 12   # let beat run sweep_outbox a couple of times
curl -s http://localhost:9101/metrics | grep -E '^jobify_task_runs_total' | head
curl -s http://localhost:8000/metrics | grep -E '^jobify_external_calls_total' | head
grep -E 'google.id-token-rejected|task_name=' var/run/api.log var/run/worker.log | head -5
scripts/stop-all.sh
```

Expected: `jobify_task_runs_total{outcome="success",task="jobify.sweep_outbox"}` > 0 on the worker endpoint; `google.id-token-rejected reason='header_invalid'` in api.log; worker lines inside tasks carry `task_name=`/`task_id=`. (`jobify_external_calls_total` may be absent locally if no provider call happened — not a failure.)

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml core/src/jobify/observability/logging.py tests/unit/test_logging.py tests/conftest.py api/src core/src worker/src core/CLAUDE.md
git commit -m "lint/logging: enable BLE001 with reasons, pin third-party loggers to WARNING, document call-site rules

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01JSP8DPirBJicB72XTMVq3o"
```
