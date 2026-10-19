from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.tenant import resolve_current_tenant
from app.models.newspaper import Edition
from app.models.tenant import Tenant
from app.schemas.epaper import EditionOut, TenantPublicConfigOut

router = APIRouter(prefix="/public", tags=["Tenant Public Config & Domain Resolution"])


@router.get("/config", response_model=TenantPublicConfigOut)
async def get_tenant_public_config(
    tenant: Tenant = Depends(resolve_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns automatic domain-resolved Tenant Branding, Colors, Logo, Editions, and Monetization settings.
    """
    stmt = (
        select(Edition)
        .where(Edition.tenant_id == tenant.id, Edition.is_active == True)
        .order_by(Edition.display_order.asc())
    )
    res = await db.execute(stmt)
    editions = res.scalars().all()

    return TenantPublicConfigOut(
        id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        custom_domains=tenant.custom_domains or [],
        logo_url=tenant.logo_url,
        favicon_url=tenant.favicon_url,
        brand_primary_color=tenant.brand_primary_color,
        brand_secondary_color=tenant.brand_secondary_color,
        header_title=tenant.header_title or f"{tenant.name} Digital E-Paper",
        footer_text=tenant.footer_text or f"Read {tenant.name} anywhere, anytime in ultra-sharp Deep Zoom clarity.",
        copyright_text=tenant.copyright_text or f"© 2026 {tenant.name}. All rights reserved.",
        monetization_settings=tenant.monetization_settings or {},
        status=tenant.status,
        editions=[EditionOut.model_validate(e) for e in editions],
    )


@router.get("/tenants")
async def list_public_active_tenants(
    db: AsyncSession = Depends(get_db),
):
    """
    Returns active tenants so the local dev switcher and multi-tenant directory can switch seamlessly.
    """
    stmt = select(Tenant).where(Tenant.status != "suspended").order_by(Tenant.created_at.asc())
    res = await db.execute(stmt)
    tenants = res.scalars().all()
    return [
        {
            "id": t.id,
            "name": t.name,
            "slug": t.slug,
            "custom_domains": t.custom_domains or [],
            "brand_primary_color": t.brand_primary_color,
            "brand_secondary_color": t.brand_secondary_color,
            "header_title": t.header_title,
            "status": t.status,
        }
        for t in tenants
    ]


@router.get("/tls-check")
async def caddy_on_demand_tls_check(
    domain: str = Query(..., description="Hostname queried by Caddy on_demand_tls"),
    db: AsyncSession = Depends(get_db),
):
    """
    Caddy `on_demand_tls` validation endpoint!
    When a reader visits https://epaper.clientnewspaper.com, Caddy queries this endpoint
    before issuing a Let's Encrypt / ZeroSSL certificate.
    Returns 200 OK if the domain belongs to an active tenant, or 403 Forbidden otherwise.
    """
    clean_domain = domain.split(":")[0].strip().lower()
    if clean_domain in ("localhost", "127.0.0.1"):
        return {"allowed": True, "domain": clean_domain}

    stmt = select(Tenant).where(Tenant.status != "suspended")
    res = await db.execute(stmt)
    tenants = res.scalars().all()

    for t in tenants:
        customs = [d.lower().strip() for d in (t.custom_domains or [])]
        if clean_domain in customs:
            return {"allowed": True, "tenant": t.slug, "domain": clean_domain}
        if clean_domain.startswith(f"{t.slug.lower()}."):
            return {"allowed": True, "tenant": t.slug, "domain": clean_domain}

    raise HTTPException(status_code=403, detail="Domain not registered to any active tenant.")
