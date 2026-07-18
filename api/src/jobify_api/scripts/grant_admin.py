"""jobify-grant-admin — bootstrap CLI to elevate a user to ADMIN role.

Usage:
    uv run --env-file=.env jobify-grant-admin <email>

Idempotent — if the user is already ADMIN, logs 'no change' and exits 0.
Exits 1 if no live user matches the email.

Writes one auth.role.granted audit row with actor_user_id=NULL (system
actor — there's no admin user logged in to grant the FIRST admin).
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.audit import audit_log
from jobify.db.models import User, UserRole
from jobify.db.session import create_engine_from_settings, make_sessionmaker
from jobify_api.settings import Settings

_log = structlog.get_logger(__name__)


@dataclass
class GrantReport:
    matched: bool
    already_admin: bool
    user_id: str | None
    from_role: str | None


async def _apply_in_session(session: AsyncSession, *, email: str) -> GrantReport:
    """Body of the grant. Separated so integration tests can run it inside
    the savepoint-bound session without going through engine construction."""
    user = (
        await session.execute(
            select(User).where(
                User.email == email,
                User.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()

    if user is None:
        return GrantReport(matched=False, already_admin=False, user_id=None, from_role=None)

    if user.role == UserRole.ADMIN:
        return GrantReport(
            matched=True, already_admin=True, user_id=str(user.id), from_role="admin"
        )

    from_role = user.role.value
    user.role = UserRole.ADMIN
    await session.flush()

    await audit_log(
        session,
        action="auth.role.granted",
        actor=None,
        actor_role="system",
        resource_type="user",
        resource_id=user.id,
        context={
            "from_role": from_role,
            "to_role": "admin",
            "by": "jobify-grant-admin-cli",
        },
    )

    return GrantReport(matched=True, already_admin=False, user_id=str(user.id), from_role=from_role)


async def _apply(email: str) -> GrantReport:
    settings = Settings()
    engine = create_engine_from_settings(settings)
    sm = make_sessionmaker(engine)
    report = GrantReport(matched=False, already_admin=False, user_id=None, from_role=None)
    try:
        async with sm() as session:
            report = await _apply_in_session(session, email=email)
            await session.commit()
    finally:
        await engine.dispose()
    return report


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: jobify-grant-admin <email>", file=sys.stderr)
        sys.exit(2)

    email = sys.argv[1].strip()
    report = asyncio.run(_apply(email))

    if not report.matched:
        _log.error("grant-admin.user-not-found", email=email)
        sys.exit(1)

    if report.already_admin:
        _log.info("grant-admin.no-change", email=email, user_id=report.user_id)
        return

    _log.info(
        "grant-admin.done",
        email=email,
        user_id=report.user_id,
        from_role=report.from_role,
        to_role="admin",
    )


if __name__ == "__main__":
    main()
