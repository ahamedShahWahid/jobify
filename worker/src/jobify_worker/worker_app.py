"""Celery worker entry: ``celery -A jobify_worker.worker_app worker``.

Imports the shared app, registers all task modules, and wires runtime signals.
"""

from jobify_worker import (
    runtime,  # noqa: F401  (connects worker_process_init/shutdown signals on import)
)
from jobify_worker.celery_app import celery_app  # noqa: F401  (the -A target)
from jobify_worker.tasks import (  # noqa: F401  (register tasks onto celery_app)
    cleanup_outbox,
    embed,
    embed_job,
    parse,
    score_applicant,
    score_job,
    sweep_notifications,
    sweep_outbox,
)
