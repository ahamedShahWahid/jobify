from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from jobify.db.models import OutboxEventKind
from jobify.outbox import (
    enqueue_blob_delete,
    enqueue_task,
    validate_blob_payload,
    validate_task_payload,
)


def test_enqueue_task_stages_event_without_committing() -> None:
    session = MagicMock()
    event = enqueue_task(session, "jobify.parse_resume", "resume-id")
    assert event.kind == OutboxEventKind.TASK_DISPATCH
    assert event.payload == {"task_name": "jobify.parse_resume", "args": ["resume-id"]}
    session.add.assert_called_once_with(event)
    session.commit.assert_not_called()


def test_enqueue_blob_delete_stages_event() -> None:
    session = MagicMock()
    event = enqueue_blob_delete(session, "resumes/id.pdf")
    assert event.kind == OutboxEventKind.BLOB_DELETE
    assert event.payload == {"storage_key": "resumes/id.pdf"}


@pytest.mark.parametrize("payload", [{}, {"task_name": "", "args": []}, {"task_name": "x"}])
def test_invalid_task_payload_rejected(payload: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        validate_task_payload(payload)


def test_invalid_blob_payload_rejected() -> None:
    with pytest.raises(ValueError):
        validate_blob_payload({"storage_key": ""})
