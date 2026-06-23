"""Sanity checks on the curated skills dictionary."""

from __future__ import annotations

from jobify.integrations.parser.skills_dict import SKILLS


def test_skills_dict_has_minimum_coverage() -> None:
    """The matcher relies on some skill signal — ensure we ship a reasonable set."""
    assert len(SKILLS) >= 150


def test_skills_are_lowercased_and_unique() -> None:
    """The parser does case-insensitive matching and dedupes by lower(); ensure the
    source already is lower so the dedupe is a no-op against this list."""
    lowered = [s.lower() for s in SKILLS]
    assert lowered == list(SKILLS), "dictionary entries must be lowercased"
    assert len(set(SKILLS)) == len(SKILLS), "dictionary entries must be unique"


def test_skills_dict_includes_core_signals() -> None:
    """Smoke test: a handful of well-known skills the matcher should always detect."""
    must_include = {"python", "java", "javascript", "fastapi", "aws", "postgres", "docker"}
    assert must_include.issubset(set(SKILLS))
