"""Celery workers — separate process from uvicorn.

Each task module under :mod:`.tasks` is included via the `include` arg in
:mod:`.celery_app`. The Celery instance is `kpa.workers.celery_app.celery_app`.
"""
