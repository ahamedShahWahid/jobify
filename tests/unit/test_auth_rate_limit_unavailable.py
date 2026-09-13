"""A rate-limiter backend outage (Redis down) is logged, not just turned into a 503."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from structlog.testing import capture_logs

from jobify_api.app_factory import create_app


class _BrokenLimiter:
    async def hit(self, **_kwargs: object) -> None:
        raise ConnectionError("redis unavailable")


def test_rate_limiter_outage_logs_and_returns_503(monkeypatch: pytest.MonkeyPatch) -> None:
    app = create_app()
    app.state.rate_limiter = _BrokenLimiter()

    with TestClient(app) as client, capture_logs() as logs:
        response = client.post("/v1/auth/oauth/google", json={"id_token": "x"})

    assert response.status_code == 503
    (line,) = (e for e in logs if e["event"] == "auth.rate-limiter-unavailable")
    assert line["log_level"] == "error"
    assert line["scope"] == "google"
    assert line["exc_info"] is True
