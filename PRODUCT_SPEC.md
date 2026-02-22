# CalAgent — Product Specification
### AI-Powered Calibration Compliance Platform
**Version:** 1.0.0 | **Status:** Production (cal.gp3.app) | **Date:** 2026-02-22

---

## 1. Product Overview

### What It Is
CalAgent is a containerized, multi-tenant SaaS platform that automates calibration management for manufacturing facilities. It uses AI to extract data from calibration certificates, answer compliance questions in natural language, and generate audit-ready evidence packages on demand.

### Problem Statement
Quality departments in manufacturing spend 10-20 hours per month manually tracking calibration schedules across spreadsheets, filing paper certificates, and assembling audit evidence packages. Missed calibrations create regulatory exposure (ISO 9001, IATF 16949, AS9100). Failed audits cost $50K-500K in remediation.

### Solution
Three-function interface: **Upload** a certificate, **Ask** a question, **Download** an evidence package. The AI agent handles data extraction, schedule tracking, and report generation. No training required — if you can upload a PDF and type a question, you can use CalAgent.

### Target Customer
- Manufacturing quality managers (first: Bunting Magnetics)
- 50-500 pieces of calibrated equipment
- Currently tracking with Excel, paper, or outdated CMMS modules
- Under ISO 9001 / IATF 16949 / AS9100 audit pressure

---

## 2. Product Architecture

### System Diagram

```
┌──────────────────────────────────────────────────────┐
│                  cal.gp3.app (HTTPS)                 │
│                                                      │
│  ┌─────────┐    ┌──────────────┐    ┌─────────────┐ │
│  │  Caddy   │───│  FastAPI      │───│  PostgreSQL  │ │
│  │  (SSL +  │   │  (Backend)    │   │  15-Alpine   │ │
│  │  Static) │   │               │   │              │ │
│  └─────────┘    │  ┌──────────┐ │   │  RLS Enforced│ │
│       │         │  │ Anthropic │ │   │  per Tenant  │ │
│  ┌─────────┐    │  │ Claude    │ │   │              │ │
│  │ React   │    │  │ Sonnet    │ │   │  cal_app     │ │
│  │ SPA     │    │  └──────────┘ │   │  (restricted)│ │
│  └─────────┘    └──────────────┘    └─────────────┘ │
│                                                      │
│  Docker Compose on Maggie VPS (89.116.157.23)        │
└──────────────────────────────────────────────────────┘
```

