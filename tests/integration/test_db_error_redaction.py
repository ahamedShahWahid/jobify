"""DB exception text must not carry bound parameter values.

SQLAlchemy renders ``[parameters: (...)]`` into ``str(DBAPIError)`` unless the
engine sets ``hide_parameters=True`` — and tracebacks put that string in logs.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.pool import NullPool

from jobify.db.session import create_engine_from_settings

pytestmark = pytest.mark.integration


@dataclass(frozen=True)
class _DbSettings:
    db_url: str
    db_pool_size: int = 1
    db_max_overflow: int = 0
    db_pool_timeout_seconds: float = 5.0
    db_pool_recycle_seconds: int = 1800
    db_command_timeout_seconds: float = 5.0


async def test_db_error_text_omits_bound_parameters(migrated_db: str) -> None:
    engine = create_engine_from_settings(_DbSettings(db_url=migrated_db), poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            with pytest.raises(DBAPIError) as info:
                # 1/0 fails at execution without Postgres echoing the value, so
                # only SQLAlchemy's own [parameters: ...] suffix could leak it.
                await connection.execute(
                    text("SELECT CAST(:value AS text), 1/0"), {"value": "secret-param-value"}
                )
    finally:
        await engine.dispose()

    assert "secret-param-value" not in str(info.value)
