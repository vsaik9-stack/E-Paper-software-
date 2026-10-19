import os
from typing import Optional
import aiofiles
from app.core.config import settings
from app.storage.base import AbstractStorageDriver


class LocalStorageDriver(AbstractStorageDriver):
    """Local filesystem storage driver."""

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = base_dir or settings.LOCAL_STORAGE_DIR
        os.makedirs(self.base_dir, exist_ok=True)

    def _get_absolute_path(self, storage_key: str) -> str:
        # Sanitize storage key to prevent directory traversal
        clean_key = storage_key.lstrip("/").replace("..", "_")
        return os.path.abspath(os.path.join(self.base_dir, clean_key))

    async def save(
        self,
        storage_key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> int:
        dest_path = self._get_absolute_path(storage_key)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        async with aiofiles.open(dest_path, "wb") as f:
            await f.write(data)
        return len(data)

    async def get(self, storage_key: str) -> Optional[bytes]:
        file_path = self._get_absolute_path(storage_key)
        if not os.path.exists(file_path):
            return None
        async with aiofiles.open(file_path, "rb") as f:
            return await f.read()

    async def exists(self, storage_key: str) -> bool:
        file_path = self._get_absolute_path(storage_key)
        return os.path.exists(file_path)

    async def delete(self, storage_key: str) -> bool:
        file_path = self._get_absolute_path(storage_key)
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
        return False

    def get_url(
        self,
        storage_key: str,
        expires_in_seconds: Optional[int] = None,
    ) -> str:
        clean_key = storage_key.lstrip("/")
        if settings.CDN_BASE_URL:
            return f"{settings.CDN_BASE_URL.rstrip('/')}/{clean_key}"
        return f"{settings.API_V1_PREFIX}/assets/{clean_key}"
