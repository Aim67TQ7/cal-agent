# cal.gp3.app — Product Specification

## Product Summary

**cal.gp3.app** is a multi-tenant, AI-powered calibration management agent. It automates certificate processing, tracks equipment calibration schedules, answers compliance questions in natural language, and generates audit evidence packages on demand.

**Target:** Manufacturing quality departments drowning in calibration paperwork.
**Value Prop:** Eliminates the calibration tracking burden — upload a cert, ask a question, pull an audit package.

---

## Architecture

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Backend | FastAPI + Python 3.11 | API, auth, agent orchestration |
| Database | PostgreSQL 15 | Multi-tenant data store with RLS |
| Frontend | React 18 + Vite | SPA served via Caddy |
| Reverse Proxy | Caddy 2 | Auto-SSL, static files, proxy |
| AI Engine | Claude Sonnet (Anthropic API) | Certificate parsing, Q&A, evidence |
| Container | Docker Compose | Full-stack orchestration |

### Multi-Tenancy Model

**Phase 1 (MVP):** Path-based routing
- `cal.gp3.app` → Login → redirects to `/cal/{tenant_slug}`
- Single SSL cert, single deployment
- Row-Level Security (RLS) in PostgreSQL isolates all tenant data

**Phase 2 (Post-validation, 3-5 customers):** Subdomain routing
- `bunting.cal.gp3.app`, `acme.cal.gp3.app`
- Wildcard SSL cert via Caddy

---

## Core Features

### 1. Certificate Upload
- Drag-and-drop PDF/JPG/PNG calibration certificates
- AI extracts: equipment ID, calibration date, expiration date, lab name, technician, pass/fail
- Auto-matches to equipment registry
- Stores cert file + structured data

### 2. Natural Language Q&A
- "Which gauges expire in Q2?"
- "What's our compliance rate?"
- "Show me everything calibrated by Lab X"
- Context-aware — agent sees full equipment registry + cal records

### 3. Audit Evidence Generation
- Generate compliance packages filtered by: all current, overdue, expiring soon
- Cover sheet with summary stats + compliance rate
- Organized by equipment type
- Flags non-conformances

### 4. Equipment Registry
- Add/manage equipment with: ID, type, manufacturer, model, serial, location
- Set calibration frequency (months)
- Mark critical equipment
- Tracks last calibration + next expiration

### 5. Dashboard
- Compliance rate at a glance
- Equipment count, expiring soon, overdue counts
- Upcoming expirations (60-day window)
- Recent activity timeline
- Token usage tracking

---

## Database Schema

### Tables

| Table | Purpose |
|-------|---------|
| `tenants` | Multi-tenant registry (slug, company, subscription, token budget) |
| `users` | Authentication (email/password, role, tenant association) |
| `equipment` | Equipment registry (ID, type, frequency, lab, critical flag) |
| `calibration_records` | Cal certs (dates, lab, status, file path, extracted data) |
| `calibration_events` | Audit trail (uploads, alerts, escalations) |
| `token_usage` | API cost tracking per tenant |

### Security
- All data tables have RLS policies keyed on `tenant_id`
- `SET LOCAL app.current_tenant_id` per request
- JWT tokens encode `tenant_id` + `tenant_slug`
- Tenant access verified on every endpoint

### Auto-Status
- Database trigger auto-sets calibration status on INSERT/UPDATE:
  - `current` → expiration > 30 days out
  - `expiring_soon` → expiration within 30 days
  - `overdue` → expiration has passed
- `refresh_calibration_statuses()` function for daily cron

---

## API Endpoints

### Authentication
| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/login` | Email/password login → JWT |
| POST | `/auth/register` | Create user for existing tenant |

### Agent (Tenant-Scoped via JWT)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/cal/upload` | Upload cal cert → AI extraction |
| POST | `/cal/question` | Natural language Q&A |
| POST | `/cal/download` | Generate evidence package |
| GET | `/cal/equipment` | List equipment + latest cal status |
| POST | `/cal/equipment` | Add equipment to registry |
| GET | `/cal/dashboard` | Dashboard stats + activity |

### System
| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |

---

## Infrastructure

