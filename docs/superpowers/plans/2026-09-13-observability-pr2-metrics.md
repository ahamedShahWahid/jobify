# Observability PR 2 — Metrics on `prometheus_client` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the hand-rolled in-process metrics exporter with `prometheus_client` (multiprocess-capable), record HTTP + error counters from the request/error paths, and give the worker its own opt-in scrape endpoint.

**Architecture:** One declaration module `core/src/jobify/observability/metrics.py` owns every metric and `build_registry()` (fresh `MultiProcessCollector` registry when `PROMETHEUS_MULTIPROC_DIR` is set, else the default `REGISTRY`). The API's `RequestContextMiddleware` (added in PR 1) absorbs `MetricsMiddleware`'s recording; error handlers bump two counters; `/metrics` renders `build_registry()` plus a per-scrape DB-backed collector. The worker starts `prometheus_client.start_http_server` from Celery's `worker_init` when `JOBIFY_WORKER_METRICS_PORT` is set and marks dead prefork children. External-call and task metrics are PR 3 (they are declared there, next to their first use).

**Tech Stack:** Python 3.12, prometheus-client 0.26, FastAPI 0.115 / Starlette 0.46, Celery 5.6, structlog 24.4, pytest (asyncio_mode=auto).

**Spec:** `docs/superpowers/specs/2026-09-13-backend-observability-foundation-design.md` ("Rollout → PR 2"; "Metric catalog").

## Global Constraints

- **Only new dependency:** `prometheus-client>=0.26,<1` in `core/pyproject.toml` (`uv add --package jobify-core`). 0.26 is required: `start_http_server` returns `(server, thread)`.
- **Every metric is declared in `core/src/jobify/observability/metrics.py`** — nowhere else (the DB-backed async-work gauges are a per-scrape custom collector, not declared metrics).
- **Cardinality rule (verbatim from spec):** label values come only from closed sets — route templates, registered task names, literal service/operation strings, and `outcome ∈ {success, error, retry, failure}`. Never ids, raw paths or messages.
- **Metric names and labels (verbatim from spec):** `http_requests_total{method,status}` (counter), `http_request_duration_seconds{method,route}` (histogram, buckets `(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5)`), `jobify_unhandled_exceptions_total{route}` (counter), `jobify_http_validation_failures_total{route}` (counter), `jobify_async_items{queue,status}`, `jobify_async_oldest_actionable_age_seconds{queue}`, `jobify_async_metrics_up` (gauges via collector).
- **`_created` series disabled** (`prometheus_client.disable_created_metrics()` in the metrics module).
- **`/metrics` content type stays** `text/plain; version=0.0.4; charset=utf-8` (`CONTENT_TYPE_PLAIN_0_0_4`); bearer-token check unchanged.
- **Multiprocess directories are per service** (API and worker must never share one — `MultiProcessCollector` would merge their series) and are wiped on start.
- **Worker metrics server is off unless `JOBIFY_WORKER_METRICS_PORT` is set**; binds `JOBIFY_WORKER_METRICS_HOST` (default `127.0.0.1` — it has no auth). Failing to bind logs ERROR and the worker keeps processing tasks.
- **New middleware must be pure ASGI**; structlog only in `src`.
- Tests assert counter **deltas** via `prometheus_client.REGISTRY.get_sample_value(...)` (the default registry is process-global; never assume zero).
- Workers read `settings` from `jobify_worker.celery_app` (worker/CLAUDE.md).
- All commands from repo root. CI gate verbatim: `uv run ruff check core/src api/src worker/src tests` · `uv run ruff format --check core/src api/src worker/src tests` · `uv run mypy` · `uv run pytest -v -m "not integration and not eval"` · `uv run pytest -v -s -m eval` · `uv run pytest -v -m integration`.
- Commit trailer on every commit:
  ```
  Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01JSP8DPirBJicB72XTMVq3o
  ```
- Branch: `feat/observability-metrics` (created off `origin/main` @ `b690400`, which contains PR 1).

## File Structure

| File | Status | Responsibility |
|---|---|---|
| `core/pyproject.toml`, `uv.lock` | modify | `prometheus-client` dependency |
| `core/src/jobify/observability/metrics.py` | create | metric declarations, `multiprocess_enabled()`, `build_registry()` |
| `tests/unit/test_observability_metrics.py` | create | registry selection, no `_created`, multiprocess aggregation |
| `api/src/jobify_api/middleware/request_context.py` | modify | record `http_requests_total` + duration |
| `api/src/jobify_api/middleware/metrics.py`, `api/src/jobify_api/metrics.py` | delete | hand-rolled substrate |
| `api/src/jobify_api/app_factory.py` | modify | drop `MetricsMiddleware` |
| `api/src/jobify_api/middleware/error_handler.py` | modify | unhandled + validation counters |
| `tests/unit/test_metrics.py` | rewrite | middleware recording semantics |
| `tests/unit/test_error_handler.py` | modify | counter tests |
| `api/src/jobify_api/operational_metrics.py` | rewrite | `AsyncWorkSnapshot`, `fetch_async_work_snapshot`, `AsyncWorkCollector` |
| `api/src/jobify_api/routes/metrics.py` | rewrite | render `build_registry()` + collector |
| `tests/unit/test_metrics_route.py` | create | exposition, auth, DB-down, collector |
| `tests/integration/test_operational_metrics.py` | modify | float exposition values |
| `worker/src/jobify_worker/settings.py` | modify | `worker_metrics_port`, `worker_metrics_host` |
| `worker/src/jobify_worker/observability.py` | modify | `worker_init` server + `worker_process_shutdown` mark-dead |
| `tests/unit/worker/test_worker_metrics.py` | create | server start/skip/bind-failure, mark-dead |
| `scripts/start-all.sh` | modify | per-service multiprocess dirs, worker metrics port |
| `api/CLAUDE.md`, `core/CLAUDE.md`, `worker/CLAUDE.md`, `api/README.md`, `worker/README.md` | modify | invariants + env vars |

---

### Task 1: `prometheus_client` dependency + metrics declaration module

