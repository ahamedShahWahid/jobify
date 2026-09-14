from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from structlog.testing import capture_logs

from jobify.db.models import RefreshToken, User, UserRole
from jobify_worker.celery_app import settings
from jobify_worker.tasks.cleanup_refresh_tokens import _cleanup_refresh_tokens_async

pytestmark = pytest.mark.integration


def _make_sm(session: AsyncSession) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(bind=session.bind, expire_on_commit=False)


async def _make_user(session: AsyncSession, email: str) -> User:
    user = User(email=email, role=UserRole.APPLICANT)
    session.add(user)
    await session.flush()
    return user


def _token(
    *, user_id: uuid.UUID, family_id: uuid.UUID, expires_at: datetime, **kw: object
) -> RefreshToken:
    return RefreshToken(
        user_id=user_id,
        family_id=family_id,
        token_hash=uuid.uuid4().hex + uuid.uuid4().hex,  # 64 hex chars, unique per row
        expires_at=expires_at,
        **kw,  # type: ignore[arg-type]
    )


async def test_cleanup_deletes_expired_and_old_revoked_but_keeps_live_rows(
    session: AsyncSession,
) -> None:
    now = datetime(2026, 7, 18, tzinfo=UTC)
    user = await _make_user(session, "cleanup-refresh@example.com")
    family = uuid.uuid4()

    expired_unrevoked = _token(
        user_id=user.id, family_id=family, expires_at=now - timedelta(days=1)
    )
    old_revoked = _token(
        user_id=user.id,
        family_id=family,
        expires_at=now + timedelta(days=1),
        revoked_at=now - timedelta(days=8),
        revocation_reason="rotated",
    )
    recently_revoked = _token(
        user_id=user.id,
        family_id=family,
        expires_at=now + timedelta(days=1),
        revoked_at=now - timedelta(days=1),
        revocation_reason="rotated",
    )
    live = _token(user_id=user.id, family_id=family, expires_at=now + timedelta(days=1))
    rows = [expired_unrevoked, old_revoked, recently_revoked, live]
    session.add_all(rows)
    await session.commit()
    row_ids = [row.id for row in rows]

    with capture_logs() as captured:
        deleted = await _cleanup_refresh_tokens_async(sm=_make_sm(session), now=now)

    assert deleted == 2
    remaining = set(
        (
            await session.execute(select(RefreshToken.id).where(RefreshToken.id.in_(row_ids)))
        ).scalars()
    )
    assert remaining == {recently_revoked.id, live.id}
    completed = [c for c in captured if c["event"] == "refresh_tokens.cleanup-completed"]
    assert completed == [
        {
            "event": "refresh_tokens.cleanup-completed",
            "log_level": "info",
            "deleted_count": 2,
            "retention_days": 7,
        }
    ]


async def test_cleanup_loops_across_batches_until_backlog_is_empty(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime(2026, 7, 18, tzinfo=UTC)
    user = await _make_user(session, "cleanup-refresh-loop@example.com")
    family = uuid.uuid4()
    rows = [
        _token(user_id=user.id, family_id=family, expires_at=now - timedelta(days=i + 1))
        for i in range(5)
    ]
    session.add_all(rows)
    await session.commit()
    row_ids = [row.id for row in rows]
    monkeypatch.setattr(settings, "refresh_token_cleanup_batch_size", 2)

    assert await _cleanup_refresh_tokens_async(sm=_make_sm(session), now=now) == 5

    remaining = (
        (await session.execute(select(RefreshToken.id).where(RefreshToken.id.in_(row_ids))))
        .scalars()
        .all()
    )
    assert remaining == []


async def test_cleanup_stops_and_warns_at_the_max_batches_safety_cap(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime(2026, 7, 18, tzinfo=UTC)
    user = await _make_user(session, "cleanup-refresh-cap@example.com")
    family = uuid.uuid4()
    rows = [
        _token(user_id=user.id, family_id=family, expires_at=now - timedelta(days=i + 1))
        for i in range(5)
    ]
    session.add_all(rows)
    await session.commit()
    row_ids = [row.id for row in rows]
    monkeypatch.setattr(settings, "refresh_token_cleanup_batch_size", 1)
    monkeypatch.setattr(settings, "refresh_token_cleanup_max_batches", 2)

    with capture_logs() as captured:
        assert await _cleanup_refresh_tokens_async(sm=_make_sm(session), now=now) == 2

    remaining = (
        (await session.execute(select(RefreshToken.id).where(RefreshToken.id.in_(row_ids))))
        .scalars()
        .all()
    )
    assert len(remaining) == 3
    warnings = [c for c in captured if c["event"] == "refresh_tokens.cleanup-max-batches-reached"]
    assert len(warnings) == 1
    assert warnings[0]["deleted_count"] == 2
    assert warnings[0]["max_batches"] == 2
