"""current_user binds user_id into the log context of the rest of the request."""

from __future__ import annotations

import httpx
import pytest
import structlog
from fastapi import Depends, FastAPI

from jobify.db.models import User
from jobify.observability.logging import configure_logging
from jobify_api.auth.dependencies import current_user
from tests.logging_helpers import LogSettings, json_log_lines

pytestmark = pytest.mark.integration


async def test_logs_after_auth_carry_user_id_and_request_id(
    integration_app: FastAPI,
    async_client: httpx.AsyncClient,
    applicant_user_and_token: tuple[User, str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    user, token = applicant_user_and_token
    probe_log = structlog.get_logger("test.probe")

    @integration_app.get("/_t/whoami")
    async def whoami(_user: User = Depends(current_user)) -> dict[str, str]:  # noqa: B008
        probe_log.info("probe-after-auth")
        return {}

    configure_logging(LogSettings())
    capsys.readouterr()

    response = await async_client.get("/_t/whoami", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    lines = json_log_lines(capsys.readouterr().out)
    (probe,) = (line for line in lines if line["event"] == "probe-after-auth")
    (access,) = (line for line in lines if line["event"] == "http.request")
    assert probe["user_id"] == str(user.id)
    assert probe["request_id"] == response.headers["x-request-id"]
    assert access["user_id"] == str(user.id)
    structlog.contextvars.clear_contextvars()
