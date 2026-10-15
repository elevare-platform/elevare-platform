"""Tests for StorageService.get_object_size, used to confirm an interview
recording really arrived before the interview is marked UPLOADED."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from botocore.exceptions import ClientError

from app.core.storage import MockStorageService, R2StorageService


@pytest.mark.asyncio
async def test_mock_storage_reports_size_or_none():
    storage = MockStorageService()
    await storage.upload_file(b"12345", "a/b.webm", "video/webm")

    assert await storage.get_object_size("a/b.webm") == 5
    assert await storage.get_object_size("missing") is None


def _r2_with_head_object(head_object):
    """Build an R2StorageService without credentials, wired to a fake client."""
    s3 = MagicMock()
    s3.head_object = head_object

    client_cm = MagicMock()
    client_cm.__aenter__ = AsyncMock(return_value=s3)
    client_cm.__aexit__ = AsyncMock(return_value=False)

    session = MagicMock()
    session.client = MagicMock(return_value=client_cm)

    service = R2StorageService.__new__(R2StorageService)
    service._bucket = "bucket"
    service._endpoint_url = "https://example.invalid"
    service._session = session
    return service


def _client_error(code):
    return ClientError({"Error": {"Code": code, "Message": "x"}}, "HeadObject")


@pytest.mark.asyncio
async def test_r2_returns_content_length_when_object_exists():
    service = _r2_with_head_object(AsyncMock(return_value={"ContentLength": 4096}))

    assert await service.get_object_size("k") == 4096


@pytest.mark.asyncio
@pytest.mark.parametrize("code", ["404", "NoSuchKey", "NotFound"])
async def test_r2_returns_none_only_for_a_definitive_not_found(code):
    service = _r2_with_head_object(AsyncMock(side_effect=_client_error(code)))

    assert await service.get_object_size("k") is None


@pytest.mark.asyncio
async def test_r2_raises_on_other_errors_so_the_caller_can_decide():
    """A permissions or network error is not evidence the file is missing."""
    service = _r2_with_head_object(AsyncMock(side_effect=_client_error("403")))

    with pytest.raises(ClientError):
        await service.get_object_size("k")
