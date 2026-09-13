# Observability PR 1 — Logging Substrate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every backend log line — structlog and stdlib (uvicorn, SQLAlchemy, httpx, Celery) — renders in one redacted format with `request_id`/`user_id` context, every HTTP request produces one structured access line, and 422/5xx errors are logged.

**Architecture:** `configure_logging` gains a `structlog.stdlib.ProcessorFormatter` on the root handler (stdlib path) and a shared redaction processor on both paths; the worker calls it via Celery's `setup_logging` signal. A new pure-ASGI `RequestContextMiddleware` binds `request_id` into structlog contextvars and writes the access line; `current_user` binds `user_id`. Error handlers add a log-only 422 handler and ERROR logging for `HTTPException` ≥500. Metrics are untouched in this PR (PR 2).

**Tech Stack:** Python 3.12, structlog 24.4, FastAPI 0.115 / Starlette 0.46, uvicorn 0.32, Celery 5.6, SQLAlchemy async + asyncpg, pytest (asyncio_mode=auto).

**Spec:** `docs/superpowers/specs/2026-09-13-backend-observability-foundation-design.md` (this plan = "Rollout → PR 1").

## Global Constraints

- **structlog only** — `structlog.get_logger(__name__)`, context as kwargs; no `print` / `logging.getLogger` in `src` (tests may use `logging.getLogger` to emit stdlib records).
- **New middleware must be pure ASGI**, never `BaseHTTPMiddleware` (asyncpg "Future attached to a different loop").
- **Log shapes, never values.** No query strings, raw paths, request bodies, validation `input`/`msg`/`ctx`, tokens or emails in log fields.
- **Redaction key list (verbatim from spec):** `email`, `recipient`, `to`, `token`, `access_token`, `refresh_token`, `id_token`, `authorization`, `password`, `secret`, `api_key`, `raw_text`, `resume_text`, `text`, `body`, `payload` — matched case-insensitively, any depth, dicts and lists → `"[REDACTED]"`. Email addresses in any string value → `"[REDACTED_EMAIL]"`.
- **422 response body unchanged** — byte-identical to FastAPI's default.
- **Canonical traceback line** for unhandled API exceptions is `unhandled-exception`; uvicorn's `"Exception in ASGI application"` duplicate is dropped.
- **Redaction tests run the real `configure_logging` chain and assert on captured stdout** — never `structlog.testing.capture_logs()` (it replaces the processor chain).
- Access-line levels: status ≥500 ERROR; ≥400 WARNING; else INFO; `/health`, `/ready`, `/metrics` with status <400 at DEBUG.
- Workers read `settings` from `jobify_worker.celery_app`, never construct `WorkerSettings()` (worker/CLAUDE.md).
- All commands from repo root. CI gate verbatim: `uv run ruff check core/src api/src worker/src tests` · `uv run ruff format --check core/src api/src worker/src tests` · `uv run mypy` · `uv run pytest -v -m "not integration and not eval"` · `uv run pytest -v -s -m eval` · `uv run pytest -v -m integration`.
- Commit trailer on every commit:
  ```
  Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01JSP8DPirBJicB72XTMVq3o
  ```
- Branch: `feat/backend-observability` (already created off `origin/main`, spec committed at `a263d2e`).

## File Structure

| File | Status | Responsibility |
|---|---|---|
| `core/src/jobify/observability/redaction.py` | create | `redact_sensitive` structlog processor + key list + email scrub |
| `core/src/jobify/observability/logging.py` | modify | stdlib routing via `ProcessorFormatter`, uvicorn logger reset + duplicate-traceback filter, wire redaction |
| `core/src/jobify/db/session.py` | modify | `hide_parameters=True` |
| `worker/src/jobify_worker/observability.py` | create | Celery `setup_logging` receiver |
| `worker/src/jobify_worker/worker_app.py` | modify | import `observability` for its signal side effect |
| `api/src/jobify_api/middleware/request_context.py` | create | contextvar binding + `http.request` access line + `route_template()` |
| `api/src/jobify_api/app_factory.py` | modify | mount `RequestContextMiddleware` inside `RequestIdMiddleware` |
| `api/src/jobify_api/auth/dependencies.py` | modify | bind `user_id` in `current_user` |
| `api/src/jobify_api/middleware/error_handler.py` | modify | 422 log-only handler, `http.error` for ≥500, `route` on `unhandled-exception` |
| `tests/logging_helpers.py` | create | `LogSettings` stub + `json_log_lines()` parser shared by log tests |
| `tests/unit/test_logging.py` | modify | stdlib routing, redaction, email scrub, uvicorn tests |
| `tests/unit/test_session.py` | modify | `hide_parameters` flag |
| `tests/integration/test_db_error_redaction.py` | create | DB error text carries no bound params |
| `tests/unit/worker/test_worker_logging.py` | create | signal receiver configures worker logging |
| `tests/unit/test_request_context.py` | create | access line, levels, no query string, context isolation |
| `tests/integration/test_request_log_context.py` | create | real `current_user` binds `user_id` |
| `tests/unit/test_error_handler.py` | modify | 422 body parity + log, 5xx log, unhandled log |
| `scripts/start-all.sh`, `api/README.md`, `api/src/jobify_api/main.py` | modify | `--no-access-log` |
| `core/CLAUDE.md`, `api/CLAUDE.md`, `worker/CLAUDE.md` | modify | invariants |

---

### Task 1: Log redaction + stdlib routing in `configure_logging`

**Files:**
- Create: `core/src/jobify/observability/redaction.py`
- Modify: `core/src/jobify/observability/logging.py` (whole file)
- Create: `tests/logging_helpers.py`
- Modify: `tests/unit/test_logging.py` (append tests)
- Modify: `core/CLAUDE.md` (new section after "## Soft delete model")

**Interfaces:**
- Consumes: nothing new.
- Produces:
  - `jobify.observability.redaction.redact_sensitive(logger, method_name, event_dict) -> EventDict`
  - `jobify.observability.redaction.SENSITIVE_KEYS: frozenset[str]`, `REDACTED = "[REDACTED]"`, `REDACTED_EMAIL = "[REDACTED_EMAIL]"`
  - `jobify.observability.logging.configure_logging(settings: LoggingSettings | None = None) -> None` (same signature, new behavior)
  - `jobify.observability.logging.DropUvicornDuplicateTraceback(logging.Filter)`
  - `tests.logging_helpers.LogSettings(log_level: str = "INFO", log_format: str = "json")` and `tests.logging_helpers.json_log_lines(output: str) -> list[dict[str, Any]]`

- [ ] **Step 1: Create the shared test helper**

`tests/logging_helpers.py`:

