"""Worker scrape endpoint (worker_init) and prefork child cleanup
(worker_process_shutdown). Receivers are called directly — eager tasks never
fire worker signals."""

from __future__ import annotations

from pathlib import Path
from urllib.request import urlopen

import pytest

import jobify_worker.observability as worker_observability
from jobify_worker.celery_app import settings


def test_metrics_server_not_started_without_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "worker_metrics_port", None)

    assert worker_observability.start_worker_metrics_server() is None


def test_metrics_server_serves_prometheus_exposition(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "worker_metrics_port", 0)  # ephemeral port
    monkeypatch.setattr(settings, "worker_metrics_host", "127.0.0.1")

    server = worker_observability.start_worker_metrics_server()

    assert server is not None
    try:
        with urlopen(f"http://127.0.0.1:{server.server_port}/metrics", timeout=5) as response:
            status = response.status
            body = response.read().decode()
    finally:
        server.shutdown()
        server.server_close()
    # Not pinning http_requests_total here: that's an API metric and doesn't
    # belong to the WORKER scrape. A 200 with at least one declared metric is
    # enough to prove the endpoint serves real Prometheus exposition format.
    assert status == 200
    assert "# TYPE " in body


def test_metrics_server_bind_failure_does_not_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    def _refuse(*_args: object, **_kwargs: object) -> None:
        raise OSError(48, "Address already in use")

    monkeypatch.setattr(settings, "worker_metrics_port", 9101)
    monkeypatch.setattr(worker_observability, "start_http_server", _refuse)

    assert worker_observability.start_worker_metrics_server() is None


def test_dead_child_is_marked_in_multiprocess_mode(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    marked: list[int] = []
    monkeypatch.setenv("PROMETHEUS_MULTIPROC_DIR", str(tmp_path))
    monkeypatch.setattr(worker_observability.multiprocess, "mark_process_dead", marked.append)

    worker_observability.mark_worker_process_dead(pid=4242, exitcode=0)

    assert marked == [4242]


def test_dead_child_not_marked_in_single_process_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    marked: list[int] = []
    monkeypatch.delenv("PROMETHEUS_MULTIPROC_DIR", raising=False)
    monkeypatch.setattr(worker_observability.multiprocess, "mark_process_dead", marked.append)

    worker_observability.mark_worker_process_dead(pid=4242, exitcode=0)

    assert marked == []
