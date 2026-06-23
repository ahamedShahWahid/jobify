"""Storage protocol + FastAPI dependency.

Keeps the route layer storage-agnostic: routes only see the ``Storage``
protocol and pull a concrete instance via ``Depends(get_storage)``.
"""

from __future__ import annotations

from typing import Protocol

from fastapi import Request


class Storage(Protocol):
    """Object-storage abstraction over async byte payloads.

    Keys are opaque strings; impls decide how to map them to paths/objects.
    Content is `bytes` because the upload cap is small (see settings); a
    streaming variant lands the day we lift the cap into the hundreds of MB.
    """

    async def save(self, *, key: str, content: bytes, content_type: str) -> None: ...
    async def read(self, key: str) -> bytes: ...
    async def delete(self, key: str) -> None: ...


def get_storage(request: Request) -> Storage:
    """FastAPI dependency: pull the configured Storage off ``app.state``."""
    storage: Storage = request.app.state.storage
    return storage
