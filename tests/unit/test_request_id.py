"""Tests for the request-id middleware."""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

UUID_V4 = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
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


def test_request_id_rejected_when_wrong_version(client: TestClient) -> None:
    # uuid1 — syntactically valid UUID, but version nibble is 1, not 4.
    uuid1 = "6ba7b810-9dad-11d1-80b4-00c04fd430c8"

    response = client.get("/health", headers={"X-Request-Id": uuid1})

    echoed = response.headers["x-request-id"]
    assert echoed != uuid1
    assert UUID_V4.match(echoed)


def test_response_has_exactly_one_request_id_header(monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression guard: middleware must upsert, not append. The 500 error handler
    sets X-Request-Id explicitly; without upsert, the middleware would double it.
    """
    monkeypatch.setenv("JOBIFY_ENV", "local")
    monkeypatch.setenv("JOBIFY_SERVICE_NAME", "jobify-api")
    monkeypatch.setenv("JOBIFY_DB_URL", "postgresql+asyncpg://u:p@h:5432/d")

    from fastapi import FastAPI
    from fastapi.responses import PlainTextResponse
    from fastapi.testclient import TestClient

    from jobify_api.middleware.request_id import REQUEST_ID_HEADER, RequestIdMiddleware

    app = FastAPI()
    app.add_middleware(RequestIdMiddleware)

    @app.get("/preset")
    def preset() -> PlainTextResponse:
        response = PlainTextResponse("ok")
        response.headers[REQUEST_ID_HEADER] = "00000000-0000-4000-8000-000000000000"
        return response

    with TestClient(app) as c:
        response = c.get("/preset")

    # httpx exposes multiple values as a comma-joined string; counting commas + 1 = header count
    assert response.headers.get_list(REQUEST_ID_HEADER) is not None
    headers = response.headers.get_list(REQUEST_ID_HEADER)
    assert len(headers) == 1, f"Expected 1 X-Request-Id header, got {len(headers)}: {headers}"
