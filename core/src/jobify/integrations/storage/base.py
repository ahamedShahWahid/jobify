"""Storage protocol.

Keeps the route layer storage-agnostic: routes only see the ``Storage``
protocol and pull a concrete instance via ``Depends(get_storage)`` (defined
in ``jobify_api.dependencies``).
"""

from __future__ import annotations

from typing import Protocol


class Storage(Protocol):
    """Object-storage abstraction over async byte payloads.

    Keys are opaque strings; impls decide how to map them to paths/objects.
    Content is `bytes` because the upload cap is small (see settings); a
    streaming variant lands the day we lift the cap into the hundreds of MB.
    """

    async def save(self, *, key: str, content: bytes, content_type: str) -> None: ...
    async def read(self, key: str) -> bytes: ...
    async def delete(self, key: str) -> None: ...
