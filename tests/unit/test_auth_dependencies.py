"""Unit tests for jobify.auth.dependencies — bearer extraction only.

Full current_user happy/sad paths live in tests/integration/test_me.py
(needs a real DB session).
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from jobify_api.auth.dependencies import _extract_bearer_or_raise_401


def _request_with_headers(headers: list[tuple[bytes, bytes]]) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/v1/me",
        "headers": headers,
        "state": {},
    }
    return Request(scope)  # type: ignore[arg-type]


def test_extract_bearer_returns_token_when_present() -> None:
    req = _request_with_headers([(b"authorization", b"Bearer abc.def.ghi")])
    assert _extract_bearer_or_raise_401(req) == "abc.def.ghi"


def test_extract_bearer_case_insensitive_scheme() -> None:
    req = _request_with_headers([(b"authorization", b"bearer abc.def.ghi")])
    assert _extract_bearer_or_raise_401(req) == "abc.def.ghi"


def test_extract_bearer_missing_header_raises_401() -> None:
    req = _request_with_headers([])
    with pytest.raises(HTTPException) as info:
        _extract_bearer_or_raise_401(req)
    assert info.value.status_code == 401
    assert info.value.detail == "missing_bearer_token"


def test_extract_bearer_wrong_scheme_raises_401() -> None:
    req = _request_with_headers([(b"authorization", b"Basic abc")])
    with pytest.raises(HTTPException) as info:
        _extract_bearer_or_raise_401(req)
    assert info.value.detail == "missing_bearer_token"


def test_extract_bearer_empty_token_raises_401() -> None:
    req = _request_with_headers([(b"authorization", b"Bearer ")])
    with pytest.raises(HTTPException) as info:
        _extract_bearer_or_raise_401(req)
    assert info.value.detail == "missing_bearer_token"
