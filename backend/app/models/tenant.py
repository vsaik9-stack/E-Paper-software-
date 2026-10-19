import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


class Tenant(Base):
    """Newspaper Publisher Tenant (White-Label SaaS Organization)."""
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)

    # Custom Domains e.g. ["epaper.dishadaily.com", "dishadaily.com"]
    custom_domains: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)

    # White-Label Branding
    logo_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    favicon_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    brand_primary_color: Mapped[str] = mapped_column(String(32), default="#dc2626", nullable=False)
    brand_secondary_color: Mapped[str] = mapped_column(String(32), default="#1e293b", nullable=False)
    header_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    footer_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    copyright_text: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    # Monetization & Ad Placements
    # Structure: {"adsense_client_id": "ca-pub-xxx", "auto_ads": False, "header_ad_slot": "", "sidebar_ad_slot": "", "bottom_ad_slot": "", "custom_header_banner_url": "", "custom_header_link": ""}
    monetization_settings: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        default=lambda: {
            "adsense_client_id": "",
            "auto_ads": False,
            "header_ad_slot": "",
            "sidebar_ad_slot": "",
            "bottom_ad_slot": "",
            "custom_header_banner_url": "",
            "custom_header_link": "",
        },
        nullable=False,
    )

    # Status: active, suspended, trial
    status: Mapped[str] = mapped_column(String(32), default="active", index=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    users: Mapped[List["TenantUser"]] = relationship(
        "TenantUser", back_populates="tenant", cascade="all, delete-orphan"
    )
    editions: Mapped[List["Edition"]] = relationship(
        "Edition", back_populates="tenant", cascade="all, delete-orphan"
    )
    issues: Mapped[List["Issue"]] = relationship(
        "Issue", back_populates="tenant", cascade="all, delete-orphan"
    )


class TenantUser(Base):
    """Multi-Tenant User Account (SUPER_ADMIN, TENANT_ADMIN, TENANT_STAFF)."""
    __tablename__ = "tenant_users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    tenant_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=True
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    # Roles: SUPER_ADMIN, TENANT_ADMIN, TENANT_STAFF
    role: Mapped[str] = mapped_column(String(32), default="TENANT_ADMIN", index=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    tenant: Mapped[Optional["Tenant"]] = relationship("Tenant", back_populates="users")
