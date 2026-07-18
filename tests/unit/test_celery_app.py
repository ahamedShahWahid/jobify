"""sweep_notifications must actually be scheduled — see arch review finding #10:
routes write Notification rows but nothing was dispatching the sweeper."""

from __future__ import annotations

from jobify_worker.celery_app import celery_app


def test_sweep_notifications_is_beat_scheduled() -> None:
    schedule = celery_app.conf.beat_schedule
    assert "sweep-notifications" in schedule
    entry = schedule["sweep-notifications"]
    assert entry["task"] == "jobify.sweep_notifications"
    assert entry["schedule"].run_every.total_seconds() > 0


def test_every_beat_scheduled_task_has_a_queue_route() -> None:
    """beat_schedule and task_routes are two independent dicts in this module
    (arch review finding) -- a periodic task with no matching task_routes
    entry silently falls back to task_default_queue instead of its intended
    queue. Cheap to keep them consistent as they grow past one entry."""
    task_names = {entry["task"] for entry in celery_app.conf.beat_schedule.values()}
    routed_names = set(celery_app.conf.task_routes)
    missing_routes = task_names - routed_names
    assert not missing_routes, (
        f"beat-scheduled task(s) with no task_routes entry: {missing_routes} "
        "-- add a task_routes entry or it silently dispatches to "
        "task_default_queue instead of its intended queue."
    )
