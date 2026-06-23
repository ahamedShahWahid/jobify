"""Pure-signature contract tests for consent helpers. No DB."""

from __future__ import annotations

import inspect

from jobify.consent import get_consent, seed_default_consents, set_consent


def test_get_consent_signature() -> None:
    sig = inspect.signature(get_consent)
    assert next(iter(sig.parameters)) == "session"
    for name in ("user", "scope"):
        assert sig.parameters[name].kind == inspect.Parameter.KEYWORD_ONLY


def test_set_consent_signature() -> None:
    sig = inspect.signature(set_consent)
    assert next(iter(sig.parameters)) == "session"
    for name in ("user", "scope", "granted", "request_id"):
        assert sig.parameters[name].kind == inspect.Parameter.KEYWORD_ONLY


def test_seed_default_consents_signature() -> None:
    sig = inspect.signature(seed_default_consents)
    assert next(iter(sig.parameters)) == "session"
    for name in ("user", "request_id"):
        assert sig.parameters[name].kind == inspect.Parameter.KEYWORD_ONLY
