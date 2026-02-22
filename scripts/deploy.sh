#!/bin/bash
set -euo pipefail

# ============================================================
# cal.gp3.app Deployment — Maggie VPS (89.116.157.23)
# Co-located with KERNEL platform (n0v8v)
# Usage: ./scripts/deploy.sh
# ============================================================

PROJECT_DIR="/opt/cal-agent"
N0V8V_DIR="/opt/n0v8v"
DOMAIN="cal.gp3.app"

echo "=========================================="
echo "  cal.gp3.app — Maggie VPS Deployment"
echo "=========================================="

# Step 1: Install Node if missing
echo "[1/8] Checking Node.js..."
if ! command -v node &> /dev/null; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt-get install -y nodejs
fi

# Step 2: Project directory
echo "[2/8] Setting up ${PROJECT_DIR}..."
mkdir -p "${PROJECT_DIR}"

# Step 3: Environment file
if [ ! -f "${PROJECT_DIR}/.env" ]; then
    echo "[3/8] Creating .env..."
    cp "${PROJECT_DIR}/.env.example" "${PROJECT_DIR}/.env"
    SECRET_KEY=$(openssl rand -hex 32)
    DB_PASSWORD=$(openssl rand -hex 24)
    sed -i "s/CHANGE_ME_GENERATE_WITH_OPENSSL/${SECRET_KEY}/" "${PROJECT_DIR}/.env"
    sed -i "s/CHANGE_ME_STRONG_PASSWORD/${DB_PASSWORD}/" "${PROJECT_DIR}/.env"
    echo ""
    echo "  [!] Edit .env and add ANTHROPIC_API_KEY:"
    echo "      nano ${PROJECT_DIR}/.env"
    echo ""
    read -p "  Press Enter after updating .env..."
else
    echo "[3/8] .env exists, skipping..."
fi

# Step 4: Build frontend
echo "[4/8] Building frontend..."
cd "${PROJECT_DIR}/frontend"
npm install --silent 2>/dev/null
npm run build
cd "${PROJECT_DIR}"

# Step 5: Mount frontend into n0v8v Caddy
echo "[5/8] Mounting frontend for Caddy..."
mkdir -p /opt/cal-web
cp -r "${PROJECT_DIR}/frontend/dist/"* /opt/cal-web/

# Add volume mount to n0v8v Caddy if not present
if ! grep -q "cal-web" "${N0V8V_DIR}/docker-compose.yml"; then
    echo "  [!] Adding /opt/cal-web mount to n0v8v-caddy..."
    sed -i '/\/rpc\/web:\/rpc\/web:ro/a\      - /opt/cal-web:/cal/web:ro' "${N0V8V_DIR}/docker-compose.yml"
fi

# Step 6: Update Caddyfile
echo "[6/8] Updating Caddyfile..."
if ! grep -q "cal.gp3.app" "${N0V8V_DIR}/Caddyfile"; then
    echo "" >> "${N0V8V_DIR}/Caddyfile"
    cat "${PROJECT_DIR}/Caddyfile" >> "${N0V8V_DIR}/Caddyfile"
    echo "  Added cal.gp3.app block to Caddyfile"
else
    echo "  cal.gp3.app already in Caddyfile, skipping..."
fi

# Step 7: Start cal-agent containers
echo "[7/8] Starting cal-agent containers..."
cd "${PROJECT_DIR}"
docker compose down 2>/dev/null || true
docker compose up -d --build

# Step 8: Reload Caddy to pick up new config
echo "[8/8] Reloading Caddy..."
cd "${N0V8V_DIR}"
docker compose up -d --force-recreate n0v8v-caddy

# Verify
sleep 5
if curl -sf http://localhost:8200/health > /dev/null; then
    echo ""
    echo "=========================================="
    echo "  DEPLOYMENT SUCCESSFUL"
    echo "=========================================="
    echo ""
    echo "  URL:      https://${DOMAIN}"
    echo "  Health:   https://${DOMAIN}/health"
    echo "  API Docs: https://${DOMAIN}/docs"
    echo ""
    echo "  Logs:     docker logs cal-backend -f"
    echo "  DB:       docker exec -it cal-postgres psql -U cal_admin -d cal_gp3"
    echo ""
    echo "  Next: Point DNS A record for cal.gp3.app → 89.116.157.23"
    echo "=========================================="
else
    echo ""
    echo "[ERROR] Backend health check failed."
    echo "  docker logs cal-backend --tail 30"
    exit 1
fi
