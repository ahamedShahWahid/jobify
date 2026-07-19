"""DSR export builder — DPDP § 11 right-of-access.

Exports:
    UserExport      — Pydantic v2 envelope model (22 top-level fields).
    build_user_export — async read-only assembly function.

This module does NOT write audit rows. The route handler (routes/dsr.py)
writes user.dsr_export_requested and user.dsr_export_completed around this
call so the request row is durable even if assembly fails.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.db.models import (
    Applicant,
    ApplicantEmbedding,
    ApplicantPreferences,
    Application,
    ApplicationStageEvent,
    AuditLog,
    Employer,
    EmployerInvite,
    EmployerUser,
    Job,
    Match,
    MatchFeedback,
    Notification,
    OAuthIdentity,
    Resume,
    SavedJob,
    User,
    UserConsent,
    UserRole,
)

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class RedactionEntry(BaseModel):
    type: str
    reason: str


class UserExport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str = "1"
    exported_at: datetime
    exported_for_user_id: UUID

    user: dict[str, Any]
    applicant: dict[str, Any] | None = None
    # ALL preferences rows we hold (live + soft-deleted), matching the
    # resumes convention below — export everything, no deleted_at filter.
    applicant_preferences: list[dict[str, Any]] = []

    oauth_identities: list[dict[str, Any]] = []
    resumes: list[dict[str, Any]] = []
    applicant_embedding: dict[str, Any] | None = None
    applications: list[dict[str, Any]] = []
    # ALL stage-transition events for the applicant's applications, no
    # deleted_at filter — export convention, matching applications above.
    application_stage_events: list[dict[str, Any]] = []
    saved_jobs: list[dict[str, Any]] = []
    matches: list[dict[str, Any]] = []
    match_feedback: list[dict[str, Any]] = []
    notifications: list[dict[str, Any]] = []
    user_consents: list[dict[str, Any]] = []
    audit_history: list[dict[str, Any]] = []

    employer_memberships: list[dict[str, Any]] = []
    owned_jobs: list[dict[str, Any]] = []
    # Employer invites addressed to this user's email (any role) and invites
    # this user sent as an owner (recruiter/admin).
    received_invites: list[dict[str, Any]] = []
    sent_invites: list[dict[str, Any]] = []

    redactions: list[RedactionEntry] = []
    notes: list[str] = []


# ---------------------------------------------------------------------------
# Static constants
# ---------------------------------------------------------------------------

_REDACTIONS = [
    RedactionEntry(
        type="refresh_tokens",
        reason=(
            "Session secrets — not personal data; would let an exposed export"
            " be used to impersonate the user."
        ),
    ),
    RedactionEntry(
        type="resume_binaries",
        reason="Metadata included; binaries downloadable on request from privacy@jobify.",
    ),
]

_NOTES = [
    "This export was generated automatically.",
    "For data older than your sign-up date, contact privacy@jobify.",
    "Resume PDFs/DOCXs are not included in this JSON — request copies separately.",
]


# ---------------------------------------------------------------------------
# Row serialization helper
# ---------------------------------------------------------------------------

# Defensive denylist — any column with one of these names is dropped from the
# export, regardless of which table it lives on. Today the codebase has none
# of these (OAuth-only auth, no MFA yet, RefreshToken table is never queried
# by this module). The list exists so that when MFA / new OAuth-token storage
# / additional secrets ship in later sub-projects, those columns do NOT
# silently land in a user's DSR export. Adding a new sensitive column
# anywhere in db/models.py and forgetting it here is a real risk — the
# integration test `test_row_to_dict_drops_redacted_columns` pins the
# contract.
_REDACTED_COLUMN_NAMES: frozenset[str] = frozenset(
    {
        # MFA (reserved for future sub-project)
        "totp_secret",
        "totp_recovery_codes",
        "mfa_secret",
        "recovery_codes",
        # Raw OAuth tokens (we don't store these today; defensive against
        # future provider impls that do).
        "access_token",
        "refresh_token",
        "id_token",
        "token_secret",
        # Hashed credentials (we're OAuth-only today; defensive against a
        # future password-auth provider).
        "password_hash",
        # RefreshToken table is never queried by this module, but defensive
        # in case future code reaches in.
        "token_hash",
    }
)

# Suffix patterns that always indicate sensitive data, regardless of table.
# A future column named "session_secret" or "webhook_signing_token" would be
# caught by this without needing to extend the explicit set above.
_REDACTED_COLUMN_SUFFIXES: tuple[str, ...] = (
    "_secret",
    "_password",
)


def _is_redacted_column(name: str) -> bool:
    if name in _REDACTED_COLUMN_NAMES:
        return True
    return any(name.endswith(suffix) for suffix in _REDACTED_COLUMN_SUFFIXES)


def _row_to_dict(row: object) -> dict[str, Any]:
    """SQLAlchemy ORM row → dict via column introspection. Includes every
    mapped column EXCEPT those flagged by _is_redacted_column. Does NOT walk
    relationships.

    The denylist is module-wide — any column named `totp_secret`,
    `*_secret`, etc. is dropped regardless of which table it belongs to.
    This is defense against future schema additions that introduce
    sensitive fields whose authors forget to update the DSR builder. See
    `test_row_to_dict_drops_redacted_columns` for the pinned contract.
    """
    state = row.__dict__.copy()
    state.pop("_sa_instance_state", None)
    # Convert enums, datetimes, and UUIDs to strings for JSON friendliness.
    # Order matters: StrEnum check must come BEFORE hex check because enum
    # instances also satisfy hasattr(v, "isoformat") or hasattr(v, "hex") in
    # some edge cases; explicit enum handling is always correct and comes first.
    out: dict[str, Any] = {}
    for k, v in state.items():
        if _is_redacted_column(k):
            continue
        if hasattr(v, "value") and hasattr(type(v), "__members__"):  # StrEnum / Enum
            out[k] = v.value
        elif hasattr(v, "tolist"):  # numpy.ndarray — pgvector's asyncpg codec
            # returns vectors as ndarray on a real DB round-trip; pydantic
            # cannot JSON-serialize it (live 500 on export until converted).
            out[k] = v.tolist()
        elif hasattr(v, "isoformat"):  # datetime
            out[k] = v.isoformat()
        elif hasattr(v, "hex"):  # UUID
            out[k] = str(v)
        else:
            out[k] = v
    return out


# ---------------------------------------------------------------------------
# Public builder
# ---------------------------------------------------------------------------


async def build_user_export(
    session: AsyncSession,
    *,
    user: User,
) -> UserExport:
    """Assemble the export envelope. Pure read-only — does not write any
    audit row. The route handler writes the audit rows around this call.

    Raises nothing custom — DB errors propagate to the route, which
    converts to 500 via the standard handler.

    TODO(scale): the ~12 section queries run serially on one session
    (AsyncSession is not safe for concurrent use). Acceptable at MVP volume;
    if assembly time grows, switch the route to 202 + async delivery rather
    than parallelizing here.
    """
    user_dict = _row_to_dict(user)

    applicant_row = (
        await session.execute(select(Applicant).where(Applicant.user_id == user.id))
    ).scalar_one_or_none()
    applicant_dict = _row_to_dict(applicant_row) if applicant_row else None

    oauth_rows = (
        (await session.execute(select(OAuthIdentity).where(OAuthIdentity.user_id == user.id)))
        .scalars()
        .all()
    )

    resumes: list[dict[str, Any]] = []
    embedding_dict: dict[str, Any] | None = None
    applications: list[dict[str, Any]] = []
    application_stage_events: list[dict[str, Any]] = []
    saved_jobs: list[dict[str, Any]] = []
    matches: list[dict[str, Any]] = []
    match_feedback: list[dict[str, Any]] = []
    applicant_preferences: list[dict[str, Any]] = []

    if applicant_row is not None:
        applicant_id = applicant_row.id
        applicant_preferences = [
            _row_to_dict(p)
            for p in (
                await session.execute(
                    select(ApplicantPreferences).where(
                        ApplicantPreferences.applicant_id == applicant_id
                    )
                )
            )
            .scalars()
            .all()
        ]
        resumes = [
            _row_to_dict(r)
            for r in (
                await session.execute(select(Resume).where(Resume.applicant_id == applicant_id))
            )
            .scalars()
            .all()
        ]
        embedding_row = (
            await session.execute(
                select(ApplicantEmbedding).where(ApplicantEmbedding.applicant_id == applicant_id)
            )
        ).scalar_one_or_none()
        if embedding_row is not None:
            embedding_dict = _row_to_dict(embedding_row)
        applications = [
            _row_to_dict(a)
            for a in (
                await session.execute(
                    select(Application).where(Application.applicant_id == applicant_id)
                )
            )
            .scalars()
            .all()
        ]
        application_stage_events = [
            _row_to_dict(r)
            for r in (
                await session.execute(
                    select(ApplicationStageEvent)
                    .join(
                        Application,
                        Application.id == ApplicationStageEvent.application_id,
                    )
                    .where(Application.applicant_id == applicant_id)
                    .order_by(ApplicationStageEvent.created_at)
                )
            )
            .scalars()
            .all()
        ]
        saved_jobs = [
            _row_to_dict(s)
            for s in (
                await session.execute(select(SavedJob).where(SavedJob.applicant_id == applicant_id))
            )
            .scalars()
            .all()
        ]
        matches = [
            _row_to_dict(m)
            for m in (
                await session.execute(select(Match).where(Match.applicant_id == applicant_id))
            )
            .scalars()
            .all()
        ]
        match_feedback = [
            _row_to_dict(r)
            for r in (
                await session.execute(
                    select(MatchFeedback).where(MatchFeedback.applicant_id == applicant_id)
                )
            )
            .scalars()
            .all()
        ]

    notifications = [
        _row_to_dict(n)
        for n in (
            await session.execute(select(Notification).where(Notification.user_id == user.id))
        )
        .scalars()
        .all()
    ]

    user_consents = [
        _row_to_dict(c)
        for c in (await session.execute(select(UserConsent).where(UserConsent.user_id == user.id)))
        .scalars()
        .all()
    ]

    audit_history = [
        _row_to_dict(a)
        for a in (
            await session.execute(
                select(AuditLog)
                .where(AuditLog.actor_user_id == user.id)
                .order_by(AuditLog.created_at.desc())
            )
        )
        .scalars()
        .all()
    ]

    employer_memberships: list[dict[str, Any]] = []
    owned_jobs: list[dict[str, Any]] = []

    if user.role in (UserRole.RECRUITER, UserRole.ADMIN):
        eu_rows = (
            await session.execute(
                select(EmployerUser, Employer)
                .join(Employer, Employer.id == EmployerUser.employer_id)
                .where(EmployerUser.user_id == user.id)
            )
        ).all()
        for eu, emp in eu_rows:
            entry = _row_to_dict(eu)
            entry["employer"] = _row_to_dict(emp)
            employer_memberships.append(entry)

        if eu_rows:
            employer_ids = [eu.employer_id for eu, _ in eu_rows]
            owned_jobs = [
                _row_to_dict(j)
                for j in (
                    await session.execute(select(Job).where(Job.employer_id.in_(employer_ids)))
                )
                .scalars()
                .all()
            ]

    # Employer invites — the invitee's email is PII. Surface invites addressed
    # to this user (any role; even applicants receive invites) and, for
    # recruiters/admins, the invites they sent.
    received_invites: list[dict[str, Any]] = []
    sent_invites: list[dict[str, Any]] = []
    if user.email:
        received_rows = (
            await session.execute(
                select(EmployerInvite, Employer.name)
                .join(Employer, Employer.id == EmployerInvite.employer_id)
                .where(func.lower(EmployerInvite.email) == user.email.lower())
            )
        ).all()
        for inv, employer_name in received_rows:
            entry = _row_to_dict(inv)
            entry["employer_name"] = employer_name
            received_invites.append(entry)
    if user.role in (UserRole.RECRUITER, UserRole.ADMIN):
        sent_invites = [
            _row_to_dict(inv)
            for inv in (
                await session.execute(
                    select(EmployerInvite).where(EmployerInvite.invited_by_user_id == user.id)
                )
            )
            .scalars()
            .all()
        ]

    return UserExport(
        exported_at=datetime.now(UTC),
        exported_for_user_id=user.id,
        user=user_dict,
        applicant=applicant_dict,
        applicant_preferences=applicant_preferences,
        oauth_identities=[_row_to_dict(o) for o in oauth_rows],
        resumes=resumes,
        applicant_embedding=embedding_dict,
        applications=applications,
        application_stage_events=application_stage_events,
        saved_jobs=saved_jobs,
        matches=matches,
        match_feedback=match_feedback,
        notifications=notifications,
        user_consents=user_consents,
        audit_history=audit_history,
        employer_memberships=employer_memberships,
        owned_jobs=owned_jobs,
        received_invites=received_invites,
        sent_invites=sent_invites,
        redactions=list(_REDACTIONS),
        notes=list(_NOTES),
    )
