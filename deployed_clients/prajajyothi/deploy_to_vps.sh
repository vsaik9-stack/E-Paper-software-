#!/usr/bin/env bash
# ==============================================================================
# Automated Dedicated VPS Provisioner for Praja Jyothi (epaper.prajajyothi.com)
# Target VPS: root@65.108.142.88:22 -> /opt/epaper/prajajyothi
# ==============================================================================
set -e

VPS_IP="${1:-65.108.142.88}"
VPS_USER="${2:-root}"
VPS_PORT="${3:-22}"
REMOTE_DIR="/opt/epaper/prajajyothi"

echo "🚀 Uploading Praja Jyothi White-Label Package to ${VPS_USER}@${VPS_IP}:${REMOTE_DIR}..."
ssh -p "${VPS_PORT}" "${VPS_USER}@${VPS_IP}" "mkdir -p ${REMOTE_DIR}"
rsync -avz --exclude 'data' -e "ssh -p ${VPS_PORT}" ./ "${VPS_USER}@${VPS_IP}:${REMOTE_DIR}/"

echo "🔧 Ensuring Docker & Compose are installed and starting containers..."
ssh -p "${VPS_PORT}" "${VPS_USER}@${VPS_IP}" "cd ${REMOTE_DIR} && (which docker || curl -fsSL https://get.docker.com | sh) && docker compose up -d --build"

echo "✅ Praja Jyothi is LIVE at https://epaper.prajajyothi.com (Uploader: https://epaper.prajajyothi.com/admin)"