```python
"""Helpers for tests that assert on real rendered log output.

Use these with the REAL ``configure_logging`` chain + ``capsys`` — never
``structlog.testing.capture_logs()``, which replaces the processor chain and so
cannot prove redaction or stdlib routing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LogSettings:
    """Satisfies ``jobify.observability.logging.LoggingSettings``."""

    log_level: str = "INFO"
    log_format: str = "json"


def json_log_lines(output: str) -> list[dict[str, Any]]:
    """Parse every JSON log line in captured stdout (non-JSON lines skipped)."""
    return [json.loads(line) for line in output.splitlines() if line.startswith("{")]
```

- [ ] **Step 2: Write the failing tests**

Append to `tests/unit/test_logging.py` (add the new imports to the existing import block: `import sys`, `from collections.abc import Iterator`, `from uuid import uuid4`, `from jobify.observability.logging import DropUvicornDuplicateTraceback`, `from tests.logging_helpers import LogSettings, json_log_lines`):

```python
@pytest.fixture(autouse=True)
def _clear_log_context() -> Iterator[None]:
    structlog.contextvars.clear_contextvars()
    yield
    structlog.contextvars.clear_contextvars()


def test_stdlib_records_render_through_structlog_as_json(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(LogSettings())
    capsys.readouterr()

    logging.getLogger("httpx").warning("pool %s exhausted", "primary")

    (line,) = json_log_lines(capsys.readouterr().out)
    assert line["event"] == "pool primary exhausted"
    assert line["level"] == "warning"
    assert line["logger"] == "httpx"
    assert "timestamp" in line


def test_contextvars_are_merged_into_stdlib_records(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(LogSettings())
    capsys.readouterr()
    structlog.contextvars.bind_contextvars(request_id="req-1")

    logging.getLogger("sqlalchemy.engine").error("boom")

    (line,) = json_log_lines(capsys.readouterr().out)
    assert line["request_id"] == "req-1"


def test_sensitive_keys_redacted_at_any_depth_case_insensitive(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(LogSettings())
    capsys.readouterr()
    user_id = str(uuid4())

    structlog.get_logger("t").info(
        "signin",
        user_id=user_id,
        id_token="eyJ.secret",
        nested={"Authorization": "Bearer abc", "ok": 1},
        items=[{"EMAIL": "a@b.co"}, {"kind": "x"}],
    )

    (line,) = json_log_lines(capsys.readouterr().out)
    assert line["user_id"] == user_id  # UUIDs are correlation handles, kept
    assert line["id_token"] == "[REDACTED]"
    assert line["nested"] == {"Authorization": "[REDACTED]", "ok": 1}
    assert line["items"] == [{"EMAIL": "[REDACTED]"}, {"kind": "x"}]


def test_sensitive_stdlib_extras_are_redacted(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(LogSettings())
    capsys.readouterr()

    logging.getLogger("httpx").warning(
        "request failed", extra={"authorization": "Bearer abc", "status_code": 403}
    )

    (line,) = json_log_lines(capsys.readouterr().out)
    assert line["authorization"] == "[REDACTED]"
    assert line["status_code"] == 403


def test_emails_scrubbed_from_messages_and_tracebacks(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(LogSettings())
    capsys.readouterr()

    try:
        raise ValueError("Key (email)=(bob@example.com) already exists")
    except ValueError:
        structlog.get_logger("t").exception("native-failure")
        logging.getLogger("sqlalchemy").exception("stdlib-failure for carol@example.org")

    output = capsys.readouterr().out
    assert "bob@example.com" not in output
    assert "carol@example.org" not in output
    native, stdlib = json_log_lines(output)
    assert "[REDACTED_EMAIL]" in native["exception"]
    assert "[REDACTED_EMAIL]" in stdlib["exception"]
    assert stdlib["event"] == "stdlib-failure for [REDACTED_EMAIL]"


def test_uvicorn_loggers_propagate_to_root_after_configure() -> None:
    uvicorn_error = logging.getLogger("uvicorn.error")
    uvicorn_error.addHandler(logging.StreamHandler(sys.stderr))
    uvicorn_error.propagate = False

    configure_logging(LogSettings())

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        assert logger.handlers == []
        assert logger.propagate is True


def test_uvicorn_duplicate_asgi_traceback_is_dropped(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(LogSettings())
    capsys.readouterr()
    uvicorn_error = logging.getLogger("uvicorn.error")

    try:
        raise RuntimeError("kaboom")
    except RuntimeError:
        uvicorn_error.error("Exception in ASGI application\n", exc_info=True)
    uvicorn_error.info("Application startup complete.")

    lines = json_log_lines(capsys.readouterr().out)
    assert [line["event"] for line in lines] == ["Application startup complete."]


def test_duplicate_filter_only_matches_uvicorn_error() -> None:
    drop = DropUvicornDuplicateTraceback()

    def record(name: str, msg: str) -> logging.LogRecord:
        return logging.LogRecord(name, logging.ERROR, __file__, 1, msg, None, None)

    assert drop.filter(record("uvicorn.error", "Exception in ASGI application\n")) is False
    assert drop.filter(record("myapp", "Exception in ASGI application\n")) is True
    assert drop.filter(record("uvicorn.error", "Shutting down")) is True


def test_uvicorn_color_message_extra_is_dropped(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(LogSettings())
    capsys.readouterr()

    logging.getLogger("uvicorn.error").info(
        "Started server process", extra={"color_message": "\x1b[1mStarted\x1b[0m"}
    )

    (line,) = json_log_lines(capsys.readouterr().out)
    assert "color_message" not in line
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_logging.py -v`
Expected: collection ERROR `ImportError: cannot import name 'DropUvicornDuplicateTraceback'`. (Temporarily removing that import would show the stdlib/redaction tests failing on `json.decoder`/assertion errors — bare `%(message)s` output is not JSON.)

- [ ] **Step 4: Create the redaction processor**

`core/src/jobify/observability/redaction.py`:

