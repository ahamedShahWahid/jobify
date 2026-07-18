from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


async def test_metrics_exposes_bounded_async_work_health(async_client: AsyncClient) -> None:
    response = await async_client.get("/metrics")

    assert response.status_code == 200
    body = response.text
    assert "jobify_async_metrics_up 1" in body
    assert 'jobify_async_items{queue="notifications",status="pending"}' in body
    assert 'jobify_async_items{queue="outbox",status="pending"}' in body
    assert 'jobify_async_oldest_actionable_age_seconds{queue="notifications"}' in body
