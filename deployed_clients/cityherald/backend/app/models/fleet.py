import uuid
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import Boolean, DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


class DeployedInstance(Base):
    """
    Tracks every Newspaper Client Instance provisioned by our Fleet Manager:
    - Mode 1: LOCAL_FOLDER_DOCKER (Hosted on our shared VPS inside `deployed_clients/<slug>/`)
    - Mode 2: REMOTE_DEDICATED_VPS (Hosted on a separate VPS purchased for high-volume multi-edition clients,
      where the VPS IP & Root SSH Password stay strictly with us in this Master Registry)
    """
    __tablename__ = "deployed_instances"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    client_name: Mapped[str] = mapped_column(String(255), nullable=False)
    client_slug: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    domain: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)

    # Branding & Editions baked into the client's isolated package
    logo_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    brand_primary_color: Mapped[str] = mapped_column(String(32), default="#dc2626", nullable=False)
    brand_secondary_color: Mapped[str] = mapped_column(String(32), default="#0f172a", nullable=False)
    editions_list: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)

    # Client's Admin / Uploader Login Credentials (for epaper.domain.com/admin)
    admin_email: Mapped[str] = mapped_column(String(255), nullable=False)
    admin_password_plain: Mapped[str] = mapped_column(String(255), nullable=False)

    # Deployment Mode: "LOCAL_VPS" or "REMOTE_DEDICATED_VPS"
    deployment_mode: Mapped[str] = mapped_column(String(64), default="LOCAL_VPS", index=True, nullable=False)
    plan_name: Mapped[str] = mapped_column(String(64), default="Standard Shared VPS", nullable=False)
    monthly_price_inr: Mapped[int] = mapped_column(Integer, default=5000, nullable=False)

    # Local VPS Folder & Assigned Port
    local_folder_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    assigned_port: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Remote Dedicated VPS Credentials (Stored ONLY in our Master Control Plane)
    vps_provider: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)  # e.g. Hetzner, DigitalOcean, Hostinger
    vps_ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    vps_ssh_port: Mapped[int] = mapped_column(Integer, default=22, nullable=False)
    vps_ssh_user: Mapped[str] = mapped_column(String(64), default="root", nullable=False)
    vps_root_password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    vps_ssh_private_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    remote_deploy_path: Mapped[str] = mapped_column(String(255), default="/opt/epaper", nullable=False)

    # Status & Logs: PROVISIONED, RUNNING, REMOTE_DEPLOYED, REMOTE_QUEUED, STOPPED, ERROR
    status: Mapped[str] = mapped_column(String(64), default="PROVISIONED", nullable=False)
    provision_logs: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
