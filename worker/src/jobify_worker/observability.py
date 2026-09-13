"""Worker observability wiring — imported by ``worker_app`` for its signal side effects.

Connecting ``setup_logging`` makes Celery skip its own logging setup, so
Celery's records — including ``celery.app.trace`` task-failure tracebacks —
reach the root handler installed by ``configure_logging`` and render (and get
redacted) like every other line. Both ``celery worker`` and ``celery beat``
send this signal. It never fires for eager tasks in tests.
"""

from __future__ import annotations

from celery.signals import setup_logging

from jobify.observability.logging import configure_logging
from jobify_worker.celery_app import settings


@setup_logging.connect  # type: ignore[untyped-decorator]
def configure_worker_logging(**_kwargs: object) -> None:
    configure_logging(settings)
