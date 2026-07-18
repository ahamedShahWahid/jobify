"""S3-compatible object storage adapter."""

from __future__ import annotations

import asyncio
from typing import Any


class S3Storage:
    """Async facade over boto3's synchronous S3 client."""

    def __init__(
        self,
        *,
        bucket: str,
        prefix: str = "",
        region: str | None = None,
        endpoint_url: str | None = None,
        connect_timeout_seconds: float = 5.0,
        read_timeout_seconds: float = 30.0,
        client: Any | None = None,
    ) -> None:
        if not bucket:
            raise ValueError("bucket must not be empty")
        self._bucket = bucket
        self._prefix = prefix.strip("/")
        if client is None:
            import boto3
            from botocore.config import Config

            client = boto3.client(
                "s3",
                region_name=region,
                endpoint_url=endpoint_url,
                config=Config(
                    connect_timeout=connect_timeout_seconds,
                    read_timeout=read_timeout_seconds,
                    retries={"mode": "standard", "max_attempts": 3},
                ),
            )
        self._client = client

    def _key(self, key: str) -> str:
        clean = key.lstrip("/")
        if not clean or ".." in clean.split("/"):
            raise ValueError("key must be a safe relative object key")
        return f"{self._prefix}/{clean}" if self._prefix else clean

    async def save(self, *, key: str, content: bytes, content_type: str) -> None:
        await asyncio.to_thread(
            self._client.put_object,
            Bucket=self._bucket,
            Key=self._key(key),
            Body=content,
            ContentType=content_type,
            ServerSideEncryption="AES256",
        )

    async def read(self, key: str) -> bytes:
        response = await asyncio.to_thread(
            self._client.get_object, Bucket=self._bucket, Key=self._key(key)
        )
        return await asyncio.to_thread(response["Body"].read)

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self._client.delete_object, Bucket=self._bucket, Key=self._key(key))