**Files:**
- Modify: `core/pyproject.toml`, `uv.lock` (via `uv add`)
- Create: `core/src/jobify/observability/metrics.py`
- Create: `tests/unit/test_observability_metrics.py`

**Interfaces:**
- Consumes: nothing.
- Produces (exact names later tasks import from `jobify.observability.metrics`):
  - `HTTP_REQUESTS: Counter` labels `("method", "status")`
  - `HTTP_REQUEST_DURATION: Histogram` labels `("method", "route")`
  - `UNHANDLED_EXCEPTIONS: Counter` labels `("route",)`
  - `VALIDATION_FAILURES: Counter` labels `("route",)`
  - `multiprocess_enabled() -> bool`
  - `build_registry() -> CollectorRegistry`

- [ ] **Step 1: Add the dependency**

Run: `uv add --package jobify-core "prometheus-client>=0.26,<1"`
Expected: `core/pyproject.toml` dependencies gain `"prometheus-client>=0.26,<1"`, `uv.lock` updated. Verify: `uv run python -c "import importlib.metadata as m; print(m.version('prometheus-client'))"` prints `0.26.x` or newer `<1`.

- [ ] **Step 2: Write the failing tests**

`tests/unit/test_observability_metrics.py`:

```python
"""jobify.observability.metrics — registry selection and multiprocess aggregation.

Multiprocess mode is decided when prometheus_client is imported (it reads
PROMETHEUS_MULTIPROC_DIR then), so the multiprocess case runs in subprocesses.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
from prometheus_client import REGISTRY, generate_latest

from jobify.observability import metrics


def test_single_process_uses_default_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PROMETHEUS_MULTIPROC_DIR", raising=False)

    assert metrics.multiprocess_enabled() is False
    assert metrics.build_registry() is REGISTRY


def test_declared_metrics_render_without_created_series() -> None:
    metrics.HTTP_REQUESTS.labels(method="GET", status="200").inc()
    metrics.HTTP_REQUEST_DURATION.labels(method="GET", route="/_obs/{item_id}").observe(0.02)

    body = generate_latest(REGISTRY).decode()

    assert "# TYPE http_requests_total counter" in body
    assert "# TYPE http_request_duration_seconds histogram" in body
    assert "# TYPE jobify_unhandled_exceptions_total counter" in body
    assert "# TYPE jobify_http_validation_failures_total counter" in body
    assert 'le="0.025",method="GET",route="/_obs/{item_id}"' in body
    assert "_created" not in body


def test_multiprocess_registry_aggregates_across_processes(tmp_path: Path) -> None:
    env = {**os.environ, "PROMETHEUS_MULTIPROC_DIR": str(tmp_path)}
    writer = textwrap.dedent(
        """
        import sys
        from jobify.observability import metrics
        metrics.HTTP_REQUESTS.labels(method="GET", status="200").inc(int(sys.argv[1]))
        """
    )
    for amount in ("2", "3"):
        subprocess.run([sys.executable, "-c", writer, amount], env=env, check=True)

    reader = textwrap.dedent(
        """
        from prometheus_client import REGISTRY, generate_latest
        from jobify.observability import metrics
        registry = metrics.build_registry()
        assert metrics.multiprocess_enabled()
        assert registry is not REGISTRY
        print(generate_latest(registry).decode())
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", reader], env=env, check=True, capture_output=True, text=True
    )

    assert 'http_requests_total{method="GET",status="200"} 5.0' in result.stdout
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_observability_metrics.py -v`
Expected: collection ERROR `ImportError: cannot import name 'metrics' from 'jobify.observability'`.

- [ ] **Step 4: Implement the module**

`core/src/jobify/observability/metrics.py`:

```python
"""Prometheus metrics — the single declaration site for every metric.

Declare new metrics HERE, never inline in routes/tasks: one module keeps names,
labels and the cardinality rule reviewable in one place.

**Cardinality rule:** label values come only from closed sets — route
templates, registered task names, literal service/operation strings, and
``outcome ∈ {success, error, retry, failure}``. Never ids, raw paths or
messages.

**Multiprocess mode.** When ``PROMETHEUS_MULTIPROC_DIR`` is set *before*
``prometheus_client`` is imported, every process writes its values to
memory-mapped files in that directory and :func:`build_registry` returns a fresh
registry whose ``MultiProcessCollector`` aggregates them at scrape time. Each
service needs its OWN directory (a shared one merges API and worker series),
wiped on start. Unset (tests, single-process dev) → the default ``REGISTRY``.
"""

from __future__ import annotations

import os
from typing import Final

from prometheus_client import (
    REGISTRY,
    CollectorRegistry,
    Counter,
    Histogram,
    disable_created_metrics,
    multiprocess,
)

# `_created` companion series double every counter/histogram for no operational
# value here (multiprocess mode never emits them anyway).
disable_created_metrics()

_HTTP_DURATION_BUCKETS: Final[tuple[float, ...]] = (0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5)

HTTP_REQUESTS: Final = Counter(
    "http_requests",
    "Total HTTP requests by method and status code.",
    ("method", "status"),
)
HTTP_REQUEST_DURATION: Final = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration by matched route template.",
    ("method", "route"),
    buckets=_HTTP_DURATION_BUCKETS,
)
UNHANDLED_EXCEPTIONS: Final = Counter(
    "jobify_unhandled_exceptions",
    "Unhandled exceptions that produced a 500, by matched route template.",
    ("route",),
)
VALIDATION_FAILURES: Final = Counter(
    "jobify_http_validation_failures",
    "Request validation failures (422), by matched route template.",
    ("route",),
)


def multiprocess_enabled() -> bool:
    """True when this process runs in prometheus_client multiprocess mode."""
    return bool(os.environ.get("PROMETHEUS_MULTIPROC_DIR"))


def build_registry() -> CollectorRegistry:
    """The registry a scrape should render (see module docstring)."""
    if not multiprocess_enabled():
        return REGISTRY
    registry = CollectorRegistry()
    multiprocess.MultiProcessCollector(registry)
    return registry
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_observability_metrics.py -v`
Expected: 3 PASS.

- [ ] **Step 6: Lint, type-check, full unit suite, commit**

