"""Shared test fixtures + collection-time env defaults."""

from __future__ import annotations

import logging
import os
from collections.abc import Iterator

import pytest
import structlog
from fastapi.testclient import TestClient

from jobify_api.app_factory import create_app


def pytest_configure(config: object) -> None:
    """Set env-var defaults before pytest collects and imports test modules.

    Modules like ``jobify_worker.celery_app`` call ``WorkerSettings()`` at import time,
    which requires JOBIFY_* env vars to be present *before* collection. ``monkeypatch``
    runs after collection, so it's too late for module-level Settings calls.
    ``os.environ.setdefault`` only writes when the key is absent — real shell
    env vars (e.g. CI overrides) are never shadowed. That's the right behaviour
    for infra vars (DB/Redis/JWT secret), which are legitimate local overrides.

    Gemini-touching vars are the opposite: they are HARD-SET (``os.environ[...] =``),
    never ``setdefault``, so the suite is hermetic with respect to Gemini regardless
    of what the developer's shell exports. A real ``JOBIFY_GEMINI_API_KEY`` sitting in
    the environment must never let a test reach live Gemini — with a real key present,
    ``setdefault`` would leave it in place and any settings resolving to the ``"llm"``
    branch (resume parser, match explainer) would build a real ``genai.Client`` and
    hit the network for real, 429ing once quota is exhausted. Hard-setting forces a
    fake key + the non-LLM code paths (``library`` parser, ``templated`` explainer)
    so stray "llm" resolution is structurally impossible in tests.

    ONE opt-in exception: the on-demand LLM parse-F1 lane
    (``tests/eval/test_parse_f1_gate.py``) is *supposed* to call live Gemini.
    It cannot read ``JOBIFY_GEMINI_API_KEY`` — the hard-set above replaced it
    with the fake, so that lane received the literal ``"test-gemini-key"`` and
    failed with API_KEY_INVALID on every tier. The real key is therefore
    stashed under a distinct name, and ONLY when the operator explicitly
    selected the lane via ``JOBIFY_PARSE_EVAL_PARSER=llm``. The hard-set still
    happens unconditionally, so no settings-resolved code path can reach live
    Gemini: reaching it requires naming this separate variable on purpose.
    """
    if os.environ.get("JOBIFY_PARSE_EVAL_PARSER") == "llm":
        real_gemini_key = os.environ.get("JOBIFY_GEMINI_API_KEY")
        if real_gemini_key:
            os.environ["JOBIFY_EVAL_GEMINI_API_KEY"] = real_gemini_key

    os.environ.setdefault("JOBIFY_ENV", "local")
    os.environ.setdefault("JOBIFY_SERVICE_NAME", "jobify-api")
    os.environ.setdefault(
        "JOBIFY_DB_URL", "postgresql+asyncpg://jobify:jobify@localhost:5432/jobify_test"
    )
    os.environ.setdefault("JOBIFY_REDIS_URL", "redis://localhost:6379/0")
    os.environ.setdefault("JOBIFY_JWT_SECRET", "x" * 32)
    os.environ["JOBIFY_GEMINI_API_KEY"] = "test-gemini-key"
    os.environ["JOBIFY_RESUME_PARSER"] = "library"
    os.environ["JOBIFY_MATCH_EXPLAINER"] = "templated"
    os.environ.setdefault(
        "JOBIFY_GOOGLE_OAUTH_CLIENT_IDS",
        "test.apps.googleusercontent.com",
    )


@pytest.fixture(autouse=True)
def _restore_global_logging_state() -> Iterator[None]:
    """Undo global logging state any test's ``configure_logging()`` call leaves behind.

    ``configure_logging()`` binds structlog's ``PrintLoggerFactory`` and the root
    ``logging.StreamHandler`` to whatever ``sys.stdout`` *is at call time*. A test
    that calls it under ``capsys`` freezes the capture stream into that global
    state; capsys then closes the stream at teardown, and the next test module
    to log through structlog/stdlib logging (without configuring it itself)
    crashes with ``ValueError: I/O operation on closed file``. Snapshot + restore
    here, autoused for unit/integration/eval alike, so no test file's
    capsys-based ``configure_logging()`` call can leak into another.
    """
    root = logging.getLogger()
    saved_handlers = root.handlers[:]
    saved_level = root.level
    structlog.contextvars.clear_contextvars()
    yield
    structlog.contextvars.clear_contextvars()
    structlog.reset_defaults()
    root.handlers[:] = saved_handlers
    root.setLevel(saved_level)


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """A TestClient bound to a freshly created app with deterministic settings."""

    monkeypatch.setenv("JOBIFY_ENV", "local")
    monkeypatch.setenv("JOBIFY_SERVICE_NAME", "jobify-api")
    monkeypatch.setenv("JOBIFY_LOG_LEVEL", "INFO")
    monkeypatch.setenv("JOBIFY_LOG_FORMAT", "text")
    monkeypatch.setenv("JOBIFY_DB_URL", "postgresql+asyncpg://u:p@h:5432/d")
    monkeypatch.setenv("JOBIFY_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("JOBIFY_JWT_SECRET", "x" * 32)
    monkeypatch.setenv("JOBIFY_GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv(
        "JOBIFY_GOOGLE_OAUTH_CLIENT_IDS",
        "test.apps.googleusercontent.com",
    )

    app = create_app()
    with TestClient(app) as c:
        yield c