```python
"""Log redaction — the last processor before rendering.

Runs on BOTH paths configured in :mod:`jobify.observability.logging`: native
structlog events and stdlib records rendered through ``ProcessorFormatter``.

Two guards, because key-based masking alone cannot see PII inside free text:

- values under a sensitive key (any depth, dicts and lists, case-insensitive)
  are replaced wholesale;
- email addresses in ANY string value — including the rendered ``exception``
  traceback, which carries exception messages such as Postgres
  ``Key (email)=(a@b.c)`` details — are masked in place.

The rule for new log calls stays "log shapes, never values"; this is the safety
net, not the policy. Adding a key here is reviewed like an invariant. A false
positive shows up as ``[REDACTED]`` and is fixed by renaming the log key.
"""

from __future__ import annotations

import re
from typing import Any, Final

from structlog.types import EventDict, WrappedLogger

SENSITIVE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "email",
        "recipient",
        "to",
        "token",
        "access_token",
        "refresh_token",
        "id_token",
        "authorization",
        "password",
        "secret",
        "api_key",
        "raw_text",
        "resume_text",
        "text",
        "body",
        "payload",
    }
)
REDACTED: Final[str] = "[REDACTED]"
REDACTED_EMAIL: Final[str] = "[REDACTED_EMAIL]"
_EMAIL_RE: Final[re.Pattern[str]] = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def _redact_item(key: object, value: Any) -> Any:
    if isinstance(key, str) and key.lower() in SENSITIVE_KEYS:
        return REDACTED
    return _scrub(value)


def _scrub(value: Any) -> Any:
    if isinstance(value, str):
        return _EMAIL_RE.sub(REDACTED_EMAIL, value)
    if isinstance(value, dict):
        return {key: _redact_item(key, item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_scrub(item) for item in value]
    return value


def redact_sensitive(_logger: WrappedLogger, _method_name: str, event_dict: EventDict) -> EventDict:
    """structlog processor: mask sensitive keys and email addresses.

    Underscore-prefixed keys are processor metadata (``_record``,
    ``_from_structlog``) and pass through untouched.
    """
    return {
        key: value if key.startswith("_") else _redact_item(key, value)
        for key, value in event_dict.items()
    }
```

- [ ] **Step 5: Rewrite `configure_logging`**

Replace the whole of `core/src/jobify/observability/logging.py` with:

```python
"""Structured logging configuration.

Plain-text `key=value` output by default, compatible with Fluent Bit + ES.
JSON output is available via JOBIFY_LOG_FORMAT=json for environments that prefer it.

Two paths, one format:

- structlog events render through the processor chain configured below;
- stdlib records (uvicorn, SQLAlchemy, httpx, Celery — anything using
  ``logging``) reach the single root handler, whose ``ProcessorFormatter`` runs
  the same context merge, redaction and renderer. Without it they print as a
  bare message with no level, timestamp or JSON.

structlog itself deliberately stays on ``PrintLoggerFactory`` (not a full
``structlog.stdlib`` migration): output capture in the existing suite depends on
it, and routing only the foreign records gets the same result.
"""

from __future__ import annotations

import logging
import sys
from typing import Final, Protocol

import structlog
from structlog.types import EventDict, Processor, WrappedLogger

from jobify.observability.redaction import redact_sensitive
from jobify.settings import CoreSettings, LogFormat, LogLevel


class LoggingSettings(Protocol):
    log_level: LogLevel
    log_format: LogFormat


_LEVEL_MAP: Final[dict[str, int]] = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

# uvicorn installs its own handlers with propagate=False before importing the
# app; resetting them sends its records through the root handler below.
_UVICORN_LOGGERS: Final[tuple[str, ...]] = ("uvicorn", "uvicorn.error", "uvicorn.access")


class DropUvicornDuplicateTraceback(logging.Filter):
    """Drop uvicorn's copy of an unhandled-exception traceback.

    Starlette's ServerErrorMiddleware always re-raises after our exception
    handler has logged the canonical ``unhandled-exception`` line, and uvicorn
    then logs the same traceback again as "Exception in ASGI application".
    """

    def filter(self, record: logging.LogRecord) -> bool:
        return not (
            record.name == "uvicorn.error"
            and record.getMessage().startswith("Exception in ASGI application")
        )


def _drop_color_message(_logger: WrappedLogger, _method_name: str, event_dict: EventDict) -> EventDict:
    # uvicorn attaches an ANSI-coloured duplicate of every message as an extra.
    event_dict.pop("color_message", None)
    return event_dict


def configure_logging(settings: LoggingSettings | None = None) -> None:
    """Initialize stdlib + structlog. Idempotent: handlers do not stack.

    Reconfigures structlog every call so the logger factory binds to the
    current ``sys.stdout`` (important for tests that patch stdout).
    """
    settings = settings or CoreSettings()
    level = _LEVEL_MAP[settings.log_level]

    renderer: Processor
    if settings.log_format == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.processors.KeyValueRenderer(
            key_order=["timestamp", "level", "logger", "event"],
            drop_missing=True,
        )

    shared: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]

    # Stdlib root: replace any existing handlers with a single stdout handler.
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=[
                *shared,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.ExtraAdder(),
                _drop_color_message,
            ],
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.processors.format_exc_info,
                redact_sensitive,
                renderer,
            ],
        )
    )
    handler.addFilter(DropUvicornDuplicateTraceback())
    root.addHandler(handler)
    root.setLevel(level)

    for name in _UVICORN_LOGGERS:
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True

    structlog.configure(
        processors=[
            *shared,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            redact_sensitive,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=False,
    )
```

- [ ] **Step 6: Run the logging tests**

Run: `uv run pytest tests/unit/test_logging.py -v`
Expected: all PASS (3 existing + 9 new).

- [ ] **Step 7: Run the whole unit + integration suites (spec risk: output capture)**

Run: `uv run pytest -q -m "not integration and not eval"` then `uv run pytest -q -m integration`
Expected: all PASS. If a test that asserts on stdout/caplog now fails, read it: a failure caused by a redacted key or the new stdlib format is a legitimate update only if the test was asserting on a sensitive value; otherwise fix the config, not the test. Report any updated test in the commit message.

- [ ] **Step 8: Document the invariant**

In `core/CLAUDE.md`, insert after the "## Soft delete model" section (before "## Applicant preferences"):

```markdown
## Logging + redaction — spec `2026-09-13-backend-observability-foundation-design.md`

- **One format for every log line.** `configure_logging` routes stdlib records (uvicorn, SQLAlchemy, httpx, Celery) through a `ProcessorFormatter` on the single root handler; structlog stays on `PrintLoggerFactory`. Don't attach handlers to individual loggers — anything not reaching the root handler escapes redaction.
- **Log shapes, never values.** No query strings, raw paths, bodies, validation inputs, tokens or emails in fields. `redact_sensitive` (`observability/redaction.py`) is the safety net, not the policy: it masks a fixed key list at any depth and email addresses in every string (incl. rendered tracebacks). Adding a key is an invariant change.
- **Redaction tests must use the real chain** (`configure_logging` + `capsys`, helpers in `tests/logging_helpers.py`). `structlog.testing.capture_logs()` replaces the processor chain and proves nothing about redaction.
- **DB errors never embed bound values** — the engine is built with `hide_parameters=True`.
```