Run: `uv run ruff check core/src tests && uv run ruff format core/src tests && uv run mypy && uv run pytest -q -m "not integration and not eval"`
Expected: clean; all pass.

```bash
git add core/pyproject.toml uv.lock core/src/jobify/observability/metrics.py tests/unit/test_observability_metrics.py
git commit -m "core: prometheus_client metrics declaration module with multiprocess registry

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01JSP8DPirBJicB72XTMVq3o"
```

---

### Task 2: Record HTTP + error metrics; delete the hand-rolled substrate

**Files:**
- Modify: `api/src/jobify_api/middleware/request_context.py`
- Delete: `api/src/jobify_api/middleware/metrics.py`, `api/src/jobify_api/metrics.py`
- Modify: `api/src/jobify_api/app_factory.py` (import + the `MetricsMiddleware` block)
- Modify: `api/src/jobify_api/middleware/error_handler.py`
- Rewrite: `tests/unit/test_metrics.py`
- Modify: `tests/unit/test_error_handler.py` (append)
- Modify: `api/CLAUDE.md` (Middleware paragraph)

**Interfaces:**
- Consumes: `HTTP_REQUESTS`, `HTTP_REQUEST_DURATION`, `UNHANDLED_EXCEPTIONS`, `VALIDATION_FAILURES` (Task 1); `route_template` (PR 1, `jobify_api.middleware.request_context`).
- Produces: series `http_requests_total{method,status}`, `http_request_duration_seconds{method,route}`, `jobify_unhandled_exceptions_total{route}`, `jobify_http_validation_failures_total{route}` populated by real requests. **Breaks** (fixed in Task 3): `api/src/jobify_api/routes/metrics.py` imports `jobify_api.metrics.render_prometheus` — Task 2 must keep the app importable, so in this task replace that import/use with `generate_latest(build_registry()).decode()` as a minimal bridge (Task 3 rewrites the route fully).

- [ ] **Step 1: Rewrite the middleware metrics tests (failing)**

Replace the whole of `tests/unit/test_metrics.py` with:

```python
"""HTTP metrics recorded by RequestContextMiddleware (no DB, no app).

Status attribution: the real started status; 500 only when the app raised
before starting a response; nothing at all for a clean return with no response.
Counter values are process-global, so every assertion is a delta.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from prometheus_client import REGISTRY
from starlette.types import Message, Receive, Scope, Send

from jobify_api.middleware.request_context import RequestContextMiddleware


def _requests(method: str, status: str) -> float:
    value = REGISTRY.get_sample_value("http_requests_total", {"method": method, "status": status})
    return value or 0.0


def _durations(method: str, route: str) -> float:
    value = REGISTRY.get_sample_value(
        "http_request_duration_seconds_count", {"method": method, "route": route}
    )
    return value or 0.0


def _all_requests() -> float:
    return sum(
        sample.value
        for family in REGISTRY.collect()
        if family.name == "http_requests"
        for sample in family.samples
        if sample.name == "http_requests_total"
    )


async def _drive(app: object, *, method: str = "GET") -> None:
    scope: Scope = {"type": "http", "method": method}

    async def receive() -> Message:
        return {"type": "http.request"}

    async def send(_message: Message) -> None:
        return None

    await RequestContextMiddleware(app)(scope, receive, send)  # type: ignore[arg-type]


async def test_records_started_status_and_route_duration() -> None:
    before = _requests("GET", "204")
    before_duration = _durations("GET", "/_m/jobs/{job_id}")

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        scope["route"] = SimpleNamespace(path="/_m/jobs/{job_id}")
        await send({"type": "http.response.start", "status": 204})
        await send({"type": "http.response.body", "body": b""})

    await _drive(app)

    assert _requests("GET", "204") == before + 1
    assert _durations("GET", "/_m/jobs/{job_id}") == before_duration + 1


async def test_exception_before_response_records_500_and_reraises() -> None:
    before = _requests("GET", "500")

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        await _drive(app)

    assert _requests("GET", "500") == before + 1


async def test_clean_return_without_response_is_not_counted() -> None:
    before = _all_requests()

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        return  # no response.start emitted, no exception

    await _drive(app)

    assert _all_requests() == before


async def test_method_label_is_upper_cased() -> None:
    before = _requests("DELETE", "204")

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        await send({"type": "http.response.start", "status": 204})

    await _drive(app, method="delete")

    assert _requests("DELETE", "204") == before + 1
```

Append to `tests/unit/test_error_handler.py` (add `from prometheus_client import REGISTRY` to its imports; the `json_app` fixture already defines `/boom-unhandled/{item_id}` and `/validate/{item_id}`):

```python
def test_unhandled_exception_increments_counter(json_app: TestClient) -> None:
    labels = {"route": "/boom-unhandled/{item_id}"}
    before = REGISTRY.get_sample_value("jobify_unhandled_exceptions_total", labels) or 0.0

    json_app.get("/boom-unhandled/abc")

    assert REGISTRY.get_sample_value("jobify_unhandled_exceptions_total", labels) == before + 1


def test_validation_failure_increments_counter(json_app: TestClient) -> None:
    labels = {"route": "/validate/{item_id}"}
    before = REGISTRY.get_sample_value("jobify_http_validation_failures_total", labels) or 0.0

    json_app.post("/validate/7", json={"count": "nope"})

    assert REGISTRY.get_sample_value("jobify_http_validation_failures_total", labels) == before + 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_metrics.py tests/unit/test_error_handler.py -v`
Expected: the four middleware tests FAIL (counts unchanged — `assert 0.0 == 1.0`-style) except `test_clean_return_without_response_is_not_counted`, which passes already (it pins "nothing recorded"); both counter tests FAIL (`None == 1.0`).

- [ ] **Step 3: Record in `RequestContextMiddleware`**

In `api/src/jobify_api/middleware/request_context.py`:
- add import `from jobify.observability.metrics import HTTP_REQUEST_DURATION, HTTP_REQUESTS`;
- in the module docstring, after the "End:" bullet, add: `- **Metrics:** the same end point records ``http_requests_total{method,status}`` and ``http_request_duration_seconds{method,route}`` (this replaced the old ``MetricsMiddleware``; CORS stays outermost, so preflight short-circuits are not counted).`
- replace the `finally:` block with:

