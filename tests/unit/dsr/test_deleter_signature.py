"""Pure-signature contract test for delete_user_data. No DB."""

from __future__ import annotations

import inspect

from jobify_api.dsr.deleter import DeleteReport, OwnerlessEmployerWarning, delete_user_data


def test_delete_user_data_signature() -> None:
    sig = inspect.signature(delete_user_data)
    params = list(sig.parameters)
    assert params[0] == "session"
    assert sig.parameters["user"].kind == inspect.Parameter.KEYWORD_ONLY
    assert "storage" not in sig.parameters


def test_delete_report_top_level_fields() -> None:
    fields = set(DeleteReport.model_fields.keys())
    expected = {"deleted_at", "section_counts", "warnings"}
    assert fields == expected, f"missing={expected - fields}, extra={fields - expected}"


def test_ownerless_employer_warning_fields() -> None:
    fields = set(OwnerlessEmployerWarning.model_fields.keys())
    expected = {"type", "employer_id", "employer_name", "message"}
    assert fields == expected
