# Cal Agent — Instruction Manual
**Version 2.0.0 | Updated 2026-02-27**
**Domain:** cal.gp3.app | **Port:** 8200 | **GitHub:** github.com/Aim67TQ7/cal-agent

---

## Overview

Cal Agent is a multi-tenant AI-powered calibration management system for manufacturing quality teams. It tracks equipment calibration schedules, processes certificates via AI extraction, answers natural language questions about calibration data, and generates branded PDF audit evidence packages.

**Stack:** FastAPI + SQLAlchemy + Supabase (PostgreSQL) + Anthropic Claude Sonnet + ReportLab PDF + React/Vite frontend

**Primary Tenant:** Bunting Magnetics (company_id=3) — ~150 real tools, 100 calibration records

---

## 1. Authentication

### Login
```
POST /auth/login
Content-Type: application/json

{
  "email": "user@company.com",
  "password": "secret"
}
```

**Response:**
```json
{
  "token": "eyJhbG...",
  "company_name": "Bunting Magnetics",
  "role": "admin"
}
```

The token is a JWT (HS256, 7-day expiry) containing `user_id`, `company_id`, and `role`. All subsequent requests require `Authorization: Bearer {token}`.

### Register
```
POST /auth/register
Content-Type: application/json

{
  "email": "new@company.com",
  "password": "secret",
  "first_name": "Jane",
  "last_name": "Smith",
  "company_code": "bunting"
}
```

The `company_code` is the company slug — provided during tenant onboarding. Returns 404 if invalid, 409 if email already exists.

---

## 2. Equipment Management

### List All Equipment
```
GET /cal/equipment
Authorization: Bearer {token}
```

**Response:**
```json
{
  "equipment": [
    {
      "id": 42,
      "number": "CAL-0042",
      "type": "caliper",
      "description": "6\" Digital Caliper",
      "manufacturer": "Mitutoyo",
      "model": "CD-6CS",
      "serial_number": "123456789",
      "location": "Lab A",
      "building": "Plant 1",
      "frequency": "annual",
      "ownership": "Bunting",
      "calibration_status": "current",
      "tool_status": "active",
      "last_cal_date": "2025-12-15",
      "next_due_date": "2026-12-15"
    }
  ],
  "total": 177
}
```

Returns only equipment belonging to the authenticated user's company.

### Add Equipment
```
POST /cal/equipment
Authorization: Bearer {token}
Content-Type: application/json

{
  "number": "CAL-0200",
  "type": "micrometer",
  "description": "0-1\" Outside Micrometer",
  "manufacturer": "Mitutoyo",
  "model": "MDC-1",
  "serial_number": "SN-98765",
  "location": "QC Lab",
  "building": "Plant 1",
  "frequency": "annual",
  "ownership": "Bunting"
}
```

Only `number` is required. All other fields are optional.

---

## 3. Certificate Upload

```
POST /cal/upload
Authorization: Bearer {token}
Content-Type: multipart/form-data

file: <PDF or image of calibration certificate>
```

**What happens:**
1. File saved to `/app/uploads/{company_id}/`
2. Claude Sonnet extracts calibration data (tool number, dates, result, technician, comments)
3. System looks up the tool by number in the company's registry
4. If found: creates calibration record + attachment record, updates tool status
5. If not found: returns warning with extracted data so user can add tool first

**Success response:**
```json
{
  "status": "success",
  "message": "Calibration cert for CAL-0042 processed. Next due 2026-12-15.",
  "data": {
    "tool_number": "CAL-0042",
    "calibration_date": "2025-12-15",
    "next_due_date": "2026-12-15",
    "technician": "J. Smith",
    "result": "pass",
    "comments": "All parameters within tolerance"
  }
}
```

**Warning response (tool not in registry):**
```json
{
  "status": "warning",
  "message": "Tool 'CAL-9999' not found in registry. Please add it first.",
  "extracted_data": { ... }
}
```

---

## 4. Natural Language Q&A

```
POST /cal/question
Authorization: Bearer {token}
Content-Type: application/json

{
  "question": "Which tools are overdue for calibration?"
}
```

**Response:**
```json
{
  "status": "success",
  "answer": "Based on your records, 6 tools are currently overdue:\n\n- CAL-0012 (Bore Gage): Due 2026-01-15\n- CAL-0023 (Snap Gage): Due 2026-02-01\n..."
}
```

The agent has access to your full equipment registry, all calibration records, and status summaries. It can answer questions like:

- "What's our compliance rate?"
- "Which gauges expire in Q2 2026?"
- "How many tools does Derek Sanchez manage?"
- "List all gaussmeters and their last calibration dates"
- "What is the calibration frequency for our bore gages?"

---

## 5. Dashboard

```
GET /cal/dashboard
Authorization: Bearer {token}
```

