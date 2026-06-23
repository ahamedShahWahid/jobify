from __future__ import annotations

import pytest
from pydantic import ValidationError

from jobify.routes.employers import EmployerCreate, _normalize_name


def test_normalize_name_lowercases() -> None:
    assert _normalize_name("ACME") == "acme"


def test_normalize_name_collapses_whitespace() -> None:
    assert _normalize_name("Acme   Corp") == "acme corp"


def test_normalize_name_strips() -> None:
    assert _normalize_name("  Acme Corp  ") == "acme corp"


def test_normalize_name_combined() -> None:
    assert _normalize_name("  Acme   Corp  ") == "acme corp"


def test_employer_create_rejects_name_too_short() -> None:
    with pytest.raises(ValidationError):
        EmployerCreate(name="A")


def test_employer_create_accepts_two_char_name() -> None:
    e = EmployerCreate(name="Ab")
    assert e.name == "Ab"
    assert e.gst is None


def test_employer_create_rejects_short_gst() -> None:
    with pytest.raises(ValidationError):
        EmployerCreate(name="Acme", gst="123")


def test_employer_create_rejects_long_gst() -> None:
    with pytest.raises(ValidationError):
        EmployerCreate(name="Acme", gst="X" * 16)


def test_employer_create_accepts_exact_15_char_gst() -> None:
    e = EmployerCreate(name="Acme", gst="X" * 15)
    assert e.gst == "X" * 15


def test_employer_create_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        EmployerCreate.model_validate({"name": "Acme", "unknown": "x"})
