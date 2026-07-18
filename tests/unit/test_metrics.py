"""Unit tests for the /metrics substrate (no DB).

Guards the two code-review fixes: the /metrics handler must stay async (a sync
handler races _REQUEST_COUNTS between the threadpool and the event loop), and the
counter middleware must attribute status correctly (real started status; 500 only
on an exception with no response; no phantom 500 on a clean no-response return).
"""

from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from jobify_api.metrics import record_request, render_prometheus, reset_metrics
from jobify_api.middleware.metrics import MetricsMiddleware
from jobify_api.routes import metrics as metrics_route


@pytest.fixture(autouse=True)
def _clean_counters() -> None:
    reset_metrics()


def test_render_exposition_format_and_case_folding() -> None:
    record_request("get", 200, route="/v1/jobs/{job_id}", duration_seconds=0.02)
    record_request("GET", 200, route="/v1/jobs/{job_id}", duration_seconds=0.2)
    record_request("POST", 500)
    out = render_prometheus()
    assert "# TYPE http_requests_total counter" in out
    assert 'http_requests_total{method="GET",status="200"} 2' in out
    assert 'http_requests_total{method="POST",status="500"} 1' in out
    assert (
        'http_request_duration_seconds_bucket{method="GET",route="/v1/jobs/{job_id}",'
        'le="0.025"} 1' in out
    )
    assert 'http_request_duration_seconds_count{method="GET",route="/v1/jobs/{job_id}"} 2' in out


def test_metrics_route_handler_is_async() -> None:
    # A sync handler would run in a threadpool and race the event loop's
    # record_request mutating the dict during render's iteration.
    assert inspect.iscoroutinefunction(metrics_route.metrics)


def test_metrics_bearer_token_is_enforced() -> None:
    from jobify_api.app_factory import create_app

    app = create_app()
    app.state.settings.metrics_bearer_token = SecretStr("ops-secret")
    with TestClient(app) as client:
        assert client.get("/metrics").status_code == 401
        response = client.get("/metrics", headers={"Authorization": "Bearer ops-secret"})
    assert response.status_code == 200


async def _drive(app: MetricsMiddleware, *, method: str = "GET") -> None:
    scope = {"type": "http", "method": method}

    async def receive() -> dict[str, object]:
        return {"type": "http.request"}

    async def send(_message: dict[str, object]) -> None:
        return None

    await app(scope, receive, send)


async def test_records_actual_started_status() -> None:
    async def app(scope, receive, send) -> None:  # type: ignore[no-untyped-def]
        scope["route"] = SimpleNamespace(path="/v1/jobs/{job_id}")
        await send({"type": "http.response.start", "status": 204})
        await send({"type": "http.response.body", "body": b""})

    await _drive(MetricsMiddleware(app))
    assert 'http_requests_total{method="GET",status="204"} 1' in render_prometheus()
    assert 'route="/v1/jobs/{job_id}"' in render_prometheus()


async def test_exception_before_response_records_500_and_reraises() -> None:
    async def app(scope, receive, send) -> None:  # type: ignore[no-untyped-def]
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        await _drive(MetricsMiddleware(app))
    assert 'http_requests_total{method="GET",status="500"} 1' in render_prometheus()


async def test_clean_return_without_response_is_not_counted() -> None:
    async def app(scope, receive, send) -> None:  # type: ignore[no-untyped-def]
        return  # no response.start emitted, no exception

    await _drive(MetricsMiddleware(app))
    # No phantom 500 (or any series) for a request that emitted nothing.
    assert "http_requests_total{" not in render_prometheus()
