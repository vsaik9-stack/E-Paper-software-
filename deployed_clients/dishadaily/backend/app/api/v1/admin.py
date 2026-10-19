from datetime import date, datetime, timezone
from typing import List, Optional
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.core.database import AsyncSessionLocal, get_db
from app.core.tenant import get_current_tenant_admin, resolve_current_tenant
from app.models.newspaper import ArticleRegion, Edition, Issue, Page
from app.models.tenant import Tenant, TenantUser
from app.pdf.processor import PDFProcessingError, pdf_processor
from app.schemas.epaper import (
    ArticleRegionCreateRequest,
    EditionCreateRequest,
    EditionOut,
    TenantBrandingUpdate,
)
from app.storage.keys import build_issue_pdf_key, sanitize_slug
from app.storage.service import storage_service

router = APIRouter(prefix="/admin", tags=["Tenant Publisher Admin Portal"])


async def _background_process_issue_pdf(
    issue_id: str,
    pdf_bytes: bytes,
    edition_slug: str,
):
    """Background task executing PyMuPDF 300 DPI + 512x512 WebP DeepZoom pyramid generation."""
    async with AsyncSessionLocal() as db:
        try:
            stmt = select(Issue).where(Issue.id == issue_id)
            res = await db.execute(stmt)
            issue = res.scalar_one_or_none()
            if not issue:
                return

            async def update_progress(progress_pct: float, msg: str):
                issue.processing_progress = int(progress_pct)
                issue.processing_message = msg
                await db.commit()

            await pdf_processor.process_issue_pdf(
                pdf_bytes=pdf_bytes,
                issue=issue,
                edition_slug=edition_slug,
                db_session=db,
                progress_callback=update_progress,
            )
            issue.processing_progress = 100
            issue.processing_message = "Published & DeepZoom Tiles Ready"
            await db.commit()
        except Exception as exc:
            stmt = select(Issue).where(Issue.id == issue_id)
            res = await db.execute(stmt)
            issue = res.scalar_one_or_none()
            if issue:
                issue.status = "FAILED"
                issue.processing_message = str(exc)
                await db.commit()


@router.get("/dashboard")
async def get_tenant_dashboard_metrics(
    tenant: Tenant = Depends(resolve_current_tenant),
    _user: TenantUser = Depends(get_current_tenant_admin),
    db: AsyncSession = Depends(get_db),
):
    """Returns comprehensive publisher metrics (views, issues count, pages count, editions, recent issues)."""
    ed_count_res = await db.execute(
        select(func.count(Edition.id)).where(Edition.tenant_id == tenant.id)
    )
    editions_count = ed_count_res.scalar() or 0

    iss_count_res = await db.execute(
        select(func.count(Issue.id)).where(Issue.tenant_id == tenant.id)
    )
    issues_count = iss_count_res.scalar() or 0

    views_res = await db.execute(
        select(func.sum(Issue.views_count)).where(Issue.tenant_id == tenant.id)
    )
    total_views = views_res.scalar() or 0

    pages_res = await db.execute(
        select(func.sum(Issue.page_count)).where(Issue.tenant_id == tenant.id)
    )
    total_pages = pages_res.scalar() or 0

    recent_stmt = (
        select(Issue)
        .options(selectinload(Issue.edition))
        .where(Issue.tenant_id == tenant.id)
        .order_by(desc(Issue.publication_date), desc(Issue.created_at))
        .limit(20)
    )
    recent_res = await db.execute(recent_stmt)
    recent_issues = recent_res.scalars().all()

    return {
        "tenant": {
            "id": tenant.id,
            "name": tenant.name,
            "slug": tenant.slug,
            "custom_domains": tenant.custom_domains or [],
            "brand_primary_color": tenant.brand_primary_color,
            "brand_secondary_color": tenant.brand_secondary_color,
            "status": tenant.status,
        },
        "metrics": {
            "total_views": total_views,
            "active_readers_estimate": max(12, total_views * 3),
            "issues_count": issues_count,
            "editions_count": editions_count,
            "total_pages_rendered": total_pages,
        },
        "recent_issues": [
            {
                "id": iss.id,
                "edition_id": iss.edition_id,
                "edition_name": iss.edition.name if iss.edition else "Main",
                "edition_slug": iss.edition.slug if iss.edition else "main",
                "publication_date": iss.publication_date.isoformat(),
                "revision": iss.revision,
                "page_count": iss.page_count,
                "status": iss.status,
                "processing_progress": iss.processing_progress,
                "processing_message": iss.processing_message,
                "views_count": iss.views_count,
                "created_at": iss.created_at.isoformat() if iss.created_at else None,
            }
            for iss in recent_issues
        ],
    }


