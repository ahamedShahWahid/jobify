from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from jobify.db.models import OutboxEvent, OutboxEventKind
from jobify.integrations.storage.base import Storage


async def task_event_args(session: AsyncSession, task_name: str) -> list[list[object]]:
    rows = (
        (
            await session.execute(
                select(OutboxEvent)
                .where(
                    OutboxEvent.kind == OutboxEventKind.TASK_DISPATCH,
                    OutboxEvent.deleted_at.is_(None),
                )
                .order_by(OutboxEvent.created_at, OutboxEvent.id)
            )
        )
        .scalars()
        .all()
    )
    return [row.payload["args"] for row in rows if row.payload.get("task_name") == task_name]


async def drain_outbox_eager(db_url: str, storage: Storage) -> None:
    """Test helper: repeatedly process outbox events through registered eager tasks."""
    from jobify_worker.celery_app import celery_app
    from jobify_worker.tasks.sweep_outbox import _sweep_outbox_async

    engine = create_async_engine(db_url, poolclass=NullPool)
    sm = async_sessionmaker(engine, expire_on_commit=False)

    def dispatch(name: str, args: list[object]) -> None:
        task = celery_app.tasks[name]
        task.apply(args=args).get()

    try:
        for _ in range(8):
            async with sm() as session:
                pending = (
                    await session.execute(
                        select(OutboxEvent.id).where(
                            OutboxEvent.kind == OutboxEventKind.TASK_DISPATCH,
                            OutboxEvent.status.in_(["pending", "processing"]),
                            OutboxEvent.deleted_at.is_(None),
                        )
                    )
                ).first()
            if pending is None:
                return
            await _sweep_outbox_async(sm=sm, storage=storage, dispatch=dispatch)
        raise AssertionError("outbox did not drain after 8 sweeps")
    finally:
        await engine.dispose()
