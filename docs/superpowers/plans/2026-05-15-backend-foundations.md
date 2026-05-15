# KPA Backend Foundations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scaffold the KPA FastAPI service so it runs, returns a structured `/health` response, is built into a slim container image, and passes CI on every push — with request-id propagation, structured logging, and RFC 7807 error responses already wired in. No DB or business logic yet; those land in later plans.

**Architecture:** A single FastAPI service in `api/` using a `src/` layout. The app is created by a factory (`create_app()`) that composes middlewares (request id → logging → error handler) and mounts routes. Settings are env-driven via `pydantic-settings` and validated at startup (the app refuses to boot on missing required vars). Tests use FastAPI's `TestClient` (sync) for route-level assertions and direct calls for unit-level pieces. Production runs in a multi-stage Docker image built on `python:3.12-slim`.

**Tech Stack:** Python 3.12, uv (env + deps), FastAPI 0.115+, pydantic 2.x, pydantic-settings 2.x, structlog 24+, pytest 8+, httpx (test client transport), ruff (lint+format), mypy `--strict` on `src/kpa/`, Docker (multi-stage), GitHub Actions.

**Project location:** Everything in this plan lives under `api/` inside the repo root (`/Users/ahamadshah/ahamed_personal/kpa/`). Working branch: `feat/p0-backend-foundations`.

---

## File structure produced by this plan

```
api/
├── .env.example                          # documented env vars, no real values
├── .python-version                       # 3.12
├── Dockerfile                            # multi-stage build
├── README.md                             # how to run, test, build locally
├── pyproject.toml                        # uv-managed deps + tool config
├── uv.lock                               # uv-generated lockfile
├── src/
│   └── kpa/
│       ├── __init__.py
│       ├── main.py                       # entrypoint (uvicorn target)
│       ├── app_factory.py                # create_app() — composes middlewares + routes
│       ├── settings.py                   # Settings (pydantic-settings)
│       ├── middleware/
│       │   ├── __init__.py
│       │   ├── request_id.py             # X-Request-Id propagation + contextvar binding
│       │   └── error_handler.py          # RFC 7807 problem-detail responses
│       ├── observability/
│       │   ├── __init__.py
│       │   └── logging.py                # structlog configuration
│       └── routes/
│           ├── __init__.py
│           └── health.py                 # GET /health
└── tests/
    ├── __init__.py
    ├── conftest.py                       # shared fixtures (client, env override)
    └── unit/
        ├── __init__.py
        ├── test_settings.py
        ├── test_health.py
        ├── test_request_id.py
        ├── test_error_handler.py
        └── test_logging.py

.github/
└── workflows/
    └── api-ci.yml                        # ruff, mypy, pytest on every push
```

---

### Task 1: Initialize Python project with uv

**Files:**
- Create: `api/pyproject.toml`
- Create: `api/.python-version`
- Create: `api/.env.example`
- Create: `api/src/kpa/__init__.py`
- Create: `api/tests/__init__.py`
- Create: `api/tests/unit/__init__.py`

- [ ] **Step 1: Verify `uv` is installed**

Run: `uv --version`
Expected: a version string like `uv 0.5.x` (any 0.5+). If not installed, install via:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```
Then re-open the shell so `uv` is on PATH.

- [ ] **Step 2: Create `api/.python-version`**

```
3.12
```

- [ ] **Step 3: Create `api/pyproject.toml`**

```toml
[project]
name = "kpa-api"
version = "0.1.0"
description = "Khan Placement Agency API"
requires-python = ">=3.12,<3.13"
dependencies = [
    "fastapi>=0.115,<0.116",
    "uvicorn[standard]>=0.32,<0.33",
    "pydantic>=2.9,<3",
    "pydantic-settings>=2.5,<3",
    "structlog>=24.4,<25",
]

[dependency-groups]
dev = [
    "pytest>=8.3,<9",
    "pytest-asyncio>=0.24,<0.25",
    "httpx>=0.27,<0.28",
    "ruff>=0.7,<0.8",
    "mypy>=1.13,<2",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/kpa"]

[tool.ruff]
line-length = 100
target-version = "py312"
src = ["src"]

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "N", "S", "RUF"]
ignore = ["S101"]  # allow assert in tests

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S"]

