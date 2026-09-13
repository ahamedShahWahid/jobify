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
