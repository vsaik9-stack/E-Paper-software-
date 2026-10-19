#!/usr/bin/env bash
# ==============================================================================
# Automated Dedicated VPS Provisioner for Disha Daily (epaper.dishadaily.com)
# Target VPS: root@127.0.0.1:22 -> /opt/epaper/dishadaily
# ==============================================================================
set -e

VPS_IP="${1:-127.0.0.1}"
VPS_USER="${2:-root}"
VPS_PORT="${3:-22}"
REMOTE_DIR="/opt/epaper/dishadaily"

echo "🚀 Uploading Disha Daily White-Label Package to ${VPS_USER}@${VPS_IP}:${REMOTE_DIR}..."
ssh -p "${VPS_PORT}" "${VPS_USER}@${VPS_IP}" "mkdir -p ${REMOTE_DIR}"
rsync -avz --exclude 'data' -e "ssh -p ${VPS_PORT}" ./ "${VPS_USER}@${VPS_IP}:${REMOTE_DIR}/"

echo "🔧 Ensuring Docker & Compose are installed and starting containers..."
ssh -p "${VPS_PORT}" "${VPS_USER}@${VPS_IP}" "cd ${REMOTE_DIR} && (which docker || curl -fsSL https://get.docker.com | sh) && docker compose up -d --build"

echo "✅ Disha Daily is LIVE at https://epaper.dishadaily.com (Uploader: https://epaper.dishadaily.com/admin)"