### VPS: Maggie (Co-located)
- **IP:** 89.116.157.23 (SSH port 22)
- **Host:** Hostinger — 16GB RAM / 4 vCPUs / 193GB SSD
- **Co-located with:** KERNEL platform (n0v8v), ttc-encoder, ai-intake, taskqueue
- **Available resources:** ~14GB RAM free, 182GB disk free
- **Incremental cost:** $0 (existing VPS)

### DNS
- A record: `cal.gp3.app` → `89.116.157.23`
- SSL handled by existing `n0v8v-caddy` container (auto Let's Encrypt)

### Containers
| Container | Image | Port | Network |
|-----------|-------|------|---------|
| cal-postgres | postgres:15-alpine | 5435 (host) → 5432 | cal-net |
| cal-backend | custom (Python 3.11) | 8200 (host) → 8000 | cal-net + n0v8v-net |

### Integration with Existing Stack
- `cal-backend` joins `n0v8v_n0v8v-net` so `n0v8v-caddy` can reverse proxy to it
- Caddy block appended to `/opt/n0v8v/Caddyfile`
- Frontend built to `/opt/cal-web/` and mounted into Caddy at `/cal/web`
- Own postgres instance (separate from n0v8v-postgres) for clean isolation

### Volumes
- `cal-pgdata` — database persistence
- `cal-uploads` — uploaded certificate files

### Key Paths on VPS
- Project: `/opt/cal-agent/`
- Frontend static: `/opt/cal-web/`
- Caddy config: `/opt/n0v8v/Caddyfile` (shared)

---

## Tenant Onboarding (2-3 days per customer)

1. **Add tenant record** → `./scripts/add-tenant.sh acme "ACME Manufacturing"`
2. **Interview cal manager** → Extract equipment list, labs, processes, frequencies
3. **Create tenant kernel** → `kernels/acme_calibrations_v1.0.ttc` (customized system prompt)
4. **Create admin user** → POST `/auth/register`
5. **Customer uploads equipment** → Through UI
6. **Upload existing certs** → Bulk upload through UI
7. **Agent operational** → Q&A and evidence generation live

---

## Economics

### Cost Per Tenant (Monthly)
| Item | Cost |
|------|------|
| VPS allocation | $0 (co-located on Maggie) |
| Anthropic tokens | $0.50-1.00 |
| **Total COGS** | **~$1** |

### Revenue
- Platform fee: **$700/month** per tenant
- Gross margin: **99%**

### Breakeven
- 4 customers = $2,800/month revenue vs ~$4 COGS (co-located)

---

## 2-Week Build Schedule

### Week 1: Infrastructure + Backend
| Day | Task |
|-----|------|
| 1 | VPS setup, Docker, DNS, SSL |
| 2 | Database schema, Docker Compose postgres, seed data, verify RLS |
| 3-4 | Kernel authoring (interview Bunting cal manager), test in Claude |
| 5-7 | FastAPI endpoints, auth, upload/question/download, tenant isolation |

### Week 2: Frontend + Deploy
| Day | Task |
|-----|------|
| 8-10 | React UI — login, dashboard, 3 agent functions, equipment mgmt |
| 11-12 | Full-stack deploy via Docker Compose, HTTPS verification |
| 13-14 | Upload 10 real certs, test all flows, bug fixes, GO LIVE |

---

## Success Criteria

- [ ] cal.gp3.app live with Bunting deployed
- [ ] Upload/Question/Download all functional
- [ ] Multi-tenant DB working (ready for customer #2)
- [ ] Docker stack runs reliably
- [ ] Token usage <3k per interaction
- [ ] RLS prevents cross-tenant data leakage
- [ ] Bunting feedback: "This works, eliminates burden"

---

## File Structure

```
cal-agent/
├── SPEC.md                     # This document
├── docker-compose.yml          # Full stack orchestration
├── Caddyfile                   # Snippet appended to /opt/n0v8v/Caddyfile
├── .env.example                # Environment template
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── main.py                 # FastAPI app (auth + agent + equipment)
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   └── src/
│       ├── main.jsx
│       ├── index.css
│       └── App.jsx             # Full SPA (login, dashboard, agent UI)
├── database/
│   └── init.sql                # Schema + RLS + triggers + seed
├── kernels/
│   └── calibrations_v1.0.ttc   # Agent system prompt template
└── scripts/
    ├── deploy.sh               # Full deployment script
    └── add-tenant.sh           # New tenant onboarding
```
