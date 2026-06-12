"""Celery instance + broker config + per-worker DB engine lifecycle.

Run a worker (from `api/`):

    uv run --env-file=.env celery -A jobify.workers.celery_app worker \\
        --pool=solo --concurrency=1 -Q parse

--pool=solo is the MVP choice: single-concurrency, no subprocess fan-out,
plays cleanly with `asyncio.run()` in the task body. P5 hardening switches
to --pool=prefork + per-process engine without changes here (the
worker_process_init signal handles both).
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from celery import Celery
from celery.signals import worker_process_init, worker_shutting_down
from sqlalchemy.pool import NullPool

from jobify.settings import Settings

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

    from jobify.integrations.embeddings.gemini import GeminiEmbeddingProvider
    from jobify.integrations.notifications.base import EmailChannel
    from jobify.scoring.explainer import MatchExplainer

# Settings is built at import time — one Settings object for the worker process.
# Tasks read this rather than instantiating Settings repeatedly.
settings = Settings()

celery_app = Celery(
    "jobify",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "jobify.workers.tasks.parse",
        "jobify.workers.tasks.embed",
        "jobify.workers.tasks.embed_job",
        "jobify.workers.tasks.score_applicant",
        "jobify.workers.tasks.score_job",
        "jobify.workers.tasks.sweep_notifications",
    ],
)

celery_app.conf.update(
    task_default_queue="parse",
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_always_eager=settings.celery_task_always_eager,
    task_eager_propagates=True,
    broker_connection_retry_on_startup=True,
    result_expires=3600,  # 1h — most jobs surface state via DB row, not result
    task_routes={
        "jobify.parse_resume": {"queue": "parse"},
        "jobify.embed_applicant": {"queue": "embed"},
        "jobify.embed_job": {"queue": "embed"},
        "jobify.score_applicant": {"queue": "score"},
        "jobify.score_job": {"queue": "score"},
        "jobify.sweep_notifications": {"queue": "notify"},
    },
)


# --- Per-worker engine + sessionmaker ---

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


@worker_process_init.connect  # type: ignore[untyped-decorator]
def _init_engine(**_kwargs: object) -> None:
    """Build the async engine + sessionmaker once per worker process.

    Works with --pool=solo (single process) AND --pool=prefork (one signal
    per subprocess) — each subprocess gets its own engine.
    """
    global _engine, _sessionmaker
    from jobify.db.session import create_engine_from_settings, make_sessionmaker

    # NullPool is LOAD-BEARING, not an oversight: each task body runs under a
    # fresh `asyncio.run()` loop, and pooled asyncpg connections stay bound to
    # the loop that created them — a QueuePool would hand task N+1 a connection
    # bound to task N's dead loop ("Future attached to a different loop").
    # Revisit only alongside a persistent-loop worker (e.g. a single
    # long-lived loop per process).
    _engine = create_engine_from_settings(settings, poolclass=NullPool)
    _sessionmaker = make_sessionmaker(_engine)


@worker_shutting_down.connect  # type: ignore[untyped-decorator]
def _dispose_engine(**_kwargs: object) -> None:
    """Dispose the engine on graceful shutdown so asyncpg releases connections."""
    if _engine is not None:
        asyncio.run(_engine.dispose())


def get_session_maker() -> async_sessionmaker[AsyncSession]:
    """Return the worker's sessionmaker.

    In eager mode (tests), the worker_process_init signal doesn't fire because
    no worker process exists — build a fresh sessionmaker on demand. The settings
    object's redis_url isn't used in eager mode, but the DB url is.
    """
    global _engine, _sessionmaker
    if _sessionmaker is None:
        from jobify.db.session import create_engine_from_settings, make_sessionmaker

        _engine = create_engine_from_settings(settings, poolclass=NullPool)
        _sessionmaker = make_sessionmaker(_engine)
    return _sessionmaker


# --- Per-worker embedding provider ---

_embedding_provider: GeminiEmbeddingProvider | None = None


def _gemini_api_key_or_raise() -> str:
    if settings.gemini_api_key is None:
        raise RuntimeError("JOBIFY_GEMINI_API_KEY is required for Gemini-backed worker providers")
    return settings.gemini_api_key.get_secret_value()


def get_embedding_provider() -> GeminiEmbeddingProvider:
    """Return the worker's embedding provider, building it lazily.

    Like ``get_session_maker``, the provider is built on first call rather than
    at module import because eager-mode tests construct the provider on a
    fresh app and don't fire ``worker_process_init``.
    """
    global _embedding_provider
    if _embedding_provider is None:
        from jobify.integrations.embeddings.gemini import GeminiEmbeddingProvider

        _embedding_provider = GeminiEmbeddingProvider(
            api_key=_gemini_api_key_or_raise(),
            model=settings.embedding_model,
            output_dim=settings.embedding_dim,
        )
    return _embedding_provider


# --- Per-worker email channel ---

_email_channel: EmailChannel | None = None


def get_email_channel() -> EmailChannel:
    """Return the worker's email channel adapter, building it lazily.

    Reads ``settings.email_channel`` to choose the implementation:
    - ``"logging"`` — ``LoggingEmailChannel`` (stub; no email is actually sent).
    - ``"ses"``     — raises ``NotImplementedError`` (deferred until deploy target is picked).

    Like ``get_embedding_provider``, the channel is built on first call so that
    eager-mode tests can monkeypatch before the factory is invoked.
    """
    global _email_channel
    if _email_channel is None:
        if settings.email_channel == "logging":
            from jobify.integrations.notifications.logging_email import LoggingEmailChannel

            _email_channel = LoggingEmailChannel()
        elif settings.email_channel == "ses":
            raise NotImplementedError("SES email channel is not yet implemented")
        else:
            raise ValueError(f"unknown email_channel: {settings.email_channel!r}")
    return _email_channel


# --- Per-worker match explainer ---

_match_explainer: MatchExplainer | None = None


def get_match_explainer() -> MatchExplainer:
    """Return the worker's match explainer, building it lazily.

    Reads ``settings.match_explainer`` to choose the implementation:
    - ``"templated"`` — ``TemplatedExplainer`` (default; deterministic, no network).
    - ``"llm"``       — ``GeminiMatchExplainer`` wrapping ``genai.Client``.

    Like ``get_embedding_provider``, the explainer is built on first call so
    that eager-mode tests can monkeypatch before the factory is invoked. The
    LLM branch defers ``from google import genai`` so the templated path never
    pays the import cost.
    """
    global _match_explainer
    if _match_explainer is None:
        if settings.match_explainer == "templated":
            from jobify.scoring.explainer import TemplatedExplainer

            _match_explainer = TemplatedExplainer()
        elif settings.match_explainer == "llm":
            from google import genai

            from jobify.scoring.llm_explainer import GeminiMatchExplainer

            _match_explainer = GeminiMatchExplainer(
                client=genai.Client(api_key=_gemini_api_key_or_raise()),
                model=settings.match_explainer_model,
            )
        else:
            raise ValueError(f"unknown match_explainer: {settings.match_explainer!r}")
    return _match_explainer
