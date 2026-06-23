"""Tests for jobify.celery_app.enqueue dispatch logic."""

from __future__ import annotations

from unittest.mock import patch

from jobify.celery_app import enqueue


def test_enqueue_sends_unregistered_task_via_send_task() -> None:
    """When a task is not registered, enqueue falls back to send_task (production API path)."""
    unregistered_task_name = "jobify.__definitely_not_registered__"
    arg1 = "resume_123"
    arg2 = "parse_v2"

    with patch("jobify.celery_app.celery_app.send_task") as mock_send_task:
        enqueue(unregistered_task_name, arg1, arg2)

        # Assert send_task was called exactly once with the task name and args.
        mock_send_task.assert_called_once_with(unregistered_task_name, args=[arg1, arg2])


def test_enqueue_with_single_arg() -> None:
    """enqueue works with a single argument and sends via send_task when unregistered."""
    unregistered_task_name = "jobify.__test_task_123__"
    arg = "single_arg_value"

    with patch("jobify.celery_app.celery_app.send_task") as mock_send_task:
        enqueue(unregistered_task_name, arg)

        # Assert send_task was called with the single arg in args list.
        mock_send_task.assert_called_once_with(unregistered_task_name, args=[arg])
