"""Bare shared Celery app: broker/backend + routing + config. No task imports,
no worker-runtime signals, no provider singletons (those live in jobify_worker)."""

from __future__ import annotations

from celery import Celery

from jobify.settings import Settings

settings = Settings()

celery_app = Celery("jobify", broker=settings.redis_url, backend=settings.redis_url)
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


def enqueue(name: str, *args: object) -> None:
    """Fire-and-forget dispatch by task name (producers never import task code).

    Uses ``apply_async`` when the task is registered on the celery_app (i.e.
    when running inside the worker process or in eager-mode tests that have
    imported ``jobify_worker.worker_app``).  Falls back to ``send_task`` when
    the task is not yet registered (normal API process without a loaded worker).

    ``apply_async`` respects ``task_always_eager``; ``send_task`` does not.
    """
    task = celery_app.tasks.get(name)
    if task is not None:
        task.apply_async(args=list(args))
    else:
        celery_app.send_task(name, args=list(args))