(The `hide_parameters` bullet lands with Task 2; add it now so the section is written once.)

- [ ] **Step 9: Lint, type-check, commit**

Run: `uv run ruff check core/src tests && uv run ruff format core/src tests && uv run mypy`
Expected: clean.

```bash
git add core/src/jobify/observability/redaction.py core/src/jobify/observability/logging.py \
  tests/logging_helpers.py tests/unit/test_logging.py core/CLAUDE.md
git commit -m "core: route stdlib logs through structlog; redact sensitive keys and emails

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01JSP8DPirBJicB72XTMVq3o"
```

---

### Task 2: DB errors never embed bound parameters

**Files:**
- Modify: `core/src/jobify/db/session.py` (the `kwargs` dict in `create_engine_from_settings`)
- Modify: `tests/unit/test_session.py` (append)
- Create: `tests/integration/test_db_error_redaction.py`

**Interfaces:**
- Consumes: `jobify.db.session.create_engine_from_settings(settings, *, poolclass=None) -> AsyncEngine`; integration fixture `migrated_db: str` (DB URL).
- Produces: engines with `engine.sync_engine.hide_parameters is True`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_session.py`:

```python
def test_create_engine_hides_bound_parameters_in_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JOBIFY_ENV", "local")
    monkeypatch.setenv("JOBIFY_SERVICE_NAME", "jobify-api")
    monkeypatch.setenv("JOBIFY_DB_URL", "postgresql+asyncpg://u:p@h:5432/d")

    engine = core_session_module.create_engine_from_settings()

    assert engine.sync_engine.hide_parameters is True
```

Create `tests/integration/test_db_error_redaction.py`:

```python
"""DB exception text must not carry bound parameter values.

SQLAlchemy renders ``[parameters: (...)]`` into ``str(DBAPIError)`` unless the
engine sets ``hide_parameters=True`` — and tracebacks put that string in logs.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.pool import NullPool

from jobify.db.session import create_engine_from_settings

pytestmark = pytest.mark.integration


@dataclass(frozen=True)
class _DbSettings:
    db_url: str
    db_pool_size: int = 1
    db_max_overflow: int = 0
    db_pool_timeout_seconds: float = 5.0
    db_pool_recycle_seconds: int = 1800
    db_command_timeout_seconds: float = 5.0


async def test_db_error_text_omits_bound_parameters(migrated_db: str) -> None:
    engine = create_engine_from_settings(_DbSettings(db_url=migrated_db), poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            with pytest.raises(DBAPIError) as info:
                # 1/0 fails at execution without Postgres echoing the value, so
                # only SQLAlchemy's own [parameters: ...] suffix could leak it.
                await connection.execute(
                    text("SELECT CAST(:value AS text), 1/0"), {"value": "secret-param-value"}
                )
    finally:
        await engine.dispose()

    assert "secret-param-value" not in str(info.value)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_session.py::test_create_engine_hides_bound_parameters_in_errors tests/integration/test_db_error_redaction.py -v`
Expected: both FAIL (`assert False is True`; `assert 'secret-param-value' not in "...[parameters: ('secret-param-value',)]..."`).

- [ ] **Step 3: Implement**

In `core/src/jobify/db/session.py`, in `create_engine_from_settings`, change the `kwargs` literal to:

```python
    kwargs: dict[str, Any] = {
        "echo": False,
        "pool_pre_ping": True,
        # Exception text (and so every logged traceback) must not embed bound
        # values — they are applicant PII. See core/CLAUDE.md "Logging + redaction".
        "hide_parameters": True,
        "connect_args": {
            "server_settings": {"search_path": _SCHEMA},
            "command_timeout": settings.db_command_timeout_seconds,
        },
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_session.py tests/integration/test_db_error_redaction.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
uv run ruff check core/src tests && uv run ruff format core/src tests && uv run mypy
git add core/src/jobify/db/session.py tests/unit/test_session.py tests/integration/test_db_error_redaction.py
git commit -m "core: hide bound parameters in DB exception text

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01JSP8DPirBJicB72XTMVq3o"
```

---

### Task 3: Worker and beat use `configure_logging`

**Files:**
- Create: `worker/src/jobify_worker/observability.py`
- Modify: `worker/src/jobify_worker/worker_app.py`
- Create: `tests/unit/worker/test_worker_logging.py`
- Modify: `worker/CLAUDE.md` ("## Worker runtime" bullets)

**Interfaces:**
- Consumes: `configure_logging` (Task 1); `jobify_worker.celery_app.settings` (WorkerSettings instance with `log_level`, `log_format`).
- Produces: `jobify_worker.observability.configure_worker_logging(**_kwargs: object) -> None`, connected to `celery.signals.setup_logging` on import. PR 3 adds task signals to this same module.

- [ ] **Step 1: Write the failing test**

`tests/unit/worker/test_worker_logging.py`:

```python
"""Worker logging goes through configure_logging via Celery's setup_logging signal.

Signal receivers are exercised by sending the signal directly — eager tasks
(``task_always_eager``) never run Celery's logging setup.
"""

from __future__ import annotations

import logging

import pytest
from celery.signals import setup_logging

from tests.logging_helpers import json_log_lines


def test_setup_logging_signal_configures_structured_worker_logs(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import jobify_worker.worker_app  # noqa: F401  (connects the receiver)
    from jobify_worker.celery_app import settings
    from jobify_worker.observability import configure_worker_logging

    monkeypatch.setattr(settings, "log_format", "json")

    responses = setup_logging.send(
        sender=None, loglevel=logging.INFO, logfile=None, format="", colorize=False
    )

    # A receiver exists, so Celery skips hijacking the root logger itself.
    assert configure_worker_logging in [receiver for receiver, _ in responses]
    capsys.readouterr()

    try:
        raise RuntimeError("task exploded")
    except RuntimeError:
        logging.getLogger("celery.app.trace").error("Task jobify.parse_resume failed", exc_info=True)

    (line,) = json_log_lines(capsys.readouterr().out)
    assert line["logger"] == "celery.app.trace"
    assert line["level"] == "error"
    assert "task exploded" in line["exception"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/worker/test_worker_logging.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'jobify_worker.observability'`.

- [ ] **Step 3: Implement the receiver**

`worker/src/jobify_worker/observability.py`:

```python
"""Worker observability wiring — imported by ``worker_app`` for its signal side effects.

