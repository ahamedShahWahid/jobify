"""/metrics rendering (unit: the DB is unreachable here, so the async-work
collector reports down) + the collector itself against a fixed snapshot."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from prometheus_client import CollectorRegistry
from pydantic import SecretStr

from jobify_api.app_factory import create_app
from jobify_api.operational_metrics import AsyncWorkCollector, AsyncWorkSnapshot


def _unreachable_db(monkeypatch: pytest.MonkeyPatch) -> None:
    # The root conftest defaults JOBIFY_DB_URL to the local jobify_test database,
    # which is usually up; port 1 refuses instantly, forcing the "down" branch.
    monkeypatch.setenv("JOBIFY_DB_URL", "postgresql+asyncpg://u:p@127.0.0.1:1/d")


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    _unreachable_db(monkeypatch)
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def test_metrics_bearer_token_is_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    _unreachable_db(monkeypatch)
    app = create_app()
    app.state.settings.metrics_bearer_token = SecretStr("ops-secret")
    with TestClient(app) as client:
        assert client.get("/metrics").status_code == 401
        response = client.get("/metrics", headers={"Authorization": "Bearer ops-secret"})
    assert response.status_code == 200


def test_metrics_renders_prometheus_exposition(client: TestClient) -> None:
    client.get("/health")

    response = client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/plain; version=0.0.4; charset=utf-8"
    body = response.text
    assert "# TYPE http_requests_total counter" in body
    assert 'http_requests_total{method="GET",status="200"}' in body
    assert "_created" not in body


def test_metrics_reports_async_work_down_when_db_unreachable(client: TestClient) -> None:
    body = client.get("/metrics").text

    assert "jobify_async_metrics_up 0.0" in body.splitlines()
    assert "jobify_async_items{" not in body


def test_async_work_collector_renders_snapshot() -> None:
    snapshot = AsyncWorkSnapshot(
        notification_counts={"pending": 2, "failed": 1},
        outbox_counts={"processing": 1},
        notification_oldest_age_seconds=120.5,
        outbox_oldest_age_seconds=0.0,
    )
    registry = CollectorRegistry()
    registry.register(AsyncWorkCollector(snapshot))

    def value(name: str, labels: dict[str, str] | None = None) -> float | None:
        return registry.get_sample_value(name, labels or {})

    assert value("jobify_async_metrics_up") == 1.0
    assert value("jobify_async_items", {"queue": "notifications", "status": "pending"}) == 2.0
    assert value("jobify_async_items", {"queue": "notifications", "status": "sent"}) == 0.0
    assert value("jobify_async_items", {"queue": "outbox", "status": "processing"}) == 1.0
    assert value("jobify_async_oldest_actionable_age_seconds", {"queue": "notifications"}) == 120.5
    assert value("jobify_async_oldest_actionable_age_seconds", {"queue": "outbox"}) == 0.0


def test_async_work_collector_without_snapshot_reports_only_down() -> None:
    registry = CollectorRegistry()
    registry.register(AsyncWorkCollector(None))

    assert registry.get_sample_value("jobify_async_metrics_up") == 0.0
    assert (
        registry.get_sample_value("jobify_async_items", {"queue": "outbox", "status": "pending"})
        is None
    )