```python
        finally:
            # No status (e.g. client disconnect / CancelledError): nothing was
            # served — no access line and no metric sample.
            if status is not None:
                route = route_template(scope)
                method = str(scope.get("method", "")).upper()
                duration_seconds = max(perf_counter() - started_at, 0.0)
                HTTP_REQUESTS.labels(method=method, status=str(status)).inc()
                HTTP_REQUEST_DURATION.labels(method=method, route=route).observe(duration_seconds)
                user_id = state.get("current_user_id")
                _log.log(
                    _level_for(status, route),
                    "http.request",
                    method=method,
                    route=route,
                    status=status,
                    duration_ms=round(duration_seconds * 1000, 1),
                    user_id=str(user_id) if user_id is not None else None,
                )
```

- [ ] **Step 4: Count in the error handlers**

In `api/src/jobify_api/middleware/error_handler.py` add `from jobify.observability.metrics import UNHANDLED_EXCEPTIONS, VALIDATION_FAILURES`. In `_handle_validation_error`, compute `route = route_template(request.scope)` once, pass `route=route` to the log call, and add `VALIDATION_FAILURES.labels(route=route).inc()` before the `return`. In `_handle_unhandled`, likewise compute `route` once, use it in the log call, and add `UNHANDLED_EXCEPTIONS.labels(route=route).inc()` directly after `_log.exception(...)`.

- [ ] **Step 5: Delete the hand-rolled substrate and bridge the route**

- `git rm api/src/jobify_api/middleware/metrics.py api/src/jobify_api/metrics.py`
- `api/src/jobify_api/app_factory.py`: delete `from jobify_api.middleware.metrics import MetricsMiddleware` and the three-line comment + `app.add_middleware(MetricsMiddleware)`. Replace the CORS block's leading comment sentence "Added after RequestIdMiddleware so it wraps it (outermost)" with "Added last so it is outermost" (keep the rest of that comment).
- `api/src/jobify_api/routes/metrics.py` (bridge only; Task 3 rewrites it): replace `from jobify_api.metrics import render_prometheus` with `from prometheus_client import generate_latest` and `from jobify.observability.metrics import build_registry`; replace `process_metrics = render_prometheus()` with `process_metrics = generate_latest(build_registry()).decode()`; delete the handler's comment block about `_REQUEST_COUNTS` racing.

Run: `grep -rn "jobify_api.metrics\|middleware.metrics\|MetricsMiddleware\|render_prometheus\|record_request\|reset_metrics" core api worker tests scripts` — expected: only the comment/doc hits handled in Step 6 (none in code).

- [ ] **Step 6: Update `api/CLAUDE.md`**

In the "## Middleware — pure ASGI, not BaseHTTPMiddleware" paragraph:
- change the order to `ServerErrorMiddleware → CORS → RequestIdMiddleware → RequestContextMiddleware → ExceptionMiddleware (Starlette) → router`;
- replace the sentence starting `` `MetricsMiddleware` wraps `RequestIdMiddleware` `` (through "aren't counted.") with: `` `RequestContextMiddleware` also records `http_requests_total{method,status}` + `http_request_duration_seconds{method,route}` at the same point as the access line (metrics declared only in `jobify.observability.metrics`); CORS stays outermost, so preflight (OPTIONS) short-circuits aren't counted. ``
- replace `` `CORSMiddleware` mounted **after** both (outermost). `` with `` `CORSMiddleware` mounted last (outermost). ``