Connecting ``setup_logging`` makes Celery skip its own logging setup, so
Celery's records — including ``celery.app.trace`` task-failure tracebacks —
reach the root handler installed by ``configure_logging`` and render (and get
redacted) like every other line. Both ``celery worker`` and ``celery beat``
send this signal. It never fires for eager tasks in tests.
"""

from __future__ import annotations

from celery.signals import setup_logging

from jobify.observability.logging import configure_logging
from jobify_worker.celery_app import settings


@setup_logging.connect  # type: ignore[untyped-decorator]
def configure_worker_logging(**_kwargs: object) -> None:
    configure_logging(settings)
```

Modify `worker/src/jobify_worker/worker_app.py` — replace the first import block with:

```python
from jobify_worker import (
    observability,  # noqa: F401  (connects setup_logging so Celery logs render via structlog)
    runtime,  # noqa: F401  (connects worker_process_init/shutdown signals on import)
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/worker/test_worker_logging.py tests/unit/test_celery_app.py -v`
Expected: all PASS.

- [ ] **Step 5: Document**

In `worker/CLAUDE.md`, append to the "## Worker runtime (shared by all tasks)" bullet list:

```markdown
- **Logging is configured by the `setup_logging` signal** (`jobify_worker/observability.py` → `configure_logging(settings)`), for worker and beat. Keep the receiver connected: without it Celery hijacks the root logger and its task tracebacks bypass structlog formatting and redaction. The signal never fires under eager mode — test receivers by sending the signal directly.
```

- [ ] **Step 6: Commit**

```bash
uv run ruff check worker/src tests && uv run ruff format worker/src tests && uv run mypy
git add worker/src/jobify_worker/observability.py worker/src/jobify_worker/worker_app.py \
  tests/unit/worker/test_worker_logging.py worker/CLAUDE.md
git commit -m "worker: configure structured logging via Celery setup_logging signal

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01JSP8DPirBJicB72XTMVq3o"
```

---

### Task 4: Request context binding + structured access log

**Files:**
- Create: `api/src/jobify_api/middleware/request_context.py`
- Modify: `api/src/jobify_api/app_factory.py` (middleware block)
- Modify: `api/src/jobify_api/auth/dependencies.py` (`current_user`, after `request.state.current_role = ...`)
- Create: `tests/unit/test_request_context.py`
- Create: `tests/integration/test_request_log_context.py`
- Modify: `scripts/start-all.sh:103`, `api/README.md:29,39`, `api/src/jobify_api/main.py` docstring
- Modify: `api/CLAUDE.md` (Middleware section line 13; Feed filters bullet line 59)

**Interfaces:**
- Consumes: `configure_logging` (Task 1), `tests.logging_helpers` (Task 1); `scope["state"]["request_id"]` set by `RequestIdMiddleware`; `request.state.current_user_id` set by `current_user`.
- Produces:
  - `jobify_api.middleware.request_context.RequestContextMiddleware(app: ASGIApp)`
  - `jobify_api.middleware.request_context.route_template(scope: Scope) -> str` (matched template or `"__unmatched__"`) — used by Task 5 and PR 2.
  - `jobify_api.middleware.request_context.UNMATCHED_ROUTE: Final[str] = "__unmatched__"`
  - log event `http.request` with fields `method, route, status, duration_ms, user_id` (+ `request_id` from context).

- [ ] **Step 1: Write the failing unit tests**

`tests/unit/test_request_context.py`:

```python
"""RequestContextMiddleware: contextvar binding + one structured access line."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
import structlog
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from jobify_api.app_factory import create_app
from tests.logging_helpers import json_log_lines

_log = structlog.get_logger("test.request_context")


