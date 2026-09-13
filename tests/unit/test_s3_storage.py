from __future__ import annotations

from io import BytesIO
from unittest.mock import MagicMock

import pytest
from prometheus_client import REGISTRY

from jobify.integrations.storage.s3 import S3Storage


def _external_calls(service: str, operation: str, outcome: str) -> float:
    labels = {"service": service, "operation": operation, "outcome": outcome}
    return REGISTRY.get_sample_value("jobify_external_calls_total", labels) or 0.0


@pytest.mark.asyncio
async def test_s3_storage_round_trip_calls_encrypted_object_api() -> None:
    client = MagicMock()
    client.get_object.return_value = {"Body": BytesIO(b"resume")}
    storage = S3Storage(bucket="jobify", prefix="prod", client=client)
    before_put = _external_calls("s3", "put_object", "success")
    before_get = _external_calls("s3", "get_object", "success")
    before_delete = _external_calls("s3", "delete_object", "success")

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
    assert _external_calls("s3", "put_object", "success") == before_put + 1
    assert _external_calls("s3", "get_object", "success") == before_get + 1
    assert _external_calls("s3", "delete_object", "success") == before_delete + 1


@pytest.mark.asyncio
async def test_s3_storage_rejects_escaping_key() -> None:
    storage = S3Storage(bucket="jobify", client=MagicMock())
    with pytest.raises(ValueError):
        await storage.delete("../secret")
