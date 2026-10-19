import os
from typing import Optional
import boto3
from botocore.client import Config
from starlette.concurrency import run_in_threadpool
from app.core.config import settings
from app.storage.base import AbstractStorageDriver


class S3StorageDriver(AbstractStorageDriver):
    """Amazon S3 / Cloudflare R2 / MinIO compatible storage driver."""

    def __init__(self):
        self.bucket = settings.S3_BUCKET_NAME or "epaper-assets"
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL,
            aws_access_key_id=settings.S3_ACCESS_KEY_ID,
            aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
            region_name=settings.S3_REGION_NAME,
            config=Config(signature_version="s3v4"),
        )

    async def save(
        self,
        storage_key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> int:
        clean_key = storage_key.lstrip("/")
        await run_in_threadpool(
            self.client.put_object,
            Bucket=self.bucket,
            Key=clean_key,
            Body=data,
            ContentType=content_type,
            CacheControl="public, max-age=31536000, immutable",
        )
        return len(data)

    async def get(self, storage_key: str) -> Optional[bytes]:
        clean_key = storage_key.lstrip("/")
        try:
            response = await run_in_threadpool(
                self.client.get_object, Bucket=self.bucket, Key=clean_key
            )
            return await run_in_threadpool(response["Body"].read)
        except Exception:
            return None

    async def exists(self, storage_key: str) -> bool:
        clean_key = storage_key.lstrip("/")
        try:
            await run_in_threadpool(
                self.client.head_object, Bucket=self.bucket, Key=clean_key
            )
            return True
        except Exception:
            return False

    async def delete(self, storage_key: str) -> bool:
        clean_key = storage_key.lstrip("/")
        try:
            await run_in_threadpool(
                self.client.delete_object, Bucket=self.bucket, Key=clean_key
            )
            return True
        except Exception:
            return False

    def get_url(
        self,
        storage_key: str,
        expires_in_seconds: Optional[int] = None,
    ) -> str:
        clean_key = storage_key.lstrip("/")
        if settings.CDN_BASE_URL:
            return f"{settings.CDN_BASE_URL.rstrip('/')}/{clean_key}"
        if expires_in_seconds:
            return self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": clean_key},
                ExpiresIn=expires_in_seconds,
            )
        return f"{settings.API_V1_PREFIX}/assets/{clean_key}"
