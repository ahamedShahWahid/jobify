"""Append-only audit substrate for P4 DPDP.

The single entry point is `audit_log()`. It writes one row to `audit_logs`
inside the caller's transaction. There is no commit, no flush-and-discard,
no fire-and-forget dispatch — the row is exactly as durable as the business
action it records. If the caller's txn rolls back, the audit row rolls back
too. That is the contract.

Action slugs are dotted, lowercase, verb-past
(`resume.accessed`, `consent.granted`). See
docs/superpowers/specs/2026-05-28-audit-logs-substrate-design.md §4 for the
reserved namespace.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from jobify.db.models import AuditLog, User


async def audit_log(
    session: AsyncSession,
    *,
    action: str,
    actor: User | None,
    actor_role: str | None = None,
    resource_type: str | None = None,
    resource_id: UUID | None = None,
    context: dict[str, Any] | None = None,
) -> AuditLog:
    """Append one row to audit_logs. Caller owns the txn.

    actor_role is derived from actor.role when actor is not None; pass
    explicitly for system actions (actor=None, actor_role='system'). Raises
    ValueError if both actor and actor_role are None.
    """
    if actor is None and actor_role is None:
        raise ValueError(
            "audit_log requires actor_role when actor is None "
            "(e.g. actor_role='system' for cron / worker actions)"
        )

    resolved_role = actor_role if actor_role is not None else actor.role.value  # type: ignore[union-attr]
    resolved_actor_id = actor.id if actor is not None else None

    row = AuditLog(
        actor_user_id=resolved_actor_id,
        actor_role=resolved_role,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        context=context if context is not None else {},
    )
    session.add(row)
    await session.flush()
    return row
