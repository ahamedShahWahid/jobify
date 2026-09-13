"""Helpers for classifying DB errors without logging their text.

``IntegrityError`` text includes the violating row's values (e.g.
``Key (email)=(...)``) — log the constraint NAME, never the message.
"""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError


def constraint_name(exc: IntegrityError) -> str | None:
    """The violated constraint's name from asyncpg's cause chain, if present.

    SQLAlchemy wraps the adapter exception (``exc.orig``); asyncpg's
    ``UniqueViolationError`` (which carries ``constraint_name``) is at
    ``exc.orig.__cause__``.
    """
    orig = getattr(exc, "orig", None)
    for candidate in (getattr(orig, "__cause__", None), orig):
        name = getattr(candidate, "constraint_name", None)
        if isinstance(name, str) and name:
            return name
    return None
