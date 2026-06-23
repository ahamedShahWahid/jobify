"""Cursor encode/decode tests for the feed endpoint — pure functions, no DB."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from jobify_api.routes.feed import decode_cursor, encode_cursor


def test_cursor_roundtrip() -> None:
    score = Decimal("0.8500")
    mid = uuid4()
    cursor = encode_cursor(score, mid)
    assert decode_cursor(cursor) == (score, mid)


def test_cursor_score_precision_preserved() -> None:
    score = Decimal("0.8500")
    mid = uuid4()
    decoded_score, _ = decode_cursor(encode_cursor(score, mid))
    assert decoded_score == Decimal("0.8500")
    assert str(decoded_score) == "0.8500"


def test_cursor_malformed_base64_rejected() -> None:
    with pytest.raises(ValueError):
        decode_cursor("not_base64!!!")


def test_cursor_missing_keys_rejected() -> None:
    import base64
    import json

    bad = base64.urlsafe_b64encode(json.dumps({"score": "0.5"}).encode()).decode("ascii")
    with pytest.raises(ValueError):
        decode_cursor(bad)


def test_cursor_bad_uuid_rejected() -> None:
    import base64
    import json

    bad = base64.urlsafe_b64encode(
        json.dumps({"score": "0.5", "match_id": "not-a-uuid"}).encode()
    ).decode("ascii")
    with pytest.raises(ValueError):
        decode_cursor(bad)
