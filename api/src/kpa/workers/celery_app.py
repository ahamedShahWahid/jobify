"""Celery instance + broker config + per-worker DB engine lifecycle.

Run a worker (from `api/`):

    uv run --env-file=.env celery -A kpa.workers.celery_app worker \\
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

from kpa.settings import Settings

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

    from kpa.integrations.embeddings.gemini import GeminiEmbeddingProvider

# Settings is built at import time — one Settings object for the worker process.
# Tasks read this rather than instantiating Settings repeatedly.
settings = Settings()

celery_app = Celery(
    "kpa",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "kpa.workers.tasks.parse",
        "kpa.workers.tasks.embed",
        "kpa.workers.tasks.embed_job",
        "kpa.workers.tasks.score_applicant",
        "kpa.workers.tasks.score_job",
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
        "kpa.parse_resume": {"queue": "parse"},
        "kpa.embed_applicant": {"queue": "embed"},
        "kpa.embed_job": {"queue": "embed"},
        "kpa.score_applicant": {"queue": "score"},
        "kpa.score_job": {"queue": "score"},
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
    from kpa.db.session import create_engine_from_settings, make_sessionmaker

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
        from kpa.db.session import create_engine_from_settings, make_sessionmaker

        _engine = create_engine_from_settings(settings, poolclass=NullPool)
        _sessionmaker = make_sessionmaker(_engine)
    return _sessionmaker


# --- Per-worker embedding provider ---

_embedding_provider: GeminiEmbeddingProvider | None = None


def get_embedding_provider() -> GeminiEmbeddingProvider:
    """Return the worker's embedding provider, building it lazily.

    Like ``get_session_maker``, the provider is built on first call rather than
    at module import because eager-mode tests construct the provider on a
    fresh app and don't fire ``worker_process_init``.
    """
    global _embedding_provider
    if _embedding_provider is None:
        from kpa.integrations.embeddings.gemini import GeminiEmbeddingProvider

        _embedding_provider = GeminiEmbeddingProvider(
            api_key=settings.gemini_api_key.get_secret_value(),
            model=settings.embedding_model,
            output_dim=settings.embedding_dim,
        )
    return _embedding_provider
