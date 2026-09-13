"""observe_external_call: timing, outcome counter, one log line, never swallows."""

from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest
import structlog
from prometheus_client import REGISTRY
from structlog.testing import capture_logs

from jobify.observability.external import http_status_of, observe_external_call


def _calls(service: str, operation: str, outcome: str) -> float:
    labels = {"service": service, "operation": operation, "outcome": outcome}
    return REGISTRY.get_sample_value("jobify_external_calls_total", labels) or 0.0


def _durations(service: str, operation: str) -> float:
    labels = {"service": service, "operation": operation}
    return REGISTRY.get_sample_value("jobify_external_call_duration_seconds_count", labels) or 0.0


def test_success_counts_times_and_logs_debug() -> None:
    before, before_duration = _calls("t", "ok", "success"), _durations("t", "ok")

    with capture_logs() as logs, observe_external_call("t", "ok"):
        pass

    assert _calls("t", "ok", "success") == before + 1
    assert _durations("t", "ok") == before_duration + 1
    (line,) = (e for e in logs if e["event"] == "external.call")
    assert line["log_level"] == "debug"
    assert line["service"] == "t" and line["operation"] == "ok" and line["outcome"] == "success"
    assert isinstance(line["duration_ms"], float)


def test_failure_reraises_counts_error_and_logs_warning_with_traceback() -> None:
    before = _calls("t", "boom", "error")

    with capture_logs() as logs, pytest.raises(RuntimeError), observe_external_call("t", "boom"):
        raise RuntimeError("provider down")

    assert _calls("t", "boom", "error") == before + 1
    (line,) = (e for e in logs if e["event"] == "external.call")
    assert line["log_level"] == "warning"
    assert line["outcome"] == "error"
    assert line["error_type"] == "RuntimeError"
    assert line["exc_info"] is True


def test_log_traceback_false_omits_exc_info() -> None:
    with (
        capture_logs() as logs,
        pytest.raises(ValueError),
        observe_external_call("t", "quiet", log_traceback=False),
    ):
        raise ValueError("message may carry an address")

    (line,) = (e for e in logs if e["event"] == "external.call")
    assert "exc_info" not in line
    assert line["error_type"] == "ValueError"


def test_http_status_extracted_into_log() -> None:
    request = httpx.Request("GET", "https://example.test/jwks")
    error = httpx.HTTPStatusError(
        "503", request=request, response=httpx.Response(503, request=request)
    )

    with (
        capture_logs() as logs,
        pytest.raises(httpx.HTTPStatusError),
        observe_external_call("t", "status"),
    ):
        raise error

    (line,) = (e for e in logs if e["event"] == "external.call")
    assert line["http_status"] == 503


def test_http_status_of_known_shapes() -> None:
    request = httpx.Request("GET", "https://example.test")
    assert (
        http_status_of(
            httpx.HTTPStatusError(
                "x", request=request, response=httpx.Response(429, request=request)
            )
        )
        == 429
    )
    assert http_status_of(SimpleNamespace(code=403)) == 403  # type: ignore[arg-type]  # google-genai APIError shape
    boto_like = RuntimeError("x")
    boto_like.response = {"ResponseMetadata": {"HTTPStatusCode": 400}}  # type: ignore[attr-defined]
    assert http_status_of(boto_like) == 400
    assert http_status_of(RuntimeError("no status")) is None
    assert http_status_of(SimpleNamespace(code="not-an-int")) is None  # type: ignore[arg-type]


def test_base_exceptions_are_not_counted_as_errors() -> None:
    before = _calls("t", "cancel", "error")

    with pytest.raises(KeyboardInterrupt), observe_external_call("t", "cancel"):
        raise KeyboardInterrupt

    assert _calls("t", "cancel", "error") == before
    structlog.contextvars.clear_contextvars()
