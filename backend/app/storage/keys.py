from datetime import date
from typing import Optional, Union


def sanitize_slug(name: str) -> str:
    """Ensure safe path characters."""
    return "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in name.lower()).strip("_")


def _tenant_prefix(tenant_id: Optional[str]) -> str:
    if tenant_id:
        return f"tenants/{sanitize_slug(str(tenant_id))}/"
    return ""


def build_issue_pdf_key(
    pub_date: Union[date, str],
    edition_slug: str,
    revision: int = 1,
    tenant_id: Optional[str] = None,
) -> str:
    """Generate canonical storage key for the raw uploaded issue PDF."""
    if isinstance(pub_date, str):
        pub_date = date.fromisoformat(pub_date)
    slug = sanitize_slug(edition_slug)
    prefix = _tenant_prefix(tenant_id)
    return f"{prefix}issues/{pub_date.year}/{pub_date.month:02d}/{pub_date.day:02d}/{slug}/rev_{revision}/original.pdf"


def build_page_image_key(
    pub_date: Union[date, str],
    edition_slug: str,
    page_number: int,
    variant: str = "large",  # original, large, medium, thumb
    extension: str = "webp",
    revision: int = 1,
    tenant_id: Optional[str] = None,
) -> str:
    """Generate canonical storage key for rendered newspaper page images."""
    if isinstance(pub_date, str):
        pub_date = date.fromisoformat(pub_date)
    slug = sanitize_slug(edition_slug)
    prefix = _tenant_prefix(tenant_id)
    return (
        f"{prefix}issues/{pub_date.year}/{pub_date.month:02d}/{pub_date.day:02d}/{slug}/"
        f"rev_{revision}/pages/p_{page_number:03d}_{variant}.{extension}"
    )


def build_page_dzi_key(
    pub_date: Union[date, str],
    edition_slug: str,
    page_number: int,
    revision: int = 1,
    tenant_id: Optional[str] = None,
) -> str:
    """Generate canonical storage key for the DeepZoom XML manifest."""
    if isinstance(pub_date, str):
        pub_date = date.fromisoformat(pub_date)
    slug = sanitize_slug(edition_slug)
    prefix = _tenant_prefix(tenant_id)
    return (
        f"{prefix}issues/{pub_date.year}/{pub_date.month:02d}/{pub_date.day:02d}/{slug}/"
        f"rev_{revision}/pages/p_{page_number:03d}_dzi.dzi"
    )


def build_page_tile_key(
    pub_date: Union[date, str],
    edition_slug: str,
    page_number: int,
    level: int,
    col: int,
    row: int,
    extension: str = "webp",
    revision: int = 1,
    tenant_id: Optional[str] = None,
) -> str:
    """Generate canonical storage key for individual DeepZoom pyramid tile."""
    if isinstance(pub_date, str):
        pub_date = date.fromisoformat(pub_date)
    slug = sanitize_slug(edition_slug)
    prefix = _tenant_prefix(tenant_id)
    return (
        f"{prefix}issues/{pub_date.year}/{pub_date.month:02d}/{pub_date.day:02d}/{slug}/"
        f"rev_{revision}/pages/p_{page_number:03d}_dzi_files/{level}/{col}_{row}.{extension}"
    )


def build_clip_key(
    article_id: str,
    variant: str = "high_res",  # high_res, social, thumb
    extension: str = "jpg",
    tenant_id: Optional[str] = None,
) -> str:
    """Generate canonical storage key for generated branded clips."""
    prefix = _tenant_prefix(tenant_id)
    return f"{prefix}clips/{article_id}/{variant}.{extension}"


def build_edition_logo_key(edition_slug: str, filename: str, tenant_id: Optional[str] = None) -> str:
    """Generate canonical storage key for edition logos."""
    slug = sanitize_slug(edition_slug)
    clean_fn = sanitize_slug(filename.split(".")[0])
    ext = filename.split(".")[-1] if "." in filename else "png"
    prefix = _tenant_prefix(tenant_id)
    return f"{prefix}editions/{slug}/logo_{clean_fn}.{ext}"


def build_category_logo_key(category_slug: str, filename: str, tenant_id: Optional[str] = None) -> str:
    """Generate canonical storage key for category logos."""
    slug = sanitize_slug(category_slug)
    clean_fn = sanitize_slug(filename.split(".")[0])
    ext = filename.split(".")[-1] if "." in filename else "png"
    prefix = _tenant_prefix(tenant_id)
    return f"{prefix}categories/{slug}/logo_{clean_fn}.{ext}"


def build_ad_image_key(ad_id: str, filename: str, tenant_id: Optional[str] = None) -> str:
    """Generate canonical storage key for advertisement media."""
    ext = filename.split(".")[-1] if "." in filename else "png"
    prefix = _tenant_prefix(tenant_id)
    return f"{prefix}ads/{ad_id}/banner.{ext}"