In the "## Error handling" paragraph's Logging sentence, append: `` `unhandled-exception` and `http.validation-failed` also bump `jobify_unhandled_exceptions_total{route}` / `jobify_http_validation_failures_total{route}`. ``

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_metrics.py tests/unit/test_error_handler.py tests/unit/test_request_context.py tests/unit/test_request_id.py -v`
Expected: all PASS. Then `uv run pytest -q -m "not integration and not eval"` and `uv run pytest -q -m integration` — all PASS except: `tests/integration/test_operational_metrics.py` may now fail on value formatting (`1` → `1.0` is Task 3's change; the bridge in Step 5 still renders the old async-work text, so it should still pass — if it fails, report it, do not edit that test here).

- [ ] **Step 8: Commit**

```bash
uv run ruff check api/src tests && uv run ruff format api/src tests && uv run mypy
git add -A api/src/jobify_api tests/unit/test_metrics.py tests/unit/test_error_handler.py api/CLAUDE.md
git commit -m "api: record HTTP and error metrics via prometheus_client; drop hand-rolled exporter

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01JSP8DPirBJicB72XTMVq3o"
```

---

### Task 3: `/metrics` on `prometheus_client` + DB-backed async-work collector

**Files:**
- Rewrite: `api/src/jobify_api/operational_metrics.py`
- Rewrite: `api/src/jobify_api/routes/metrics.py`
- Create: `tests/unit/test_metrics_route.py`
- Modify: `tests/integration/test_operational_metrics.py` (value assertions)

**Interfaces:**
- Consumes: `build_registry()` (Task 1); `request.app.state.db_sessionmaker`, `request.app.state.settings.metrics_bearer_token` (existing).
- Produces: `jobify_api.operational_metrics.AsyncWorkSnapshot` (frozen dataclass: `notification_counts: dict[str, int]`, `outbox_counts: dict[str, int]`, `notification_oldest_age_seconds: float`, `outbox_oldest_age_seconds: float`), `fetch_async_work_snapshot(session: AsyncSession) -> AsyncWorkSnapshot`, `AsyncWorkCollector(snapshot: AsyncWorkSnapshot | None)` (a `prometheus_client.registry.Collector`).

- [ ] **Step 1: Write the failing tests**

`tests/unit/test_metrics_route.py`:

```python
"""/metrics rendering (unit: the DB is unreachable here, so the async-work
collector reports down) + the collector itself against a fixed snapshot."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from prometheus_client import CollectorRegistry
from pydantic import SecretStr

from jobify_api.app_factory import create_app
from jobify_api.operational_metrics import AsyncWorkCollector, AsyncWorkSnapshot


def _unreachable_db(monkeypatch: pytest.MonkeyPatch) -> None:
    # The root conftest defaults JOBIFY_DB_URL to the local jobify_test database,
    # which is usually up; port 1 refuses instantly, forcing the "down" branch.
    monkeypatch.setenv("JOBIFY_DB_URL", "postgresql+asyncpg://u:p@127.0.0.1:1/d")


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    _unreachable_db(monkeypatch)
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def test_metrics_bearer_token_is_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    _unreachable_db(monkeypatch)
    app = create_app()
    app.state.settings.metrics_bearer_token = SecretStr("ops-secret")
    with TestClient(app) as client:
        assert client.get("/metrics").status_code == 401
        response = client.get("/metrics", headers={"Authorization": "Bearer ops-secret"})
    assert response.status_code == 200


def test_metrics_renders_prometheus_exposition(client: TestClient) -> None:
    client.get("/health")

    response = client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/plain; version=0.0.4; charset=utf-8"
    body = response.text
    assert "# TYPE http_requests_total counter" in body
    assert 'http_requests_total{method="GET",status="200"}' in body
    assert "_created" not in body


def test_metrics_reports_async_work_down_when_db_unreachable(client: TestClient) -> None:
    body = client.get("/metrics").text

    assert "jobify_async_metrics_up 0.0" in body.splitlines()
    assert "jobify_async_items{" not in body


def test_async_work_collector_renders_snapshot() -> None:
    snapshot = AsyncWorkSnapshot(
        notification_counts={"pending": 2, "failed": 1},
        outbox_counts={"processing": 1},
        notification_oldest_age_seconds=120.5,
        outbox_oldest_age_seconds=0.0,
    )
    registry = CollectorRegistry()
    registry.register(AsyncWorkCollector(snapshot))

    def value(name: str, labels: dict[str, str] | None = None) -> float | None:
        return registry.get_sample_value(name, labels or {})

    assert value("jobify_async_metrics_up") == 1.0
    assert value("jobify_async_items", {"queue": "notifications", "status": "pending"}) == 2.0
    assert value("jobify_async_items", {"queue": "notifications", "status": "sent"}) == 0.0
    assert value("jobify_async_items", {"queue": "outbox", "status": "processing"}) == 1.0
    assert value("jobify_async_oldest_actionable_age_seconds", {"queue": "notifications"}) == 120.5
    assert value("jobify_async_oldest_actionable_age_seconds", {"queue": "outbox"}) == 0.0


def test_async_work_collector_without_snapshot_reports_only_down() -> None:
    registry = CollectorRegistry()
    registry.register(AsyncWorkCollector(None))

    assert registry.get_sample_value("jobify_async_metrics_up") == 0.0
    assert (
        registry.get_sample_value("jobify_async_items", {"queue": "outbox", "status": "pending"})
        is None
    )
```

In `tests/integration/test_operational_metrics.py`, change the exact-line assertions to the float exposition prometheus_client renders:

```python
    assert "jobify_async_metrics_up 1.0" in lines
    assert 'jobify_async_items{queue="notifications",status="pending"} 2.0' in lines
    assert 'jobify_async_items{queue="notifications",status="failed"} 1.0' in lines
    assert 'jobify_async_items{queue="outbox",status="processing"} 1.0' in lines
    assert 'jobify_async_items{queue="outbox",status="completed"} 1.0' in lines
```

(`_age_value` parses floats already; leave it.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_metrics_route.py -v` → collection ERROR `ImportError: cannot import name 'AsyncWorkCollector'`.
Run: `uv run pytest tests/integration/test_operational_metrics.py -v` → FAIL (`'jobify_async_metrics_up 1.0' in lines` false; old renderer prints `1`).

- [ ] **Step 3: Rewrite `operational_metrics.py`**

Replace the whole file:

```python
"""Database-backed health metrics for durable asynchronous work queues.

The route fetches an :class:`AsyncWorkSnapshot` with the async session, then
hands it to a per-scrape :class:`AsyncWorkCollector` — ``Collector.collect()``
is synchronous, so the query cannot run inside it. Labels use only the fixed
queue/status sets below.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Final

from prometheus_client.core import GaugeMetricFamily
from prometheus_client.metrics_core import Metric
from prometheus_client.registry import Collector
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.db.models import Notification, OutboxEvent

_NOTIFICATION_STATUSES: Final = ("pending", "dispatching", "sent", "failed", "cancelled")
_OUTBOX_STATUSES: Final = ("pending", "processing", "completed", "failed")


@dataclass(frozen=True)
class AsyncWorkSnapshot:
    notification_counts: dict[str, int]
    outbox_counts: dict[str, int]
    notification_oldest_age_seconds: float
    outbox_oldest_age_seconds: float


async def _status_counts(
    session: AsyncSession, model: type[Notification] | type[OutboxEvent]
) -> dict[str, int]:
    rows = (
        await session.execute(
            select(model.status, func.count(model.id))
            .where(model.deleted_at.is_(None))
            .group_by(model.status)
        )
    ).all()
    return {str(getattr(status, "value", status)): int(count) for status, count in rows}


async def _oldest_age_seconds(
    session: AsyncSession,
    model: type[Notification] | type[OutboxEvent],
    actionable_statuses: Sequence[str],
) -> float:
    oldest = (
        await session.execute(
            select(func.extract("epoch", func.now() - func.min(model.created_at))).where(
                model.deleted_at.is_(None), model.status.in_(actionable_statuses)
            )
        )
    ).scalar_one_or_none()
    return max(float(oldest or 0.0), 0.0)


async def fetch_async_work_snapshot(session: AsyncSession) -> AsyncWorkSnapshot:
    """Query queue depth and oldest actionable age for both durable queues."""
    return AsyncWorkSnapshot(
        notification_counts=await _status_counts(session, Notification),
        outbox_counts=await _status_counts(session, OutboxEvent),
        notification_oldest_age_seconds=await _oldest_age_seconds(
            session, Notification, ("pending", "dispatching")
        ),
        outbox_oldest_age_seconds=await _oldest_age_seconds(
            session, OutboxEvent, ("pending", "processing")
        ),
    )