@router.get("/editions", response_model=List[EditionOut])
async def list_tenant_editions(
    tenant: Tenant = Depends(resolve_current_tenant),
    _user: TenantUser = Depends(get_current_tenant_admin),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Edition)
        .where(Edition.tenant_id == tenant.id)
        .order_by(Edition.display_order.asc())
    )
    res = await db.execute(stmt)
    return [EditionOut.model_validate(e) for e in res.scalars().all()]


@router.post("/editions", response_model=EditionOut)
async def create_tenant_edition(
    payload: EditionCreateRequest,
    tenant: Tenant = Depends(resolve_current_tenant),
    _user: TenantUser = Depends(get_current_tenant_admin),
    db: AsyncSession = Depends(get_db),
):
    clean_slug = sanitize_slug(payload.slug or payload.name)
    edition = Edition(
        tenant_id=tenant.id,
        name=payload.name.strip(),
        slug=clean_slug,
        display_order=payload.display_order,
        is_active=payload.is_active,
    )
    db.add(edition)
    await db.flush()
    return EditionOut.model_validate(edition)


@router.delete("/editions/{edition_id}")
async def delete_tenant_edition(
    edition_id: str,
    tenant: Tenant = Depends(resolve_current_tenant),
    _user: TenantUser = Depends(get_current_tenant_admin),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Edition).where(Edition.id == edition_id, Edition.tenant_id == tenant.id)
    res = await db.execute(stmt)
    ed = res.scalar_one_or_none()
    if not ed:
        raise HTTPException(status_code=404, detail="Edition not found.")
    await db.delete(ed)
    await db.flush()
    return {"deleted": True, "id": edition_id}


