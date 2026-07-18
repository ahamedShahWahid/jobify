"""Transactional helpers for durable external side-effect intents."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from jobify.db.models import OutboxEvent, OutboxEventKind


def enqueue_task(
    session: AsyncSession,
    task_name: str,
    *args: object,
) -> OutboxEvent:
    """Stage a Celery task dispatch in the caller's transaction."""
    event = OutboxEvent(
        kind=OutboxEventKind.TASK_DISPATCH,
        payload={"task_name": task_name, "args": list(args)},
    )
    session.add(event)
    return event


def enqueue_blob_delete(session: AsyncSession, storage_key: str) -> OutboxEvent:
    """Stage an idempotent storage deletion in the caller's transaction."""
    event = OutboxEvent(
        kind=OutboxEventKind.BLOB_DELETE,
        payload={"storage_key": storage_key},
    )
    session.add(event)
    return event


def validate_task_payload(payload: dict[str, object]) -> tuple[str, Sequence[object]]:
    """Validate persisted JSON before it reaches Celery."""
    task_name = payload.get("task_name")
    args = payload.get("args")
    if not isinstance(task_name, str) or not task_name:
        raise ValueError("outbox task payload requires a non-empty task_name")
    if not isinstance(args, list):
        raise ValueError("outbox task payload requires an args list")
    return task_name, args


def validate_blob_payload(payload: dict[str, object]) -> str:
    """Validate a persisted storage deletion payload."""
    storage_key = payload.get("storage_key")
    if not isinstance(storage_key, str) or not storage_key:
        raise ValueError("outbox blob payload requires a non-empty storage_key")
    return storage_key
