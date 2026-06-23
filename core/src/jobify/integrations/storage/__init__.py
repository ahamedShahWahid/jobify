"""Storage interface + concrete implementations.

The protocol is in :mod:`.base`; the local-filesystem impl is in :mod:`.local`.
An S3 impl will live in :mod:`.s3` once it's needed.

The ``get_storage`` FastAPI dependency lives in ``jobify_api.dependencies``
so that the core domain package stays FastAPI-free.
"""

from jobify.integrations.storage.base import Storage
from jobify.integrations.storage.local import LocalFileStorage

__all__ = ["LocalFileStorage", "Storage"]