class AsyncWorkCollector(Collector):
    """Per-scrape collector; ``None`` means the query failed (``up`` = 0 only)."""

    def __init__(self, snapshot: AsyncWorkSnapshot | None) -> None:
        self._snapshot = snapshot

    def collect(self) -> Iterable[Metric]:
        snapshot = self._snapshot
        yield GaugeMetricFamily(
            "jobify_async_metrics_up",
            "Whether durable async-work metrics were queried successfully.",
            value=0 if snapshot is None else 1,
        )
        if snapshot is None:
            return
        items = GaugeMetricFamily(
            "jobify_async_items",
            "Durable async-work rows by queue and status.",
            labels=["queue", "status"],
        )
        for queue, statuses, counts in (
            ("notifications", _NOTIFICATION_STATUSES, snapshot.notification_counts),
            ("outbox", _OUTBOX_STATUSES, snapshot.outbox_counts),
        ):
            for status in statuses:
                items.add_metric([queue, status], counts.get(status, 0))
        yield items
        ages = GaugeMetricFamily(
            "jobify_async_oldest_actionable_age_seconds",
            "Age of the oldest live actionable row.",
            labels=["queue"],
        )
        ages.add_metric(["notifications"], snapshot.notification_oldest_age_seconds)
        ages.add_metric(["outbox"], snapshot.outbox_oldest_age_seconds)
        yield ages
```

- [ ] **Step 4: Rewrite the route**

Replace the whole of `api/src/jobify_api/routes/metrics.py`:

```python
"""Prometheus scrape endpoint.

Renders the process (or, in multiprocess mode, all API processes') metrics from
``jobify.observability.metrics.build_registry()`` plus the DB-backed async-work
gauges from a per-scrape collector. Unversioned and excluded from OpenAPI.
``JOBIFY_METRICS_BEARER_TOKEN`` protects the endpoint and is mandatory in
staging/prod; local development may leave it unset.
"""

from __future__ import annotations

import hmac

import structlog
from fastapi import APIRouter, HTTPException, Request
from prometheus_client import CONTENT_TYPE_PLAIN_0_0_4, CollectorRegistry, generate_latest
from starlette.responses import Response

from jobify.observability.metrics import build_registry
from jobify_api.operational_metrics import (
    AsyncWorkCollector,
    AsyncWorkSnapshot,
    fetch_async_work_snapshot,
)

router = APIRouter()

_log = structlog.get_logger(__name__)


@router.get("/metrics", include_in_schema=False)
async def metrics(request: Request) -> Response:
    configured = request.app.state.settings.metrics_bearer_token
    if configured is not None:
        expected = f"Bearer {configured.get_secret_value()}"
        supplied = request.headers.get("Authorization", "")
        if not hmac.compare_digest(supplied, expected):
            raise HTTPException(status_code=401, detail="invalid_metrics_token")

    snapshot: AsyncWorkSnapshot | None
    try:
        async with request.app.state.db_sessionmaker() as session:
            snapshot = await fetch_async_work_snapshot(session)
    except Exception:
        _log.exception("metrics.async-work-query-failed")
        snapshot = None

    # A separate per-scrape registry: the collector holds this scrape's snapshot,
    # and the process registry may be the global REGISTRY (single-process mode).
    scrape_registry = CollectorRegistry()
    scrape_registry.register(AsyncWorkCollector(snapshot))
    body = generate_latest(build_registry()) + generate_latest(scrape_registry)
    return Response(content=body, media_type=CONTENT_TYPE_PLAIN_0_0_4)
```

Note: `media_type=CONTENT_TYPE_PLAIN_0_0_4` already carries `; charset=utf-8`; if Starlette appends a second charset, the content-type test will show it — in that case set `headers={"Content-Type": CONTENT_TYPE_PLAIN_0_0_4}` instead of `media_type` and report it.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_metrics_route.py tests/unit/test_metrics.py tests/unit/test_openapi_contract.py -v` and `uv run pytest tests/integration/test_operational_metrics.py -v`
Expected: all PASS.

- [ ] **Step 6: Full suites, commit**

Run: `uv run ruff check api/src tests && uv run ruff format api/src tests && uv run mypy && uv run pytest -q -m "not integration and not eval" && uv run pytest -q -m integration`
Expected: clean; all pass.

```bash
git add api/src/jobify_api/operational_metrics.py api/src/jobify_api/routes/metrics.py \
  tests/unit/test_metrics_route.py tests/integration/test_operational_metrics.py
git commit -m "api: serve /metrics from prometheus_client with a DB-backed async-work collector

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01JSP8DPirBJicB72XTMVq3o"
```

---

### Task 4: Worker metrics server + prefork-safe shutdown

**Files:**
- Modify: `worker/src/jobify_worker/settings.py` (fields next to the other optional settings)
- Modify: `worker/src/jobify_worker/observability.py`
- Create: `tests/unit/worker/test_worker_metrics.py`
- Modify: `worker/CLAUDE.md` ("## Worker runtime" bullets), `worker/README.md`

**Interfaces:**
- Consumes: `build_registry()`, `multiprocess_enabled()` (Task 1); `jobify_worker.celery_app.settings`.
- Produces:
  - `WorkerSettings.worker_metrics_port: int | None` (env `JOBIFY_WORKER_METRICS_PORT`, default `None`, `0..65535`; `0` = ephemeral, for tests)
  - `WorkerSettings.worker_metrics_host: str` (env `JOBIFY_WORKER_METRICS_HOST`, default `"127.0.0.1"`)
  - `jobify_worker.observability.start_worker_metrics_server(**_kwargs: object) -> WSGIServer | None` connected to `celery.signals.worker_init`
  - `jobify_worker.observability.mark_worker_process_dead(pid: int | None = None, **_kwargs: object) -> None` connected to `celery.signals.worker_process_shutdown`
  - PR 3 adds task/external metrics that this server exposes.

- [ ] **Step 1: Write the failing tests**

