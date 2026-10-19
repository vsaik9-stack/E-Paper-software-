from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from app.api.v1 import admin, assets, auth, clipping, fleet, public, reader, superadmin
from app.core.config import settings
from app.core.database import AsyncSessionLocal, Base, engine
from app.core.seed import seed_initial_multi_tenant_data
from app.core.tenant import extract_clean_hostname
from app.models.fleet import DeployedInstance
import app.models  # noqa: F401 - register models with Base.metadata


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database schema and seed initial multi-tenant newspapers & VPS Fleet folders."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        await seed_initial_multi_tenant_data(db)

        # Ensure Fleet instances are seeded even if database already existed from earlier run
        existing_fleet = await db.execute(select(DeployedInstance).limit(1))
        if not existing_fleet.scalars().first():
            from app.core.provisioner import client_provisioner

            fleet_seed = [
                {
                    "client_name": "Disha Daily",
                    "client_slug": "dishadaily",
                    "domain": "epaper.dishadaily.com",
                    "brand_primary_color": "#dc2626",
                    "brand_secondary_color": "#0f172a",
                    "editions": ["Hyderabad Main", "Warangal Edition", "Vijayawada Edition"],
                    "admin_email": "editor@dishadaily.com",
                    "admin_password": "Admin@123",
                    "deployment_mode": "LOCAL_VPS",
                    "plan_name": "Standard Shared VPS (Docker Folder)",
                    "monthly_price_inr": 6500,
                    "assigned_port": 8101,
                    "vps_provider": "Our Primary Shared VPS",
                    "vps_ip": "127.0.0.1",
                    "vps_root_password": None,
                },
                {
                    "client_name": "Praja Jyothi",
                    "client_slug": "prajajyothi",
                    "domain": "epaper.prajajyothi.com",
                    "brand_primary_color": "#034ea2",
                    "brand_secondary_color": "#1e293b",
                    "editions": ["State Main Edition", "Greater Hyderabad", "Visakhapatnam", "Tirupati", "Warangal", "Khammam"],
                    "admin_email": "editor@prajajyothi.com",
                    "admin_password": "Admin@123",
                    "deployment_mode": "REMOTE_DEDICATED_VPS",
                    "plan_name": "Enterprise Multi-Edition Dedicated VPS",
                    "monthly_price_inr": 18500,
                    "assigned_port": 8102,
                    "vps_provider": "Hetzner Cloud Dedicated (8 vCPU / 32GB RAM)",
                    "vps_ip": "65.108.142.88",
                    "vps_root_password": "RootVps#Praja2026!Secret",
                },
                {
                    "client_name": "City Herald",
                    "client_slug": "cityherald",
                    "domain": "epaper.cityherald.com",
                    "brand_primary_color": "#059669",
                    "brand_secondary_color": "#064e3b",
                    "editions": ["Metro Financial", "National Edition"],
                    "admin_email": "editor@cityherald.com",
                    "admin_password": "Admin@123",
                    "deployment_mode": "LOCAL_VPS",
                    "plan_name": "Standard Shared VPS (Docker Folder)",
                    "monthly_price_inr": 5000,
                    "assigned_port": 8103,
                    "vps_provider": "Our Primary Shared VPS",
                    "vps_ip": "127.0.0.1",
                    "vps_root_password": None,
                },
            ]
            for f_item in fleet_seed:
                folder_path, logs = client_provisioner.build_client_instance_folder(
                    client_name=f_item["client_name"],
                    client_slug=f_item["client_slug"],
                    domain=f_item["domain"],
                    brand_primary_color=f_item["brand_primary_color"],
                    brand_secondary_color=f_item["brand_secondary_color"],
                    editions_list=f_item["editions"],
                    admin_email=f_item["admin_email"],
                    admin_password=f_item["admin_password"],
                    assigned_port=f_item["assigned_port"],
                    deployment_mode=f_item["deployment_mode"],
                    vps_ip=f_item["vps_ip"],
                )
                db.add(
                    DeployedInstance(
                        client_name=f_item["client_name"],
                        client_slug=f_item["client_slug"],
                        domain=f_item["domain"],
                        brand_primary_color=f_item["brand_primary_color"],
                        brand_secondary_color=f_item["brand_secondary_color"],
                        editions_list=f_item["editions"],
                        admin_email=f_item["admin_email"],
                        admin_password_plain=f_item["admin_password"],
                        deployment_mode=f_item["deployment_mode"],
                        plan_name=f_item["plan_name"],
                        monthly_price_inr=f_item["monthly_price_inr"],
                        local_folder_path=folder_path,
                        assigned_port=f_item["assigned_port"],
                        vps_provider=f_item["vps_provider"],
                        vps_ip=f_item["vps_ip"],
                        vps_ssh_port=22,
                        vps_ssh_user="root",
                        vps_root_password=f_item["vps_root_password"],
                        remote_deploy_path="/opt/epaper",
                        status="REMOTE_VPS_PACKAGE_READY" if f_item["deployment_mode"] == "REMOTE_DEDICATED_VPS" else "RUNNING_LOCAL_VPS",
                        provision_logs=logs,
                    )
                )
            await db.commit()

    yield
    await engine.dispose()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="2.1.0",
    description="White-Label E-Paper SaaS & Dedicated VPS Fleet Provisioning Engine",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def multi_tenant_host_context_middleware(request: Request, call_next):
    hostname = extract_clean_hostname(request)
    request.state.hostname = hostname
    response = await call_next(request)
    response.headers["X-Resolved-Host"] = hostname
    return response


# Register API v1 Routers
app.include_router(public.router, prefix=settings.API_V1_PREFIX)
app.include_router(reader.router, prefix=settings.API_V1_PREFIX)
app.include_router(clipping.router, prefix=settings.API_V1_PREFIX)
app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(admin.router, prefix=settings.API_V1_PREFIX)
app.include_router(superadmin.router, prefix=settings.API_V1_PREFIX)
app.include_router(fleet.router, prefix=settings.API_V1_PREFIX)
app.include_router(assets.router, prefix=settings.API_V1_PREFIX)


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": settings.PROJECT_NAME,
        "engine": "PyMuPDF 300-DPI + 512x512 WebP DeepZoom Pyramid + VPS Fleet Provisioner",
    }
