"""Per-user consent state for P4 DPDP scopes.

Three entry points:

* ``get_consent`` — read current state. Raises ``LookupError`` if no live
  row exists (means seeding was skipped — caller may fall back to
  ``DEFAULT_CONSENTS[scope]``).
* ``set_consent`` — UPSERT + audit row. No-op on noop (doesn't write
  audit when the requested state matches current state).
* ``seed_default_consents`` — insert one row per ConsentScope using
  ``DEFAULT_CONSENTS`` as values, + one audit row per insertion. Idempotent.

All three participate in the caller's transaction — no commit, no
fire-and-forget. Mirrors ``audit_log()``.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.audit import audit_log
from jobify.db.models import (
    DEFAULT_CONSENTS,
    ConsentScope,
    User,
    UserConsent,
)


async def get_consent(
    session: AsyncSession,
    *,
    user: User,
    scope: ConsentScope,
) -> bool:
    row = (
        await session.execute(
            select(UserConsent).where(
                UserConsent.user_id == user.id,
                UserConsent.scope == scope.value,
                UserConsent.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise LookupError(f"no live consent row for user={user.id} scope={scope.value}")
    return row.granted


async def set_consent(
    session: AsyncSession,
    *,
    user: User,
    scope: ConsentScope,
    granted: bool,
    request_id: str | None = None,
) -> UserConsent:
    row = (
        await session.execute(
            select(UserConsent).where(
                UserConsent.user_id == user.id,
                UserConsent.scope == scope.value,
                UserConsent.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()

    if row is not None and row.granted == granted:
        # No-op — don't write a spurious audit row.
        return row

    if row is None:
        row = UserConsent(user_id=user.id, scope=scope.value, granted=granted)
        session.add(row)
    else:
        row.granted = granted

    await session.flush()

    await audit_log(
        session,
        action="consent.granted" if granted else "consent.revoked",
        actor=user,
        resource_type="consent",
        resource_id=row.id,
        context={
            "scope": scope.value,
            "granted": granted,
            **({"request_id": request_id} if request_id else {}),
        },
    )

    return row


async def seed_default_consents(
    session: AsyncSession,
    *,
    user: User,
    request_id: str | None = None,
) -> list[UserConsent]:
    """Insert default rows for every scope that doesn't already have one.

    Idempotent: re-running on a user who already has live rows leaves them
    untouched and only inserts what's missing. The backfill CLI relies on
    this.
    """
    existing = {
        row.scope
        for row in (
            await session.execute(
                select(UserConsent).where(
                    UserConsent.user_id == user.id,
                    UserConsent.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    }

    created: list[UserConsent] = []
    for scope, default_value in DEFAULT_CONSENTS.items():
        if scope.value in existing:
            continue
        row = UserConsent(
            user_id=user.id,
            scope=scope.value,
            granted=default_value,
        )
        session.add(row)
        created.append(row)

    if not created:
        return created

    await session.flush()

    for row in created:
        await audit_log(
            session,
            action="consent.seeded",
            actor=user,
            resource_type="consent",
            resource_id=row.id,
            context={
                "scope": row.scope,
                "granted": row.granted,
                **({"request_id": request_id} if request_id else {}),
            },
        )

    return created