[tool.mypy]
python_version = "3.12"
strict = true
files = ["src/kpa"]
plugins = ["pydantic.mypy"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
pythonpath = ["src"]
```

- [ ] **Step 4: Create `api/.env.example`**

```
# KPA API local environment example.
# Copy to .env and fill in real values; .env is git-ignored.

KPA_ENV=local
KPA_LOG_LEVEL=INFO
KPA_LOG_FORMAT=text          # text | json
KPA_SERVICE_NAME=kpa-api
```

- [ ] **Step 5: Create empty package markers**

`api/src/kpa/__init__.py`:
```python
"""Khan Placement Agency API package."""

__version__ = "0.1.0"
```

`api/tests/__init__.py`: (empty file)

`api/tests/unit/__init__.py`: (empty file)

- [ ] **Step 6: Generate the lockfile and verify install**

Run (from `api/`):
```bash
uv sync
```
Expected: uv creates `.venv/` and `uv.lock`; final line is `Resolved N packages` and `Installed N packages` with no errors.

- [ ] **Step 7: Add `api/.gitignore`**

Create `api/.gitignore`:
```
.venv/
__pycache__/
*.pyc
.pytest_cache/
.mypy_cache/
.ruff_cache/
.env
.coverage
htmlcov/
dist/
build/
*.egg-info/
```

- [ ] **Step 8: Commit**

```bash
git add api/.python-version api/pyproject.toml api/uv.lock api/.env.example api/.gitignore api/src/kpa/__init__.py api/tests/__init__.py api/tests/unit/__init__.py
git commit -m "chore(api): initialize FastAPI project with uv"
```

---

### Task 2: Settings module (env-driven, validated at startup)

**Files:**
- Create: `api/src/kpa/settings.py`
- Test: `api/tests/unit/test_settings.py`

- [ ] **Step 1: Write the failing test**

Create `api/tests/unit/test_settings.py`:
```python
"""Tests for the Settings module."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kpa.settings import Settings


def test_settings_loads_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KPA_ENV", "local")
    monkeypatch.setenv("KPA_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("KPA_LOG_FORMAT", "text")
    monkeypatch.setenv("KPA_SERVICE_NAME", "kpa-api")

    settings = Settings()

    assert settings.env == "local"
    assert settings.log_level == "DEBUG"
    assert settings.log_format == "text"
    assert settings.service_name == "kpa-api"


def test_settings_rejects_unknown_log_level(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KPA_ENV", "local")
    monkeypatch.setenv("KPA_LOG_LEVEL", "VERBOSE")  # invalid
    monkeypatch.setenv("KPA_LOG_FORMAT", "text")
    monkeypatch.setenv("KPA_SERVICE_NAME", "kpa-api")

    with pytest.raises(ValidationError):
        Settings()


def test_settings_rejects_unknown_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KPA_ENV", "uat")  # invalid
    monkeypatch.setenv("KPA_LOG_LEVEL", "INFO")
    monkeypatch.setenv("KPA_LOG_FORMAT", "text")
    monkeypatch.setenv("KPA_SERVICE_NAME", "kpa-api")

    with pytest.raises(ValidationError):
        Settings()


def test_settings_defaults_when_optional_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    # Required vars only; optional vars take defaults.
    for k in ("KPA_LOG_LEVEL", "KPA_LOG_FORMAT"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("KPA_ENV", "local")
    monkeypatch.setenv("KPA_SERVICE_NAME", "kpa-api")

    settings = Settings()

    assert settings.log_level == "INFO"
    assert settings.log_format == "text"
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `api/`):
```bash
uv run pytest tests/unit/test_settings.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'kpa.settings'`.

- [ ] **Step 3: Implement settings**

Create `api/src/kpa/settings.py`:
```python
"""Application settings, sourced from environment variables.

Settings are validated at startup; the app refuses to boot on invalid input.
"""

from __future__ import annotations

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["local", "dev", "staging", "prod"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
LogFormat = Literal["text", "json"]


class Settings(BaseSettings):
    """Service-wide configuration.

    Backed by environment variables prefixed with `KPA_`.
    """

    model_config = SettingsConfigDict(
        env_prefix="KPA_",
        env_file=None,  # loaded explicitly via uv run --env-file in dev
        case_sensitive=False,
        extra="ignore",
    )

    env: Environment
    service_name: str
    log_level: LogLevel = "INFO"
    log_format: LogFormat = "text"
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
uv run pytest tests/unit/test_settings.py -v
```
Expected: PASS — 4 passed.

- [ ] **Step 5: Lint + type-check**

Run:
```bash
uv run ruff check src/ tests/
uv run mypy
```
Expected: both exit 0.

- [ ] **Step 6: Commit**

```bash
git add api/src/kpa/settings.py api/tests/unit/test_settings.py
git commit -m "feat(api): add Settings backed by env vars with validation"
```

---

### Task 3: App factory + health route

**Files:**
- Create: `api/src/kpa/routes/__init__.py`
- Create: `api/src/kpa/routes/health.py`
- Create: `api/src/kpa/app_factory.py`
- Create: `api/src/kpa/main.py`
- Test: `api/tests/conftest.py`
- Test: `api/tests/unit/test_health.py`

- [ ] **Step 1: Write the failing test**

Create `api/tests/conftest.py`:
```python
"""Shared test fixtures."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from kpa.app_factory import create_app


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """A TestClient bound to a freshly created app with deterministic settings."""

    monkeypatch.setenv("KPA_ENV", "local")
    monkeypatch.setenv("KPA_SERVICE_NAME", "kpa-api")
    monkeypatch.setenv("KPA_LOG_LEVEL", "INFO")
    monkeypatch.setenv("KPA_LOG_FORMAT", "text")

    app = create_app()
    with TestClient(app) as c:
        yield c
```

Create `api/tests/unit/test_health.py`:
```python
"""Tests for the health endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "kpa-api"
    assert "version" in body
    assert "env" in body
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
uv run pytest tests/unit/test_health.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'kpa.app_factory'`.

- [ ] **Step 3: Implement the health route**

Create `api/src/kpa/routes/__init__.py`: (empty file)

Create `api/src/kpa/routes/health.py`:
```python
"""Health endpoint.

This is a liveness check only — no downstream dependency probes.
DB/Redis readiness probes land in a later plan.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

from kpa import __version__
from kpa.settings import Environment, Settings

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    env: Environment


@router.get("/health", response_model=HealthResponse, tags=["meta"])
def health(request: Request) -> HealthResponse:
    # Settings is parsed once at app startup and stored on app.state;
    # don't re-parse env vars per request.
    settings: Settings = request.app.state.settings
    return HealthResponse(
        status="ok",
        service=settings.service_name,
        version=__version__,
        env=settings.env,
    )
```

- [ ] **Step 4: Implement the app factory**

Create `api/src/kpa/app_factory.py`:
```python
"""FastAPI application factory.

`create_app()` builds a fresh app on every call so tests get isolation.
"""

from __future__ import annotations

from fastapi import FastAPI

from kpa import __version__
from kpa.routes import health
from kpa.settings import Settings


def create_app() -> FastAPI:
    settings = Settings()  # validated; raises on misconfiguration
    app = FastAPI(
        title="Khan Placement Agency API",
        version=__version__,
        openapi_url="/openapi.json",
    )
    app.state.settings = settings
    app.include_router(health.router)
    return app
```

- [ ] **Step 5: Implement the main entrypoint**

Create `api/src/kpa/main.py`:
```python
"""Uvicorn entrypoint.

Run locally:
    uv run uvicorn kpa.main:app --reload --port 8000
"""

from __future__ import annotations

from kpa.app_factory import create_app

app = create_app()
```

- [ ] **Step 6: Run test to verify it passes**

Run:
```bash
uv run pytest tests/unit/test_health.py -v
```
Expected: PASS — 1 passed.

- [ ] **Step 7: Smoke-test the running server**

Run (in one terminal):
```bash
KPA_ENV=local KPA_SERVICE_NAME=kpa-api uv run uvicorn kpa.main:app --port 8000
```

In another terminal:
```bash
curl -s http://127.0.0.1:8000/health | python -m json.tool
```
Expected: JSON body with `"status": "ok"`, `"service": "kpa-api"`, `"version": "0.1.0"`, `"env": "local"`.

Then `Ctrl-C` the uvicorn process.

- [ ] **Step 8: Lint + type-check**

Run:
```bash
uv run ruff check src/ tests/
uv run mypy
```
Expected: both exit 0.

- [ ] **Step 9: Commit**

```bash
git add api/src/kpa/app_factory.py api/src/kpa/main.py api/src/kpa/routes/__init__.py api/src/kpa/routes/health.py api/tests/conftest.py api/tests/unit/test_health.py
git commit -m "feat(api): add app factory and /health endpoint"
```

---

### Task 4: Request ID middleware

**Files:**
- Create: `api/src/kpa/middleware/__init__.py`
- Create: `api/src/kpa/middleware/request_id.py`
- Modify: `api/src/kpa/app_factory.py` (add the middleware)
- Test: `api/tests/unit/test_request_id.py`

- [ ] **Step 1: Write the failing test**

Create `api/tests/unit/test_request_id.py`:
```python
"""Tests for the request-id middleware."""

from __future__ import annotations

import re

from fastapi.testclient import TestClient

UUID_V4 = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


def test_request_id_assigned_when_missing(client: TestClient) -> None:
    response = client.get("/health")

    request_id = response.headers.get("x-request-id")
    assert request_id is not None
    assert UUID_V4.match(request_id), f"not a uuid4: {request_id}"


def test_request_id_echoed_when_provided(client: TestClient) -> None:
    provided = "11111111-2222-4333-8444-555555555555"

    response = client.get("/health", headers={"X-Request-Id": provided})

    assert response.headers["x-request-id"] == provided


def test_request_id_rejected_when_malformed(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-Id": "not-a-uuid"})

    # Malformed ids are replaced with a fresh uuid4, not propagated.
    echoed = response.headers["x-request-id"]
    assert echoed != "not-a-uuid"
    assert UUID_V4.match(echoed)
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
uv run pytest tests/unit/test_request_id.py -v
```
Expected: FAIL — `x-request-id` header is missing.

- [ ] **Step 3: Implement the middleware**

Create `api/src/kpa/middleware/__init__.py`: (empty file)

Create `api/src/kpa/middleware/request_id.py`:
```python
"""Request-ID middleware.

Generates a uuid4 per request (or accepts a client-supplied one if it's a valid
uuid4) and exposes it on `request.state.request_id` as well as the response
`X-Request-Id` header. The id is the primary correlation handle in logs.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

HEADER = "x-request-id"
_UUID_V4_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _looks_like_uuid4(value: str) -> bool:
    return bool(_UUID_V4_RE.match(value))


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        incoming = request.headers.get(HEADER)
        request_id = incoming if incoming and _looks_like_uuid4(incoming) else str(uuid.uuid4())
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers[HEADER] = request_id
        return response
```

- [ ] **Step 4: Register the middleware**

Modify `api/src/kpa/app_factory.py`:
```python
"""FastAPI application factory.

`create_app()` builds a fresh app on every call so tests get isolation.
"""

from __future__ import annotations

from fastapi import FastAPI

from kpa import __version__
from kpa.middleware.request_id import RequestIdMiddleware
from kpa.routes import health
from kpa.settings import Settings


def create_app() -> FastAPI:
    settings = Settings()  # validated; raises on misconfiguration
    app = FastAPI(
        title="Khan Placement Agency API",
        version=__version__,
        openapi_url="/openapi.json",
    )
    app.state.settings = settings
    app.add_middleware(RequestIdMiddleware)
    app.include_router(health.router)
    return app
```

- [ ] **Step 5: Run test to verify it passes**

Run:
```bash
uv run pytest tests/unit/test_request_id.py -v
```
Expected: PASS — 3 passed.

- [ ] **Step 6: Lint + type-check**

Run:
```bash
uv run ruff check src/ tests/
uv run mypy
```
Expected: both exit 0.

- [ ] **Step 7: Commit**

```bash
git add api/src/kpa/middleware/__init__.py api/src/kpa/middleware/request_id.py api/src/kpa/app_factory.py api/tests/unit/test_request_id.py
git commit -m "feat(api): add X-Request-Id middleware with uuid4 validation"
```

---

### Task 5: Structured logging via structlog

**Files:**
- Create: `api/src/kpa/observability/__init__.py`
- Create: `api/src/kpa/observability/logging.py`
- Modify: `api/src/kpa/app_factory.py`
- Test: `api/tests/unit/test_logging.py`

- [ ] **Step 1: Write the failing test**

Create `api/tests/unit/test_logging.py`:
```python
"""Tests for the logging configuration."""

from __future__ import annotations

import logging

import pytest
import structlog

from kpa.observability.logging import configure_logging


def test_configure_logging_text_format_renders_key_equals_value(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KPA_ENV", "local")
    monkeypatch.setenv("KPA_SERVICE_NAME", "kpa-api")
    monkeypatch.setenv("KPA_LOG_LEVEL", "INFO")
    monkeypatch.setenv("KPA_LOG_FORMAT", "text")

    configure_logging()
    log = structlog.get_logger("test")
    log.info("hello", user_id="u-1", path="/health")

    captured = capsys.readouterr().out
    # KeyValueRenderer uses repr() for values, so strings are quoted.
    # Assert on substrings to stay renderer-quoting-agnostic.
    assert "hello" in captured
    assert "user_id" in captured and "u-1" in captured
    assert "path" in captured and "/health" in captured


def test_configure_logging_respects_log_level(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KPA_ENV", "local")
    monkeypatch.setenv("KPA_SERVICE_NAME", "kpa-api")
    monkeypatch.setenv("KPA_LOG_LEVEL", "WARNING")
    monkeypatch.setenv("KPA_LOG_FORMAT", "text")

    configure_logging()
    log = structlog.get_logger("test")
    log.info("should-not-appear")
    log.warning("should-appear")

    captured = capsys.readouterr().out
    assert "should-not-appear" not in captured
    assert "should-appear" in captured


def test_configure_logging_does_not_stack_handlers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KPA_ENV", "local")
    monkeypatch.setenv("KPA_SERVICE_NAME", "kpa-api")
    monkeypatch.setenv("KPA_LOG_LEVEL", "INFO")
    monkeypatch.setenv("KPA_LOG_FORMAT", "text")

    configure_logging()
    configure_logging()
    configure_logging()

    # Only one handler regardless of how many times configure_logging() runs.
    assert len(logging.getLogger().handlers) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
uv run pytest tests/unit/test_logging.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'kpa.observability'`.

- [ ] **Step 3: Implement the logging module**

Create `api/src/kpa/observability/__init__.py`: (empty file)

Create `api/src/kpa/observability/logging.py`:
```python
"""Structured logging configuration.

Plain-text `key=value` output by default, compatible with Fluent Bit + ES.
JSON output is available via KPA_LOG_FORMAT=json for environments that prefer it.
"""

from __future__ import annotations

import logging
import sys
from typing import Final

import structlog

from kpa.settings import Settings

_LEVEL_MAP: Final[dict[str, int]] = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def configure_logging() -> None:
    """Initialize stdlib + structlog. Idempotent: handlers do not stack.

    Reconfigures structlog every call so the logger factory binds to the
    current ``sys.stdout`` (important for tests that patch stdout).
    """
    settings = Settings()
    level = _LEVEL_MAP[settings.log_level]

    # Stdlib root: replace any existing handlers with a single stdout handler.
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    root.addHandler(handler)
    root.setLevel(level)

    renderer: structlog.types.Processor
    if settings.log_format == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.processors.KeyValueRenderer(
            key_order=["timestamp", "level", "logger", "event"],
            drop_missing=True,
        )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=False,
    )
```

- [ ] **Step 4: Wire it into the app factory**

Modify `api/src/kpa/app_factory.py`:
```python
"""FastAPI application factory.

`create_app()` builds a fresh app on every call so tests get isolation.
"""

from __future__ import annotations

from fastapi import FastAPI

from kpa import __version__
from kpa.middleware.request_id import RequestIdMiddleware
from kpa.observability.logging import configure_logging
from kpa.routes import health
from kpa.settings import Settings


def create_app() -> FastAPI:
    settings = Settings()  # validated; raises on misconfiguration
    configure_logging()
    app = FastAPI(
        title="Khan Placement Agency API",
        version=__version__,
        openapi_url="/openapi.json",
    )
    app.state.settings = settings
    app.add_middleware(RequestIdMiddleware)
    app.include_router(health.router)
    return app
```

- [ ] **Step 5: Run test to verify it passes**

Run:
```bash
uv run pytest tests/unit/test_logging.py -v
```
Expected: PASS — 3 passed.

- [ ] **Step 6: Full test suite + lint + types**

Run:
```bash
uv run pytest -v
uv run ruff check src/ tests/
uv run mypy
```
Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add api/src/kpa/observability/__init__.py api/src/kpa/observability/logging.py api/src/kpa/app_factory.py api/tests/unit/test_logging.py
git commit -m "feat(api): add structlog-based key=value logging with json option"
```

---

### Task 6: RFC 7807 error handler middleware

**Files:**
- Create: `api/src/kpa/middleware/error_handler.py`
- Modify: `api/src/kpa/app_factory.py`
- Test: `api/tests/unit/test_error_handler.py`

- [ ] **Step 1: Write the failing test**

Create `api/tests/unit/test_error_handler.py`:
```python
"""Tests for the RFC 7807 error handler."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from kpa.app_factory import create_app


@pytest.fixture
def app_with_boom(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("KPA_ENV", "local")
    monkeypatch.setenv("KPA_SERVICE_NAME", "kpa-api")
    monkeypatch.setenv("KPA_LOG_LEVEL", "INFO")
    monkeypatch.setenv("KPA_LOG_FORMAT", "text")

    app = create_app()

    @app.get("/boom-unhandled")
    def boom_unhandled() -> None:
        raise RuntimeError("kaboom")

    @app.get("/boom-http")
    def boom_http() -> None:
        raise HTTPException(status_code=404, detail="missing")

    return TestClient(app, raise_server_exceptions=False)


def test_unhandled_exception_returns_problem_json(app_with_boom: TestClient) -> None:
    response = app_with_boom.get("/boom-unhandled")

    assert response.status_code == 500
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["title"] == "Internal Server Error"
    assert body["status"] == 500
    assert body["type"] == "about:blank"
    assert body["request_id"] == response.headers["x-request-id"]
    # Internal error detail must not leak.
    assert "kaboom" not in body["detail"]


def test_http_exception_returns_problem_json(app_with_boom: TestClient) -> None:
    response = app_with_boom.get("/boom-http")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["status"] == 404
    assert body["title"] == "Not Found"
    assert body["detail"] == "missing"
    assert body["request_id"] == response.headers["x-request-id"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
uv run pytest tests/unit/test_error_handler.py -v
```
Expected: FAIL — current handler returns FastAPI's default `{"detail": "..."}` shape.

- [ ] **Step 3: Implement the error handlers**

Create `api/src/kpa/middleware/error_handler.py`:
```python
"""RFC 7807 problem-detail error handlers.

Replaces FastAPI's default JSON error shape with `application/problem+json`
responses that include the request id for traceability.
"""

from __future__ import annotations

from http import HTTPStatus
from typing import Any

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

_log = structlog.get_logger(__name__)


def _problem(
    *,
    status: int,
    title: str,
    detail: str,
    request_id: str,
    extra: dict[str, Any] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": "about:blank",
        "title": title,
        "status": status,
        "detail": detail,
        "request_id": request_id,
    }
    if extra:
        body.update(extra)
    return JSONResponse(
        status_code=status,
        content=body,
        media_type="application/problem+json",
    )


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def _handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
        status = exc.status_code
        title = HTTPStatus(status).phrase if status in HTTPStatus._value2member_map_ else "Error"
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        request_id = getattr(request.state, "request_id", "unknown")
        return _problem(status=status, title=title, detail=detail, request_id=request_id)

    @app.exception_handler(Exception)
    async def _handle_unhandled(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "unknown")
        _log.exception(
            "unhandled-exception",
            request_id=request_id,
            path=request.url.path,
            method=request.method,
        )
        return _problem(
            status=500,
            title="Internal Server Error",
            detail="An unexpected error occurred.",
            request_id=request_id,
        )
```

- [ ] **Step 4: Wire it into the app factory**

Modify `api/src/kpa/app_factory.py`:
```python
"""FastAPI application factory.

`create_app()` builds a fresh app on every call so tests get isolation.
"""

from __future__ import annotations

from fastapi import FastAPI

from kpa import __version__
from kpa.middleware.error_handler import register_error_handlers
from kpa.middleware.request_id import RequestIdMiddleware
from kpa.observability.logging import configure_logging
from kpa.routes import health
from kpa.settings import Settings


def create_app() -> FastAPI:
    settings = Settings()  # validated; raises on misconfiguration
    configure_logging()
    app = FastAPI(
        title="Khan Placement Agency API",
        version=__version__,
        openapi_url="/openapi.json",
    )
    app.state.settings = settings
    app.add_middleware(RequestIdMiddleware)
    register_error_handlers(app)
    app.include_router(health.router)
    return app
```

- [ ] **Step 5: Run test to verify it passes**

Run:
```bash
uv run pytest tests/unit/test_error_handler.py -v
```
Expected: PASS — 2 passed.

- [ ] **Step 6: Full test suite + lint + types**

Run:
```bash
uv run pytest -v
uv run ruff check src/ tests/
uv run mypy
```
Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add api/src/kpa/middleware/error_handler.py api/src/kpa/app_factory.py api/tests/unit/test_error_handler.py
git commit -m "feat(api): return RFC 7807 problem+json error responses"
```

---

### Task 7: Multi-stage Dockerfile

**Files:**
- Create: `api/Dockerfile`
- Create: `api/.dockerignore`

- [ ] **Step 1: Write the Dockerfile**

Create `api/Dockerfile`:
```dockerfile
# syntax=docker/dockerfile:1.7

# ---- Builder ----------------------------------------------------------------
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv

# uv is distributed as a single binary; pin a specific minor for reproducibility.
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /usr/local/bin/uv

WORKDIR /app

# Install deps in a separate layer so app code changes don't bust the cache.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# Now install the project itself.
COPY src/ ./src/
RUN uv sync --frozen --no-dev

# ---- Runtime ----------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

RUN groupadd --system --gid 10001 kpa \
 && useradd --system --uid 10001 --gid kpa --home-dir /app --shell /usr/sbin/nologin kpa

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app/src /app/src

USER kpa
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; \
sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).status==200 else 1)"

CMD ["uvicorn", "kpa.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Add `.dockerignore`**

Create `api/.dockerignore`:
```
.venv/
__pycache__/
*.pyc
.pytest_cache/
.mypy_cache/
.ruff_cache/
.env
.coverage
htmlcov/
dist/
build/
*.egg-info/
tests/
.git/
.github/
docs/
README.md
```

- [ ] **Step 3: Build the image**

Run (from `api/`):
```bash
docker build -t kpa-api:dev .
```
Expected: build succeeds; final line `naming to docker.io/library/kpa-api:dev done`.

- [ ] **Step 4: Run the container and verify /health**

Run:
```bash
docker run --rm -d --name kpa-api-smoke \
  -e KPA_ENV=local -e KPA_SERVICE_NAME=kpa-api \
  -e KPA_LOG_LEVEL=INFO -e KPA_LOG_FORMAT=text \
  -p 8000:8000 kpa-api:dev
sleep 2
curl -fsS http://127.0.0.1:8000/health
echo
docker stop kpa-api-smoke
```
Expected: a JSON object with `"status": "ok"` is printed, then the container stops cleanly.

- [ ] **Step 5: Commit**

```bash
git add api/Dockerfile api/.dockerignore
git commit -m "feat(api): add multi-stage Dockerfile with non-root runtime user"
```

---

### Task 8: GitHub Actions CI workflow

**Files:**
- Create: `.github/workflows/api-ci.yml`

- [ ] **Step 1: Write the workflow**

Create `.github/workflows/api-ci.yml`:
```yaml
name: api-ci

on:
  push:
    branches: ["**"]
    paths:
      - "api/**"
      - ".github/workflows/api-ci.yml"
  pull_request:
    paths:
      - "api/**"
      - ".github/workflows/api-ci.yml"

defaults:
  run:
    working-directory: api

jobs:
  lint-type-test:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v3
        with:
          version: "0.5.x"

      - name: Set up Python
        run: uv python install 3.12

      - name: Install dependencies
        run: uv sync --frozen

      - name: Lint
        run: uv run ruff check src/ tests/

      - name: Format check
        run: uv run ruff format --check src/ tests/

      - name: Type check
        run: uv run mypy

      - name: Test
        env:
          KPA_ENV: local
          KPA_SERVICE_NAME: kpa-api
          KPA_LOG_LEVEL: INFO
          KPA_LOG_FORMAT: text
        run: uv run pytest -v

  build-image:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    needs: lint-type-test
    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build image
        uses: docker/build-push-action@v6
        with:
          context: api
          push: false
          tags: kpa-api:ci
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

- [ ] **Step 2: Validate the YAML locally**

Run (from repo root):
```bash
python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/api-ci.yml')); print('ok')"
```
Expected: prints `ok`.

- [ ] **Step 3: Confirm format check would pass locally**

Run (from `api/`):
```bash
uv run ruff format --check src/ tests/
```
Expected: exit 0. If it fails, run `uv run ruff format src/ tests/` and stage the changes.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/api-ci.yml
git commit -m "ci(api): add ruff/mypy/pytest workflow and docker build job"
```

---

### Task 9: API README

**Files:**
- Create: `api/README.md`

- [ ] **Step 1: Write the README**

Create `api/README.md`:
````markdown
# KPA API

FastAPI service for the Khan Placement Agency platform. This directory contains
the backend foundations only — DB layer, auth, and domain code land in
follow-on plans.

## Requirements

- Python 3.12
- [uv](https://docs.astral.sh/uv/) 0.5+
- Docker (for container builds + future local Postgres/Redis)

## First-time setup

```bash
cd api
uv sync
cp .env.example .env   # adjust as needed
```

## Run locally

```bash
KPA_ENV=local KPA_SERVICE_NAME=kpa-api uv run uvicorn kpa.main:app --reload --port 8000
```

Then:

```bash
curl http://127.0.0.1:8000/health
```

## Tests

```bash
uv run pytest -v
```

## Lint, format, type-check

```bash
uv run ruff check src/ tests/
uv run ruff format src/ tests/
uv run mypy
```

## Container build

```bash
docker build -t kpa-api:dev .
docker run --rm -e KPA_ENV=local -e KPA_SERVICE_NAME=kpa-api \
  -e KPA_LOG_LEVEL=INFO -e KPA_LOG_FORMAT=text \
  -p 8000:8000 kpa-api:dev
```

## Configuration

All settings are read from environment variables prefixed `KPA_`:

| Variable           | Required | Default | Purpose                         |
| ------------------ | -------- | ------- | ------------------------------- |
| `KPA_ENV`          | yes      | —       | `local` \| `dev` \| `staging` \| `prod` |
| `KPA_SERVICE_NAME` | yes      | —       | Reported in `/health`           |
| `KPA_LOG_LEVEL`    | no       | `INFO`  | Stdlib log level                |
| `KPA_LOG_FORMAT`   | no       | `text`  | `text` (key=value) or `json`    |

The service refuses to boot if required variables are missing or invalid.

## Project layout

```
api/
├── src/kpa/
│   ├── app_factory.py        # create_app() — middlewares + routes
│   ├── main.py               # uvicorn entry point
│   ├── settings.py
│   ├── middleware/
│   │   ├── request_id.py     # X-Request-Id propagation
│   │   └── error_handler.py  # RFC 7807 problem+json
│   ├── observability/
│   │   └── logging.py        # structlog config
│   └── routes/
│       └── health.py         # GET /health
└── tests/
```
````

- [ ] **Step 2: Commit**

```bash
git add api/README.md
git commit -m "docs(api): add backend README"
```

---

## Final check

After all tasks are complete, run the full local pipeline once from `api/`:

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy
uv run pytest -v
docker build -t kpa-api:dev .
```

All five must exit 0. Then push the branch and confirm `api-ci` is green on GitHub.

---

## Out of scope (intentionally — handled by later plans)

- Database access (SQLAlchemy async session, Alembic migrations, users table) — next plan.
- Auth (OAuth2 callbacks, JWT, MFA, /me) — plan after that.
- docker-compose with Postgres and Redis for local dev — bundled with the DB plan.
- Helm chart / Terraform — separate IaC plan.
- Flutter app scaffold — separate frontend plan.

## Spec traceback

This plan covers the subset of `IMPLEMENTATION_SPEC.md` §4 (FastAPI module
layout, conventions) and §12 (observability — logs, request id) needed to land
P0 "Foundations" from §13 of the spec. It deliberately does **not** cover §5
(data model), §9 (auth), §11 (infrastructure beyond a buildable image), or §10
(API endpoint surface beyond /health), since those require additional plans.
