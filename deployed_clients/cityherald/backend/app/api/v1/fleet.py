import os
from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.provisioner import client_provisioner
from app.core.security import get_password_hash
from app.core.tenant import get_current_superadmin
from app.models.fleet import DeployedInstance
from app.models.newspaper import Edition, Issue
from app.models.tenant import Tenant, TenantUser
from app.storage.keys import sanitize_slug

router = APIRouter(prefix="/fleet", tags=["VPS Fleet & Client Instance Provisioner"])


class ProvisionClientRequest(BaseModel):
    client_name: str
    client_slug: Optional[str] = None
    domain: str  # e.g. epaper.vaartha.com
    logo_url: Optional[str] = None
    brand_primary_color: str = "#dc2626"
    brand_secondary_color: str = "#0f172a"
    editions: List[str] = ["Main Edition"]
    admin_email: Optional[str] = None
    admin_password: str = "Editor@123"
    # "LOCAL_VPS" (Folder/Docker on our shared VPS) or "REMOTE_DEDICATED_VPS" (Separate VPS for heavy multi-edition client)
    deployment_mode: str = "LOCAL_VPS"
    plan_name: str = "Standard Shared VPS"
    monthly_price_inr: int = 5000
    # Remote Dedicated VPS SSH Credentials (kept strictly with us!)
    vps_provider: Optional[str] = None
    vps_ip: Optional[str] = None
    vps_ssh_port: int = 22
    vps_ssh_user: str = "root"
    vps_root_password: Optional[str] = None
    vps_ssh_private_key: Optional[str] = None
    remote_deploy_path: str = "/opt/epaper"


