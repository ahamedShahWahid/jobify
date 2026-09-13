"""jobify.observability.metrics — registry selection and multiprocess aggregation.

Multiprocess mode is decided when prometheus_client is imported (it reads
PROMETHEUS_MULTIPROC_DIR then), so the multiprocess case runs in subprocesses.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
from prometheus_client import REGISTRY, generate_latest

from jobify.observability import metrics


def test_single_process_uses_default_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PROMETHEUS_MULTIPROC_DIR", raising=False)

    assert metrics.multiprocess_enabled() is False
    assert metrics.build_registry() is REGISTRY


def test_declared_metrics_render_without_created_series() -> None:
    metrics.HTTP_REQUESTS.labels(method="GET", status="200").inc()
    metrics.HTTP_REQUEST_DURATION.labels(method="GET", route="/_obs/{item_id}").observe(0.02)

    body = generate_latest(REGISTRY).decode()

    assert "# TYPE http_requests_total counter" in body
    assert "# TYPE http_request_duration_seconds histogram" in body
    assert "# TYPE jobify_unhandled_exceptions_total counter" in body
    assert "# TYPE jobify_http_validation_failures_total counter" in body
    assert 'le="0.025",method="GET",route="/_obs/{item_id}"' in body
    assert "_created" not in body


def test_multiprocess_registry_aggregates_across_processes(tmp_path: Path) -> None:
    env = {**os.environ, "PROMETHEUS_MULTIPROC_DIR": str(tmp_path)}
    writer = textwrap.dedent(
        """
        import sys
        from jobify.observability import metrics
        metrics.HTTP_REQUESTS.labels(method="GET", status="200").inc(int(sys.argv[1]))
        """
    )
    for amount in ("2", "3"):
        subprocess.run([sys.executable, "-c", writer, amount], env=env, check=True)

    reader = textwrap.dedent(
        """
        from prometheus_client import REGISTRY, generate_latest
        from jobify.observability import metrics
        registry = metrics.build_registry()
        assert metrics.multiprocess_enabled()
        assert registry is not REGISTRY
        print(generate_latest(registry).decode())
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", reader], env=env, check=True, capture_output=True, text=True
    )

    assert 'http_requests_total{method="GET",status="200"} 5.0' in result.stdout