**Response:**
```json
{
  "tool_count": 177,
  "calibration_count": 100,
  "status_summary": {
    "current": 140,
    "expiring_soon": 20,
    "overdue": 17
  },
  "upcoming_expirations": [
    {
      "number": "CAL-0042",
      "type": "caliper",
      "manufacturer": "Mitutoyo",
      "next_due_date": "2026-03-15",
      "status": "expiring_soon"
    }
  ],
  "overdue": [
    {
      "number": "CAL-0012",
      "type": "bore_gage",
      "manufacturer": "Sunnen",
      "next_due_date": "2026-01-15",
      "status": "overdue"
    }
  ]
}
```

- **upcoming_expirations**: Tools due within the next 60 days
- **overdue**: Tools past their due date

---

## 6. Evidence Package Download

```
POST /cal/download
Authorization: Bearer {token}
Content-Type: application/json

{
  "evidence_type": "all_current",
  "format": "pdf"
}
```

**Evidence types:**
| Type | Description |
|------|-------------|
| `all_current` | All equipment with current calibrations |
| `overdue` | Only overdue items |
| `expiring_soon` | Items expiring within 30 days |

**Format options:**
- `pdf` — Returns a branded PDF with cover page, executive summary, and equipment table
- `json` — Returns AI summary text + record count