### Technology Stack

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| Frontend | React + Vite | 18.2 / 5.0 | Single-page application |
| Backend | FastAPI + Uvicorn | 0.109 / 0.27 | REST API, auth, agent orchestration |
| AI Engine | Claude Sonnet | claude-sonnet-4-5 | Certificate parsing, NLP Q&A, evidence generation |
| Database | PostgreSQL | 15-alpine | Multi-tenant data store |
| Reverse Proxy | Caddy | 2-alpine | Auto-SSL (Let's Encrypt), static files, routing |
| Container | Docker Compose | 3.8 | Full-stack orchestration |
| OS | Ubuntu | 24.04 LTS | Host operating system |

### Container Inventory

| Container | Image | Ports | Network | Resources |
|-----------|-------|-------|---------|-----------|
| `cal-postgres` | postgres:15-alpine | 5435→5432 (localhost only) | cal-net | ~200MB RAM |
| `cal-backend` | python:3.11-slim (custom) | 8200→8000 (localhost only) | cal-net + n0v8v-net | ~150MB RAM |
| `n0v8v-caddy` | caddy:2-alpine (shared) | 80, 443 (public) | n0v8v-net | shared |

**Total footprint:** ~350MB RAM, ~500MB disk (excluding data volumes)

---

## 3. Multi-Tenancy

### Isolation Model

CalAgent enforces tenant isolation at **two independent layers**. Both must be compromised for cross-tenant data access.

#### Layer 1: Application (JWT)
```
User login → JWT issued with embedded tenant_id
              ↓
Every API call → JWT decoded → tenant_id extracted
              ↓
All database queries scoped to that tenant_id
```

- JWT signed with 256-bit HMAC secret
- 7-day expiration
- `tenant_id` is a UUID — not guessable, not enumerable
- No tenant identifier appears in any URL

#### Layer 2: Database (PostgreSQL Row-Level Security)

```sql
-- Backend connects as cal_app (non-superuser)
-- RLS is FORCE-enabled — cannot be bypassed by cal_app

CREATE POLICY rls_equipment ON equipment
    FOR ALL TO cal_app
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::UUID);
```

| Scenario | Result |
|----------|--------|
| No tenant context set | Query errors (not silent empty) |
| Wrong tenant UUID | 0 rows returned |
| Correct tenant UUID | Only that tenant's rows visible |
| SQL injection attempt | RLS still enforces — policy is at DB level |

#### What Is NOT RLS-Protected (By Design)
| Table | Reason |
|-------|--------|
| `tenants` | Needed for registration lookup (by opaque code, not enumerable) |
| `users` | Needed for login before tenant context exists (lookup by email only) |

### URL Opacity

No tenant identity is exposed in any URL or API path.

| Before (removed) | After (current) |
|---|---|
| `cal.gp3.app/cal/bunting/upload` | `cal.gp3.app/cal/upload` |
| `cal.gp3.app/cal/bunting/dashboard` | `cal.gp3.app/cal/dashboard` |

Tenant context is derived exclusively from the JWT Bearer token.

### Tenant Onboarding

| Step | Action | Time |
|------|--------|------|
| 1 | Add tenant record via `add-tenant.sh` | 5 min |
| 2 | Interview calibration manager | 1-2 hrs |
| 3 | Author tenant-specific kernel (.ttc file) | 2-4 hrs |
| 4 | Create admin user via `/auth/register` | 5 min |
| 5 | Customer imports equipment list | 30 min |
| 6 | Customer uploads existing certificates | 1-2 hrs |
| **Total** | | **2-3 days** |

---

## 4. Core Features

### 4.1 Certificate Upload

**Endpoint:** `POST /cal/upload` (multipart/form-data)

**Flow:**
1. User drags/drops PDF, JPG, or PNG certificate
2. File saved to tenant-isolated upload directory (`/app/uploads/{tenant_id}/`)
3. AI agent receives filename + file metadata
4. Agent extracts structured data: equipment ID, calibration date, expiration date, lab name, technician, pass/fail
5. System matches equipment ID to registry
6. Calibration record created with auto-status trigger
7. Event logged to audit trail

**AI Extraction Format:**
```json
{
    "equipment_id": "CAL-0042",
    "calibration_date": "2026-01-15",
    "expiration_date": "2027-01-15",
    "lab_name": "Transcat Inc.",
    "technician": "J. Smith",
    "pass_fail": "pass",
    "notes": "All parameters within tolerance"
}
```

**Edge Cases:**
- Equipment not in registry → warning returned with extracted data, user prompted to add equipment first
- Unparseable certificate → error returned, manual entry suggested
- JSON extraction failure → fallback parser attempts to find JSON in response

### 4.2 Natural Language Q&A

**Endpoint:** `POST /cal/question`

**Context Injection:** Before calling the AI agent, the system injects:
- All calibration records (equipment ID, type, dates, status, lab, result)
- Equipment summary (total count, critical count)
- Tenant-specific kernel with equipment registry

**Example Queries:**
| Question | Agent Behavior |
|----------|---------------|
| "Which gauges expire in Q2?" | Filters by expiration date range, returns list |
| "What's our compliance rate?" | Calculates current/total, returns percentage |
| "Show me everything from Transcat" | Filters by lab_name |
| "Are any critical items overdue?" | Filters critical=true + status=overdue |
| "What do I need for the ISO audit next week?" | Generates prioritized action list |

**Token Budget:** Target <3,000 tokens per interaction (~$0.01)

### 4.3 Audit Evidence Generation

**Endpoint:** `POST /cal/download`

**Evidence Types:**
| Type | Filter |
|------|--------|
| `all_current` | All calibration records with status = current |
| `overdue` | Only overdue calibrations |
| `expiring_soon` | Expiring within 30 days |

**Output:** AI-generated evidence package summary including:
- Cover sheet (total equipment, compliance rate, generation date)
- Records organized by equipment type
- Non-conformances flagged
- Recommendation summary

### 4.4 Equipment Registry

**Endpoints:** `GET /cal/equipment`, `POST /cal/equipment`

**Equipment Record Fields:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| equipment_id | string | Yes | Unique identifier (e.g., CAL-0042) |
| equipment_type | string | No | Category (caliper, gauge, scale, etc.) |
| description | text | No | Free-text description |
| manufacturer | string | No | OEM name |
| model | string | No | Model number |
| serial_number | string | No | Serial number |
| location | string | No | Physical location |
| cal_frequency_months | integer | No | Calibration interval (default: 12) |
| lab_name | string | No | Default calibration lab |
| critical | boolean | No | Critical measurement equipment flag |

**Equipment list view** joins latest calibration record to show: last cal date, next expiration, current status.

### 4.5 Dashboard

**Endpoint:** `GET /cal/dashboard`

**Widgets:**
| Widget | Data |
|--------|------|
| Equipment Count | Total registered equipment |
| Compliance Rate | (current records / total records) * 100 |
| Expiring Soon | Count of records expiring within 30 days |
| Overdue | Count of expired records |
| Upcoming Expirations | Table: equipment expiring within 60 days, sorted by date |
| Recent Activity | Last 10 events (uploads, alerts, escalations) |
| Token Usage | Monthly token consumption + estimated cost |

---

## 5. Database Schema

### Entity Relationship

```
tenants 1──────M users
   │
   ├──────M equipment 1──────M calibration_records
   │           │
   ├──────M calibration_events (references equipment)
   │
   └──────M token_usage (references users)
```

### Tables

#### `tenants`
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK, auto-generated |
| tenant_slug | VARCHAR(50) | UNIQUE, NOT NULL (internal only) |
| company_name | VARCHAR(200) | NOT NULL |
| subscription_status | VARCHAR(50) | DEFAULT 'active' |
| token_budget_daily | INTEGER | DEFAULT 5000 |
| logo_url | TEXT | White-label branding |
| primary_color | VARCHAR(7) | DEFAULT '#1a1a2e' |
| created_at | TIMESTAMP | DEFAULT NOW() |
| updated_at | TIMESTAMP | DEFAULT NOW() |

#### `users`
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| tenant_id | UUID | FK → tenants(id) CASCADE |
| email | VARCHAR(255) | UNIQUE, NOT NULL |
| password_hash | VARCHAR(255) | bcrypt |
| name | VARCHAR(200) | |
| role | VARCHAR(50) | DEFAULT 'admin' |
| last_login | TIMESTAMP | |
| created_at | TIMESTAMP | DEFAULT NOW() |

#### `equipment`
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| tenant_id | UUID | FK → tenants(id) CASCADE |
| equipment_id | VARCHAR(100) | UNIQUE per tenant |
| equipment_type | VARCHAR(50) | |
| description | TEXT | |
| manufacturer | VARCHAR(200) | |
| model | VARCHAR(200) | |
| serial_number | VARCHAR(200) | |
| location | VARCHAR(200) | |
| cal_frequency_months | INTEGER | |
| lab_name | VARCHAR(200) | |
| critical | BOOLEAN | DEFAULT false |
| status | VARCHAR(50) | DEFAULT 'active' |
| metadata | JSONB | DEFAULT '{}' |
| created_at | TIMESTAMP | DEFAULT NOW() |
| updated_at | TIMESTAMP | DEFAULT NOW() |

**RLS:** FORCE enabled, policy on `tenant_id`

#### `calibration_records`
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| tenant_id | UUID | FK → tenants(id) CASCADE |
| equipment_id | UUID | FK → equipment(id) CASCADE |
| cert_file_path | TEXT | Server-side file path |
| cert_file_name | VARCHAR(255) | Original filename |
| calibration_date | DATE | NOT NULL |
| expiration_date | DATE | NOT NULL |
| lab_name | VARCHAR(200) | |
| technician | VARCHAR(200) | |
| status | VARCHAR(50) | Auto-set by trigger |
| pass_fail | VARCHAR(10) | DEFAULT 'pass' |
| notes | TEXT | |
| extracted_data | JSONB | Raw AI extraction |
| created_at | TIMESTAMP | DEFAULT NOW() |

**RLS:** FORCE enabled, policy on `tenant_id`

**Auto-Status Trigger:**
```
expiration_date < today           → 'overdue'
expiration_date < today + 30 days → 'expiring_soon'
expiration_date >= today + 30     → 'current'
```

#### `calibration_events`
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| tenant_id | UUID | FK → tenants(id) CASCADE |
| equipment_id | UUID | FK → equipment(id) |
| event_type | VARCHAR(50) | NOT NULL |
| event_data | JSONB | DEFAULT '{}' |
| created_by | UUID | FK → users(id) |
| created_at | TIMESTAMP | DEFAULT NOW() |

**Event Types:** `cert_uploaded`, `alert_sent`, `escalation`, `status_change`

**RLS:** FORCE enabled, policy on `tenant_id`

#### `token_usage`
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| tenant_id | UUID | FK → tenants(id) CASCADE |
| user_id | UUID | FK → users(id) |
| request_type | VARCHAR(50) | upload, question, download |
| input_tokens | INTEGER | |
| output_tokens | INTEGER | |
| cost | DECIMAL(10,6) | Computed at write time |
| model | VARCHAR(100) | DEFAULT 'claude-sonnet-4-5' |
| timestamp | TIMESTAMP | DEFAULT NOW() |

**RLS:** FORCE enabled, policy on `tenant_id`

### Indexes

| Index | Table | Columns | Purpose |
|-------|-------|---------|---------|
| idx_equipment_tenant | equipment | tenant_id | Tenant filtering |
| idx_equipment_lookup | equipment | tenant_id, equipment_id | Certificate matching |
| idx_equipment_type | equipment | tenant_id, equipment_type | Type filtering |
| idx_cal_records_tenant | calibration_records | tenant_id | Tenant filtering |
| idx_cal_records_expiration | calibration_records | expiration_date | Expiration queries |
| idx_cal_records_equipment | calibration_records | equipment_id | Equipment joins |
| idx_cal_records_status | calibration_records | tenant_id, status | Dashboard counts |
| idx_events_tenant | calibration_events | tenant_id | Activity feed |
| idx_events_equipment | calibration_events | equipment_id | Equipment history |
| idx_token_usage_tenant | token_usage | tenant_id | Usage reporting |
| idx_token_usage_timestamp | token_usage | tenant_id, timestamp | Monthly aggregation |
| idx_users_tenant | users | tenant_id | Tenant user listing |

### Database Users

| User | Role | Purpose |
|------|------|---------|
| `cal_admin` | Superuser | Schema migrations, admin queries. NOT used by application. |
| `cal_app` | Restricted (LOGIN, DML only) | Application connection. RLS enforced. |

---

## 6. API Reference

### Authentication

#### `POST /auth/login`
**Body:** `{ "email": "string", "password": "string" }`
**Response:** `{ "token": "jwt...", "company_name": "string", "role": "string" }`
**Token lifetime:** 7 days

#### `POST /auth/register`
**Body:** `{ "email": "string", "password": "string", "name": "string", "tenant_code": "string" }`
**Response:** `{ "status": "success", "message": "User created. Please login." }`
**Note:** `tenant_code` is the internal slug, provided during onboarding. Not discoverable.

### Agent Endpoints (All require Bearer token)

#### `POST /cal/upload`
**Content-Type:** multipart/form-data
**Body:** `file` (PDF, JPG, PNG)
**Response:**
```json
{
    "status": "success|warning|error",
    "message": "string",
    "data": { "equipment_id": "...", "calibration_date": "...", ... }
}
```

#### `POST /cal/question`
**Body:** `{ "question": "string" }`
**Response:** `{ "status": "success", "answer": "string" }`

#### `POST /cal/download`
**Body:** `{ "evidence_type": "all_current|overdue|expiring_soon" }`
**Response:**
```json
{
    "status": "success",
    "package_description": "string (markdown)",
    "record_count": 42,
    "generated_at": "2026-02-22T21:00:00Z"
}
```

#### `GET /cal/equipment`
**Response:** `{ "equipment": [...], "total": 42 }`

#### `POST /cal/equipment`
**Body:** `{ "equipment_id": "string", "equipment_type": "string", ... }`
**Response:** `{ "status": "success", "message": "Equipment CAL-0042 added." }`

#### `GET /cal/dashboard`
**Response:**
```json
{
    "equipment_count": 42,
    "status_summary": { "current": 38, "expiring_soon": 3, "overdue": 1 },
    "upcoming_expirations": [...],
    "token_usage": { "tokens": 15000, "cost": 0.045 },
    "recent_events": [...]
}
```

### System

#### `GET /health`
**Response:** `{ "status": "healthy", "product": "cal.gp3.app", "version": "1.0.0" }`

---

## 7. AI Agent Architecture

### Kernel System

Each tenant gets a **kernel** — a system prompt template stored as a `.ttc` file. The kernel defines the agent's identity, knowledge, and behavior for that specific customer.

**Template:** `kernels/calibrations_v1.0.ttc`

**Dynamic Injection:** At request time, the kernel template is hydrated with:
- `{TENANT_NAME}` → Company name from tenants table
- `{EQUIPMENT_LIST}` → Current equipment registry formatted as a tree

**Token Budget:** Kernel + context + question should remain under 3,000 input tokens per interaction.

### Request Flow

```
User Action → API Endpoint
                 ↓
         JWT decoded → tenant_id
                 ↓
         SET LOCAL tenant context
                 ↓
         Load tenant kernel (.ttc)
                 ↓
         Inject equipment data into kernel
                 ↓
         Build context (cal records, equipment summary)
                 ↓
         Call Claude Sonnet (kernel as system, context + question as user)
                 ↓
         Parse response → store results → log tokens
                 ↓
         Return to user
```

### Cost Model

| Operation | Avg Input Tokens | Avg Output Tokens | Est. Cost |
|-----------|-----------------|------------------|-----------|
| Upload (cert extraction) | ~1,500 | ~200 | $0.0075 |
| Question | ~2,000 | ~500 | $0.014 |
| Evidence download | ~2,500 | ~1,000 | $0.023 |

**Monthly estimate per tenant** (assuming 100 interactions): **$0.50-1.00**

---

## 8. Frontend

### UI Framework
Single-page React application with dark theme. No component library — vanilla CSS with CSS variables for theming.

### Views

| View | Route | Description |
|------|-------|-------------|
| Login | `/` (unauthenticated) | Email/password form |
| Dashboard | Dashboard nav | Stats, expirations, activity feed |
| Upload | Upload nav | Drag-and-drop certificate upload |
| Ask Agent | Ask Agent nav | Chat-style Q&A with conversation history |
| Evidence | Evidence nav | Evidence type selector + generated report |
| Equipment | Equipment nav | Table with inline add form |

### Layout
- Fixed 220px sidebar with navigation
- Main content area (max 1100px)
- Company name displayed in sidebar header
- No tenant identifier visible anywhere in UI

### White-Label Ready
- `primary_color` field in tenants table (reserved for Phase 2)
- `logo_url` field in tenants table (reserved for Phase 2)
- "Powered by n0v8v" footer on login page

---

## 9. Infrastructure

### Host
**VPS:** Maggie (89.116.157.23) — Hostinger
- 16GB RAM / 4 vCPUs / 193GB SSD
- Co-located with: KERNEL, ttc-encoder, ai-intake, taskqueue
- CalAgent footprint: ~350MB RAM, ~500MB disk

### Networking

```
Internet → cal.gp3.app (DNS A record)
              ↓
         Caddy (:443) — n0v8v-caddy container
              ↓
         ┌─ /auth/*  → cal-backend:8000 ─┐
         ├─ /cal/*   → cal-backend:8000  ├─ n0v8v_n0v8v-net
         ├─ /health  → cal-backend:8000  │
         └─ /*       → /cal/web (static) ┘
```

### Volumes

| Volume | Mount | Contents |
|--------|-------|----------|
| `cal-pgdata` | postgres data dir | Database files |
| `cal-uploads` | /app/uploads/ | Uploaded certificates (per-tenant subdirs) |
| `/opt/cal-web` (bind) | Caddy /cal/web | Built frontend static files |
| `/opt/cal-agent/kernels` (bind) | /app/kernels (read-only) | Agent kernel templates |

### SSL
Automated via Caddy + Let's Encrypt. Certificate issued on first request, auto-renewed.

### Key Paths on VPS

| Path | Purpose |
|------|---------|
| `/opt/cal-agent/` | Project root (backend, docker-compose, .env) |
| `/opt/cal-agent/kernels/` | Tenant kernel files |
| `/opt/cal-web/` | Built frontend (served by Caddy) |
| `/opt/n0v8v/Caddyfile` | Shared reverse proxy config |

### Operations

| Task | Command |
|------|---------|
| View backend logs | `docker logs cal-backend -f` |
| View DB logs | `docker logs cal-postgres -f` |
| Restart backend | `cd /opt/cal-agent && docker compose restart cal-backend` |
| Rebuild + restart | `cd /opt/cal-agent && docker compose up -d --build cal-backend` |
| Rebuild frontend | `cd /opt/cal-agent/frontend && npm run build && cp -r dist/* /opt/cal-web/` |
| DB shell | `docker exec -it cal-postgres psql -U cal_admin -d cal_gp3` |
| App DB shell (RLS) | `docker exec -it cal-postgres psql -U cal_app -d cal_gp3` |
| Add tenant | `cd /opt/cal-agent && ./scripts/add-tenant.sh <slug> "<Company>"` |

---

## 10. Security

| Vector | Mitigation |
|--------|------------|
| Cross-tenant data access | JWT + PostgreSQL RLS (two independent layers) |
| SQL injection | SQLAlchemy parameterized queries (no string interpolation) |
| Password storage | bcrypt hashing (passlib) |
| Token forgery | HMAC-SHA256 JWT with 256-bit secret |
| Brute force login | (Phase 2: rate limiting) |
| File upload abuse | Files stored server-side, never served directly back |
| XSS | React auto-escapes, no dangerouslySetInnerHTML on user data |
| HTTPS | Caddy auto-SSL with Let's Encrypt |
| DB credential exposure | Backend connects as restricted `cal_app`, not superuser |
| Tenant enumeration | No tenant identifiers in URLs, slugs, or error messages |

---

## 11. Economics

### Unit Economics (Per Tenant, Monthly)

| Item | Cost |
|------|------|
| VPS allocation | $0 (co-located) |
| Anthropic API tokens | $0.50-1.00 |
| **Total COGS** | **~$1** |
| **Revenue** | **$700** |
| **Gross margin** | **99.8%** |

### Scaling Thresholds

| Tenants | Monthly Revenue | Monthly COGS | Action Needed |
|---------|----------------|-------------|---------------|
| 1-10 | $700-7,000 | $1-10 | Current VPS sufficient |
| 10-25 | $7,000-17,500 | $10-25 | Monitor RAM, may need dedicated VPS |
| 25-50 | $17,500-35,000 | $25-50 | Dedicated VPS ($48/mo), connection pooling |
| 50+ | $35,000+ | $50+ | Kubernetes, read replicas, CDN |

---

## 12. Roadmap

### Phase 1: Ship Calibration (Current)
- [x] Multi-tenant backend with RLS
- [x] Certificate upload + AI extraction
- [x] Natural language Q&A
- [x] Evidence package generation
- [x] Equipment registry
- [x] Dashboard
- [x] JWT-only routing (no tenant in URLs)
- [ ] Kernel authoring for Bunting (requires cal manager interview)
- [ ] Upload 10 real certificates
- [ ] Bunting validation: "This works"

### Phase 2: Production Hardening
- [ ] Rate limiting on auth endpoints
- [ ] Email notifications for expiring/overdue equipment
- [ ] Daily cron for status refresh (`refresh_calibration_statuses()`)
- [ ] Bulk equipment CSV import
- [ ] Bulk certificate upload
- [ ] Password reset flow
- [ ] White-label theming (logo, color per tenant)

### Phase 3: Platform Expansion
- [ ] Subdomain routing (`{tenant}.cal.gp3.app`)
- [ ] Additional kernel types:
  - Preventive maintenance schedules
  - Safety inspection tracking
  - Asset lifecycle management
- [ ] PDF evidence package download (not just AI summary)
- [ ] Stripe billing integration
- [ ] Admin dashboard (cross-tenant, for n0v8v internal use)

---

## 13. File Structure

```
cal-agent/
├── PRODUCT_SPEC.md              # This document
├── SPEC.md                      # Build/deploy notes
├── docker-compose.yml           # Postgres + Backend (Caddy is shared)
├── Caddyfile                    # Appended to /opt/n0v8v/Caddyfile
├── .env.example                 # Environment template
├── backend/
│   ├── Dockerfile               # Python 3.11-slim + deps
│   ├── requirements.txt         # Pinned dependencies
│   └── main.py                  # FastAPI app (560 lines)
├── frontend/
│   ├── package.json             # React 18 + Vite 5
│   ├── vite.config.js           # Dev proxy config
│   ├── index.html               # Entry point
│   └── src/
│       ├── main.jsx             # React root
│       ├── index.css            # Dark theme, CSS variables
│       └── App.jsx              # Full SPA (490 lines, 7 components)
├── database/
│   └── init.sql                 # Schema + RLS + triggers + seed
├── kernels/
│   └── calibrations_v1.0.ttc    # Agent system prompt template
└── scripts/
    ├── deploy.sh                # Full VPS deployment
    └── add-tenant.sh            # Tenant onboarding helper
```

---

## 14. Source & Access

| Resource | Location |
|----------|----------|
| GitHub | github.com/Aim67TQ7/cal-agent |
| Local source | C:\CLAUDE\cal-agent\ |
| Live URL | https://cal.gp3.app |
| API docs | https://cal.gp3.app/docs |
| Health check | https://cal.gp3.app/health |
| VPS | ssh root@89.116.157.23 |
| Project dir (VPS) | /opt/cal-agent/ |
| Frontend dir (VPS) | /opt/cal-web/ |
