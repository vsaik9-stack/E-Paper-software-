import os
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "PressGrid White-Label E-Paper SaaS Platform"
    API_V1_PREFIX: str = "/api/v1"
    SECRET_KEY: str = os.getenv(
        "SECRET_KEY", "super-secret-epaper-saas-platform-jwt-key-2026-production"
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # Database Configuration (Supports PostgreSQL Asyncpg & Local SQLite Async)
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "sqlite+aiosqlite:///./epaper_saas.db",
    )

    # Multi-Tenancy Default Fallback Slug
    DEFAULT_TENANT_SLUG: str = os.getenv("DEFAULT_TENANT_SLUG", "dishadaily")
    PLATFORM_BASE_DOMAIN: str = os.getenv("PLATFORM_BASE_DOMAIN", "localhost")

    # Storage Configuration
    STORAGE_PROVIDER: str = os.getenv("STORAGE_PROVIDER", "local")  # local or s3
    LOCAL_STORAGE_DIR: str = os.getenv(
        "LOCAL_STORAGE_DIR",
        os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "storage_data")),
    )
    CDN_BASE_URL: Optional[str] = os.getenv("CDN_BASE_URL", None)

    # S3 / Cloudflare R2 / MinIO Configuration
    S3_BUCKET_NAME: Optional[str] = os.getenv("S3_BUCKET_NAME", None)
    S3_ENDPOINT_URL: Optional[str] = os.getenv("S3_ENDPOINT_URL", None)
    S3_ACCESS_KEY_ID: Optional[str] = os.getenv("S3_ACCESS_KEY_ID", None)
    S3_SECRET_ACCESS_KEY: Optional[str] = os.getenv("S3_SECRET_ACCESS_KEY", None)
    S3_REGION_NAME: str = os.getenv("S3_REGION_NAME", "auto")

    # High-Resolution Newspaper Rendering Engine Settings
    PAGE_RENDER_DPI: int = int(os.getenv("PAGE_RENDER_DPI", "220"))
    PAGE_LARGE_MAX_DIMENSION: int = 3200
    PAGE_MEDIUM_MAX_DIMENSION: int = 1600
    PAGE_THUMB_MAX_DIMENSION: int = 450
    PAGE_IMAGE_FORMAT: str = "WEBP"
    PAGE_IMAGE_QUALITY: int = 85

    CORS_ORIGINS: List[str] = ["*"]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
