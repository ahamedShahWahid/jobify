"""Pure-signature contract tests for audit_log(). No DB.

The helper must reject the (actor=None, actor_role=None) combo because we'd
have nothing to record for actor_role (NOT NULL in DB). Catching this at the
helper boundary is cheaper than waiting for asyncpg to surface a NotNull.
"""

from __future__ import annotations

import inspect

import pytest

from jobify.audit import audit_log


def test_helper_signature_has_keyword_only_args() -> None:
    sig = inspect.signature(audit_log)
    params = sig.parameters
    assert params["session"].kind in (
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
        inspect.Parameter.POSITIONAL_ONLY,
    )
    for name in (
        "action",
        "actor",
        "actor_role",
        "resource_type",
        "resource_id",
        "context",
    ):
        assert params[name].kind == inspect.Parameter.KEYWORD_ONLY, f"{name} must be keyword-only"


@pytest.mark.asyncio
async def test_helper_rejects_actor_none_and_actor_role_none() -> None:
    with pytest.raises(ValueError, match="actor_role"):
        await audit_log(
            session=None,  # type: ignore[arg-type]
            action="x.y",
            actor=None,
            actor_role=None,
        )
