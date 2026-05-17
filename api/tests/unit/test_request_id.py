"""Tests for the request-id middleware."""

from __future__ import annotations

import re

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
