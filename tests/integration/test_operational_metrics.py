from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from jobify.db.models import (
    Notification,
    NotificationChannel,
    NotificationStatus,
    OutboxEvent,
    OutboxEventKind,
    OutboxEventStatus,
    User,
    UserRole,
)

pytestmark = pytest.mark.integration


def _age_value(body: str, *, queue: str) -> float:
    prefix = f'jobify_async_oldest_actionable_age_seconds{{queue="{queue}"}} '
    samples = [line for line in body.splitlines() if line.startswith(prefix)]
    assert len(samples) == 1
    return float(samples[0].removeprefix(prefix))


async def test_metrics_exposes_bounded_async_work_health(
    async_client: AsyncClient,
    integration_app: FastAPI,
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert session.bind is not None
    monkeypatch.setattr(
        integration_app.state,
        "db_sessionmaker",
        async_sessionmaker(
            bind=session.bind,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        ),
    )

    await session.execute(delete(Notification))
    await session.execute(delete(OutboxEvent))

    seeded_at = datetime.now(UTC) - timedelta(seconds=120)
    user = User(email=f"metrics-{uuid4()}@example.com", role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()
    session.add_all(
        [
            Notification(
                user_id=user.id,
                kind="application_received",
                channel=NotificationChannel.IN_APP,
                status=NotificationStatus.PENDING,
                payload={},
                created_at=seeded_at,
            ),
            Notification(
                user_id=user.id,
                kind="application_received",
                channel=NotificationChannel.IN_APP,
                status=NotificationStatus.PENDING,
                payload={},
            ),
            Notification(
                user_id=user.id,
                kind="application_received",
                channel=NotificationChannel.IN_APP,
                status=NotificationStatus.FAILED,
                payload={},
            ),
            OutboxEvent(
                kind=OutboxEventKind.TASK_DISPATCH,
                status=OutboxEventStatus.PROCESSING,
                payload={"task_name": "jobify.parse_resume", "args": ["metrics"]},
                created_at=seeded_at,
            ),
            OutboxEvent(
                kind=OutboxEventKind.TASK_DISPATCH,
                status=OutboxEventStatus.COMPLETED,
                payload={},
            ),
        ]
    )
    await session.commit()

    response = await async_client.get("/metrics")

    assert response.status_code == 200
    body = response.text
    lines = body.splitlines()
    assert "jobify_async_metrics_up 1" in lines
    assert 'jobify_async_items{queue="notifications",status="pending"} 2' in lines
    assert 'jobify_async_items{queue="notifications",status="failed"} 1' in lines
    assert 'jobify_async_items{queue="outbox",status="processing"} 1' in lines
    assert 'jobify_async_items{queue="outbox",status="completed"} 1' in lines
    notification_age = _age_value(body, queue="notifications")
    outbox_age = _age_value(body, queue="outbox")
    assert 115.0 <= notification_age <= 300.0
    assert 115.0 <= outbox_age <= 300.0
