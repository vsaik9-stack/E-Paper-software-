from abc import ABC, abstractmethod
from typing import Optional


class AbstractStorageDriver(ABC):
    """Abstract interface for all storage backends (Local, S3, Cloudflare R2, MinIO)."""

    @abstractmethod
    async def save(
        self,
        storage_key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> int:
        """Save binary data to the given storage key. Returns number of bytes saved."""
        pass

    @abstractmethod
    async def get(self, storage_key: str) -> Optional[bytes]:
        """Retrieve binary data from the given storage key."""
        pass

    @abstractmethod
    async def exists(self, storage_key: str) -> bool:
        """Check if a file exists at the given storage key."""
        pass

    @abstractmethod
    async def delete(self, storage_key: str) -> bool:
        """Delete file at the given storage key."""
        pass

    @abstractmethod
    def get_url(
        self,
        storage_key: str,
        expires_in_seconds: Optional[int] = None,
    ) -> str:
        """Resolve public, CDN, or signed download URL for the storage key."""
        pass
