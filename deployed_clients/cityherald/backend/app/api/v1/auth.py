from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import create_access_token, verify_password
from app.core.tenant import get_current_user
from app.models.tenant import Tenant, TenantUser
from app.schemas.epaper import LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["Multi-Tenant JWT Authentication"])


@router.post("/login", response_model=TokenResponse)
async def login_for_access_token(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate user (SUPER_ADMIN, TENANT_ADMIN, or TENANT_STAFF) and issue JWT with tenant claims."""
    stmt = select(TenantUser).where(
        TenantUser.email == payload.email.strip().lower(),
        TenantUser.is_active == True,
    )
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        )

    tenant_slug = None
    tenant_name = None
    if user.tenant_id:
        t_res = await db.execute(select(Tenant).where(Tenant.id == user.tenant_id))
        tenant_obj = t_res.scalar_one_or_none()
        if tenant_obj:
            tenant_slug = tenant_obj.slug
            tenant_name = tenant_obj.name

    token = create_access_token(
        subject=user.id,
        role=user.role,
        tenant_id=user.tenant_id,
    )

    return TokenResponse(
        access_token=token,
        user={
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "tenant_id": user.tenant_id,
            "tenant_slug": tenant_slug,
            "tenant_name": tenant_name,
        },
    )


@router.get("/me")
async def get_authenticated_user_profile(
    current_user: TenantUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return current logged-in user and their associated tenant metadata."""
    tenant_slug = None
    tenant_name = None
    if current_user.tenant_id:
        t_res = await db.execute(select(Tenant).where(Tenant.id == current_user.tenant_id))
        tenant_obj = t_res.scalar_one_or_none()
        if tenant_obj:
            tenant_slug = tenant_obj.slug
            tenant_name = tenant_obj.name

    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "tenant_id": current_user.tenant_id,
        "tenant_slug": tenant_slug,
        "tenant_name": tenant_name,
    }
