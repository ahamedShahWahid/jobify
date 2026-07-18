from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
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
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transport = async_client._transport
    assert isinstance(transport, ASGITransport)
    assert session.bind is not None
    monkeypatch.setattr(
        transport.app.state,
        "db_sessionmaker",
        async_sessionmaker(
            bind=session.bind,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        ),
    )

    await session.execute(delete(Notification))
    await session.execute(delete(OutboxEvent))

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
    assert _age_value(body, queue="notifications") >= 0.0
    assert _age_value(body, queue="outbox") >= 0.0
