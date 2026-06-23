"""Storage interface + concrete implementations.

The protocol is in :mod:`.base`; the local-filesystem impl is in :mod:`.local`.
An S3 impl will live in :mod:`.s3` once it's needed.
"""

from jobify.integrations.storage.base import Storage, get_storage
from jobify.integrations.storage.local import LocalFileStorage

__all__ = ["LocalFileStorage", "Storage", "get_storage"]
