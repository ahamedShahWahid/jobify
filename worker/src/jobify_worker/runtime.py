"""Per-worker engine lifecycle, signal handlers, and provider singletons.

Imported by :mod:`jobify_worker.worker_app` on startup. Importing this module
connects the ``worker_process_init`` and ``worker_shutting_down`` Celery signals,
which fire per worker process (including on ``--pool=solo`` and ``--pool=prefork``).

In eager test mode the signals don't fire — all factories fall back to building
their objects lazily on first call, which is why every getter checks for ``None``
rather than relying on the signal-time initialisation.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from celery.signals import worker_process_init, worker_shutting_down
from sqlalchemy.pool import NullPool

from jobify_worker.celery_app import settings

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

    from jobify.integrations.embeddings.gemini import GeminiEmbeddingProvider
    from jobify.integrations.notifications.base import EmailChannel
    from jobify.integrations.storage.base import Storage
    from jobify.scoring.explainer import MatchExplainer


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


# --- Per-worker storage adapter ---

_storage: Storage | None = None


def get_storage() -> Storage:
    """Return the configured storage adapter shared by worker tasks."""
    global _storage
    if _storage is None:
        from jobify.integrations.storage import create_storage

        _storage = create_storage(settings)
    return _storage


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
            timeout_seconds=settings.provider_read_timeout_seconds,
        )
    return _embedding_provider


# --- Per-worker email channel ---

_email_channel: EmailChannel | None = None


def get_email_channel() -> EmailChannel:
    """Return the worker's email channel adapter, building it lazily.

    Reads ``settings.email_channel`` to choose the implementation:
    - ``"logging"`` — ``LoggingEmailChannel`` (stub; no email is actually sent).
    - ``"ses"``     — ``SesEmailChannel`` using the configured verified sender.

    Like ``get_embedding_provider``, the channel is built on first call so that
    eager-mode tests can monkeypatch before the factory is invoked.
    """
    global _email_channel
    if _email_channel is None:
        if settings.email_channel == "logging":
            from jobify.integrations.notifications.logging_email import LoggingEmailChannel

            _email_channel = LoggingEmailChannel()
        elif settings.email_channel == "ses":
            from jobify.integrations.notifications.ses import SesEmailChannel

            if settings.email_from_address is None:  # defense in depth
                raise ValueError("email_from_address is required for SES")
            _email_channel = SesEmailChannel(
                from_address=settings.email_from_address,
                region=settings.aws_region,
                connect_timeout_seconds=settings.provider_connect_timeout_seconds,
                read_timeout_seconds=settings.provider_read_timeout_seconds,
            )
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
                client=genai.Client(
                    api_key=_gemini_api_key_or_raise(),
                    http_options=genai.types.HttpOptions(
                        timeout=int(settings.provider_read_timeout_seconds * 1000)
                    ),
                ),
                model=settings.match_explainer_model,
            )
        else:
            raise ValueError(f"unknown match_explainer: {settings.match_explainer!r}")
    return _match_explainer
