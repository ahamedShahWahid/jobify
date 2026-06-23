"""Filesystem-backed Storage. Default for local dev + CI.

S3 swap is a config + impl change; nothing in the route layer or the DB
layer needs to know about it.
"""

from __future__ import annotations

import functools
from pathlib import Path

import anyio.to_thread


class LocalFileStorage:
    """Writes under ``root``. ``key`` is treated as a relative path; intermediate
    directories are created on save. Reads and deletes resolve against ``root``.

    Keys that try to escape the root (`..`, absolute paths) raise ``ValueError``.
    """

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    def _resolve(self, key: str) -> Path:
        candidate = (self._root / key).resolve()
        try:
            candidate.relative_to(self._root)
        except ValueError as exc:
            raise ValueError("key must be a relative path under the storage root") from exc
        return candidate

    async def save(self, *, key: str, content: bytes, content_type: str) -> None:
        path = self._resolve(key)
        await anyio.to_thread.run_sync(functools.partial(self._write, path, content))

    @staticmethod
    def _write(path: Path, content: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    async def read(self, key: str) -> bytes:
        path = self._resolve(key)
        return await anyio.to_thread.run_sync(path.read_bytes)

    async def delete(self, key: str) -> None:
        path = self._resolve(key)
        await anyio.to_thread.run_sync(functools.partial(self._unlink, path))

    @staticmethod
    def _unlink(path: Path) -> None:
        path.unlink(missing_ok=True)
