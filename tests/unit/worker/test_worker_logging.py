"""Worker logging goes through configure_logging via Celery's setup_logging signal.

Signal receivers are exercised by sending the signal directly — eager tasks
(``task_always_eager``) never run Celery's logging setup.
"""

from __future__ import annotations

import logging

import pytest
from celery.signals import setup_logging

from jobify.observability.logging import configure_logging
from tests.logging_helpers import LogSettings, json_log_lines


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

    # Shaped like celery.app.trace.TraceInfo._log_error's real call: format
    # string + a single mapping arg, PLUS `extra={"data": context}` — the
    # same `context` dict, carrying a SECOND copy of the traceback and the
    # task's raw args/kwargs (celery/app/trace.py `_log_error`).
    try:
        raise RuntimeError("task exploded")
    except RuntimeError:
        import traceback as tb_module

        rendered_tb = "".join(tb_module.format_exc())
        context = {
            "hostname": "worker1@host",
            "id": "task-id-1",
            "name": "jobify.parse_resume",
            "exc": "RuntimeError('task exploded')",
            "traceback": rendered_tb,
            "args": "('Priya Sharma', '+91-9876543210')",
            "kwargs": "{}",
            "description": "raised unexpected",
            "internal": False,
        }
        logging.getLogger("celery.app.trace").log(
            logging.ERROR,
            "Task %(name)s[%(id)s] %(description)s: %(exc)s",
            context,
            exc_info=True,
            extra={"data": context},
        )

    lines = json_log_lines(capsys.readouterr().out)
    (line,) = lines
    assert line["logger"] == "celery.app.trace"
    assert line["level"] == "error"
    assert "task exploded" in line["exception"]
    # The `data` extra (Celery's second traceback + raw args/kwargs) must be
    # dropped entirely — not merely redacted — leaving exactly one traceback.
    assert "data" not in line
    assert sum("exception" in x for x in lines) == 1
    assert "Priya Sharma" not in line["exception"]
    assert "+91-9876543210" not in line["exception"]


def test_celery_success_line_drops_data_extra_and_task_args(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Celery's own `celery.app.trace.info()` logs LOG_SUCCESS as
    ``logger.info(fmt, context, extra={"data": context})`` (celery/app/
    trace.py). `id`/`name`/`runtime`/`return_value` are legitimately
    interpolated into the rendered message by `fmt`, so the fake PII used to
    prove `args`/`kwargs` don't leak lives only inside `data`, never in the
    interpolated fields — an email in `args` would be caught by the email
    scrub regardless of whether `data` is dropped, hiding the real bug.
    """
    configure_logging(LogSettings())
    capsys.readouterr()

    fmt = "Task %(name)s[%(id)s] succeeded in %(runtime)ss: %(return_value)s"
    context = {
        "id": "task-id-2",
        "name": "jobify.parse_resume",
        "return_value": "None",
        "runtime": 0.42,
        "args": "('Priya Sharma', '+91-9876543210')",
        "kwargs": "{}",
        "hostname": "worker1@host",
    }
    logging.getLogger("celery.app.trace").info(fmt, context, extra={"data": context})

    output = capsys.readouterr().out
    (line,) = json_log_lines(output)
    assert line["logger"] == "celery.app.trace"
    assert "jobify.parse_resume" in line["event"]  # %(name)s legitimately interpolated
    assert "data" not in line
    assert "Priya Sharma" not in output
    assert "+91-9876543210" not in output