def _env(monkeypatch: pytest.MonkeyPatch, *, level: str = "INFO") -> None:
    monkeypatch.setenv("JOBIFY_ENV", "local")
    monkeypatch.setenv("JOBIFY_SERVICE_NAME", "jobify-api")
    monkeypatch.setenv("JOBIFY_LOG_LEVEL", level)
    monkeypatch.setenv("JOBIFY_LOG_FORMAT", "json")
    monkeypatch.setenv("JOBIFY_DB_URL", "postgresql+asyncpg://u:p@h:5432/d")
    monkeypatch.setenv("JOBIFY_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("JOBIFY_JWT_SECRET", "x" * 32)
    monkeypatch.setenv("JOBIFY_GOOGLE_OAUTH_CLIENT_IDS", "test.apps.googleusercontent.com")


def _add_routes(app: FastAPI) -> None:
    @app.get("/_t/items/{item_id}")
    async def item(item_id: str) -> dict[str, str]:
        _log.info("inside-handler")
        return {"id": item_id}

    @app.get("/_t/bind-user")
    async def bind_user() -> dict[str, str]:
        # Simulates current_user's binding to prove the NEXT request starts clean.
        structlog.contextvars.bind_contextvars(user_id="leaky-user")
        return {}

    @app.get("/_t/missing")
    async def missing() -> None:
        raise HTTPException(status_code=404, detail="nope")

    @app.get("/_t/boom")
    async def boom() -> None:
        raise RuntimeError("kaboom")


@pytest.fixture
def app_client(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> Iterator[TestClient]:
    _env(monkeypatch)
    app = create_app()
    _add_routes(app)
    structlog.contextvars.clear_contextvars()
    with TestClient(app, raise_server_exceptions=False) as client:
        capsys.readouterr()
        yield client
    structlog.contextvars.clear_contextvars()


def _access_lines(output: str) -> list[dict[str, Any]]:
    return [line for line in json_log_lines(output) if line["event"] == "http.request"]


def test_one_access_line_with_route_template_and_request_id(
    app_client: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    response = app_client.get("/_t/items/abc?q=secret-search")

    output = capsys.readouterr().out
    (access,) = _access_lines(output)
    assert access["method"] == "GET"
    assert access["route"] == "/_t/items/{item_id}"
    assert access["status"] == 200
    assert access["level"] == "info"
    assert access["request_id"] == response.headers["x-request-id"]
    assert access["user_id"] is None
    assert isinstance(access["duration_ms"], int | float)
    # Never the query string or the raw path.
    assert "secret-search" not in output
    assert "/_t/items/abc" not in output


def test_handler_logs_carry_request_id(
    app_client: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    response = app_client.get("/_t/items/abc")

    (inside,) = [line for line in json_log_lines(capsys.readouterr().out) if line["event"] == "inside-handler"]
    assert inside["request_id"] == response.headers["x-request-id"]


def test_context_does_not_bleed_between_requests(
    app_client: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    app_client.get("/_t/bind-user")
    second = app_client.get("/_t/items/abc")

    (inside,) = [line for line in json_log_lines(capsys.readouterr().out) if line["event"] == "inside-handler"]
    assert inside["request_id"] == second.headers["x-request-id"]
    assert "user_id" not in inside


def test_4xx_access_line_is_warning(
    app_client: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    app_client.get("/_t/missing")

    (access,) = _access_lines(capsys.readouterr().out)
    assert access["status"] == 404
    assert access["level"] == "warning"


def test_unmatched_route_is_logged_with_placeholder(
    app_client: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    app_client.get("/definitely/not/a/route/123")

    (access,) = _access_lines(capsys.readouterr().out)
    assert access["route"] == "__unmatched__"
    assert access["status"] == 404


def test_unhandled_exception_access_line_is_error_500(
    app_client: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    app_client.get("/_t/boom")

    (access,) = _access_lines(capsys.readouterr().out)
    assert access["status"] == 500
    assert access["level"] == "error"
    assert access["route"] == "/_t/boom"


def test_probe_access_lines_are_debug(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _env(monkeypatch, level="INFO")
    with TestClient(create_app()) as client:
        capsys.readouterr()
        client.get("/health")
        assert _access_lines(capsys.readouterr().out) == []

    _env(monkeypatch, level="DEBUG")
    with TestClient(create_app()) as client:
        capsys.readouterr()
        client.get("/health")
        (access,) = _access_lines(capsys.readouterr().out)
        assert access["level"] == "debug"
        assert access["route"] == "/health"
```

- [ ] **Step 2: Write the failing integration test**

`tests/integration/test_request_log_context.py`:

```python
"""current_user binds user_id into the log context of the rest of the request."""

from __future__ import annotations

import httpx
import pytest
import structlog
from fastapi import Depends, FastAPI

from jobify.db.models import User
from jobify.observability.logging import configure_logging
from jobify_api.auth.dependencies import current_user
from tests.logging_helpers import LogSettings, json_log_lines

pytestmark = pytest.mark.integration


async def test_logs_after_auth_carry_user_id_and_request_id(
    integration_app: FastAPI,
    async_client: httpx.AsyncClient,
    applicant_user_and_token: tuple[User, str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    user, token = applicant_user_and_token
    probe_log = structlog.get_logger("test.probe")

    @integration_app.get("/_t/whoami")
    async def whoami(_user: User = Depends(current_user)) -> dict[str, str]:  # noqa: B008
        probe_log.info("probe-after-auth")
        return {}

    configure_logging(LogSettings())
    capsys.readouterr()

    response = await async_client.get("/_t/whoami", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    lines = json_log_lines(capsys.readouterr().out)
    (probe,) = [line for line in lines if line["event"] == "probe-after-auth"]
    (access,) = [line for line in lines if line["event"] == "http.request"]
    assert probe["user_id"] == str(user.id)
    assert probe["request_id"] == response.headers["x-request-id"]
    assert access["user_id"] == str(user.id)
    structlog.contextvars.clear_contextvars()
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_request_context.py -v` and `uv run pytest tests/integration/test_request_log_context.py -v`
Expected: FAIL — no `http.request` lines (`ValueError: not enough values to unpack`), `inside["request_id"]` KeyError, `probe["user_id"]` KeyError.

- [ ] **Step 4: Implement the middleware**

`api/src/jobify_api/middleware/request_context.py`:

```python
"""Per-request log context + structured access log.

Pure ASGI (see ``request_id.py`` for why not ``BaseHTTPMiddleware``). Mounted
INSIDE ``RequestIdMiddleware`` — added to the app before it — so
``scope["state"]["request_id"]`` is already set when this runs.

- **Start:** clear structlog contextvars (no bleed between requests) and bind
  ``request_id``. ``current_user`` binds ``user_id`` later in the request.
- **End:** exactly one ``http.request`` event. Never the query string or raw
  path — ``q`` is free text and paths carry unbounded ids — only the matched
  route template.

Context is deliberately NOT cleared on the way out: Starlette's
``ServerErrorMiddleware`` (outermost) runs the unhandled-exception handler after
this middleware has returned, and that canonical error line must still carry
``request_id``/``user_id``. The next request's clear at start is what isolates.
"""

from __future__ import annotations

import logging
from time import perf_counter
from typing import Any, Final

import structlog
from starlette.types import ASGIApp, Message, Receive, Scope, Send

_log = structlog.get_logger(__name__)

UNMATCHED_ROUTE: Final[str] = "__unmatched__"
_PROBE_ROUTES: Final[frozenset[str]] = frozenset({"/health", "/ready", "/metrics"})


def route_template(scope: Scope) -> str:
    """The matched route's path template, or ``__unmatched__`` (bounded values only)."""
    path = getattr(scope.get("route"), "path", None)
    return path if isinstance(path, str) else UNMATCHED_ROUTE


def _level_for(status: int, route: str) -> int:
    if status >= 500:
        return logging.ERROR
    if status >= 400:
        return logging.WARNING
    if route in _PROBE_ROUTES:
        return logging.DEBUG
    return logging.INFO


class RequestContextMiddleware:
    """Pure-ASGI middleware: bind log context, then log one access line."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        state: dict[str, Any] = scope.setdefault("state", {})
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=state.get("request_id"))
        started_at = perf_counter()
        status: int | None = None

        async def _send_with_status(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, _send_with_status)
        except Exception:
            # Raised before a response started → ServerErrorMiddleware sends 500.
            if status is None:
                status = 500
            raise
        finally:
            # No status (e.g. client disconnect / CancelledError): nothing was
            # served, so no access line — mirrors MetricsMiddleware.
            if status is not None:
                route = route_template(scope)
                user_id = state.get("current_user_id")
                _log.log(
                    _level_for(status, route),
                    "http.request",
                    method=scope.get("method", ""),
                    route=route,
                    status=status,
                    duration_ms=round((perf_counter() - started_at) * 1000, 1),
                    user_id=str(user_id) if user_id is not None else None,
                )
```

- [ ] **Step 5: Mount it and bind `user_id`**

In `api/src/jobify_api/app_factory.py`, add the import `from jobify_api.middleware.request_context import RequestContextMiddleware` (keep isort order: after `metrics`, before `request_id`) and replace the line `app.add_middleware(RequestIdMiddleware)` with:

```python
    # Added FIRST so it is innermost (last-added = outermost): it must sit inside
    # RequestIdMiddleware to read the request id. Binds log context + writes the
    # http.request access line (see middleware/request_context.py).
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(RequestIdMiddleware)
```

In `api/src/jobify_api/auth/dependencies.py`, in `current_user`, directly after `request.state.current_role = user.role.value`, add:

```python
    # Every later log line in this request carries the caller (UUID, not PII).
    structlog.contextvars.bind_contextvars(user_id=str(user.id))
```

(`structlog` is already imported in that module.)

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_request_context.py tests/unit/test_request_id.py tests/unit/test_metrics.py -v` and `uv run pytest tests/integration/test_request_log_context.py tests/integration/test_me.py -v`
Expected: all PASS.

- [ ] **Step 7: Disable uvicorn's access log**

- `scripts/start-all.sh:103`: change `uvicorn jobify_api.main:app --reload --port 8000` to `uvicorn jobify_api.main:app --reload --port 8000 --no-access-log`.
- `api/README.md:29` and `api/README.md:39`: append ` --no-access-log` to both `uvicorn jobify_api.main:app --reload --port 8000` commands, and add directly under the first code block: `` `--no-access-log`: the API writes its own structured `http.request` access line (route template, no query string); uvicorn's would log `q` verbatim. ``
- `api/src/jobify_api/main.py` docstring: `uv run uvicorn jobify_api.main:app --reload --port 8000 --no-access-log`.

- [ ] **Step 8: Update `api/CLAUDE.md`**

In the "## Middleware — pure ASGI, not BaseHTTPMiddleware" paragraph, replace the sentence starting `` `MetricsMiddleware` is added next `` up to (not including) `` `CORSMiddleware` mounted **after** both (outermost). `` with:

```markdown
Order, outermost first: `ServerErrorMiddleware → CORS → MetricsMiddleware → RequestIdMiddleware → RequestContextMiddleware → router`. `RequestContextMiddleware` is added **first** so it is innermost and can read the request id; it clears + binds structlog contextvars (`request_id`; `current_user` binds `user_id`) and writes exactly one `http.request` line — route **template**, status, `duration_ms`, `user_id`, never the query string or raw path (≥500 ERROR, ≥400 WARNING, probes DEBUG). It must not clear context on exit: the unhandled-exception handler runs after it returns. `MetricsMiddleware` wraps `RequestIdMiddleware` so it counts every routed request including `HTTPException`/500 responses, but stays inside `CORSMiddleware` so CORS preflight (OPTIONS) short-circuits aren't counted.
```

And change the phrase "on every response (incl. errors) as the only log correlation handle" to "on every response (incl. errors) and bound into every log line of the request".

In the Feed filters bullet, replace `` **`q` is the API's only free-text query param and lands verbatim in uvicorn's default access log** — deploy config must disable/redact access logging (flagged for the P5 security review; DSR's column denylist can't cover log lines). `` with:

```markdown
**`q` is the API's only free-text query param** — it must never reach logs: the API's own access line logs the route template only, and uvicorn runs with `--no-access-log` (its access log would write `q` verbatim; deploy entrypoints must keep the flag).
```

- [ ] **Step 9: Commit**

```bash
uv run ruff check api/src tests && uv run ruff format api/src tests && uv run mypy
git add api/src/jobify_api/middleware/request_context.py api/src/jobify_api/app_factory.py \
  api/src/jobify_api/auth/dependencies.py tests/unit/test_request_context.py \
  tests/integration/test_request_log_context.py scripts/start-all.sh api/README.md \
  api/src/jobify_api/main.py api/CLAUDE.md
git commit -m "api: bind request/user log context and write a structured access log

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01JSP8DPirBJicB72XTMVq3o"
```

---

### Task 5: Log 422s and deliberate 5xx; route on unhandled exceptions

**Files:**
- Modify: `api/src/jobify_api/middleware/error_handler.py`
- Modify: `tests/unit/test_error_handler.py` (append)
- Modify: `api/CLAUDE.md` ("## Error handling — RFC 7807 problem+json" paragraph)

**Interfaces:**
- Consumes: `jobify_api.middleware.request_context.route_template(scope) -> str` (Task 4); `tests.logging_helpers` (Task 1).
- Produces: log events `http.validation-failed` (WARNING; `route`, `fields: list[{"loc": str, "type": str}]`), `http.error` (ERROR; `status`, `detail`, `route`), `unhandled-exception` (ERROR; now `route` instead of raw `path`). PR 2 adds counters at these same three points.

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_error_handler.py` (add imports: `from collections.abc import Iterator`, `from fastapi import FastAPI`, `from pydantic import BaseModel`, `from tests.logging_helpers import json_log_lines`):

```python
class _Body(BaseModel):
    count: int


def _add_validation_route(app: FastAPI) -> None:
    @app.post("/validate/{item_id}")
    async def validate(item_id: int, body: _Body) -> dict[str, int]:
        return {"item_id": item_id, "count": body.count}


@pytest.fixture
def json_app(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> Iterator[TestClient]:
    monkeypatch.setenv("JOBIFY_ENV", "local")
    monkeypatch.setenv("JOBIFY_SERVICE_NAME", "jobify-api")
    monkeypatch.setenv("JOBIFY_LOG_LEVEL", "INFO")
    monkeypatch.setenv("JOBIFY_LOG_FORMAT", "json")
    monkeypatch.setenv("JOBIFY_DB_URL", "postgresql+asyncpg://u:p@h:5432/d")
    monkeypatch.setenv("JOBIFY_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("JOBIFY_JWT_SECRET", "x" * 32)
    monkeypatch.setenv("JOBIFY_GOOGLE_OAUTH_CLIENT_IDS", "test.apps.googleusercontent.com")
    app = create_app()
    _add_validation_route(app)

    @app.get("/boom-503")
    async def boom_503() -> None:
        raise HTTPException(status_code=503, detail="dependency_unavailable")

    @app.get("/boom-404")
    async def boom_404() -> None:
        raise HTTPException(status_code=404, detail="missing")

    @app.get("/boom-unhandled/{item_id}")
    async def boom_unhandled(item_id: str) -> None:
        raise RuntimeError("kaboom")

    with TestClient(app, raise_server_exceptions=False) as client:
        capsys.readouterr()
        yield client


def test_validation_error_body_is_identical_to_fastapi_default(json_app: TestClient) -> None:
    plain = FastAPI()
    _add_validation_route(plain)
    payload = {"count": "not-a-number-alice@example.com"}

    ours = json_app.post("/validate/7", json=payload)
    default = TestClient(plain).post("/validate/7", json=payload)

    assert ours.status_code == default.status_code == 422
    assert ours.headers["content-type"] == default.headers["content-type"]
    assert ours.content == default.content


def test_validation_error_logs_field_shapes_not_values(
    json_app: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    json_app.post("/validate/7", json={"count": "secret-input-value"})

    output = capsys.readouterr().out
    (line,) = [x for x in json_log_lines(output) if x["event"] == "http.validation-failed"]
    assert line["level"] == "warning"
    assert line["route"] == "/validate/{item_id}"
    assert line["fields"] == [{"loc": "body.count", "type": "int_parsing"}]
    assert "secret-input-value" not in output


def test_http_exception_5xx_logs_error(
    json_app: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    response = json_app.get("/boom-503")

    assert response.status_code == 503
    (line,) = [x for x in json_log_lines(capsys.readouterr().out) if x["event"] == "http.error"]
    assert line["level"] == "error"
    assert line["status"] == 503
    assert line["detail"] == "dependency_unavailable"
    assert line["route"] == "/boom-503"
    assert line["request_id"] == response.headers["x-request-id"]


def test_http_exception_4xx_does_not_log_http_error(
    json_app: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    json_app.get("/boom-404")

    assert [x for x in json_log_lines(capsys.readouterr().out) if x["event"] == "http.error"] == []


def test_unhandled_exception_logs_one_traceback_with_route(
    json_app: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    response = json_app.get("/boom-unhandled/abc-123")

    output = capsys.readouterr().out
    lines = json_log_lines(output)
    (line,) = [x for x in lines if x["event"] == "unhandled-exception"]
    assert line["route"] == "/boom-unhandled/{item_id}"
    assert line["request_id"] == response.headers["x-request-id"]
    assert "RuntimeError: kaboom" in line["exception"]
    assert "path" not in line
    assert sum("exception" in x for x in lines) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_error_handler.py -v`
Expected: `test_validation_error_body_is_identical_to_fastapi_default` PASSES already (it pins current behavior — keep it); the other four FAIL (no `http.validation-failed` / `http.error` lines; `route` KeyError / `path` present).

- [ ] **Step 3: Implement**

In `api/src/jobify_api/middleware/error_handler.py`:

Add imports:

```python
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError

from jobify_api.middleware.request_context import route_template
```

Inside `register_error_handlers`, replace `_handle_http_exception` and `_handle_unhandled`, and add the validation handler:

```python
    @app.exception_handler(HTTPException)
    async def _handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        request_id = getattr(request.state, "request_id", "unknown")
        if exc.status_code >= 500:
            # A deliberate 5xx is still an outage signal. <500 is recorded by the
            # access line alone (WARNING) — no second event.
            _log.error(
                "http.error",
                status=exc.status_code,
                detail=detail,
                route=route_template(request.scope),
            )
        return _problem(
            status=exc.status_code,
            title=_phrase_for(exc.status_code),
            detail=detail,
            request_id=request_id,
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Log-only: the body stays FastAPI's default {"detail": [...]} — both
        # clients parse it, so reshaping it is a cross-package contract change.
        # Shapes, never values: loc + type only; input/msg/ctx echo the payload.
        _log.warning(
            "http.validation-failed",
            route=route_template(request.scope),
            fields=[
                {"loc": ".".join(str(part) for part in error["loc"]), "type": error["type"]}
                for error in exc.errors()
            ],
        )
        return await request_validation_exception_handler(request, exc)

    @app.exception_handler(Exception)
    async def _handle_unhandled(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "unknown")
        # The canonical traceback line (uvicorn's duplicate is filtered in
        # configure_logging). Route template, not raw path: bounded, no ids.
        _log.exception(
            "unhandled-exception",
            request_id=request_id,
            route=route_template(request.scope),
            method=request.method,
        )
        response = _problem(
            status=500,
            title="Internal Server Error",
            detail="An unexpected error occurred.",
            request_id=request_id,
        )
        # Starlette's ServerErrorMiddleware is outside RequestIdMiddleware, so a
        # response produced here never re-enters the middleware that would
        # normally attach the header. Set it explicitly to preserve correlation.
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_error_handler.py tests/unit/test_openapi_contract.py -v`
Expected: all PASS (OpenAPI snapshot unchanged — exception handlers don't alter the schema).

- [ ] **Step 5: Update `api/CLAUDE.md`**

Append to the "## Error handling — RFC 7807 problem+json" paragraph:

```markdown
Logging: `HTTPException` ≥500 → ERROR `http.error` (status, detail slug, route); <500 relies on the access line. `RequestValidationError` → WARNING `http.validation-failed` with `fields=[{loc, type}]` only — never `input`/`msg`/`ctx` (they echo submitted values) — and the response is FastAPI's default `{"detail": [...]}` **byte-for-byte** (pinned by test; the Flutter and React clients parse it, so reshaping is a cross-package change). `unhandled-exception` is the one canonical traceback line.
```

- [ ] **Step 6: Commit**

```bash
uv run ruff check api/src tests && uv run ruff format api/src tests && uv run mypy
git add api/src/jobify_api/middleware/error_handler.py tests/unit/test_error_handler.py api/CLAUDE.md
git commit -m "api: log validation failures and deliberate 5xx; route template on unhandled errors

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01JSP8DPirBJicB72XTMVq3o"
```

---

### Task 6: Full CI gate + live smoke check

**Files:** none modified unless a check fails.

**Interfaces:**
- Consumes: everything above.
- Produces: a verified branch ready for PR 1.

- [ ] **Step 1: Run the CI gate verbatim**

```bash
uv run ruff check core/src api/src worker/src tests
uv run ruff format --check core/src api/src worker/src tests
uv run mypy
uv run pytest -v -m "not integration and not eval"
uv run pytest -v -s -m eval
uv run pytest -v -m integration
```

Expected: all green. Record the pass counts (baseline before this PR: 381 unit, 461 integration, eval 1 passed / 1 skipped) — new counts should be baseline + the tests added here.

- [ ] **Step 2: Live smoke on the local stack**

```bash
scripts/start-all.sh
curl -s -o /dev/null http://localhost:8000/health
curl -s -o /dev/null "http://localhost:8000/v1/feed?q=smoke-secret"
curl -s -o /dev/null http://localhost:8000/nope-smoke
```

Then inspect the API and worker logs under the run directory `start-all.sh` prints (e.g. `grep -E "http.request|smoke-secret" <run-dir>/api.log`, `tail -20 <run-dir>/worker.log`). Expected:
- `http.request` lines exist for `/v1/feed` (unauthenticated → 4xx, WARNING, `route='/v1/feed'`) and `/nope-smoke` (404, `route='__unmatched__'`); no line for `/health` at INFO.
- `smoke-secret` appears **nowhere** in the API log.
- No uvicorn-format access lines (`"GET /v1/feed HTTP/1.1" 401`).
- Worker and beat log lines are key=value with `timestamp=`/`level=` (Celery's own startup lines included), not Celery's default `[2026-… : INFO/MainProcess]` format.

Stop the stack afterwards only if it was not running before you started (`scripts/stop-all.sh`).

- [ ] **Step 3: Push the branch**

```bash
git push -u origin feat/backend-observability
```

(Opening the PR is the user's call — ask before `gh pr create`.)
