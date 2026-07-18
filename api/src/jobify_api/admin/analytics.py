"""Database-side admin aggregates; never drain full audit streams into clients."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.db.models import AuditLog, Employer


@dataclass(frozen=True)
class CountBucket:
    key: str
    count: int


@dataclass(frozen=True)
class DayBucket:
    day: date
    count: int


@dataclass(frozen=True)
class AuditAnalytics:
    total_events: int
    distinct_actors: int
    last_24h: int
    system_events: int
    span_start: datetime | None
    span_end: datetime | None
    activity: list[DayBucket]
    role_counts: list[CountBucket]
    action_counts: list[CountBucket]


async def load_audit_analytics(session: AsyncSession) -> AuditAnalytics:
    cutoff = datetime.now(UTC) - timedelta(hours=24)
    totals = (
        await session.execute(
            select(
                func.count(AuditLog.id),
                func.count(func.distinct(AuditLog.actor_user_id)),
                func.count(AuditLog.id).filter(AuditLog.created_at >= cutoff),
                func.count(AuditLog.id).filter(AuditLog.actor_role == "system"),
                func.min(AuditLog.created_at),
                func.max(AuditLog.created_at),
            )
        )
    ).one()

    day_expr = func.date_trunc("day", AuditLog.created_at)
    activity_rows = (
        await session.execute(
            select(day_expr.label("day"), func.count(AuditLog.id))
            .group_by(day_expr)
            .order_by(day_expr)
        )
    ).all()
    role_rows = (
        await session.execute(
            select(AuditLog.actor_role, func.count(AuditLog.id))
            .group_by(AuditLog.actor_role)
            .order_by(func.count(AuditLog.id).desc(), AuditLog.actor_role)
        )
    ).all()
    action_rows = (
        await session.execute(
            select(AuditLog.action, func.count(AuditLog.id))
            .group_by(AuditLog.action)
            .order_by(func.count(AuditLog.id).desc(), AuditLog.action)
        )
    ).all()

    return AuditAnalytics(
        total_events=int(totals[0]),
        distinct_actors=int(totals[1]),
        last_24h=int(totals[2]),
        system_events=int(totals[3]),
        span_start=totals[4],
        span_end=totals[5],
        activity=[DayBucket(day=row[0].date(), count=int(row[1])) for row in activity_rows],
        role_counts=[CountBucket(key=str(row[0]), count=int(row[1])) for row in role_rows],
        action_counts=[CountBucket(key=str(row[0]), count=int(row[1])) for row in action_rows],
    )


async def load_employer_verification_counts(session: AsyncSession) -> dict[str, int]:
    row = (
        await session.execute(
            select(
                func.count(Employer.id).filter(
                    Employer.verified_at.is_(None), Employer.rejected_at.is_(None)
                ),
                func.count(Employer.id).filter(Employer.verified_at.is_not(None)),
                func.count(Employer.id).filter(
                    Employer.verified_at.is_(None), Employer.rejected_at.is_not(None)
                ),
            ).where(Employer.deleted_at.is_(None))
        )
    ).one()
    return {"pending": int(row[0]), "verified": int(row[1]), "rejected": int(row[2])}
