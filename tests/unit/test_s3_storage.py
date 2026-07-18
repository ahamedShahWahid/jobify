from __future__ import annotations

from io import BytesIO
from unittest.mock import MagicMock

import pytest

from jobify.integrations.storage.s3 import S3Storage


@pytest.mark.asyncio
async def test_s3_storage_round_trip_calls_encrypted_object_api() -> None:
    client = MagicMock()
    client.get_object.return_value = {"Body": BytesIO(b"resume")}
    storage = S3Storage(bucket="jobify", prefix="prod", client=client)

    await storage.save(key="resumes/a.pdf", content=b"resume", content_type="application/pdf")
    assert await storage.read("resumes/a.pdf") == b"resume"
    await storage.delete("resumes/a.pdf")

    client.put_object.assert_called_once_with(
        Bucket="jobify",
        Key="prod/resumes/a.pdf",
        Body=b"resume",
        ContentType="application/pdf",
        ServerSideEncryption="AES256",
    )
    client.delete_object.assert_called_once_with(Bucket="jobify", Key="prod/resumes/a.pdf")


@pytest.mark.asyncio
async def test_s3_storage_rejects_escaping_key() -> None:
    storage = S3Storage(bucket="jobify", client=MagicMock())
    with pytest.raises(ValueError):
        await storage.delete("../secret")
