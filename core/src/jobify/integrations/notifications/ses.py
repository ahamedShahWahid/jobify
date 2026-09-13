"""AWS SES email channel."""

from __future__ import annotations

import asyncio
import html
from typing import TYPE_CHECKING, Any

from jobify.integrations.notifications.base import ChannelResult

if TYPE_CHECKING:
    from jobify.db.models import Notification


class SesEmailChannel:
    """Send transactional notifications through SES v2."""

    def __init__(
        self,
        *,
        from_address: str,
        region: str | None = None,
        connect_timeout_seconds: float = 5.0,
        read_timeout_seconds: float = 30.0,
        client: Any | None = None,
    ) -> None:
        if not from_address:
            raise ValueError("from_address must not be empty")
        self._from_address = from_address
        if client is None:
            import boto3
            from botocore.config import Config

            client = boto3.client(
                "sesv2",
                region_name=region,
                config=Config(
                    connect_timeout=connect_timeout_seconds,
                    read_timeout=read_timeout_seconds,
                    # SES sends are non-idempotent. One total attempt keeps the
                    # dispatch lease bound equal to one connect/read window.
                    retries={"mode": "standard", "total_max_attempts": 1},
                ),
            )
        self._client = client

    async def send(
        self,
        notification: Notification,
        *,
        recipient: str,
        language: str = "en",
    ) -> ChannelResult:
        subject, text_body = _render(notification.kind, notification.payload, language)
        try:
            await asyncio.to_thread(
                self._client.send_email,
                FromEmailAddress=self._from_address,
                Destination={"ToAddresses": [recipient]},
                Content={
                    "Simple": {
                        "Subject": {"Data": subject, "Charset": "UTF-8"},
                        "Body": {
                            "Text": {"Data": text_body, "Charset": "UTF-8"},
                            "Html": {
                                "Data": (
                                    "<html><body><h1>"
                                    f"{html.escape(subject)}</h1><p>"
                                    f"{html.escape(text_body).replace(chr(10), '<br>')}"
                                    "</p></body></html>"
                                ),
                                "Charset": "UTF-8",
                            },
                        },
                    }
                },
            )
        except Exception as exc:  # noqa: BLE001 — channel contract: provider failures become ChannelResult.failed (sweep retries)
            return ChannelResult.failed(f"ses:{type(exc).__name__}:{exc}"[:1000])
        return ChannelResult.success()


def _render(kind: str, payload: dict[str, Any], language: str = "en") -> tuple[str, str]:
    # employer_invite always renders English — the invited party's own
    # applicant-side language preference is irrelevant (the invite is to a
    # recruiter/employer account, which never has an ApplicantPreferences row).
    hi = language == "hi" and kind != "employer_invite"
    if kind == "application_received":
        title = str(payload.get("job_title", "इस पद" if hi else "the role"))
        employer = str(payload.get("employer_name", "नियोक्ता" if hi else "the employer"))
        if hi:
            return (
                f"आवेदन प्राप्त हुआ — {title}",
                f"{employer} में {title} के लिए आपका आवेदन प्राप्त हो गया है।",
            )
        return (
            f"Application received — {title}",
            f"Your application for {title} at {employer} has been received.",
        )
    if kind == "employer_invite":
        employer = str(payload.get("employer_name", "an employer"))
        role = str(payload.get("role", "member"))
        return (
            f"You're invited to join {employer} on Jobify",
            f"{employer} invited you to join their Jobify team as {role}. Open Jobify to respond.",
        )
    if kind == "application_stage_changed":
        title = str(payload.get("job_title", "इस पद" if hi else "the role"))
        employer = str(payload.get("employer_name", "नियोक्ता" if hi else "the employer"))
        stage = str(payload.get("stage", ""))
        if stage == "rejected":
            if hi:
                return (
                    f"आपके आवेदन पर अपडेट — {title}",
                    f"नियोक्ता ने {employer} में {title} के लिए अन्य उम्मीदवारों के साथ "
                    "आगे बढ़ने का निर्णय लिया है।",
                )
            return (
                f"Update on your application — {title}",
                f"The employer moved forward with other candidates for {title} at {employer}.",
            )
        if stage == "hired":
            if hi:
                return (
                    f"बधाई हो — {title}, {employer}",
                    f"आपको {employer} में {title} के लिए चुना गया है। "
                    "नियोक्ता अगले चरणों के लिए संपर्क करेंगे।",
                )
            return (
                f"Congratulations — {title} at {employer}",
                f"You've been hired for {title} at {employer}. "
                "The employer will be in touch with next steps.",
            )
        if hi:
            stage_line_hi = {
                "shortlisted": "आपको शॉर्टलिस्ट किया गया है",
                "interview": "आप इंटरव्यू चरण में पहुंच गए हैं",
                "offer": "आपके पास एक ऑफ़र है",
            }
            line_hi = stage_line_hi.get(stage, "आपके आवेदन में बदलाव हुआ है")
            return (
                f"{line_hi} — {title}",
                f"{employer} में {title} के लिए {line_hi}। विवरण के लिए Jobify खोलें।",
            )
        stage_line = {
            "shortlisted": "You've been shortlisted",
            "interview": "You've moved to the interview stage",
            "offer": "You have an offer",
        }
        line = stage_line.get(stage, "Your application was updated")
        return (
            f"{line} — {title}",
            f"{line} for {title} at {employer}. Open Jobify for details.",
        )
    if hi:
        return ("Jobify सूचना", f"आपके लिए एक नई Jobify सूचना है: {kind}।")
    return ("Jobify notification", f"You have a new Jobify notification: {kind}.")