`tests/unit/worker/test_worker_metrics.py`:

```python
"""Worker scrape endpoint (worker_init) and prefork child cleanup
(worker_process_shutdown). Receivers are called directly — eager tasks never
fire worker signals."""

from __future__ import annotations

from pathlib import Path
from urllib.request import urlopen

import pytest

import jobify_worker.observability as worker_observability
from jobify_worker.celery_app import settings


def test_metrics_server_not_started_without_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "worker_metrics_port", None)

    assert worker_observability.start_worker_metrics_server() is None


def test_metrics_server_serves_prometheus_exposition(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "worker_metrics_port", 0)  # ephemeral port
    monkeypatch.setattr(settings, "worker_metrics_host", "127.0.0.1")

    server = worker_observability.start_worker_metrics_server()

    assert server is not None
    try:
        with urlopen(f"http://127.0.0.1:{server.server_port}/metrics", timeout=5) as response:
            body = response.read().decode()
    finally:
        server.shutdown()
        server.server_close()
    assert "# TYPE http_requests_total counter" in body


def test_metrics_server_bind_failure_does_not_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    def _refuse(*_args: object, **_kwargs: object) -> None:
        raise OSError(48, "Address already in use")

    monkeypatch.setattr(settings, "worker_metrics_port", 9101)
    monkeypatch.setattr(worker_observability, "start_http_server", _refuse)

    assert worker_observability.start_worker_metrics_server() is None


def test_dead_child_is_marked_in_multiprocess_mode(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    marked: list[int] = []
    monkeypatch.setenv("PROMETHEUS_MULTIPROC_DIR", str(tmp_path))
    monkeypatch.setattr(worker_observability.multiprocess, "mark_process_dead", marked.append)

    worker_observability.mark_worker_process_dead(pid=4242, exitcode=0)

    assert marked == [4242]


def test_dead_child_not_marked_in_single_process_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    marked: list[int] = []
    monkeypatch.delenv("PROMETHEUS_MULTIPROC_DIR", raising=False)
    monkeypatch.setattr(worker_observability.multiprocess, "mark_process_dead", marked.append)

    worker_observability.mark_worker_process_dead(pid=4242, exitcode=0)

    assert marked == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/worker/test_worker_metrics.py -v`
Expected: FAIL — `AttributeError: module 'jobify_worker.observability' has no attribute 'start_worker_metrics_server'` (and `settings` has no `worker_metrics_port`).

- [ ] **Step 3: Add the settings**

In `worker/src/jobify_worker/settings.py`, after `provider_read_timeout_seconds`, add:

```python
    # Opt-in Prometheus scrape endpoint for the worker (no auth → loopback by
    # default; set the host to 0.0.0.0 only behind a private network).
    worker_metrics_port: int | None = Field(default=None, ge=0, le=65535)
    worker_metrics_host: str = "127.0.0.1"
```

- [ ] **Step 4: Implement the receivers**

Replace the whole of `worker/src/jobify_worker/observability.py` with (the `configure_worker_logging` receiver is carried over verbatim):

```python
"""Worker observability wiring — imported by ``worker_app`` for its signal side effects.

- ``setup_logging`` → ``configure_logging``. Connecting it makes Celery skip its
  own logging setup, so Celery's records — including ``celery.app.trace``
  task-failure tracebacks — reach the root handler and render (and get redacted)
  like every other line. Both ``celery worker`` and ``celery beat`` send it.
- ``worker_init`` (main process, before any fork) → opt-in Prometheus scrape
  endpoint on ``JOBIFY_WORKER_METRICS_PORT``. In multiprocess mode it serves a
  ``MultiProcessCollector`` registry, so prefork children's samples appear.
- ``worker_process_shutdown`` (sent in the parent for each exiting prefork
  child) → ``multiprocess.mark_process_dead(pid)`` so dead children's live-gauge
  files stop reporting.

None of these fire for eager tasks in tests — call the receivers directly.
"""

from __future__ import annotations

import os
from wsgiref.simple_server import WSGIServer

import structlog
from celery.signals import setup_logging, worker_init, worker_process_shutdown
from prometheus_client import multiprocess, start_http_server

from jobify.observability.logging import configure_logging
from jobify.observability.metrics import build_registry, multiprocess_enabled
from jobify_worker.celery_app import settings

_log = structlog.get_logger(__name__)


@setup_logging.connect  # type: ignore[untyped-decorator]
def configure_worker_logging(**_kwargs: object) -> None:
    """Ignore the signal's ``loglevel``/``logfile``/``format`` kwargs on purpose.

    ``JOBIFY_LOG_LEVEL``/``JOBIFY_LOG_FORMAT`` are the single control for
    worker log level/format (same as the API) — Celery's own ``--loglevel``
    flag has no effect once this receiver is connected.
    """
    configure_logging(settings)


@worker_init.connect  # type: ignore[untyped-decorator]
def start_worker_metrics_server(**_kwargs: object) -> WSGIServer | None:
    """Start the scrape endpoint when configured; never let it stop the worker."""
    port = settings.worker_metrics_port
    if port is None:
        return None
    try:
        server, _thread = start_http_server(
            port, addr=settings.worker_metrics_host, registry=build_registry()
        )
    except OSError:
        # Metrics are non-critical: a busy port must not stop task processing.
        _log.exception("worker.metrics-server-failed", port=port)
        return None
    _log.info(
        "worker.metrics-server-started",
        host=settings.worker_metrics_host,
        port=server.server_port,
        multiprocess=multiprocess_enabled(),
    )
    return server


@worker_process_shutdown.connect  # type: ignore[untyped-decorator]
def mark_worker_process_dead(pid: int | None = None, **_kwargs: object) -> None:
    if multiprocess_enabled():
        multiprocess.mark_process_dead(pid if pid is not None else os.getpid())
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/unit/worker/test_worker_metrics.py tests/unit/worker/test_worker_logging.py tests/unit/test_celery_app.py -v`
Expected: all PASS.

- [ ] **Step 6: Docs**

`worker/CLAUDE.md`, append to "## Worker runtime (shared by all tasks)":

