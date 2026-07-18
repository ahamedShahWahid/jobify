"""Worker-owned Celery app, routing, and periodic schedule."""

from celery import Celery
from celery.schedules import schedule as celery_schedule

from jobify_worker.settings import WorkerSettings

settings = WorkerSettings()

celery_app = Celery("jobify", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_default_queue="parse",
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_always_eager=settings.celery_task_always_eager,
    task_eager_propagates=True,
    task_soft_time_limit=settings.task_soft_time_limit_seconds,
    task_time_limit=settings.task_time_limit_seconds,
    broker_connection_retry_on_startup=True,
    result_expires=3600,
    task_routes={
        "jobify.parse_resume": {"queue": "parse"},
        "jobify.embed_applicant": {"queue": "embed"},
        "jobify.embed_job": {"queue": "embed"},
        "jobify.score_applicant": {"queue": "score"},
        "jobify.score_job": {"queue": "score"},
        "jobify.sweep_notifications": {"queue": "notify"},
        "jobify.sweep_outbox": {"queue": "outbox"},
        "jobify.cleanup_outbox": {"queue": "outbox"},
    },
)
celery_app.conf.beat_schedule = {
    "sweep-notifications": {
        "task": "jobify.sweep_notifications",
        "schedule": celery_schedule(run_every=settings.notify_sweep_interval_seconds),
    },
    "sweep-outbox": {
        "task": "jobify.sweep_outbox",
        "schedule": celery_schedule(run_every=settings.outbox_sweep_interval_seconds),
    },
    "cleanup-outbox": {
        "task": "jobify.cleanup_outbox",
        "schedule": celery_schedule(run_every=86400),
    },
}
