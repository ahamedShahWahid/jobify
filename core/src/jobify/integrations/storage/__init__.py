"""Storage interface + concrete implementations.

The protocol is in :mod:`.base`; local-filesystem and S3-compatible adapters
live in :mod:`.local` and :mod:`.s3`.

The ``get_storage`` FastAPI dependency lives in ``jobify_api.dependencies``
so that the core domain package stays FastAPI-free.
"""

from pathlib import Path
from typing import Literal, Protocol

from jobify.integrations.storage.base import Storage
from jobify.integrations.storage.local import LocalFileStorage
from jobify.integrations.storage.s3 import S3Storage


class StorageSettings(Protocol):
    storage_backend: Literal["local", "s3"]
    storage_root: Path
    s3_bucket: str | None
    s3_prefix: str
    aws_region: str | None
    aws_endpoint_url: str | None
    provider_connect_timeout_seconds: float
    provider_read_timeout_seconds: float


def create_storage(settings: StorageSettings) -> Storage:
    """Build the configured storage adapter."""
    if settings.storage_backend == "local":
        return LocalFileStorage(root=settings.storage_root)
    if settings.storage_backend == "s3":
        if settings.s3_bucket is None:  # defense in depth; Settings validates this
            raise ValueError("s3_bucket is required for S3 storage")
        return S3Storage(
            bucket=settings.s3_bucket,
            prefix=settings.s3_prefix,
            region=settings.aws_region,
            endpoint_url=settings.aws_endpoint_url,
            connect_timeout_seconds=settings.provider_connect_timeout_seconds,
            read_timeout_seconds=settings.provider_read_timeout_seconds,
        )
    raise ValueError(f"unknown storage backend: {settings.storage_backend}")


__all__ = ["LocalFileStorage", "S3Storage", "Storage", "create_storage"]
