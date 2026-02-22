#!/bin/bash
set -euo pipefail

# ============================================================
# Add New Tenant to cal.gp3.app
# Usage: ./scripts/add-tenant.sh <slug> <company_name>
# Example: ./scripts/add-tenant.sh acme "ACME Manufacturing"
# ============================================================

SLUG="${1:?Usage: add-tenant.sh <slug> <company_name>}"
COMPANY="${2:?Usage: add-tenant.sh <slug> <company_name>}"

echo "Adding tenant: ${SLUG} (${COMPANY})"

docker compose exec -T postgres psql -U cal_admin -d cal_gp3 <<EOF
INSERT INTO tenants (tenant_slug, company_name, subscription_status)
VALUES ('${SLUG}', '${COMPANY}', 'active')
ON CONFLICT (tenant_slug) DO NOTHING;
EOF

echo "Tenant '${SLUG}' created."
echo ""
echo "Next steps:"
echo "  1. Create admin user via POST /auth/register"
echo "     Body: {\"email\": \"admin@${SLUG}.com\", \"password\": \"...\", \"name\": \"Admin\", \"tenant_slug\": \"${SLUG}\"}"
echo "  2. Create kernel file: kernels/${SLUG}_calibrations_v1.0.ttc"
echo "  3. User logs in at cal.gp3.app"
