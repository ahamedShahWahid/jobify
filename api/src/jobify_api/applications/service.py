"""Transactional application commands independent of HTTP transport concerns."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.audit import audit_log
from jobify.db.models import (
    Applicant,
    Application,
    ApplicationStage,
    ApplicationStageEvent,
    ApplicationStatus,
    Employer,
    Job,
    JobStatus,
    Notification,
    NotificationChannel,
    User,
)

_log = structlog.get_logger(__name__)


class ApplicationCommandError(Exception):
    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


@dataclass(frozen=True)
class ApplyOutcome:
    application: Application
    created: bool


async def apply_to_open_job(
    session: AsyncSession,
    *,
    applicant_id: uuid.UUID,
    user_id: uuid.UUID,
    job_id: uuid.UUID,
    source: str,
) -> ApplyOutcome:
    """Apply idempotently and create first-application notifications atomically."""
    job_employer = (
        await session.execute(
            select(Job, Employer)
            .join(Employer, Employer.id == Job.employer_id)
            .where(
                Job.id == job_id,
                Job.status == JobStatus.OPEN,
                Job.deleted_at.is_(None),
                Employer.deleted_at.is_(None),
            )
        )
    ).first()
    if job_employer is None:
        raise ApplicationCommandError("job_not_found")
    job, employer = job_employer

    existing = (
        await session.execute(
            select(Application).where(
                Application.applicant_id == applicant_id,
                Application.job_id == job_id,
                Application.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        if existing.status == ApplicationStatus.APPLIED:
            return ApplyOutcome(application=existing, created=False)
        old_stage = existing.stage
        await session.execute(
            update(Application)
            .where(Application.id == existing.id)
            .values(
                status=ApplicationStatus.APPLIED,
                stage=ApplicationStage.APPLIED.value,
                source=source,
                created_at=func.now(),
                updated_at=func.now(),
            )
        )
        if old_stage != ApplicationStage.APPLIED.value:
            session.add(
                ApplicationStageEvent(
                    application_id=existing.id,
                    from_stage=old_stage,
                    to_stage=ApplicationStage.APPLIED.value,
                    actor_user_id=user_id,
                )
            )
        await session.commit()
        refreshed = (
            await session.execute(select(Application).where(Application.id == existing.id))
        ).scalar_one()
        return ApplyOutcome(application=refreshed, created=False)

    application = Application(
        applicant_id=applicant_id,
        job_id=job_id,
        status=ApplicationStatus.APPLIED,
        source=source,
    )
    session.add(application)
    await session.flush()
    notification_payload = {
        "kind": "application_received",
        "application_id": str(application.id),
        "job_id": str(job.id),
        "job_title": job.title,
        "employer_name": employer.name,
    }
    session.add_all(
        [
            Notification(
                user_id=user_id,
                kind="application_received",
                channel=channel,
                payload=notification_payload,
            )
            for channel in (NotificationChannel.EMAIL, NotificationChannel.IN_APP)
        ]
    )
    await session.commit()
    await session.refresh(application)
    return ApplyOutcome(application=application, created=True)


async def withdraw_application(
    session: AsyncSession,
    *,
    applicant_id: uuid.UUID,
    application_id: uuid.UUID,
    target_status: str,
) -> Application:
    """Apply the only supported transition: applied to withdrawn."""
    application = (
        await session.execute(
            select(Application).where(
                Application.id == application_id,
                Application.applicant_id == applicant_id,
                Application.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if application is None:
        raise ApplicationCommandError("application_not_found")
    if target_status != ApplicationStatus.WITHDRAWN.value:
        raise ApplicationCommandError("invalid_transition")
    if application.status == ApplicationStatus.WITHDRAWN:
        return application
    if application.status != ApplicationStatus.APPLIED:
        raise ApplicationCommandError("invalid_transition")

    await session.execute(
        update(Application)
        .where(Application.id == application.id)
        .values(status=ApplicationStatus.WITHDRAWN, updated_at=func.now())
    )
    await session.commit()
    return (
        await session.execute(select(Application).where(Application.id == application.id))
    ).scalar_one()


class StageChangeError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def _stage_notification_payload(
    *, application: Application, job: Job, employer: Employer, stage: str
) -> dict[str, str]:
    return {
        "kind": "application_stage_changed",
        "application_id": str(application.id),
        "job_id": str(job.id),
        "job_title": job.title,
        "employer_name": employer.name,
        "stage": stage,
    }


async def change_application_stage(
    session: AsyncSession,
    *,
    job: Job,
    application_id: uuid.UUID,
    actor: User,
    target_stage: str,
) -> Application:
    """Move an application to ``target_stage`` (recruiter pipeline).

    Caller has already validated recruiter membership + job ownership
    (``_load_recruiter_job``). One transaction: structlog -> audit ->
    stage event -> dual-channel notification. Same-stage = no-op.
    Raises StageChangeError(404/409).
    """
    row = (
        await session.execute(
            select(Application, Applicant, Employer)
            .join(Applicant, Applicant.id == Application.applicant_id)
            .join(Job, Job.id == Application.job_id)
            .join(Employer, Employer.id == Job.employer_id)
            .where(
                Application.id == application_id,
                Application.job_id == job.id,
                Application.deleted_at.is_(None),
                Applicant.deleted_at.is_(None),
                Employer.deleted_at.is_(None),
            )
        )
    ).first()
    if row is None:
        raise StageChangeError(404, "application_not_found")
    application: Application
    applicant: Applicant
    employer: Employer
    application, applicant, employer = row

    if application.status == ApplicationStatus.WITHDRAWN:
        raise StageChangeError(409, "application_withdrawn")

    if application.stage == target_stage:
        return application  # no-op: no event, no notification, no audit

    from_stage = application.stage
    _log.info(
        "recruiter.application-stage-changed",
        application_id=str(application.id),
        job_id=str(job.id),
        from_stage=from_stage,
        to_stage=target_stage,
    )
    await audit_log(
        session,
        action="application.stage_changed",
        actor=actor,
        resource_type="application",
        resource_id=application.id,
        context={"from_stage": from_stage, "to_stage": target_stage},
    )
    application.stage = target_stage
    session.add(
        ApplicationStageEvent(
            application_id=application.id,
            from_stage=from_stage,
            to_stage=target_stage,
            actor_user_id=actor.id,
        )
    )
    payload = _stage_notification_payload(
        application=application, job=job, employer=employer, stage=target_stage
    )
    session.add_all(
        [
            Notification(
                user_id=applicant.user_id,
                kind="application_stage_changed",
                channel=channel,
                payload=payload,
            )
            for channel in (NotificationChannel.EMAIL, NotificationChannel.IN_APP)
        ]
    )
    await session.commit()
    await session.refresh(application)
    return application