@router.get("/instances")
async def list_deployed_instances(
    _superadmin: TenantUser = Depends(get_current_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """
    Lists all provisioned Newspaper Client Instances (both Local Shared VPS Folders
    and Remote Dedicated VPS Servers, including stored VPS IP & Root SSH Password for the platform owner).
    """
    stmt = select(DeployedInstance).order_by(desc(DeployedInstance.created_at))
    res = await db.execute(stmt)
    instances = res.scalars().all()

    return {
        "summary": {
            "total_instances": len(instances),
            "local_vps_containers": sum(
                1 for i in instances if i.deployment_mode == "LOCAL_VPS"
            ),
            "remote_dedicated_vps": sum(
                1 for i in instances if i.deployment_mode == "REMOTE_DEDICATED_VPS"
            ),
            "monthly_recurring_revenue_inr": sum(
                (i.monthly_price_inr or 0) for i in instances
            ),
        },
        "instances": [
            {
                "id": inst.id,
                "client_name": inst.client_name,
                "client_slug": inst.client_slug,
                "domain": inst.domain,
                "logo_url": inst.logo_url,
                "brand_primary_color": inst.brand_primary_color,
                "brand_secondary_color": inst.brand_secondary_color,
                "editions_list": inst.editions_list,
                "admin_email": inst.admin_email,
                "admin_password_plain": inst.admin_password_plain,
                "deployment_mode": inst.deployment_mode,
                "plan_name": inst.plan_name,
                "monthly_price_inr": inst.monthly_price_inr,
                "local_folder_path": inst.local_folder_path,
                "assigned_port": inst.assigned_port,
                "vps_provider": inst.vps_provider,
                "vps_ip": inst.vps_ip,
                "vps_ssh_port": inst.vps_ssh_port,
                "vps_ssh_user": inst.vps_ssh_user,
                "vps_root_password": inst.vps_root_password,
                "remote_deploy_path": inst.remote_deploy_path,
                "status": inst.status,
                "provision_logs": inst.provision_logs,
                "created_at": inst.created_at.isoformat() if inst.created_at else None,
            }
            for inst in instances
        ],
    }


@router.post("/provision")
async def provision_client_instance(
    payload: ProvisionClientRequest,
    _superadmin: TenantUser = Depends(get_current_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """
    1-Click Client Provisioner:
    1. Creates the isolated client folder in `deployed_clients/<slug>/` with our core DeepZoom PDF engine,
       clip generator, OSDViewer, CropOverlay, and their custom branding (`brand_config.json`, `.env`, `docker-compose.yml`, `Caddyfile`).
    2. Gives them a dedicated Single-Tenant Reader URL and `/admin` Uploader page with their Editor credentials.
    3. If `deployment_mode == "REMOTE_DEDICATED_VPS"`, stores the VPS IP & Root SSH Password in our Master Vault
       and connects via SSH to deploy their dedicated server.
    """
    clean_slug = sanitize_slug(payload.client_slug or payload.client_name)
    clean_domain = payload.domain.strip().lower().replace("https://", "").replace("http://", "").rstrip("/")

    existing_res = await db.execute(
        select(DeployedInstance).where(DeployedInstance.client_slug == clean_slug)
    )
    if existing_res.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail=f"Client instance '{clean_slug}' is already provisioned.",
        )

    # Calculate next available port for local VPS isolation (8101, 8102, ...)
    all_res = await db.execute(select(DeployedInstance))
    existing_all = all_res.scalars().all()
    assigned_port = 8101 + len(existing_all)

    admin_email = (
        payload.admin_email.strip().lower()
        if payload.admin_email
        else f"editor@{clean_domain.replace('epaper.', '')}"
    )

    # 1. Build physical isolated client folder in `deployed_clients/<clean_slug>/`
    folder_path, build_logs = client_provisioner.build_client_instance_folder(
        client_name=payload.client_name.strip(),
        client_slug=clean_slug,
        domain=clean_domain,
        brand_primary_color=payload.brand_primary_color,
        brand_secondary_color=payload.brand_secondary_color,
        editions_list=payload.editions,
        admin_email=admin_email,
        admin_password=payload.admin_password,
        assigned_port=assigned_port,
        logo_url=payload.logo_url,
        deployment_mode=payload.deployment_mode,
        vps_ip=payload.vps_ip,
        vps_ssh_port=payload.vps_ssh_port,
        vps_ssh_user=payload.vps_ssh_user,
        remote_deploy_path=payload.remote_deploy_path,
    )

    status_val = "RUNNING_LOCAL_VPS"
    combined_logs = build_logs

    # 2. If Remote Dedicated VPS is selected and VPS IP is provided, run SSH deployment
    if payload.deployment_mode == "REMOTE_DEDICATED_VPS":
        if payload.vps_ip and payload.vps_ip.strip():
            ssh_ok, ssh_logs = await client_provisioner.deploy_to_remote_vps_via_ssh(
                local_client_dir=folder_path,
                client_slug=clean_slug,
                vps_ip=payload.vps_ip.strip(),
                vps_ssh_port=payload.vps_ssh_port,
                vps_ssh_user=payload.vps_ssh_user,
                vps_root_password=payload.vps_root_password,
                vps_ssh_private_key=payload.vps_ssh_private_key,
                remote_deploy_path=payload.remote_deploy_path,
            )
            combined_logs = f"{build_logs}\n\n--- SSH DEDICATED VPS DEPLOYMENT ---\n{ssh_logs}"
            status_val = "REMOTE_VPS_ACTIVE" if ssh_ok else "REMOTE_VPS_PACKAGE_READY"
        else:
            status_val = "REMOTE_VPS_PACKAGE_READY"

    instance = DeployedInstance(
        client_name=payload.client_name.strip(),
        client_slug=clean_slug,
        domain=clean_domain,
        logo_url=payload.logo_url,
        brand_primary_color=payload.brand_primary_color,
        brand_secondary_color=payload.brand_secondary_color,
        editions_list=payload.editions,
        admin_email=admin_email,
        admin_password_plain=payload.admin_password,
        deployment_mode=payload.deployment_mode,
        plan_name=payload.plan_name,
        monthly_price_inr=payload.monthly_price_inr,
        local_folder_path=folder_path,
        assigned_port=assigned_port,
        vps_provider=payload.vps_provider,
        vps_ip=payload.vps_ip,
        vps_ssh_port=payload.vps_ssh_port,
        vps_ssh_user=payload.vps_ssh_user,
        vps_root_password=payload.vps_root_password,
        vps_ssh_private_key=payload.vps_ssh_private_key,
        remote_deploy_path=payload.remote_deploy_path,
        status=status_val,
        provision_logs=combined_logs,
    )
    db.add(instance)
    await db.flush()

    # 3. Also register/sync in live local runtime so the owner & client can immediately test their
    # dedicated Single-Tenant Reader (`/?tenant=<slug>&single=1`) and Admin Uploader (`/admin?tenant=<slug>&single=1`)!
    t_res = await db.execute(select(Tenant).where(Tenant.slug == clean_slug))
    tenant = t_res.scalar_one_or_none()
    if not tenant:
        tenant = Tenant(
            name=payload.client_name.strip(),
            slug=clean_slug,
            custom_domains=[clean_domain, f"{clean_slug}.localhost"],
            logo_url=payload.logo_url,
            brand_primary_color=payload.brand_primary_color,
            brand_secondary_color=payload.brand_secondary_color,
            header_title=f"{payload.client_name.strip()} Digital E-Paper",
            footer_text=f"Official Digital Edition of {payload.client_name.strip()}",
            copyright_text=f"© 2026 {payload.client_name.strip()}. All rights reserved.",
            status="active",
        )
        db.add(tenant)
        await db.flush()

        first_ed = None
        for idx, ed_name in enumerate(payload.editions or ["Main Edition"], start=1):
            ed = Edition(
                tenant_id=tenant.id,
                name=ed_name.strip(),
                slug=sanitize_slug(ed_name),
                display_order=idx,
                is_active=True,
            )
            db.add(ed)
            if idx == 1:
                first_ed = ed
        await db.flush()

        u_res = await db.execute(select(TenantUser).where(TenantUser.email == admin_email))
        if not u_res.scalar_one_or_none():
            db.add(
                TenantUser(
                    tenant_id=tenant.id,
                    email=admin_email,
                    full_name=f"{tenant.name} Editor",
                    hashed_password=get_password_hash(payload.admin_password),
                    role="TENANT_ADMIN",
                    is_active=True,
                )
            )
            await db.flush()

        if first_ed:
            from app.core.seed import generate_sample_newspaper_pdf_bytes
            from app.pdf.processor import pdf_processor
            from app.storage.keys import build_issue_pdf_key
            from app.storage.service import storage_service

            sample_pdf = generate_sample_newspaper_pdf_bytes(
                newspaper_name=tenant.name,
                edition_name=first_ed.name,
                primary_hex=tenant.brand_primary_color,
                pub_date=date.today(),
                num_pages=4,
            )
            pdf_key = build_issue_pdf_key(
                pub_date=date.today(),
                edition_slug=first_ed.slug,
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
                edition_id=first_ed.id,
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
                edition_slug=first_ed.slug,
                db_session=db,
            )

    return {
        "provisioned": True,
        "instance_id": instance.id,
        "client_slug": instance.client_slug,
        "domain": instance.domain,
        "local_folder_path": instance.local_folder_path,
        "deployment_mode": instance.deployment_mode,
        "status": instance.status,
        "admin_email": instance.admin_email,
        "admin_password": instance.admin_password_plain,
        "provision_logs": instance.provision_logs,
    }


@router.get("/instances/{instance_id}/files")
async def inspect_instance_folder_files(
    instance_id: str,
    _superadmin: TenantUser = Depends(get_current_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Returns the generated files inside `deployed_clients/<slug>/` for inspection."""
    stmt = select(DeployedInstance).where(DeployedInstance.id == instance_id)
    res = await db.execute(stmt)
    inst = res.scalar_one_or_none()
    if not inst or not inst.local_folder_path:
        raise HTTPException(status_code=404, detail="Instance folder not found.")

    folder = inst.local_folder_path
    files_preview = {}
    for fname in ["brand_config.json", ".env", "docker-compose.yml", "Caddyfile", "deploy_to_vps.sh"]:
        fpath = os.path.join(folder, fname)
        if os.path.exists(fpath):
            with open(fpath, "r", encoding="utf-8") as f:
                files_preview[fname] = f.read()

    return {
        "client_name": inst.client_name,
        "local_folder_path": folder,
        "files": files_preview,
    }
