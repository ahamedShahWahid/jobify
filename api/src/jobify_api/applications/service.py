"""Transactional application commands independent of HTTP transport concerns."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from jobify.db.models import (
    Application,
    ApplicationStatus,
    Employer,
    Job,
    JobStatus,
    Notification,
    NotificationChannel,
)


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
        await session.execute(
            update(Application)
            .where(Application.id == existing.id)
            .values(
                status=ApplicationStatus.APPLIED,
                source=source,
                created_at=func.now(),
                updated_at=func.now(),
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
