"""Unit tests for LocalFileStorage.

These tests don't need a DB; they use pytest's `tmp_path` fixture for an
isolated filesystem root per test.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from jobify.integrations.storage.local import LocalFileStorage


async def test_save_and_read_round_trip(tmp_path: Path) -> None:
    storage = LocalFileStorage(root=tmp_path)
    await storage.save(
        key="resumes/abc.pdf", content=b"hello world", content_type="application/pdf"
    )

    out = await storage.read("resumes/abc.pdf")

    assert out == b"hello world"
    assert (tmp_path / "resumes" / "abc.pdf").is_file()


async def test_save_creates_intermediate_directories(tmp_path: Path) -> None:
    storage = LocalFileStorage(root=tmp_path)

    await storage.save(
        key="resumes/2026/05/16/abc.pdf",
        content=b"x",
        content_type="application/pdf",
    )

    assert (tmp_path / "resumes" / "2026" / "05" / "16" / "abc.pdf").is_file()


async def test_delete_removes_the_file(tmp_path: Path) -> None:
    storage = LocalFileStorage(root=tmp_path)
    await storage.save(key="resumes/abc.pdf", content=b"x", content_type="application/pdf")

    await storage.delete("resumes/abc.pdf")

    assert not (tmp_path / "resumes" / "abc.pdf").exists()


async def test_delete_is_idempotent(tmp_path: Path) -> None:
    storage = LocalFileStorage(root=tmp_path)
    # No save before delete — must not raise.
    await storage.delete("resumes/never-existed.pdf")


async def test_read_missing_key_raises_file_not_found(tmp_path: Path) -> None:
    storage = LocalFileStorage(root=tmp_path)
    with pytest.raises(FileNotFoundError):
        await storage.read("resumes/missing.pdf")


async def test_save_rejects_keys_that_escape_root(tmp_path: Path) -> None:
    """Defense in depth: a malicious key must not let the caller write outside root."""
    storage = LocalFileStorage(root=tmp_path)
    with pytest.raises(ValueError, match="must be a relative path under the storage root"):
        await storage.save(key="../escaped.pdf", content=b"x", content_type="application/pdf")
