"""Task lifecycle receivers, driven by sending the Celery signals directly."""

from __future__ import annotations

from types import SimpleNamespace

import structlog
from celery.exceptions import Retry
from celery.signals import task_failure, task_postrun, task_prerun, task_retry
from prometheus_client import REGISTRY
from structlog.testing import capture_logs

import jobify_worker.observability  # noqa: F401  (connects the receivers)


class _Task(SimpleNamespace):
    # Signal.send() does sender_receivers_cache.get(sender), so senders must be
    # hashable. SimpleNamespace defines __eq__ (so equality is by __dict__), which
    # makes plain instances unhashable. Real Celery task senders are Task instances
    # (identity-hashed) — this mirrors that instead of hashing by field values.
    __hash__ = object.__hash__


_TASK = _Task(name="jobify.test_task", request=SimpleNamespace(retries=2))


def _runs(outcome: str) -> float:
    return (
        REGISTRY.get_sample_value(
            "jobify_task_runs_total", {"task": "jobify.test_task", "outcome": outcome}
        )
        or 0.0
    )


def _durations() -> float:
    return (
        REGISTRY.get_sample_value(
            "jobify_task_duration_seconds_count", {"task": "jobify.test_task"}
        )
        or 0.0
    )


def _run(state: str, *, task_id: str = "t-1") -> None:
    task_prerun.send(sender=_TASK, task_id=task_id, task=_TASK, args=("secret-arg",), kwargs={})
    task_postrun.send(
        sender=_TASK,
        task_id=task_id,
        task=_TASK,
        args=("secret-arg",),
        kwargs={},
        retval=None,
        state=state,
    )


def test_prerun_binds_task_context_and_postrun_restores_outer_context() -> None:
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id="outer-request")
    seen: dict[str, object] = {}

    task_prerun.send(sender=_TASK, task_id="t-ctx", task=_TASK, args=(), kwargs={})
    seen.update(structlog.contextvars.get_contextvars())
    task_postrun.send(
        sender=_TASK, task_id="t-ctx", task=_TASK, args=(), kwargs={}, retval=None, state="SUCCESS"
    )

    assert seen["task_id"] == "t-ctx"
    assert seen["task_name"] == "jobify.test_task"
    assert seen["task_retries"] == 2
    assert seen["request_id"] == "outer-request"
    after = structlog.contextvars.get_contextvars()
    assert after == {"request_id": "outer-request"}  # eager task inside a request: context restored
    structlog.contextvars.clear_contextvars()


def test_postrun_records_outcome_and_duration_per_state() -> None:
    state_outcomes = (
        ("SUCCESS", "success"),
        ("RETRY", "retry"),
        ("FAILURE", "failure"),
        ("REVOKED", "error"),
    )
    for state, outcome in state_outcomes:
        before, before_duration = _runs(outcome), _durations()
        _run(state, task_id=f"t-{state}")
        assert _runs(outcome) == before + 1, state
        assert _durations() == before_duration + 1, state


def test_postrun_without_prerun_still_counts() -> None:
    before = _runs("success")
    task_postrun.send(
        sender=_TASK,
        task_id="never-started",
        task=_TASK,
        args=(),
        kwargs={},
        retval=None,
        state="SUCCESS",
    )
    assert _runs("success") == before + 1


def test_retry_logs_warning_with_error_type_and_no_args() -> None:
    """Celery's real ``task_retry`` signal (handle_retry) sends ``reason=`` a
    ``celery.exceptions.Retry`` wrapper, not the underlying exception — the
    real cause lives at ``reason.exc``."""
    request = SimpleNamespace(id="t-r", task="jobify.test_task", retries=1, args=("secret-arg",))
    with capture_logs() as logs:
        task_retry.send(
            sender=_TASK,
            request=request,
            reason=Retry(exc=TimeoutError("slow"), when=4),
            einfo=None,
        )

    (line,) = (e for e in logs if e["event"] == "task.retry")
    assert line["log_level"] == "warning"
    assert line["task_name"] == "jobify.test_task"
    assert line["error_type"] == "TimeoutError"
    assert "secret-arg" not in repr(line)


def test_retry_logs_error_type_for_plain_exception_reason() -> None:
    """A plain exception (not wrapped in ``Retry``) also yields error_type —
    covers autoretry_for and any direct-raise path."""
    request = SimpleNamespace(id="t-r2", task="jobify.test_task", retries=0, args=())
    with capture_logs() as logs:
        task_retry.send(sender=_TASK, request=request, reason=ValueError("bad"), einfo=None)

    (line,) = (e for e in logs if e["event"] == "task.retry")
    assert line["error_type"] == "ValueError"


def test_failure_logs_error_without_second_traceback_or_args() -> None:
    with capture_logs() as logs:
        task_failure.send(
            sender=_TASK,
            task_id="t-f",
            exception=ValueError("bad"),
            args=("secret-arg",),
            kwargs={},
            traceback=None,
            einfo=None,
        )

    (line,) = (e for e in logs if e["event"] == "task.failed")
    assert line["log_level"] == "error"
    assert line["task_name"] == "jobify.test_task"
    assert line["task_id"] == "t-f"
    assert line["error_type"] == "ValueError"
    assert "exc_info" not in line
    assert "secret-arg" not in repr(line)
