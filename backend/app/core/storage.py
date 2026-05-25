from abc import ABC, abstractmethod

import aioboto3

from app.core.config import settings


class StorageService(ABC):
    """Abstract interface for file storage operations."""

    @abstractmethod
    async def upload_file(self, file: bytes, key: str, content_type: str) -> str:
        """Upload a file and return its key."""
        ...

    @abstractmethod
    async def delete_file(self, key: str) -> None:
        """Delete a file by its key."""
        ...

    @abstractmethod
    async def generate_presigned_url(self, key: str, expires_seconds: int) -> str:
        """Generate a short-lived URL for accessing a private file."""
        ...


class MockStorageService(StorageService):
    """In-memory storage for tests. No network calls, no credentials."""

    def __init__(self) -> None:
        self._store: dict[str, bytes] = {}

    async def upload_file(self, file: bytes, key: str, content_type: str) -> str:
        self._store[key] = file
        return key

    async def delete_file(self, key: str) -> None:
        self._store.pop(key, None)

    async def generate_presigned_url(self, key: str, expires_seconds: int) -> str:
        return f"https://mock-storage/{key}"


class R2StorageService(StorageService):
    """Concrete R2 implementation using aioboto3."""

    def __init__(self) -> None:
        if not all([
            settings.r2_access_key_id,
            settings.r2_secret_access_key,
            settings.r2_bucket_name,
            settings.r2_endpoint_url,
        ]):
            raise RuntimeError(
                "R2 storage is not configured. "
                "Set R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, "
                "R2_BUCKET_NAME, and R2_ENDPOINT_URL in your environment."
            )

        self._bucket = settings.r2_bucket_name
        self._session = aioboto3.Session(
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
            region_name=settings.r2_region,
        )
        self._endpoint_url = settings.r2_endpoint_url

    async def upload_file(self, file: bytes, key: str, content_type: str) -> str:
        async with self._session.client("s3", endpoint_url=self._endpoint_url) as s3:
            await s3.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=file,
                ContentType=content_type,
            )
        return key

    async def delete_file(self, key: str) -> None:
        async with self._session.client("s3", endpoint_url=self._endpoint_url) as s3:
            await s3.delete_object(Bucket=self._bucket, Key=key)

    async def generate_presigned_url(self, key: str, expires_seconds: int) -> str:
        async with self._session.client("s3", endpoint_url=self._endpoint_url) as s3:
            return await s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": key},
                ExpiresIn=expires_seconds,
            )


def get_storage_service() -> StorageService:
    """FastAPI dependency — returns R2 in production, Mock in CI."""
    if settings.r2_access_key_id:
        return R2StorageService()
    return MockStorageService()
