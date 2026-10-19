from typing import Optional
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.tenant import Tenant, TenantUser

security_scheme = HTTPBearer(auto_error=False)


def extract_clean_hostname(request: Request) -> str:
    """Extract clean domain name without port from X-Tenant-Domain, X-Forwarded-Host, or Host header."""
    override_domain = request.headers.get("x-tenant-domain")
    if override_domain:
        return override_domain.split(":")[0].strip().lower()

    forwarded_host = request.headers.get("x-forwarded-host")
    if forwarded_host:
        return forwarded_host.split(",")[0].split(":")[0].strip().lower()

    host = request.headers.get("host", "localhost")
    return host.split(":")[0].strip().lower()


async def resolve_current_tenant(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Tenant:
    """
    Automatic Multi-Tenant Resolver:
    1. Checks explicit `X-Tenant-Slug` header or `?tenant=` query parameter (useful for local dev switcher & API testing).
    2. Inspects `X-Forwarded-Host` / `Host` header against tenant `custom_domains`.
    3. Checks subdomain pattern `<slug>.<platform_domain>` (e.g., `prajajyothi.localhost` or `dishadaily.platform.com`).
    4. Falls back to default active tenant (`DEFAULT_TENANT_SLUG`) when accessed on bare `localhost` or `127.0.0.1`.
    """
    # 1. Explicit slug override via header or query param
    slug_override = (
        request.headers.get("x-tenant-slug")
        or request.query_params.get("tenant")
    )
    if slug_override:
        clean_slug = slug_override.strip().lower()
        stmt = select(Tenant).where(Tenant.slug == clean_slug)
        res = await db.execute(stmt)
        tenant = res.scalar_one_or_none()
        if tenant:
            if tenant.status == "suspended":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Tenant '{tenant.name}' is currently suspended.",
                )
            return tenant

    # 2. Hostname & Custom Domain resolution
    hostname = extract_clean_hostname(request)

    # Fetch all active/trial tenants to match custom_domains or subdomain
    stmt = select(Tenant)
    res = await db.execute(stmt)
    all_tenants = res.scalars().all()

    # Exact match in custom_domains
    for t in all_tenants:
        domains = [d.lower().strip() for d in (t.custom_domains or [])]
        if hostname in domains:
            if t.status == "suspended":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Tenant '{t.name}' is currently suspended.",
                )
            return t

    # Subdomain match (e.g., dishadaily.localhost or epaper.prajajyothi.com)
    host_parts = hostname.split(".")
    if len(host_parts) >= 2:
        first_part = host_parts[0]
        if first_part == "epaper" and len(host_parts) >= 3:
            candidate_slug = host_parts[1]
        else:
            candidate_slug = first_part

        for t in all_tenants:
            if t.slug.lower() == candidate_slug:
                if t.status == "suspended":
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Tenant '{t.name}' is currently suspended.",
                    )
                return t

    # 4. Fallback to DEFAULT_TENANT_SLUG or first active tenant
    for t in all_tenants:
        if t.slug == settings.DEFAULT_TENANT_SLUG and t.status != "suspended":
            return t

    for t in all_tenants:
        if t.status != "suspended":
            return t

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="No active newspaper tenant found for this domain.",
    )


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> TenantUser:
    """Validate JWT token and return authenticated TenantUser."""
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided.",
        )

    payload = decode_access_token(credentials.credentials)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
        )

    user_id = payload["sub"]
    stmt = select(TenantUser).where(TenantUser.id == user_id, TenantUser.is_active == True)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found or inactive.",
        )
    return user


async def get_current_tenant_admin(
    current_user: TenantUser = Depends(get_current_user),
    current_tenant: Tenant = Depends(resolve_current_tenant),
) -> TenantUser:
    """
    Ensure user is either SUPER_ADMIN or belongs to the resolved Tenant with TENANT_ADMIN / TENANT_STAFF role.
    """
    if current_user.role == "SUPER_ADMIN":
        return current_user

    if current_user.tenant_id != current_tenant.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You do not have permission to manage this newspaper tenant.",
        )
    if current_user.role not in ("TENANT_ADMIN", "TENANT_STAFF"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient role permissions.",
        )
    return current_user


async def get_current_superadmin(
    current_user: TenantUser = Depends(get_current_user),
) -> TenantUser:
    """Ensure user has platform-wide SUPER_ADMIN role."""
    if current_user.role != "SUPER_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super-Admin privileges required.",
        )
    return current_user
