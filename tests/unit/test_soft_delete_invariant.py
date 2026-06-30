"""Guard test (P2.5a) — soft-delete invariant over the ORM models.

Pure reflection over the SQLAlchemy mapper registry; no DB, no app boot.

Invariant (root CLAUDE.md "Conventions" + core/CLAUDE.md "Soft delete
model"): every domain table carries a nullable, timezone-aware
``deleted_at`` column; live queries filter ``deleted_at IS NULL`` and
uniqueness is enforced via partial indexes ``WHERE deleted_at IS NULL``.

Two models are documented exceptions and are allowlisted below. If a NEW
model is added without ``deleted_at`` and is not added to the allowlist,
this test fails — naming the offending class — which is the point.
"""

from __future__ import annotations

from sqlalchemy import DateTime

from jobify.db.models import AuditLog, Base, RefreshToken

# Documented soft-delete exceptions — see core/CLAUDE.md.
#   - AuditLog: append-only audit substrate. Deliberately omits the
#     Created/Updated/DeletedAt annotated types; audit rows are never
#     updated or soft-deleted (actor_user_id is ON DELETE SET NULL so a
#     DSR hard-delete leaves the row intact, re-identification impossible).
#   - RefreshToken: session-secret ledger. Uses `revoked_at` +
#     `revocation_reason` instead of soft-delete, as approved in the spec.
_SOFT_DELETE_EXEMPT: frozenset[type] = frozenset({AuditLog, RefreshToken})


def _domain_mapped_classes() -> list[type]:
    """Every mapped ORM class registered on the declarative Base, minus the
    documented exceptions."""
    return [
        mapper.class_
        for mapper in Base.registry.mappers
        if mapper.class_ not in _SOFT_DELETE_EXEMPT
    ]


def test_exemptions_are_real_mapped_classes() -> None:
    """The allowlist must reference classes that actually exist and are
    mapped — otherwise a rename would silently make the allowlist inert and
    re-impose the invariant on a class that legitimately opts out."""
    mapped = {mapper.class_ for mapper in Base.registry.mappers}
    for exempt in _SOFT_DELETE_EXEMPT:
        assert exempt in mapped, f"{exempt.__name__} is not a mapped ORM class"


def test_every_domain_model_has_soft_delete_column() -> None:
    """Each non-exempt model has a nullable, timezone-aware `deleted_at`."""
    models = _domain_mapped_classes()
    assert models, "no mapped models discovered — registry import is broken"

    for model in models:
        columns = {col.key: col for col in model.__mapper__.columns}
        assert "deleted_at" in columns, (
            f"{model.__name__} ({model.__tablename__}) has no `deleted_at` column. "
            f"Every domain table must soft-delete; if this model is a genuine "
            f"exception, add it to _SOFT_DELETE_EXEMPT with a justifying comment."
        )

        col = columns["deleted_at"]
        assert (
            col.nullable is True
        ), f"{model.__name__}.deleted_at must be nullable (soft delete is opt-in per row)."
        # Annotated alias (`DeletedAt`) renders to DateTime(timezone=True).
        # Assert the python-visible type/flag, not the exact Annotated name.
        assert isinstance(
            col.type, DateTime
        ), f"{model.__name__}.deleted_at must be a DateTime, got {col.type!r}."
        assert col.type.timezone is True, (
            f"{model.__name__}.deleted_at must be timezone-aware "
            f"(DateTime(timezone=True)), i.e. TIMESTAMPTZ."
        )