@router.post("/issues/upload")
async def upload_issue_pdf(
    background_tasks: BackgroundTasks,
    edition_id: str = Form(...),
    publication_date: date = Form(...),
    sync_process: bool = Form(True),
    file: UploadFile = File(...),
    tenant: Tenant = Depends(resolve_current_tenant),
    _user: TenantUser = Depends(get_current_tenant_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Multi-page PDF uploader triggering PyMuPDF validation, raw PDF archival,
    and Deep Zoom 512x512 WebP tile pyramid generation.
    """
    ed_stmt = select(Edition).where(Edition.id == edition_id, Edition.tenant_id == tenant.id)
    ed_res = await db.execute(ed_stmt)
    edition = ed_res.scalar_one_or_none()
    if not edition:
        raise HTTPException(status_code=404, detail="Edition not found for this tenant.")

    pdf_bytes = await file.read()
    try:
        meta = pdf_processor.validate_pdf(pdf_bytes)
    except PDFProcessingError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Determine revision number if an issue already exists for this date & edition
    existing_stmt = (
        select(Issue)
        .where(
            Issue.tenant_id == tenant.id,
            Issue.edition_id == edition.id,
            Issue.publication_date == publication_date,
        )
        .order_by(desc(Issue.revision))
    )
    existing_res = await db.execute(existing_stmt)
    latest_existing = existing_res.scalars().first()
    next_revision = (latest_existing.revision + 1) if latest_existing else 1

    pdf_key = build_issue_pdf_key(
        pub_date=publication_date,
        edition_slug=edition.slug,
        revision=next_revision,
        tenant_id=tenant.id,
    )
    await storage_service.save_asset(
        storage_key=pdf_key,
        data=pdf_bytes,
        asset_type="ISSUE_PDF",
        mime_type="application/pdf",
        original_filename=file.filename,
        db_session=db,
        tenant_id=tenant.id,
    )

    issue = Issue(
        tenant_id=tenant.id,
        edition_id=edition.id,
        publication_date=publication_date,
        revision=next_revision,
        page_count=meta["page_count"],
        pdf_storage_key=pdf_key,
        pdf_file_size=meta["file_size"],
        status="PROCESSING",
        processing_progress=5,
        processing_message="Validated PDF & Queued for DeepZoom Rendering",
    )
    db.add(issue)
    await db.flush()

    if sync_process:
        await pdf_processor.process_issue_pdf(
            pdf_bytes=pdf_bytes,
            issue=issue,
            edition_slug=edition.slug,
            db_session=db,
        )
        issue.processing_progress = 100
        issue.processing_message = "Published & DeepZoom Tiles Ready"
        await db.flush()
    else:
        background_tasks.add_task(
            _background_process_issue_pdf,
            issue.id,
            pdf_bytes,
            edition.slug,
        )

    return {
        "id": issue.id,
        "tenant_id": tenant.id,
        "edition_id": edition.id,
        "edition_name": edition.name,
        "publication_date": issue.publication_date.isoformat(),
        "revision": issue.revision,
        "page_count": issue.page_count,
        "status": issue.status,
        "processing_progress": issue.processing_progress,
        "processing_message": issue.processing_message,
    }


@router.delete("/issues/{issue_id}")
async def delete_tenant_issue(
    issue_id: str,
    tenant: Tenant = Depends(resolve_current_tenant),
    _user: TenantUser = Depends(get_current_tenant_admin),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Issue).where(Issue.id == issue_id, Issue.tenant_id == tenant.id)
    res = await db.execute(stmt)
    issue = res.scalar_one_or_none()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found.")
    await db.delete(issue)
    await db.flush()
    return {"deleted": True, "id": issue_id}


@router.put("/branding")
async def update_tenant_branding_and_monetization(
    payload: TenantBrandingUpdate,
    tenant: Tenant = Depends(resolve_current_tenant),
    _user: TenantUser = Depends(get_current_tenant_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update White-Label Branding (colors, logo, header/footer) and AdSense/Banner Monetization settings."""
    if payload.name is not None:
        tenant.name = payload.name.strip()
    if payload.logo_url is not None:
        tenant.logo_url = payload.logo_url.strip() or None
    if payload.favicon_url is not None:
        tenant.favicon_url = payload.favicon_url.strip() or None
    if payload.brand_primary_color is not None:
        tenant.brand_primary_color = payload.brand_primary_color.strip()
    if payload.brand_secondary_color is not None:
        tenant.brand_secondary_color = payload.brand_secondary_color.strip()
    if payload.header_title is not None:
        tenant.header_title = payload.header_title.strip()
    if payload.footer_text is not None:
        tenant.footer_text = payload.footer_text.strip()
    if payload.copyright_text is not None:
        tenant.copyright_text = payload.copyright_text.strip()
    if payload.monetization_settings is not None:
        merged = dict(tenant.monetization_settings or {})
        merged.update(payload.monetization_settings)
        tenant.monetization_settings = merged

    await db.flush()
    return {
        "updated": True,
        "tenant": {
            "id": tenant.id,
            "name": tenant.name,
            "slug": tenant.slug,
            "logo_url": tenant.logo_url,
            "brand_primary_color": tenant.brand_primary_color,
            "brand_secondary_color": tenant.brand_secondary_color,
            "header_title": tenant.header_title,
            "footer_text": tenant.footer_text,
            "copyright_text": tenant.copyright_text,
            "monetization_settings": tenant.monetization_settings,
        },
    }


@router.post("/articles")
async def create_article_region(
    payload: ArticleRegionCreateRequest,
    tenant: Tenant = Depends(resolve_current_tenant),
    _user: TenantUser = Depends(get_current_tenant_admin),
    db: AsyncSession = Depends(get_db),
):
    """Map clickable smart article regions onto a newspaper page."""
    region = ArticleRegion(
        tenant_id=tenant.id,
        issue_id=payload.issue_id,
        page_id=payload.page_id,
        title=payload.title,
        coordinates=payload.coordinates,
        content_text=payload.content_text,
    )
    db.add(region)
    await db.flush()
    return {
        "id": region.id,
        "title": region.title,
        "coordinates": region.coordinates,
    }
