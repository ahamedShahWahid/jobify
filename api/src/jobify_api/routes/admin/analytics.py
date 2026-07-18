"""Admin analytics summary backed by database aggregates."""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.db.models import User
from jobify_api.admin.analytics import load_audit_analytics
from jobify_api.auth.dependencies import _require_admin, current_user
from jobify_api.dependencies import get_session

router = APIRouter(prefix="/v1/admin", tags=["admin"])


class CountBucketRead(BaseModel):
    key: str
    count: int


class DayBucketRead(BaseModel):
    day: date
    count: int


class AuditAnalyticsRead(BaseModel):
    total_events: int
    distinct_actors: int
    last_24h: int
    system_events: int
    span_start: datetime | None
    span_end: datetime | None
    activity: list[DayBucketRead]
    role_counts: list[CountBucketRead]
    action_counts: list[CountBucketRead]


@router.get("/analytics/summary", response_model=AuditAnalyticsRead)
async def analytics_summary(
    user: User = Depends(current_user),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> AuditAnalyticsRead:
    await _require_admin(user)
    summary = await load_audit_analytics(session)
    return AuditAnalyticsRead(
        total_events=summary.total_events,
        distinct_actors=summary.distinct_actors,
        last_24h=summary.last_24h,
        system_events=summary.system_events,
        span_start=summary.span_start,
        span_end=summary.span_end,
        activity=[DayBucketRead(day=row.day, count=row.count) for row in summary.activity],
        role_counts=[CountBucketRead(key=row.key, count=row.count) for row in summary.role_counts],
        action_counts=[
            CountBucketRead(key=row.key, count=row.count) for row in summary.action_counts
        ],
    )
