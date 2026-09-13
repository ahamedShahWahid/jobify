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
    monkeypatch.delenv("prometheus_multiproc_dir", raising=False)

    assert metrics.multiprocess_enabled() is False
    assert metrics.build_registry() is REGISTRY


def test_multiprocess_enabled_true_for_legacy_lowercase_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Mirrors prometheus_client's own predicate (values.py / multiprocess.py):
    # presence of either spelling counts, not truthiness of either.
    monkeypatch.delenv("PROMETHEUS_MULTIPROC_DIR", raising=False)
    monkeypatch.setenv("prometheus_multiproc_dir", "/tmp/whatever-not-checked-here")

    assert metrics.multiprocess_enabled() is True


def test_multiprocess_enabled_true_for_empty_string_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROMETHEUS_MULTIPROC_DIR", "")

    assert metrics.multiprocess_enabled() is True


def test_ensure_multiprocess_dir_ready_noop_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PROMETHEUS_MULTIPROC_DIR", raising=False)
    monkeypatch.delenv("prometheus_multiproc_dir", raising=False)

    metrics.ensure_multiprocess_dir_ready()  # must not raise


def test_ensure_multiprocess_dir_ready_passes_for_existing_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PROMETHEUS_MULTIPROC_DIR", str(tmp_path))

    metrics.ensure_multiprocess_dir_ready()  # must not raise


def test_ensure_multiprocess_dir_ready_raises_for_missing_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    missing = tmp_path / "does-not-exist"
    monkeypatch.setenv("PROMETHEUS_MULTIPROC_DIR", str(missing))

    with pytest.raises(RuntimeError, match="PROMETHEUS_MULTIPROC_DIR"):
        metrics.ensure_multiprocess_dir_ready()


def test_ensure_multiprocess_dir_ready_raises_for_empty_string_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PROMETHEUS_MULTIPROC_DIR", "")

    with pytest.raises(RuntimeError, match="PROMETHEUS_MULTIPROC_DIR"):
        metrics.ensure_multiprocess_dir_ready()


def test_ensure_multiprocess_dir_ready_prefers_uppercase_over_legacy(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Matches prometheus_client's own precedence (uppercase wins when both are
    # set) — validating the wrong one would pass a directory the client never
    # actually writes to.
    missing = tmp_path / "missing"
    monkeypatch.setenv("prometheus_multiproc_dir", str(tmp_path))
    monkeypatch.setenv("PROMETHEUS_MULTIPROC_DIR", str(missing))

    with pytest.raises(RuntimeError, match="PROMETHEUS_MULTIPROC_DIR"):
        metrics.ensure_multiprocess_dir_ready()


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


def _app_factory_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JOBIFY_ENV", "local")
    monkeypatch.setenv("JOBIFY_SERVICE_NAME", "jobify-api")
    monkeypatch.setenv("JOBIFY_DB_URL", "postgresql+asyncpg://u:p@h:5432/d")
    monkeypatch.setenv("JOBIFY_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("JOBIFY_JWT_SECRET", "x" * 32)
    monkeypatch.setenv("JOBIFY_GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv("JOBIFY_GOOGLE_OAUTH_CLIENT_IDS", "test.apps.googleusercontent.com")


def test_create_app_raises_when_multiproc_dir_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """create_app() must fail fast at boot, not on the first request's
    RequestContextMiddleware.finally (FileNotFoundError) or the first
    /metrics scrape (ValueError from MultiProcessCollector)."""
    from jobify_api.app_factory import create_app

    _app_factory_env(monkeypatch)
    monkeypatch.setenv("PROMETHEUS_MULTIPROC_DIR", str(tmp_path / "missing"))

    with pytest.raises(RuntimeError, match="PROMETHEUS_MULTIPROC_DIR"):
        create_app()


def test_create_app_boots_when_multiproc_dir_exists(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from jobify_api.app_factory import create_app

    _app_factory_env(monkeypatch)
    monkeypatch.setenv("PROMETHEUS_MULTIPROC_DIR", str(tmp_path))

    create_app()  # must not raise


def test_create_app_boots_when_multiproc_dir_env_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    from jobify_api.app_factory import create_app

    _app_factory_env(monkeypatch)
    monkeypatch.delenv("PROMETHEUS_MULTIPROC_DIR", raising=False)
    monkeypatch.delenv("prometheus_multiproc_dir", raising=False)

    create_app()  # must not raise


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
