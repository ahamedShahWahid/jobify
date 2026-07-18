"""Requeue terminal failed outbox events after an operator resolves the cause."""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from jobify.db.models import OutboxEvent, OutboxEventStatus
from jobify.db.session import create_engine_from_settings, make_sessionmaker
from jobify_worker.settings import WorkerSettings


async def _requeue_rows(sm: async_sessionmaker[AsyncSession], *, limit: int, dry_run: bool) -> int:
    async with sm() as session:
        rows = (
            (
                await session.execute(
                    select(OutboxEvent)
                    .where(
                        OutboxEvent.status == OutboxEventStatus.FAILED,
                        OutboxEvent.deleted_at.is_(None),
                    )
                    .order_by(OutboxEvent.created_at, OutboxEvent.id)
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                )
            )
            .scalars()
            .all()
        )
        if dry_run:
            await session.rollback()
            return len(rows)
        for event in rows:
            event.status = OutboxEventStatus.PENDING
            event.available_at = datetime.now(UTC)
            event.dispatch_token = None
            event.locked_until = None
            event.attempts = 0
            event.last_error = None
        await session.commit()
        return len(rows)


async def _requeue(*, limit: int, dry_run: bool) -> int:
    settings = WorkerSettings()
    engine = create_engine_from_settings(settings)
    sm = make_sessionmaker(engine)
    try:
        return await _requeue_rows(sm, limit=limit, dry_run=dry_run)
    finally:
        await engine.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jobify-requeue-outbox")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.limit < 1 or args.limit > 10_000:
        parser.error("--limit must be between 1 and 10000")
    count = asyncio.run(_requeue(limit=args.limit, dry_run=args.dry_run))
    print(f"{'would requeue' if args.dry_run else 'requeued'} {count} outbox event(s)")
    return 0
