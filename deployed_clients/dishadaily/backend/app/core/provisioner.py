import io
import json
import os
import shutil
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import paramiko
from starlette.concurrency import run_in_threadpool


WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DEPLOYED_CLIENTS_DIR = WORKSPACE_ROOT / "deployed_clients"


class ClientProvisioner:
    """
    Automates packaging and provisioning of isolated Single-Tenant Newspaper E-Paper instances:
    1. Local VPS Mode (`deployed_clients/<slug>/`):
       - Creates an isolated client folder on the VPS
       - Copies the battle-tested PDF DeepZoom Engine (`processor.py`, `clip_generator.py`, `storage/`, `assets.py`)
         and Frontend Reader (`OSDViewer.tsx`, `CropOverlay.tsx`, `sound.ts`)
       - Injects the client's `brand_config.json`, `.env`, `docker-compose.yml`, and `Caddyfile` for `epaper.domain.com`
       - Generates a `deploy_to_remote_vps.sh` script for 1-command migration or remote push
    2. Remote Dedicated VPS Mode (via SSH `paramiko`):
       - Connects using the VPS IP, SSH Port, and Root Password stored in our Master Registry
       - Automatically installs Docker, Docker Compose, and Caddy on the remote server
       - Streams the packaged client tarball over SFTP to `/opt/epaper/<slug>/`
       - Starts the isolated Docker stack and binds `https://epaper.domain.com`
    """

    def __init__(self):
        DEPLOYED_CLIENTS_DIR.mkdir(parents=True, exist_ok=True)

    def build_client_instance_folder(
        self,
        client_name: str,
        client_slug: str,
        domain: str,
        brand_primary_color: str,
        brand_secondary_color: str,
        editions_list: List[str],
        admin_email: str,
        admin_password: str,
        assigned_port: int,
        logo_url: Optional[str] = None,
        deployment_mode: str = "LOCAL_VPS",
        vps_ip: Optional[str] = None,
        vps_ssh_port: int = 22,
        vps_ssh_user: str = "root",
        remote_deploy_path: str = "/opt/epaper",
    ) -> Tuple[str, str]:
        """
        Builds a complete, self-contained Single-Tenant White-Label client folder
        under `deployed_clients/<client_slug>/` with all core engine files, branding,
        Docker Compose, Caddyfile, and dedicated `/admin` uploader configuration.
        Returns `(folder_path, log_output)`.
        """
        logs: List[str] = []
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        client_dir = DEPLOYED_CLIENTS_DIR / client_slug
        client_dir.mkdir(parents=True, exist_ok=True)

        logs.append(f"[{now_str}] 🚀 Starting Client Package Builder for '{client_name}' ({domain})")
        logs.append(f"[{now_str}] 📁 Target VPS Client Directory: {client_dir}")

        # 1. Copy core backend engine files into client_dir/backend
        src_backend = WORKSPACE_ROOT / "backend"
        dst_backend = client_dir / "backend"
        if dst_backend.exists():
            shutil.rmtree(dst_backend)

        shutil.copytree(
            src_backend,
            dst_backend,
            ignore=shutil.ignore_patterns(
                ".venv", "__pycache__", "*.pyc", "*.db", "storage_data", ".git"
            ),
        )
        logs.append(
            f"[{now_str}] ✅ Copied Core Backend Engine (processor.py 512x512 WebP DeepZoom, clip_generator.py, storage/, assets.py)"
        )

        # 2. Copy core frontend files into client_dir/frontend (excluding node_modules and .next build artifacts)
        src_frontend = WORKSPACE_ROOT / "frontend"
        dst_frontend = client_dir / "frontend"
        if dst_frontend.exists():
            shutil.rmtree(dst_frontend)

        shutil.copytree(
            src_frontend,
            dst_frontend,
            ignore=shutil.ignore_patterns("node_modules", ".next", ".git"),
        )
        logs.append(
            f"[{now_str}] ✅ Copied Core Frontend Reader (OSDViewer.tsx, CropOverlay.tsx, sound.ts, Dedicated /admin Uploader)"
        )

        # 3. Write Client Brand Configuration (brand_config.json)
        brand_config = {
            "single_tenant_lock": True,
            "client_name": client_name,
            "client_slug": client_slug,
            "domain": domain,
            "logo_url": logo_url,
            "brand_primary_color": brand_primary_color,
            "brand_secondary_color": brand_secondary_color,
            "editions": editions_list,
            "admin_portal_url": f"https://{domain}/admin",
            "admin_email": admin_email,
            "generated_at": now_str,
        }
        (client_dir / "brand_config.json").write_text(
            json.dumps(brand_config, indent=2), encoding="utf-8"
        )
        logs.append(f"[{now_str}] 🎨 Injected White-Label Brand Config (brand_config.json) for {domain}")

        # 4. Write Client-Specific .env file (Locks the instance to this single newspaper client)
        backend_port = assigned_port
        frontend_port = assigned_port + 100
        env_content = (
            f"# ==================================================================\n"
            f"# Dedicated White-Label E-Paper Instance: {client_name}\n"
            f"# Custom Domain: https://{domain}\n"
            f"# Publisher Admin Uploader: https://{domain}/admin\n"
            f"# ==================================================================\n"
            f"PROJECT_NAME=\"{client_name} Digital E-Paper\"\n"
            f"SINGLE_TENANT_MODE=true\n"
            f"DEFAULT_TENANT_SLUG={client_slug}\n"
            f"CLIENT_CUSTOM_DOMAIN={domain}\n"
            f"BRAND_PRIMARY_COLOR={brand_primary_color}\n"
            f"BRAND_SECONDARY_COLOR={brand_secondary_color}\n"
            f"ADMIN_EMAIL={admin_email}\n"
            f"ADMIN_PASSWORD={admin_password}\n"
            f"BACKEND_PORT={backend_port}\n"
            f"FRONTEND_PORT={frontend_port}\n"
            f"DATABASE_URL=postgresql+asyncpg://epaper:epaper_{client_slug}_pass@postgres:5432/epaper_{client_slug}\n"
            f"STORAGE_PROVIDER=local\n"
            f"LOCAL_STORAGE_DIR=/app/storage_data\n"
            f"NEXT_PUBLIC_SINGLE_TENANT_SLUG={client_slug}\n"
        )
        (client_dir / ".env").write_text(env_content, encoding="utf-8")
        (dst_backend / ".env").write_text(env_content, encoding="utf-8")

        # 5. Write Isolated Docker Compose for this Client Instance
        compose_content = f"""version: "3.9"

# Isolated Docker Stack for {client_name} ({domain})
services:
  postgres_{client_slug}:
    image: postgres:16-alpine
    container_name: epaper_db_{client_slug}
    restart: unless-stopped
    environment:
      POSTGRES_USER: epaper
      POSTGRES_PASSWORD: epaper_{client_slug}_pass
      POSTGRES_DB: epaper_{client_slug}
    volumes:
      - ./data/postgres:/var/lib/postgresql/data

  backend_{client_slug}:
    build: ./backend
    container_name: epaper_api_{client_slug}
    restart: unless-stopped
    env_file: .env
    volumes:
      - ./data/storage:/app/storage_data
    ports:
      - "{backend_port}:8000"
    depends_on:
      - postgres_{client_slug}

  frontend_{client_slug}:
    build: ./frontend
    container_name: epaper_web_{client_slug}
    restart: unless-stopped
    environment:
      BACKEND_INTERNAL_URL: http://backend_{client_slug}:8000
      NEXT_PUBLIC_SINGLE_TENANT_SLUG: {client_slug}
    ports:
      - "{frontend_port}:3000"
    depends_on:
      - backend_{client_slug}
"""
        if deployment_mode == "REMOTE_DEDICATED_VPS":
            # Include dedicated Caddy SSL reverse proxy inside the remote VPS stack
            compose_content += f"""
  caddy_{client_slug}:
    image: caddy:2.8-alpine
    container_name: epaper_caddy_{client_slug}
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - ./data/caddy_data:/data
      - ./data/caddy_config:/config
    depends_on:
      - backend_{client_slug}
      - frontend_{client_slug}
"""
        (client_dir / "docker-compose.yml").write_text(compose_content, encoding="utf-8")
        logs.append(
            f"[{now_str}] 🐳 Generated isolated docker-compose.yml (API Port: {backend_port}, Web Port: {frontend_port})"
        )

        # 6. Write Client Caddyfile for automatic Let's Encrypt SSL on epaper.domain.com
        caddy_content = f"""# Automatic HTTPS / SSL for {client_name} ({domain})
{domain} {{
    encode zstd gzip

    handle /api/v1/* {{
        reverse_proxy 127.0.0.1:{backend_port} {{
            header_up Host {{host}}
            header_up X-Tenant-Slug {client_slug}
        }}
    }}

    handle {{
        reverse_proxy 127.0.0.1:{frontend_port} {{
            header_up Host {{host}}
            header_up X-Tenant-Slug {client_slug}
        }}
    }}
}}
"""
        (client_dir / "Caddyfile").write_text(caddy_content, encoding="utf-8")

        # 7. Write Automated SSH Remote VPS Deployment Script (`deploy_to_vps.sh`)
        target_ip = vps_ip or "YOUR_DEDICATED_VPS_IP"
        deploy_script = f"""#!/usr/bin/env bash
# ==============================================================================
# Automated Dedicated VPS Provisioner for {client_name} ({domain})
# Target VPS: {vps_ssh_user}@{target_ip}:{vps_ssh_port} -> {remote_deploy_path}/{client_slug}
# ==============================================================================
set -e

VPS_IP="${{1:-{target_ip}}}"
VPS_USER="${{2:-{vps_ssh_user}}}"
VPS_PORT="${{3:-{vps_ssh_port}}}"
REMOTE_DIR="{remote_deploy_path}/{client_slug}"

echo "🚀 Uploading {client_name} White-Label Package to ${{VPS_USER}}@${{VPS_IP}}:${{REMOTE_DIR}}..."
ssh -p "${{VPS_PORT}}" "${{VPS_USER}}@${{VPS_IP}}" "mkdir -p ${{REMOTE_DIR}}"
rsync -avz --exclude 'data' -e "ssh -p ${{VPS_PORT}}" ./ "${{VPS_USER}}@${{VPS_IP}}:${{REMOTE_DIR}}/"

echo "🔧 Ensuring Docker & Compose are installed and starting containers..."
ssh -p "${{VPS_PORT}}" "${{VPS_USER}}@${{VPS_IP}}" "cd ${{REMOTE_DIR}} && (which docker || curl -fsSL https://get.docker.com | sh) && docker compose up -d --build"

echo "✅ {client_name} is LIVE at https://{domain} (Uploader: https://{domain}/admin)"
"""
        script_path = client_dir / "deploy_to_vps.sh"
        script_path.write_text(deploy_script, encoding="utf-8")
        os.chmod(script_path, 0o755)

        # Create isolated data directories
        (client_dir / "data" / "storage").mkdir(parents=True, exist_ok=True)
        (client_dir / "data" / "postgres").mkdir(parents=True, exist_ok=True)

        logs.append(f"[{now_str}] 🔐 Created Dedicated Uploader Credentials: {admin_email}")
        logs.append(f"[{now_str}] 🌐 Reader URL: https://{domain} (Local Preview: http://localhost:3000/?tenant={client_slug}&single=1)")
        logs.append(f"[{now_str}] 📤 Client Admin Uploader URL: https://{domain}/admin (Local Preview: http://localhost:3000/admin?tenant={client_slug}&single=1)")

        return str(client_dir), "\n".join(logs)

    async def deploy_to_remote_vps_via_ssh(
        self,
        local_client_dir: str,
        client_slug: str,
        vps_ip: str,
        vps_ssh_port: int,
        vps_ssh_user: str,
        vps_root_password: Optional[str] = None,
        vps_ssh_private_key: Optional[str] = None,
        remote_deploy_path: str = "/opt/epaper",
    ) -> Tuple[bool, str]:
        """
        Connects to a Dedicated Remote VPS via SSH (Paramiko) using the root password or SSH key
        stored in our Master Registry, uploads the client's isolated package, installs Docker if needed,
        and launches `docker compose up -d --build`.
        """
        def _sync_ssh_deploy() -> Tuple[bool, str]:
            ssh_logs: List[str] = []
            now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            ssh_logs.append(
                f"[{now_str}] 🔌 Connecting to Dedicated Remote VPS {vps_ssh_user}@{vps_ip}:{vps_ssh_port}..."
            )
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            try:
                connect_kwargs: Dict[str, Any] = {
                    "hostname": vps_ip,
                    "port": vps_ssh_port,
                    "username": vps_ssh_user,
                    "timeout": 12,
                }
                if vps_ssh_private_key and vps_ssh_private_key.strip():
                    pkey = paramiko.RSAKey.from_private_key(io.StringIO(vps_ssh_private_key))
                    connect_kwargs["pkey"] = pkey
                elif vps_root_password:
                    connect_kwargs["password"] = vps_root_password

                client.connect(**connect_kwargs)
                ssh_logs.append(f"[{now_str}] ✅ SSH Authentication Successful on {vps_ip}!")

                target_remote_dir = f"{remote_deploy_path.rstrip('/')}/{client_slug}"
                client.exec_command(f"mkdir -p {target_remote_dir}")

                # Create in-memory tar.gz of the prepared client folder
                tar_buffer = io.BytesIO()
                with tarfile.open(fileobj=tar_buffer, mode="w:gz") as tar:
                    tar.add(local_client_dir, arcname=".")
                tar_buffer.seek(0)

                sftp = client.open_sftp()
                remote_tar_path = f"{target_remote_dir}/client_package.tar.gz"
                sftp.putfo(tar_buffer, remote_tar_path)
                sftp.close()
                ssh_logs.append(
                    f"[{now_str}] 📦 Uploaded Branded Core Engine Package to {remote_tar_path}"
                )

                # Extract package and launch Docker Compose on remote VPS
                remote_cmd = (
                    f"cd {target_remote_dir} && "
                    f"tar -xzf client_package.tar.gz && "
                    f"rm -f client_package.tar.gz && "
                    f"(which docker >/dev/null 2>&1 || curl -fsSL https://get.docker.com | sh) && "
                    f"docker compose up -d --build"
                )
                stdin, stdout, stderr = client.exec_command(remote_cmd)
                exit_status = stdout.channel.recv_exit_status()
                out_text = stdout.read().decode("utf-8", errors="ignore").strip()
                err_text = stderr.read().decode("utf-8", errors="ignore").strip()

                if out_text:
                    ssh_logs.append(f"[REMOTE STDOUT] {out_text[:600]}")
                if exit_status == 0:
                    ssh_logs.append(
                        f"[{now_str}] 🎉 Remote Dedicated VPS Stack is RUNNING on {vps_ip}!"
                    )
                    return True, "\n".join(ssh_logs)
                else:
                    ssh_logs.append(f"[REMOTE STDERR] {err_text[:600]}")
                    return False, "\n".join(ssh_logs)

            except Exception as exc:
                ssh_logs.append(
                    f"[{now_str}] ⚠️ SSH Connection Note ({exc}). Package & `deploy_to_vps.sh` are ready in `{local_client_dir}` and VPS credentials are saved in the Master Vault for 1-click retry as soon as VPS is reachable."
                )
                return False, "\n".join(ssh_logs)
            finally:
                client.close()

        return await run_in_threadpool(_sync_ssh_deploy)


client_provisioner = ClientProvisioner()
