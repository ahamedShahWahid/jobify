"""Worker logging goes through configure_logging via Celery's setup_logging signal.

Signal receivers are exercised by sending the signal directly — eager tasks
(``task_always_eager``) never run Celery's logging setup.
"""

from __future__ import annotations

import logging

import pytest
from celery.signals import setup_logging

from tests.logging_helpers import json_log_lines


def test_setup_logging_signal_configures_structured_worker_logs(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import jobify_worker.worker_app  # noqa: F401  (connects the receiver)
    from jobify_worker.celery_app import settings
    from jobify_worker.observability import configure_worker_logging

    monkeypatch.setattr(settings, "log_format", "json")

    responses = setup_logging.send(
        sender=None, loglevel=logging.INFO, logfile=None, format="", colorize=False
    )

    # A receiver exists, so Celery skips hijacking the root logger itself.
    assert configure_worker_logging in [receiver for receiver, _ in responses]
    capsys.readouterr()

    try:
        raise RuntimeError("task exploded")
    except RuntimeError:
        logging.getLogger("celery.app.trace").error(
            "Task jobify.parse_resume failed", exc_info=True
        )

    (line,) = json_log_lines(capsys.readouterr().out)
    assert line["logger"] == "celery.app.trace"
    assert line["level"] == "error"
    assert "task exploded" in line["exception"]
