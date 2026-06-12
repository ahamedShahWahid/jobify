"""DSR delete orchestrator — DPDP § 12 erasure right.

Walks the user's data graph and applies the brainstorm-locked strategy:
"hard-delete PII, keep anonymized aggregates." See
docs/superpowers/specs/2026-05-29-dsr-delete-design.md §2 for the
per-table policy table and §5 for the order of operations.

Pure executor — does NOT write audit rows. The route handler writes
``user.dsr_delete_requested`` BEFORE this call and
``user.dsr_deleted`` AFTER, in the same transaction.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog
from pydantic import BaseModel, ConfigDict
from sqlalchemy import delete, exists, func, or_, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from jobify.db.models import (
    Applicant,
    ApplicantEmbedding,
    Employer,
    EmployerInvite,
    EmployerUser,
    Notification,
    OAuthIdentity,
    RefreshToken,
    Resume,
    SavedJob,
    User,
    UserConsent,
    UserRole,
)
from jobify.integrations.storage import Storage

_log = structlog.get_logger(__name__)


class OwnerlessEmployerWarning(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str = "ownerless_employer"
    employer_id: UUID
    employer_name: str
    message: str


class DeleteReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deleted_at: datetime
    section_counts: dict[str, int]
    warnings: list[OwnerlessEmployerWarning]


async def _detect_ownerless_employers(
    session: AsyncSession, *, user: User
) -> list[OwnerlessEmployerWarning]:
    """Find employers where the user is currently the last live owner.

    The check runs BEFORE we delete the user's employer_users rows so we
    can compare against the pre-delete state.
    """
    if user.role != UserRole.RECRUITER:
        return []

    other_owner = aliased(EmployerUser)
    inner = select(other_owner.id).where(
        other_owner.employer_id == EmployerUser.employer_id,
        other_owner.user_id != user.id,
        other_owner.role == "owner",
        other_owner.deleted_at.is_(None),
    )

    stmt = (
        select(EmployerUser.employer_id, Employer.name)
        .join(Employer, Employer.id == EmployerUser.employer_id)
        .where(
            EmployerUser.user_id == user.id,
            EmployerUser.role == "owner",
            EmployerUser.deleted_at.is_(None),
            ~exists(inner),
        )
    )

    rows = (await session.execute(stmt)).all()
    return [
        OwnerlessEmployerWarning(
            employer_id=eid,
            employer_name=ename,
            message=(
                f"Employer '{ename}' has no remaining owners. "
                "Contact privacy@jobify to reassign or close."
            ),
        )
        for (eid, ename) in rows
    ]


async def delete_user_data(
    session: AsyncSession,
    *,
    storage: Storage,
    user: User,
) -> DeleteReport:
    """Erase a user's personal data per the spec §2 table. Caller owns
    the transaction — no commit; if any step raises, the whole graph
    rolls back atomically.
    """
    counts: dict[str, int] = {}

    # Detect sole-owner employers BEFORE deleting memberships.
    warnings = await _detect_ownerless_employers(session, user=user)

    r: CursorResult[Any]

    # 1. Notifications — payload may contain PII (job titles in apply confirmations).
    r = await session.execute(  # type: ignore[assignment]
        delete(Notification).where(Notification.user_id == user.id)
    )
    counts["notifications"] = r.rowcount or 0

    # 2. Refresh tokens — session secrets.
    r = await session.execute(  # type: ignore[assignment]
        delete(RefreshToken).where(RefreshToken.user_id == user.id)
    )
    counts["refresh_tokens"] = r.rowcount or 0

    # 3. OAuth identities — provider linkage.
    r = await session.execute(  # type: ignore[assignment]
        delete(OAuthIdentity).where(OAuthIdentity.user_id == user.id)
    )
    counts["oauth_identities"] = r.rowcount or 0

    # 4. Consents — operational state. History lives in audit_logs.
    r = await session.execute(  # type: ignore[assignment]
        delete(UserConsent).where(UserConsent.user_id == user.id)
    )
    counts["user_consents"] = r.rowcount or 0

    # 5. Employer memberships (recruiter case).
    r = await session.execute(  # type: ignore[assignment]
        delete(EmployerUser).where(EmployerUser.user_id == user.id)
    )
    counts["employer_users"] = r.rowcount or 0

    # 5b. Employer invites addressed to (or accepted by) this user — the invite
    # `email` column is the user's PII. Invites this user *sent* hold other
    # people's emails and stay with the employer's records (the
    # invited_by_user_id pointer survives to the tombstone, like audit actors).
    invite_match = EmployerInvite.accepted_user_id == user.id
    if user.email:
        invite_match = or_(invite_match, func.lower(EmployerInvite.email) == user.email.lower())
    r = await session.execute(  # type: ignore[assignment]
        delete(EmployerInvite).where(invite_match)
    )
    counts["employer_invites"] = r.rowcount or 0

    # 6. Resolve the applicant id once for downstream queries.
    applicant_row = (
        await session.execute(select(Applicant).where(Applicant.user_id == user.id))
    ).scalar_one_or_none()
    applicant_id = applicant_row.id if applicant_row else None

    if applicant_id is not None:
        # 7. Saved jobs.
        r = await session.execute(  # type: ignore[assignment]
            delete(SavedJob).where(SavedJob.applicant_id == applicant_id)
        )
        counts["saved_jobs"] = r.rowcount or 0

        # 8. Embedding row.
        r = await session.execute(  # type: ignore[assignment]
            delete(ApplicantEmbedding).where(ApplicantEmbedding.applicant_id == applicant_id)
        )
        counts["applicant_embeddings"] = r.rowcount or 0

        # 9. Resume blobs — best-effort; storage failure must NOT roll back the DB.
        resume_rows = (
            (await session.execute(select(Resume).where(Resume.applicant_id == applicant_id)))
            .scalars()
            .all()
        )
        for resume in resume_rows:
            if resume.storage_key:
                try:
                    await storage.delete(resume.storage_key)
                except Exception:
                    _log.warning(
                        "dsr.blob-delete-failed",
                        resume_id=str(resume.id),
                        storage_key=resume.storage_key,
                        exc_info=True,
                    )

        # 10. Resume rows — scrub PII fields + tombstone.
        now = datetime.now(UTC)
        r = await session.execute(  # type: ignore[assignment]
            update(Resume)
            .where(Resume.applicant_id == applicant_id)
            .values(
                parsed_json=None,
                original_filename=None,
                storage_key=None,
                deleted_at=now,
                updated_at=now,
            )
        )
        counts["resumes_scrubbed"] = r.rowcount or 0

        # 11. Applicant — scrub PII + tombstone.
        await session.execute(
            update(Applicant)
            .where(Applicant.id == applicant_id)
            .values(
                full_name=None,
                locations=None,
                notice_period_days=None,
                current_ctc=None,
                expected_ctc=None,
                years_experience=None,
                deleted_at=now,
                updated_at=now,
            )
        )
        counts["applicant_tombstoned"] = 1
    else:
        now = datetime.now(UTC)
        counts["saved_jobs"] = 0
        counts["applicant_embeddings"] = 0
        counts["resumes_scrubbed"] = 0
        counts["applicant_tombstoned"] = 0

    # 12. User — scrub PII + tombstone.
    now = datetime.now(UTC)
    await session.execute(
        update(User)
        .where(User.id == user.id)
        .values(
            email=None,
            phone=None,
            deleted_at=now,
            updated_at=now,
        )
    )
    counts["user_tombstoned"] = 1

    await session.flush()

    return DeleteReport(
        deleted_at=now,
        section_counts=counts,
        warnings=warnings,
    )
