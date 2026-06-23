"""jobify-seed-consents — backfill default consents for users created before the
P4-B migration. Safe to re-run; seed_default_consents is idempotent.

Usage:
    uv run --env-file=.env jobify-seed-consents
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.consent import seed_default_consents
from jobify.db.models import User
from jobify.db.session import create_engine_from_settings, make_sessionmaker
from jobify.settings import Settings

_log = structlog.get_logger(__name__)


@dataclass
class SeedReport:
    scanned: int = 0
    seeded_users: int = 0
    rows_inserted: int = 0
    skipped_already_seeded: int = 0
    user_ids_seeded: list[str] = field(default_factory=list)


async def _apply_in_session(session: AsyncSession, report: SeedReport) -> None:
    """Body of the backfill. Separated so integration tests can run it inside
    the savepoint-bound session without going through engine construction."""
    users = (await session.execute(select(User).where(User.deleted_at.is_(None)))).scalars().all()
    report.scanned = len(users)
    for user in users:
        created = await seed_default_consents(session, user=user)
        if created:
            report.seeded_users += 1
            report.rows_inserted += len(created)
            report.user_ids_seeded.append(str(user.id))
        else:
            report.skipped_already_seeded += 1


async def _apply() -> SeedReport:
    settings = Settings()
    engine = create_engine_from_settings(settings)
    sm = make_sessionmaker(engine)
    report = SeedReport()
    try:
        async with sm() as session:
            await _apply_in_session(session, report)
            await session.commit()
    finally:
        await engine.dispose()
    return report


def main() -> None:
    report = asyncio.run(_apply())
    _log.info(
        "seed-consents.done",
        scanned=report.scanned,
        seeded_users=report.seeded_users,
        rows_inserted=report.rows_inserted,
        skipped=report.skipped_already_seeded,
    )


if __name__ == "__main__":
    main()
