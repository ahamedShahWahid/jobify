from __future__ import annotations

from sqlalchemy.exc import IntegrityError

from jobify.db.errors import constraint_name


class _UniqueViolationError(Exception):
    def __init__(self, constraint: str | None) -> None:
        super().__init__("duplicate key")
        self.constraint_name = constraint


def _wrapped(cause: BaseException | None) -> IntegrityError:
    orig = Exception("adapter error")
    orig.__cause__ = cause
    return IntegrityError("INSERT ...", {}, orig)


def test_constraint_name_walks_asyncpg_cause_chain() -> None:
    assert constraint_name(_wrapped(_UniqueViolationError("ix_employers_name_norm_live"))) == (
        "ix_employers_name_norm_live"
    )


def test_constraint_name_none_when_unknown() -> None:
    assert constraint_name(_wrapped(None)) is None
    assert constraint_name(_wrapped(_UniqueViolationError(None))) is None
