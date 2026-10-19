import uuid
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


class Edition(Base):
    """Newspaper Regional or Supplement Edition scoped to a Tenant."""
    __tablename__ = "editions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="editions")
    issues: Mapped[List["Issue"]] = relationship(
        "Issue", back_populates="edition", cascade="all, delete-orphan"
    )


class Issue(Base):
    """Daily Publication Issue for a specific Edition and Tenant."""
    __tablename__ = "issues"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    edition_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("editions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    publication_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pdf_storage_key: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    pdf_file_size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Status: DRAFT, PROCESSING, PUBLISHED, FAILED
    status: Mapped[str] = mapped_column(String(32), default="DRAFT", index=True, nullable=False)
    processing_progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    processing_message: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    views_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="issues")
    edition: Mapped["Edition"] = relationship("Edition", back_populates="issues")
    pages: Mapped[List["Page"]] = relationship(
        "Page",
        back_populates="issue",
        cascade="all, delete-orphan",
        order_by="Page.page_number",
    )
    articles: Mapped[List["ArticleRegion"]] = relationship(
        "ArticleRegion", back_populates="issue", cascade="all, delete-orphan"
    )


class Page(Base):
    """Rendered Broadsheet Newspaper Page with Deep Zoom DZI & Multi-Resolution WebP Assets."""
    __tablename__ = "pages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    tenant_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=True
    )
    issue_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("issues.id", ondelete="CASCADE"), index=True, nullable=False
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)

    original_image_key: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    large_image_key: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    medium_image_key: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    thumbnail_image_key: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    dzi_key: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    width: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    height: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    dpi: Mapped[int] = mapped_column(Integer, default=220, nullable=False)
    rotation: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    processing_status: Mapped[str] = mapped_column(String(32), default="COMPLETED", nullable=False)
    ocr_status: Mapped[str] = mapped_column(String(32), default="PENDING", nullable=False)
    article_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    issue: Mapped["Issue"] = relationship("Issue", back_populates="pages")
    articles: Mapped[List["ArticleRegion"]] = relationship(
        "ArticleRegion", back_populates="page", cascade="all, delete-orphan"
    )


class ArticleRegion(Base):
    """Mapped Clickable Article Region on a Broadsheet Page."""
    __tablename__ = "article_regions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    issue_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("issues.id", ondelete="CASCADE"), index=True, nullable=False
    )
    page_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("pages.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    # Normalized bounding box: {"x": 0.1, "y": 0.2, "width": 0.4, "height": 0.3}
    coordinates: Mapped[Dict[str, float]] = mapped_column(JSON, nullable=False)
    content_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    clip_image_key: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    issue: Mapped["Issue"] = relationship("Issue", back_populates="articles")
    page: Mapped["Page"] = relationship("Page", back_populates="articles")
