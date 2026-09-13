from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from structlog.testing import capture_logs

from jobify_api.app_factory import create_app


class _DownRedis:
    async def ping(self) -> None:
        raise ConnectionError("redis down")

    async def aclose(self) -> None:
        return None


def test_ready_logs_each_failed_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JOBIFY_DB_URL", "postgresql+asyncpg://u:p@127.0.0.1:1/d")
    app = create_app()
    app.state.redis = _DownRedis()

    with TestClient(app) as client, capture_logs() as logs:
        response = client.get("/ready")

    assert response.status_code == 503
    failed = {e["dependency"]: e for e in logs if e["event"] == "ready.dependency-failed"}
    assert set(failed) == {"db", "redis"}
    assert failed["redis"]["error_type"] == "ConnectionError"
    assert all(e["log_level"] == "warning" for e in failed.values())