**PDF includes:**
- Company logo (if uploaded)
- Company name, address, contact info
- Cover stats: total equipment, compliance rate, current/expiring/overdue counts
- AI-generated executive summary
- Full equipment detail table (tool #, type, manufacturer, cal date, due date, status, result)
- Branded footer

### Upload Logo (admin only)
```
POST /cal/upload-logo
Authorization: Bearer {token}
Content-Type: multipart/form-data

file: <PNG or JPG logo>
```

---

## 7. Health Check

```
GET /health
```

No authentication required.

```json
{
  "status": "healthy",
  "product": "cal.gp3.app",
  "version": "2.0.0",
  "timestamp": "2026-02-27T14:30:00"
}
```

---

## 8. Database Schema

All tables live in the `cal` schema on Supabase (GP3 project: ezlmmegowggujpcnzoda).

### cal.companies
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | 1=Default, 2=Demo, 3=Bunting |
| name | VARCHAR(200) | Display name |
| slug | VARCHAR(50) UNIQUE | Registration code |
| subscription_plan | VARCHAR(50) | basic / professional / enterprise |
| max_users | INTEGER | Plan limit |
| max_tools | INTEGER | Plan limit |
| is_active | BOOLEAN | Soft delete |

### cal.users
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| email | VARCHAR(255) UNIQUE | Login credential |
| password_hash | VARCHAR(255) | bcrypt |
| first_name, last_name | VARCHAR(100) | Display |
| role | VARCHAR(50) | admin / user |
| company_id | FK → companies | Tenant isolation |
| is_active | BOOLEAN | Soft delete |
| last_login_at | TIMESTAMPTZ | Updated on login |

### cal.tools
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment (sequence starts at 200) |
| company_id | FK → companies | Tenant isolation |
| number | VARCHAR(100) | Equipment identifier (e.g., "CAL-0042") |
| type | VARCHAR(100) | Category (caliper, gauge, CMM, etc.) |
| description | TEXT | Free-form |
| manufacturer | VARCHAR(200) | OEM |
| model | VARCHAR(200) | Model number |
| serial_number | VARCHAR(200) | Traceability |
| location | VARCHAR(200) | Physical location |
| building | VARCHAR(100) | Facility |
| frequency | VARCHAR(50) | Calibration interval (annual, semi-annual, etc.) |
| ownership | VARCHAR(200) | Owner |
| calibration_status | VARCHAR(50) | current / expiring_soon / overdue |
| tool_status | VARCHAR(50) | active / retired |
| last_calibration_date | TIMESTAMPTZ | Updated on cert upload |
| next_due_date | TIMESTAMPTZ | Updated on cert upload |

### cal.calibrations
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment (sequence starts at 200) |
| record_number | VARCHAR(100) | Human-friendly ID |
| tool_id | FK → tools | Links to equipment |
| calibration_date | TIMESTAMPTZ | When calibrated |
| result | VARCHAR(50) | pass / fail / conditional |
| next_due_date | TIMESTAMPTZ | When next cal is due |
| technician | VARCHAR(200) | From certificate |
| comments | TEXT | Notes/measurements |

### cal.attachments
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| tool_id | FK → tools | |
| calibration_id | FK → calibrations | |
| filename | VARCHAR(255) | Stored name (uuid + original) |
| original_name | VARCHAR(255) | User's filename |
| file_size | INTEGER | Bytes |
| mime_type | VARCHAR(100) | application/pdf, etc. |

### cal.settings
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| key | VARCHAR(100) | Setting name |
| value | TEXT | Setting value |
| company_id | FK → companies | Per-tenant config |

**Security:** All tables have RLS enabled with `service_role` bypass policies. The backend connects as service_role via the Supabase direct connection string.

---

## 9. Tenant Kernel System (TTC)

Cal Agent uses a two-tier context system to customize AI behavior per tenant.

### Layer 1: Agent Kernel (shared)
**File:** `/app/kernels/calibrations_v1.0.ttc.md`

Defines the agent's core behavior: how to extract certificate data, answer compliance questions, generate evidence packages, and calculate calibration status (current / expiring_soon / overdue).

Variables `{TENANT_NAME}` and `{EQUIPMENT_LIST}` are injected at request time.

### Layer 2: Tenant Kernel (per-customer)
**File:** `/app/kernels/tenants/{slug}.ttc.md`

Contains tenant-specific details:
- Company profile (industry, locations, standards like ISO 9001)
- Equipment categories used
- Calibration labs (primary, secondary, in-house)
- Business rules (escalation paths, response times)
- Branding (logo, colors, fonts, contact info, report footer)

### Branding Block Example
Inside the tenant kernel file:
```
logo_file     := bunting-logo.png
primary_color := #003366
accent_color  := #CC0000
font          := Helvetica
line1         := "Bunting Magnetics Company"
line2         := "500 S. Spencer Ave."
line3         := "Newton, KS 67114"
phone         := "(316) 284-2020"
web           := "bfrgroup.com"
report_footer := "Confidential — Bunting Magnetics Quality Department"
```

---

## 10. Frontend

The React/Vite SPA lives in `frontend/` and includes:

| Page | Purpose |
|------|---------|
| **Login** | Email/password login + registration with company code |
| **Dashboard** | Stats cards (total, compliance %, expiring, overdue) + upcoming/overdue tables |
| **Upload** | Drag-and-drop certificate upload with AI extraction feedback |
| **Ask Agent** | Natural language Q&A chat interface |
| **Evidence** | Generate audit evidence packages (select type + format) |
| **Equipment** | Browse/add equipment registry |

**Navigation:** Sidebar with 5 tabs + sign out. Auth state persisted in localStorage.

**Build:** `cd frontend && npm install && npm run build` → outputs to `dist/`

---

## 11. Deployment

### Prerequisites
- Docker + Docker Compose
- Supabase project with `cal` schema (already set up)
- Anthropic API key
- Domain pointing to server (cal.gp3.app → Maggie VPS)

### Environment Variables (.env)
```bash
SUPABASE_DB_URL=postgresql://postgres.ezlmmegowggujpcnzoda:[PASSWORD]@aws-0-us-east-1.pooler.supabase.com:6543/postgres
ANTHROPIC_API_KEY=sk-ant-api03-...
SECRET_KEY=$(openssl rand -hex 32)
ENVIRONMENT=production
```

### Deploy Commands
```bash
ssh root@89.116.157.23
cd /opt/cal-agent
docker compose down
docker compose build --no-cache
docker compose up -d
```

### Verify
```bash
curl https://cal.gp3.app/health
# {"status":"healthy","product":"cal.gp3.app","version":"2.0.0",...}
```

### Logs
```bash
docker logs -f cal-backend
```

---

## 12. Tenant Onboarding Checklist

### Day 1: Setup
- [ ] Add company to `cal.companies` (id, name, slug, plan)
- [ ] Create admin user via `POST /auth/register` with company slug
- [ ] Provide credentials to customer
- [ ] Verify login works

### Day 2: Configuration
- [ ] Interview calibration manager for equipment list, labs, standards
- [ ] Author tenant kernel: `/app/kernels/tenants/{slug}.ttc.md`
- [ ] Upload company logo via `POST /cal/upload-logo`
- [ ] Import equipment (bulk CSV or manual via `POST /cal/equipment`)

### Day 3: Testing + Go-Live
- [ ] Customer uploads 10-20 real certificates
- [ ] Test Q&A: "What's our compliance rate?"
- [ ] Test evidence PDF download — verify branding, layout, data
- [ ] Go live

---

## 13. Current Data (Bunting Magnetics)

| Table | Records |
|-------|---------|
| Companies | 3 (Default, Demo, Bunting) |
| Users | 7 (admin + Bunting team: Ryan Linton, Brandon Dick, Derek Sanchez, Steve Bryant) |
| Tools | 177 (~150 Bunting: snap gages, micrometers, bore gages, calipers, gaussmeters) |
| Calibrations | 100 (real records with dates, pass/fail, technician notes) |
| Attachments | 3 (PDF calibration certificates) |
| Settings | 10 (plan limits, alert thresholds) |

---

## 14. Error Reference

| Code | Endpoint | Cause |
|------|----------|-------|
| 401 | All protected | Missing/expired JWT token |
| 401 | /auth/login | Wrong email or password |
| 403 | /cal/upload-logo | Non-admin user |
| 404 | /auth/register | Invalid company_code (slug) |
| 404 | /cal/upload-logo | Company not found |
| 409 | /auth/register | Email already registered |

---

## 15. API Quick Reference

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| GET | /health | No | Health check |
| POST | /auth/login | No | Login → JWT |
| POST | /auth/register | No | Register with company slug |
| GET | /cal/equipment | JWT | List tools |
| POST | /cal/equipment | JWT | Add tool |
| POST | /cal/upload | JWT | Upload cal cert |
| POST | /cal/question | JWT | NL Q&A |
| POST | /cal/download | JWT | Evidence package |
| POST | /cal/upload-logo | JWT (admin) | Upload logo |
| GET | /cal/dashboard | JWT | Stats + alerts |