```markdown
- **Worker metrics endpoint is opt-in** (`JOBIFY_WORKER_METRICS_PORT`; host `JOBIFY_WORKER_METRICS_HOST`, default loopback — it has no auth). Started from `worker_init` (main process, pre-fork) by `jobify_worker/observability.py`; a bind failure logs `worker.metrics-server-failed` and the worker keeps running. In multiprocess mode (`PROMETHEUS_MULTIPROC_DIR`, its own directory — never the API's — wiped on start) `worker_process_shutdown` marks dead prefork children.
```

`worker/README.md`, add a section after "## Beat (scheduler)"'s first command block:

```markdown
## Metrics

Opt-in Prometheus endpoint: set `JOBIFY_WORKER_METRICS_PORT` (e.g. `9101`) and scrape
`http://<host>:<port>/metrics`. It binds `JOBIFY_WORKER_METRICS_HOST` (default
`127.0.0.1`; the endpoint has no auth). For `--pool=prefork` (several processes) also
set `PROMETHEUS_MULTIPROC_DIR` to a directory **owned by the worker alone** and empty
it before each start — `scripts/start-all.sh` does both locally.
```

- [ ] **Step 7: Commit**

```bash
uv run ruff check worker/src tests && uv run ruff format worker/src tests && uv run mypy
uv run pytest -q -m "not integration and not eval"
git add worker/src/jobify_worker/settings.py worker/src/jobify_worker/observability.py \
  tests/unit/worker/test_worker_metrics.py worker/CLAUDE.md worker/README.md
git commit -m "worker: opt-in Prometheus scrape endpoint and prefork-safe multiprocess cleanup

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01JSP8DPirBJicB72XTMVq3o"
```

---

### Task 5: Local multiprocess wiring, docs, CI gate + live smoke

**Files:**
- Modify: `scripts/start-all.sh` (section "3. App-layer services")
- Modify: `api/README.md` (env var table), `core/CLAUDE.md` (new "## Metrics" section)

**Interfaces:**
- Consumes: everything above.
- Produces: a verified branch ready for PR 2.

- [ ] **Step 1: Per-service multiprocess dirs in `start-all.sh`**

Directly under the `say "Starting API, worker, frontend…"` line, add:

```bash
# prometheus_client multiprocess mode: one directory PER SERVICE (a shared one
# would merge API and worker series in both scrapes), emptied on every start
# (files from dead pids of a previous run would otherwise keep reporting).
PROM_DIR="$RUN_DIR/prometheus"
rm -rf "$PROM_DIR"
mkdir -p "$PROM_DIR/api" "$PROM_DIR/worker"
```

Prefix the API command inside its quoted string: `cd '$ROOT' && PROMETHEUS_MULTIPROC_DIR='$PROM_DIR/api' exec uv run --env-file=...` (rest unchanged).
Prefix the worker command: `cd '$ROOT' && PROMETHEUS_MULTIPROC_DIR='$PROM_DIR/worker' JOBIFY_WORKER_METRICS_PORT=9101 exec uv run --env-file=...` (rest unchanged).
Beat gets neither (it runs no tasks and serves nothing).
In the script's header comment listing services (`#   • API ...`), append to the worker line: ` — metrics on :9101`.

- [ ] **Step 2: Env docs**

`api/README.md` env-var table: add a row after `JOBIFY_METRICS_BEARER_TOKEN`:

```markdown
| `PROMETHEUS_MULTIPROC_DIR` | multi-process deploys | — | prometheus_client multiprocess mode: a directory owned by the API alone, emptied before start. Unset = single-process metrics |
```

`core/CLAUDE.md`: add after the "## Logging + redaction" section:

```markdown
## Metrics — spec `2026-09-13-backend-observability-foundation-design.md`

- **Declare every metric in `jobify/observability/metrics.py`** (`prometheus_client`), never inline. Cardinality rule: label values only from closed sets — route templates, registered task names, literal service/operation strings, `outcome ∈ {success, error, retry, failure}`; never ids, raw paths or messages.
- **Multiprocess mode is decided at import** by `PROMETHEUS_MULTIPROC_DIR`; scrapes must render `build_registry()`, not `REGISTRY`. One directory per service (API ≠ worker), emptied before start.
- **Tests assert deltas** via `REGISTRY.get_sample_value(...)` — the default registry is process-global. Multiprocess behavior is tested in subprocesses.
- DB-backed gauges are per-scrape collectors (`api/.../operational_metrics.py`), not declared metrics — `Collector.collect()` is sync, so the route queries first.
```

- [ ] **Step 3: Run the CI gate verbatim**

```bash
uv run ruff check core/src api/src worker/src tests
uv run ruff format --check core/src api/src worker/src tests
uv run mypy
uv run pytest -v -m "not integration and not eval"
uv run pytest -v -s -m eval
uv run pytest -v -m integration
```

Expected: all green (record counts).

- [ ] **Step 4: Live smoke**

```bash
scripts/start-all.sh
# wait for http://localhost:8000/health (poll, ≤60s)
curl -s -o /dev/null http://localhost:8000/health
curl -s -o /dev/null http://localhost:8000/nope-smoke
curl -s http://localhost:8000/metrics | grep -E '^(http_requests_total|jobify_async_metrics_up)'
curl -s http://localhost:9101/metrics | head -5
ls var/run/prometheus/api var/run/prometheus/worker
scripts/stop-all.sh
```

Expected:
- API `/metrics` shows `http_requests_total{method="GET",status="200"}` and `{...status="404"}` samples and `jobify_async_metrics_up 1.0`.
- `var/run/prometheus/api` contains `*.db` files (multiprocess mode active); worker `:9101/metrics` answers 200 (body may be empty of samples until PR 3's task metrics — a 200 is the check).
- `worker.log` contains `worker.metrics-server-started` with `port=9101` and `multiprocess=True`.

- [ ] **Step 5: Commit**

```bash
git add scripts/start-all.sh api/README.md core/CLAUDE.md
git commit -m "scripts/docs: per-service prometheus multiprocess dirs and worker metrics port

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01JSP8DPirBJicB72XTMVq3o"
```
