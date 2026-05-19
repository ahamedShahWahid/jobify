"""FastAPI dependencies for authenticated routes.

``current_user`` decodes the Bearer access JWT, re-fetches the user row, and
returns it. Routes use ``Depends(current_user)`` directly; tests inject a fake
via ``app.dependency_overrides[current_user] = lambda: fake_user``.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from kpa.auth.tokens import AccessTokenError, decode_access_token
from kpa.db.models import User
from kpa.db.session import get_session
from kpa.settings import Settings


def _extract_bearer_or_raise_401(request: Request) -> str:
    """Return the Bearer token string, or raise 401 missing_bearer_token."""
    raw = request.headers.get("authorization", "")
    parts = raw.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing_bearer_token",
        )
    return parts[1].strip()


async def current_user(
    request: Request,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> User:
    """Resolve the Bearer access JWT to a live ``User``.

    Re-fetches the user row on every call: a user soft-deleted N seconds ago
    is locked out within the access TTL (≤10 min), not the refresh TTL.
    """
    settings: Settings = request.app.state.settings
    token = _extract_bearer_or_raise_401(request)

    try:
        claims = decode_access_token(token, secret=settings.jwt_secret)
    except AccessTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_access_token",
        ) from exc

    try:
        user_id = UUID(claims["sub"])
    except (ValueError, KeyError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_access_token",
        ) from exc

    user = await session.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="user_not_found",
        )

    request.state.current_user_id = user.id
    request.state.current_role = user.role.value
    return user


async def optional_current_user(
    request: Request,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> User | None:
    """Like :func:`current_user` but returns ``None`` if no Authorization header."""
    if not request.headers.get("authorization"):
        return None
    return await current_user(request, session=session)
