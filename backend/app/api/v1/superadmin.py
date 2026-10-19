from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.core.database import get_db
from app.core.security import get_password_hash
from app.core.tenant import get_current_superadmin
from app.models.newspaper import Edition, Issue
from app.models.tenant import Tenant, TenantUser
from app.schemas.epaper import CustomDomainUpdateRequest, SuperAdminTenantCreate
from app.storage.keys import sanitize_slug

router = APIRouter(prefix="/superadmin", tags=["Super-Admin Platform Control Plane"])


@router.get("/overview")
async def get_superadmin_platform_overview(
    _superadmin: TenantUser = Depends(get_current_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Monitor all onboarded newspaper tenants, custom domains, storage usage, and upload queues."""
    tenants_stmt = (
        select(Tenant)
        .options(selectinload(Tenant.editions), selectinload(Tenant.issues))
        .order_by(Tenant.created_at.desc())
    )
    tenants_res = await db.execute(tenants_stmt)
    tenants = tenants_res.scalars().all()

    recent_uploads_stmt = (
        select(Issue)
        .options(selectinload(Issue.tenant), selectinload(Issue.edition))
        .order_by(desc(Issue.created_at))
        .limit(25)
    )
    uploads_res = await db.execute(recent_uploads_stmt)
    recent_uploads = uploads_res.scalars().all()

    return {
        "platform_summary": {
            "total_tenants": len(tenants),
            "active_tenants": sum(1 for t in tenants if t.status == "active"),
            "total_issues_published": sum(len(t.issues) for t in tenants),
            "total_custom_domains": sum(len(t.custom_domains or []) for t in tenants),
        },
        "tenants": [
            {
                "id": t.id,
                "name": t.name,
                "slug": t.slug,
                "custom_domains": t.custom_domains or [],
                "brand_primary_color": t.brand_primary_color,
                "brand_secondary_color": t.brand_secondary_color,
                "header_title": t.header_title,
                "status": t.status,
                "editions_count": len(t.editions),
                "issues_count": len(t.issues),
                "total_views": sum((i.views_count or 0) for i in t.issues),
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in tenants
        ],
        "worker_queue": [
            {
                "issue_id": u.id,
                "tenant_name": u.tenant.name if u.tenant else "Unknown",
                "tenant_slug": u.tenant.slug if u.tenant else "unknown",
                "edition_name": u.edition.name if u.edition else "Main",
                "publication_date": u.publication_date.isoformat(),
                "page_count": u.page_count,
                "status": u.status,
                "processing_progress": u.processing_progress,
                "processing_message": u.processing_message,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            }
            for u in recent_uploads
        ],
    }


@router.post("/tenants")
async def onboard_new_tenant(
    payload: SuperAdminTenantCreate,
    _superadmin: TenantUser = Depends(get_current_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """
    Onboard a new Newspaper Publisher Client with automatic Editions, Admin Account,
    Custom Domains, and Sample Multi-Page Broadsheet Issue so they are live immediately!
    """
    clean_slug = sanitize_slug(payload.slug or payload.name)
    existing_res = await db.execute(select(Tenant).where(Tenant.slug == clean_slug))
    if existing_res.scalar_one_or_none():
        raise HTTPException(
            status_code=400, detail=f"Tenant with slug '{clean_slug}' already exists."
        )

    clean_domains = [d.strip().lower() for d in payload.custom_domains if d.strip()]
    if f"{clean_slug}.localhost" not in clean_domains:
        clean_domains.append(f"{clean_slug}.localhost")

    tenant = Tenant(
        name=payload.name.strip(),
        slug=clean_slug,
        custom_domains=clean_domains,
        brand_primary_color=payload.brand_primary_color,
        brand_secondary_color=payload.brand_secondary_color,
        header_title=payload.header_title or f"{payload.name.strip()} Digital Edition",
        footer_text=payload.footer_text
        or f"Official Digital Broadsheet Edition of {payload.name.strip()}.",
        copyright_text=payload.copyright_text
        or f"© 2026 {payload.name.strip()}. All rights reserved.",
        status="active",
    )
    db.add(tenant)
    await db.flush()

    # Create default editions
    editions_list = payload.default_editions or ["Main Edition"]
    first_edition = None
    for idx, ed_name in enumerate(editions_list, start=1):
        ed = Edition(
            tenant_id=tenant.id,
            name=ed_name.strip(),
            slug=sanitize_slug(ed_name),
            display_order=idx,
            is_active=True,
        )
        db.add(ed)
        if idx == 1:
            first_edition = ed
    await db.flush()

    # Create Tenant Admin User
    admin_email = (
        payload.admin_email.strip().lower()
        if payload.admin_email
        else f"editor@{clean_slug}.com"
    )
    existing_user_res = await db.execute(
        select(TenantUser).where(TenantUser.email == admin_email)
    )
    if not existing_user_res.scalar_one_or_none():
        tenant_admin = TenantUser(
            tenant_id=tenant.id,
            email=admin_email,
            full_name=f"{tenant.name} Chief Editor",
            hashed_password=get_password_hash(payload.admin_password),
            role="TENANT_ADMIN",
            is_active=True,
        )
        db.add(tenant_admin)
        await db.flush()

    # Generate an initial sample newspaper issue so the newly onboarded tenant has a live paper immediately
    if first_edition:
        from app.core.seed import generate_sample_newspaper_pdf_bytes
        from app.pdf.processor import pdf_processor
        from app.storage.keys import build_issue_pdf_key
        from app.storage.service import storage_service

        sample_pdf = generate_sample_newspaper_pdf_bytes(
            newspaper_name=tenant.name,
            edition_name=first_edition.name,
            primary_hex=tenant.brand_primary_color,
            pub_date=date.today(),
            num_pages=4,
        )
        pdf_key = build_issue_pdf_key(
            pub_date=date.today(),
            edition_slug=first_edition.slug,
            revision=1,
            tenant_id=tenant.id,
        )
        await storage_service.save_asset(
            storage_key=pdf_key,
            data=sample_pdf,
            asset_type="ISSUE_PDF",
            mime_type="application/pdf",
            original_filename=f"{clean_slug}_inaugural.pdf",
            db_session=db,
            tenant_id=tenant.id,
        )
        new_issue = Issue(
            tenant_id=tenant.id,
            edition_id=first_edition.id,
            publication_date=date.today(),
            revision=1,
            page_count=4,
            pdf_storage_key=pdf_key,
            pdf_file_size=len(sample_pdf),
            status="PROCESSING",
        )
        db.add(new_issue)
        await db.flush()

        await pdf_processor.process_issue_pdf(
            pdf_bytes=sample_pdf,
            issue=new_issue,
            edition_slug=first_edition.slug,
            db_session=db,
        )
        new_issue.processing_progress = 100
        new_issue.processing_message = "Published & DeepZoom Tiles Ready"
        await db.flush()

    return {
        "created": True,
        "tenant": {
            "id": tenant.id,
            "name": tenant.name,
            "slug": tenant.slug,
            "custom_domains": tenant.custom_domains,
            "admin_email": admin_email,
        },
    }


@router.put("/tenants/{tenant_id}/domains")
async def update_tenant_custom_domains(
    tenant_id: str,
    payload: CustomDomainUpdateRequest,
    _superadmin: TenantUser = Depends(get_current_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Update custom domains for a tenant (zero-downtime Caddy on_demand_tls provisioning)."""
    stmt = select(Tenant).where(Tenant.id == tenant_id)
    res = await db.execute(stmt)
    tenant = res.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found.")

    clean_domains = [d.strip().lower() for d in payload.custom_domains if d.strip()]
    tenant.custom_domains = clean_domains
    await db.flush()

    return {
        "updated": True,
        "tenant_id": tenant.id,
        "slug": tenant.slug,
        "custom_domains": tenant.custom_domains,
    }


@router.put("/tenants/{tenant_id}/status")
async def update_tenant_status(
    tenant_id: str,
    status_value: str,
    _superadmin: TenantUser = Depends(get_current_superadmin),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Tenant).where(Tenant.id == tenant_id)
    res = await db.execute(stmt)
    tenant = res.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found.")

    if status_value not in ("active", "suspended", "trial"):
        raise HTTPException(status_code=400, detail="Invalid status.")
    tenant.status = status_value
    await db.flush()
    return {"updated": True, "tenant_id": tenant.id, "status": tenant.status}
