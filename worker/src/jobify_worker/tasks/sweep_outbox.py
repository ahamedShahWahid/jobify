"""Lease and process durable task-dispatch and blob-cleanup intents."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import structlog
from sqlalchemy import or_, select

from jobify.db.models import OutboxEvent, OutboxEventKind, OutboxEventStatus
from jobify.integrations.storage.base import Storage
from jobify.outbox import validate_blob_payload, validate_task_payload
from jobify_worker.async_bridge import run_async
from jobify_worker.celery_app import celery_app, settings
from jobify_worker.runtime import get_session_maker, get_storage

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

_log = structlog.get_logger(__name__)
Dispatch = Callable[[str, list[object]], None]


@celery_app.task(name="jobify.sweep_outbox", acks_late=True)  # type: ignore[untyped-decorator]
def sweep_outbox() -> None:
    run_async(_sweep_outbox_async)


def _dispatch_task(task_name: str, args: list[object]) -> None:
    celery_app.send_task(task_name, args=args)


async def _sweep_outbox_async(
    *,
    sm: async_sessionmaker[AsyncSession] | None = None,
    storage: Storage | None = None,
    dispatch: Dispatch | None = None,
) -> None:
    sm = sm or get_session_maker()
    storage = storage or get_storage()
    dispatch = dispatch or _dispatch_task

    claims = await _claim(sm)
    for event_id, dispatch_token in claims:
        try:
            await _process_one(
                sm,
                event_id,
                dispatch_token,
                storage=storage,
                dispatch=dispatch,
            )
        except Exception as exc:
            await _record_failure(sm, event_id, dispatch_token, exc)


async def _claim(sm: async_sessionmaker[AsyncSession]) -> list[tuple[UUID, UUID]]:
    now = datetime.now(UTC)
    lease_until = now + timedelta(seconds=settings.outbox_lease_seconds)
    async with sm() as session:
        rows = (
            (
                await session.execute(
                    select(OutboxEvent)
                    .where(
                        OutboxEvent.deleted_at.is_(None),
                        or_(
                            (
                                (OutboxEvent.status == OutboxEventStatus.PENDING)
                                & (OutboxEvent.available_at <= now)
                            ),
                            (
                                (OutboxEvent.status == OutboxEventStatus.PROCESSING)
                                & or_(
                                    OutboxEvent.locked_until.is_(None),
                                    OutboxEvent.locked_until < now,
                                )
                            ),
                        ),
                    )
                    .order_by(OutboxEvent.created_at, OutboxEvent.id)
                    .limit(settings.outbox_batch_size)
                    .with_for_update(skip_locked=True)
                )
            )
            .scalars()
            .all()
        )
        claimed: list[tuple[UUID, UUID]] = []
        for event in rows:
            if event.attempts >= settings.outbox_max_attempts:
                event.status = OutboxEventStatus.FAILED
                event.last_error = event.last_error or "processing_lease_expired"
                _clear_claim(event)
                _log.warning(
                    "outbox.claim-exhausted",
                    event_id=str(event.id),
                    attempts=event.attempts,
                )
                continue
            token = uuid4()
            event.status = OutboxEventStatus.PROCESSING
            event.dispatch_token = token
            event.locked_until = lease_until
            event.attempts += 1
            claimed.append((event.id, token))
        await session.commit()
        return claimed


async def _process_one(
    sm: async_sessionmaker[AsyncSession],
    event_id: UUID,
    dispatch_token: UUID,
    *,
    storage: Storage,
    dispatch: Dispatch,
) -> None:
    async with sm() as session:
        event = await session.get(OutboxEvent, event_id)
        if event is None or not _owns_claim(event, dispatch_token):
            return
        kind = event.kind
        payload = event.payload

    if kind == OutboxEventKind.TASK_DISPATCH:
        task_name, args = validate_task_payload(payload)
        await asyncio.to_thread(dispatch, task_name, list(args))
    elif kind == OutboxEventKind.BLOB_DELETE:
        await storage.delete(validate_blob_payload(payload))
    else:  # pragma: no cover - enum constrains persisted values
        raise ValueError(f"unsupported outbox event kind: {kind}")

    await _complete(sm, event_id, dispatch_token)


async def _complete(
    sm: async_sessionmaker[AsyncSession], event_id: UUID, dispatch_token: UUID
) -> None:
    async with sm() as session:
        event = await session.get(OutboxEvent, event_id, with_for_update=True)
        if event is None or not _owns_claim(event, dispatch_token):
            return
        event.status = OutboxEventStatus.COMPLETED
        event.completed_at = datetime.now(UTC)
        event.last_error = None
        _clear_claim(event)
        # Task args and storage keys may be user-linked. Once the side effect
        # succeeds they are no longer needed for recovery, so do not retain them.
        event.payload = {}
        await session.commit()


async def _record_failure(
    sm: async_sessionmaker[AsyncSession],
    event_id: UUID,
    dispatch_token: UUID,
    exc: Exception,
) -> None:
    async with sm() as session:
        event = await session.get(OutboxEvent, event_id, with_for_update=True)
        if event is None or not _owns_claim(event, dispatch_token):
            return
        terminal = event.attempts >= settings.outbox_max_attempts
        event.status = OutboxEventStatus.FAILED if terminal else OutboxEventStatus.PENDING
        event.available_at = datetime.now(UTC) + timedelta(
            seconds=min(2 ** max(event.attempts, 1), 300)
        )
        event.last_error = f"{type(exc).__name__}: {exc}"[:2000]
        _clear_claim(event)
        await session.commit()
        _log.warning(
            "outbox.event-failed",
            event_id=str(event_id),
            attempts=event.attempts,
            terminal=terminal,
            error_type=type(exc).__name__,
        )


def _owns_claim(event: OutboxEvent, dispatch_token: UUID) -> bool:
    return event.status == OutboxEventStatus.PROCESSING and event.dispatch_token == dispatch_token


def _clear_claim(event: OutboxEvent) -> None:
    event.dispatch_token = None
    event.locked_until = None
