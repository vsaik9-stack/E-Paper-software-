import hashlib
from typing import Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.models.storage import StorageAsset
from app.storage.base import AbstractStorageDriver
from app.storage.local import LocalStorageDriver
from app.storage.s3 import S3StorageDriver


class StorageService:
    """Central storage service with driver abstraction and database asset registry."""

    def __init__(self, driver: Optional[AbstractStorageDriver] = None):
        if driver:
            self.driver = driver
        elif settings.STORAGE_PROVIDER == "s3":
            self.driver = S3StorageDriver()
        else:
            self.driver = LocalStorageDriver()

    @staticmethod
    def calculate_checksum(data: bytes) -> str:
        """Calculate SHA-256 checksum for binary data."""
        return hashlib.sha256(data).hexdigest()

    async def save_asset(
        self,
        storage_key: str,
        data: bytes,
        asset_type: str,
        mime_type: str = "application/octet-stream",
        original_filename: Optional[str] = None,
        dimensions: Optional[Tuple[int, int]] = None,
        db_session: Optional[AsyncSession] = None,
        tenant_id: Optional[str] = None,
    ) -> StorageAsset:
        """
        Store binary data using the active storage driver and register the asset in the database.
        """
        clean_key = storage_key.lstrip("/")
        bytes_saved = await self.driver.save(clean_key, data, content_type=mime_type)
        checksum = self.calculate_checksum(data)
        width, height = dimensions if dimensions else (None, None)

        asset = StorageAsset(
            tenant_id=tenant_id,
            storage_provider=settings.STORAGE_PROVIDER,
            storage_key=clean_key,
            original_filename=original_filename,
            mime_type=mime_type,
            file_size=bytes_saved,
            width=width,
            height=height,
            checksum=checksum,
            asset_type=asset_type,
        )

        if db_session:
            # Check if asset record already exists for this storage key
            stmt = select(StorageAsset).where(StorageAsset.storage_key == clean_key)
            result = await db_session.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing:
                existing.tenant_id = tenant_id or existing.tenant_id
                existing.storage_provider = settings.STORAGE_PROVIDER
                existing.original_filename = original_filename
                existing.mime_type = mime_type
                existing.file_size = bytes_saved
                existing.width = width
                existing.height = height
                existing.checksum = checksum
                existing.asset_type = asset_type
                asset = existing
            else:
                db_session.add(asset)
            await db_session.flush()

        return asset

    async def get_data(self, storage_key: str) -> Optional[bytes]:
        """Retrieve binary data from storage."""
        return await self.driver.get(storage_key.lstrip("/"))

    async def exists(self, storage_key: str) -> bool:
        """Check if file exists in storage."""
        return await self.driver.exists(storage_key.lstrip("/"))

    async def delete(self, storage_key: str, db_session: Optional[AsyncSession] = None) -> bool:
        """Delete file and its database asset record."""
        clean_key = storage_key.lstrip("/")
        deleted = await self.driver.delete(clean_key)
        if db_session:
            stmt = select(StorageAsset).where(StorageAsset.storage_key == clean_key)
            result = await db_session.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing:
                await db_session.delete(existing)
                await db_session.flush()
        return deleted

    def resolve_url(
        self,
        storage_key: Optional[str],
        expires_in_seconds: Optional[int] = None,
    ) -> Optional[str]:
        """Convert a relative storage key into a full client-accessible URL."""
        if not storage_key:
            return None
        return self.driver.get_url(storage_key.lstrip("/"), expires_in_seconds=expires_in_seconds)


# Singleton instance for general use
storage_service = StorageService()
