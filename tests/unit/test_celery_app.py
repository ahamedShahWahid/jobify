"""sweep_notifications must actually be scheduled — see arch review finding #10:
routes write Notification rows but nothing was dispatching the sweeper."""

from __future__ import annotations

from jobify.celery_app import celery_app


def test_sweep_notifications_is_beat_scheduled() -> None:
    schedule = celery_app.conf.beat_schedule
    assert "sweep-notifications" in schedule
    entry = schedule["sweep-notifications"]
    assert entry["task"] == "jobify.sweep_notifications"
    assert entry["schedule"].run_every.total_seconds() > 0
