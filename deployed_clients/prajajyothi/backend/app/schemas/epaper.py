from datetime import date, datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MonetizationSettingsSchema(BaseModel):
    adsense_client_id: str = ""
    auto_ads: bool = False
    header_ad_slot: str = ""
    sidebar_ad_slot: str = ""
    bottom_ad_slot: str = ""
    custom_header_banner_url: str = ""
    custom_header_link: str = ""


class EditionOut(BaseModel):
    id: str
    tenant_id: str
    name: str
    slug: str
    display_order: int
    is_active: bool

    class Config:
        from_attributes = True


class TenantPublicConfigOut(BaseModel):
    id: str
    name: str
    slug: str
    custom_domains: List[str]
    logo_url: Optional[str] = None
    favicon_url: Optional[str] = None
    brand_primary_color: str
    brand_secondary_color: str
    header_title: Optional[str] = None
    footer_text: Optional[str] = None
    copyright_text: Optional[str] = None
    monetization_settings: Dict[str, Any]
    status: str
    editions: List[EditionOut] = []


class ArticleRegionOut(BaseModel):
    id: str
    page_id: str
    title: str
    coordinates: Dict[str, float]
    content_text: Optional[str] = None
    clip_url: Optional[str] = None


class PageOut(BaseModel):
    id: str
    page_number: int
    title: Optional[str] = None
    width: int
    height: int
    dpi: int
    large_url: Optional[str] = None
    medium_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    dzi_url: Optional[str] = None
    articles: List[ArticleRegionOut] = []


class IssueReaderOut(BaseModel):
    id: str
    tenant_id: str
    edition_id: str
    edition_name: str
    edition_slug: str
    publication_date: date
    revision: int
    page_count: int
    status: str
    pdf_url: Optional[str] = None
    pages: List[PageOut] = []


class ArchiveDateItem(BaseModel):
    publication_date: str
    issue_id: str
    edition_slug: str
    edition_name: str
    page_count: int
    thumbnail_url: Optional[str] = None


class ClipCropRequest(BaseModel):
    issue_id: str
    page_number: int
    x: float = Field(..., ge=0.0, le=1.0)
    y: float = Field(..., ge=0.0, le=1.0)
    width: float = Field(..., gt=0.0, le=1.0)
    height: float = Field(..., gt=0.0, le=1.0)
    headline: Optional[str] = None


class ClipCropResponse(BaseModel):
    clip_id: str
    clip_url: str
    share_text: str
    tenant_name: str
    edition_name: str
    publication_date: str
    page_number: int


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]


class TenantBrandingUpdate(BaseModel):
    name: Optional[str] = None
    logo_url: Optional[str] = None
    favicon_url: Optional[str] = None
    brand_primary_color: Optional[str] = None
    brand_secondary_color: Optional[str] = None
    header_title: Optional[str] = None
    footer_text: Optional[str] = None
    copyright_text: Optional[str] = None
    monetization_settings: Optional[Dict[str, Any]] = None


class EditionCreateRequest(BaseModel):
    name: str
    slug: str
    display_order: int = 1
    is_active: bool = True


class ArticleRegionCreateRequest(BaseModel):
    issue_id: str
    page_id: str
    title: str
    coordinates: Dict[str, float]
    content_text: Optional[str] = None


class SuperAdminTenantCreate(BaseModel):
    name: str
    slug: str
    custom_domains: List[str] = []
    brand_primary_color: str = "#dc2626"
    brand_secondary_color: str = "#1e293b"
    header_title: Optional[str] = None
    footer_text: Optional[str] = None
    copyright_text: Optional[str] = None
    admin_email: Optional[str] = None
    admin_password: str = "Admin@123"
    default_editions: List[str] = ["Main Edition"]


class CustomDomainUpdateRequest(BaseModel):
    custom_domains: List[str]
