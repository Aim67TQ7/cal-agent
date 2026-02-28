from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from anthropic import Anthropic
from pydantic import BaseModel
from passlib.context import CryptContext
from jose import jwt, JWTError
from datetime import datetime, timedelta, date
from pathlib import Path
import os
import re
import io
import uuid
import json
import logging

logger = logging.getLogger("cal-agent")

# ============================================================
# APP SETUP
# ============================================================

app = FastAPI(
    title="cal.gp3.app - Calibration Agent",
    description="Multi-tenant calibration management powered by AI",
    version="2.5.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://cal.gp3.app", "http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# CONFIG
# ============================================================

DATABASE_URL = os.getenv("DATABASE_URL")  # Supabase direct connection string (may be None)
SECRET_KEY = os.getenv("SECRET_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ENVIRONMENT = os.getenv("ENVIRONMENT", "production")
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://ezlmmegowggujpcnzoda.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")  # service_role key
ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 7

# SQLAlchemy — optional, may fail if no DB connection
try:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=10) if DATABASE_URL else None
    SessionLocal = sessionmaker(bind=engine) if engine else None
except Exception:
    engine = None
    SessionLocal = None

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()
anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)

# ============================================================
# SUPABASE REST CLIENT (replaces direct Postgres when unavailable)
# ============================================================

import httpx

_sb_headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Accept-Profile": "cal",
    "Content-Profile": "cal",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

def sb_get(table: str, params: dict = None) -> list:
    """GET from Supabase REST API (cal schema)."""
    r = httpx.get(f"{SUPABASE_URL}/rest/v1/{table}", headers=_sb_headers, params=params or {}, timeout=15)
    r.raise_for_status()
    return r.json()

def sb_post(table: str, data: dict) -> dict:
    """INSERT into Supabase REST API (cal schema)."""
    r = httpx.post(f"{SUPABASE_URL}/rest/v1/{table}", headers=_sb_headers, json=data, timeout=15)
    r.raise_for_status()
    result = r.json()
    return result[0] if isinstance(result, list) and result else result

def sb_patch(table: str, params: dict, data: dict) -> list:
    """UPDATE via Supabase REST API (cal schema)."""
    r = httpx.patch(f"{SUPABASE_URL}/rest/v1/{table}", headers=_sb_headers, params=params, json=data, timeout=15)
    r.raise_for_status()
    return r.json()

def sb_rpc(fn_name: str, params: dict = None) -> any:
    """Call a Supabase RPC function."""
    r = httpx.post(f"{SUPABASE_URL}/rest/v1/rpc/{fn_name}", headers=_sb_headers, json=params or {}, timeout=30)
    r.raise_for_status()
    return r.json()

# ============================================================
# MODELS
# ============================================================

class LoginRequest(BaseModel):
    email: str
    password: str

class RegisterRequest(BaseModel):
    email: str
    password: str
    first_name: str
    last_name: str = ""
    company_code: str  # company slug used at registration

class QuestionRequest(BaseModel):
    question: str

class DownloadRequest(BaseModel):
    evidence_type: str = "all_current"
    format: str = "pdf"

class EquipmentCreate(BaseModel):
    asset_tag: str
    tool_name: str = ""
    tool_type: str = ""
    calibration_method: str = ""
    calibrating_entity: str = ""
    manufacturer: str = ""
    model: str = ""
    serial_number: str = ""
    location: str = ""
    building: str = ""
    cal_interval_days: int = 365
    notes: str = ""

# ============================================================
# DEPENDENCIES
# ============================================================

def get_db():
    if SessionLocal:
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
    else:
        yield None  # No direct DB — using Supabase REST

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        return {
            "user_id": payload["user_id"],
            "company_id": payload["company_id"],
            "role": payload.get("role", "user"),
        }
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

# ============================================================
# KERNEL LOADER
# ============================================================

def load_tenant_kernel(db_unused, company_id: int) -> str:
    """Load two-layer kernel: agent kernel (shared) + tenant kernel (per-customer)."""

    # Layer 1: Agent kernel
    agent_kernel_path = Path("/app/kernels/calibrations_v1.0.ttc.md")
    if agent_kernel_path.exists():
        agent_kernel = agent_kernel_path.read_text()
    else:
        agent_kernel = "You are a calibration management assistant. Help users manage equipment calibration schedules, upload certificates, and generate audit evidence."

    # Get company info via REST
    try:
        companies = sb_get("companies", {"select": "name,slug", "id": f"eq.{company_id}"})
        company = companies[0] if companies else {}
    except Exception:
        company = {}
    company_name = company.get("name", "Unknown")
    company_slug = company.get("slug", "unknown")

    # Get equipment registry via REST
    try:
        equipment = sb_get("tools", {
            "select": "asset_tag,tool_name,tool_type,calibration_method,cal_interval_days",
            "company_id": f"eq.{company_id}",
            "order": "tool_type,asset_tag",
        })
    except Exception:
        equipment = []

    equipment_list = "\n".join([
        f"  {eq.get('asset_tag','')}: {eq.get('tool_type','')} | method={eq.get('calibration_method','')} | interval={eq.get('cal_interval_days','')}d | {eq.get('tool_name','')}"
        for eq in equipment
    ]) or "  No equipment registered yet."

    # Inject variables into agent kernel
    kernel = agent_kernel.replace("{TENANT_NAME}", company_name)
    kernel = kernel.replace("{EQUIPMENT_LIST}", equipment_list)

    # Layer 2: Tenant kernel — per-customer customizations
    tenant_kernel_path = Path(f"/app/kernels/tenants/{company_slug}.ttc.md")
    if tenant_kernel_path.exists():
        tenant_kernel = tenant_kernel_path.read_text()
        tenant_kernel = tenant_kernel.replace("{TENANT_NAME}", company_name)
        tenant_kernel = tenant_kernel.replace("{EQUIPMENT_LIST}", equipment_list)
        kernel = kernel + "\n\n---\n\n" + tenant_kernel

    return kernel

def load_tenant_branding(company_id: int) -> dict:
    """Parse branding block from tenant kernel."""
    try:
        companies = sb_get("companies", {"select": "slug,name", "id": f"eq.{company_id}"})
        company = companies[0] if companies else None
    except Exception:
        company = None
    if not company:
        return {"company_name": "Unknown", "slug": "unknown"}

    slug = company["slug"]
    company_name = company["name"]

    branding = {
        "company_name": company_name,
        "slug": slug,
        "logo_path": None,
        "primary_color": "#003366",
        "accent_color": "#CC0000",
        "font": "Helvetica",
        "address_lines": [],
        "phone": "",
        "web": "",
        "report_footer": f"Confidential — {company_name}",
    }

    tenant_kernel_path = Path(f"/app/kernels/tenants/{slug}.ttc.md")
    if not tenant_kernel_path.exists():
        return branding

    content = tenant_kernel_path.read_text()

    brand_match = re.search(r'### 品牌标识.*?```(.*?)```', content, re.DOTALL)
    if not brand_match:
        return branding

    block = brand_match.group(1)
    for line in block.strip().split("\n"):
        line = line.strip()
        if ":=" not in line:
            continue
        key, val = line.split(":=", 1)
        key = key.strip()
        val = val.strip().strip('"')
        if key == "logo_file":
            logo_path = Path(f"/app/uploads/tenants/{slug}/{val}")
            if logo_path.exists():
                branding["logo_path"] = str(logo_path)
        elif key == "primary_color":
            branding["primary_color"] = val
        elif key == "accent_color":
            branding["accent_color"] = val
        elif key == "font":
            branding["font"] = val
        elif key == "report_footer":
            branding["report_footer"] = val
        elif key == "phone":
            branding["phone"] = val
        elif key == "web":
            branding["web"] = val
        elif key in ("line1", "line2", "line3"):
            branding["address_lines"].append(val)

    return branding


def hex_to_rgb(hex_color: str) -> tuple:
    """Convert hex color to RGB tuple (0-1 range for reportlab)."""
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    return (r / 255.0, g / 255.0, b / 255.0)


def generate_branded_pdf(branding: dict, records: list, evidence_type: str, ai_summary: str) -> bytes:
    """Generate a branded PDF evidence package."""
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.colors import Color, HexColor
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, topMargin=0.75*inch, bottomMargin=0.75*inch)

    primary = HexColor(branding["primary_color"])
    accent = HexColor(branding["accent_color"])
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        "BrandTitle", parent=styles["Title"], textColor=primary, fontSize=22, spaceAfter=6
    ))
    styles.add(ParagraphStyle(
        "BrandSubtitle", parent=styles["Normal"], textColor=primary, fontSize=11, spaceAfter=12
    ))
    styles.add(ParagraphStyle(
        "SectionHead", parent=styles["Heading2"], textColor=primary, fontSize=14, spaceBefore=16, spaceAfter=8
    ))
    styles.add(ParagraphStyle(
        "Footer", parent=styles["Normal"], textColor=HexColor("#888888"), fontSize=8, alignment=TA_CENTER
    ))

    elements = []

    # Logo
    if branding.get("logo_path") and Path(branding["logo_path"]).exists():
        logo = Image(branding["logo_path"], width=2*inch, height=1*inch)
        logo.hAlign = "LEFT"
        elements.append(logo)
        elements.append(Spacer(1, 12))

    # Title block
    elements.append(Paragraph("Calibration Evidence Package", styles["BrandTitle"]))
    elements.append(Paragraph(branding["company_name"], styles["BrandSubtitle"]))

    for line in branding.get("address_lines", []):
        elements.append(Paragraph(line, styles["Normal"]))
    if branding.get("phone"):
        elements.append(Paragraph(branding["phone"], styles["Normal"]))
    if branding.get("web"):
        elements.append(Paragraph(branding["web"], styles["Normal"]))

    elements.append(Spacer(1, 20))

    # Cover stats
    total = len(records)
    current = sum(1 for r in records if r["calibration_status"] == "current")
    overdue = sum(1 for r in records if r["calibration_status"] == "overdue")
    expiring = sum(1 for r in records if r["calibration_status"] == "expiring_soon")
    compliance_rate = f"{(current / total * 100):.1f}%" if total > 0 else "N/A"

    cover_data = [
        ["Report Type", evidence_type.replace("_", " ").title()],
        ["Generated", datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")],
        ["Total Equipment", str(total)],
        ["Compliance Rate", compliance_rate],
        ["Current", str(current)],
        ["Expiring Soon", str(expiring)],
        ["Overdue", str(overdue)],
    ]
    cover_table = Table(cover_data, colWidths=[2*inch, 3*inch])
    cover_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), primary),
        ("TEXTCOLOR", (0, 0), (0, -1), HexColor("#FFFFFF")),
        ("FONTNAME", (0, 0), (-1, -1), branding.get("font", "Helvetica")),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("PADDING", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#CCCCCC")),
    ]))
    elements.append(cover_table)
    elements.append(Spacer(1, 20))

    # AI Summary
    elements.append(Paragraph("Executive Summary", styles["SectionHead"]))
    for para in ai_summary.split("\n\n"):
        clean = para.strip()
        if clean:
            clean = re.sub(r'[#*]+\s*', '', clean)
            clean = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', clean)
            elements.append(Paragraph(clean, styles["Normal"]))
            elements.append(Spacer(1, 6))

    elements.append(Spacer(1, 12))

    # Equipment detail table
    if records:
        elements.append(Paragraph("Calibration Records", styles["SectionHead"]))
        header = ["Asset Tag", "Equipment Type", "Manufacturer", "Cal Date", "Next Due", "Status", "Result"]
        table_data = [header]
        for r in records:
            status_display = str(r.get("calibration_status") or "").replace("_", " ").title()
            table_data.append([
                str(r.get("asset_tag", "")), str(r.get("tool_type", "")),
                str(r.get("manufacturer", "")),
                str(r.get("last_calibration_date") or ""),
                str(r.get("next_due_date") or ""),
                status_display, str(r.get("result") or ""),
            ])

        t = Table(table_data, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), primary),
            ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#FFFFFF")),
            ("FONTNAME", (0, 0), (-1, 0), branding.get("font", "Helvetica") + "-Bold"),
            ("FONTNAME", (0, 1), (-1, -1), branding.get("font", "Helvetica")),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("PADDING", (0, 0), (-1, -1), 5),
            ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#CCCCCC")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [HexColor("#FFFFFF"), HexColor("#F5F5F5")]),
        ]))
        elements.append(t)

    # Footer
    elements.append(Spacer(1, 30))
    elements.append(Paragraph(branding.get("report_footer", ""), styles["Footer"]))

    doc.build(elements)
    return buf.getvalue()


def call_agent(kernel: str, user_message: str, context: str = "") -> dict:
    """Call Claude with tenant-specific kernel."""
    messages_content = f"{context}\n\n{user_message}" if context else user_message

    response = anthropic_client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=4000,
        system=kernel,
        messages=[{"role": "user", "content": messages_content}],
    )

    return {
        "text": response.content[0].text,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }

# ============================================================
# AUTH ENDPOINTS
# ============================================================

@app.post("/auth/login")
async def login(req: LoginRequest):
    # Fetch user via REST
    users = sb_get("users", {
        "select": "id,password_hash,company_id,role",
        "email": f"eq.{req.email}",
        "is_active": "eq.true",
    })
    if not users:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    user = users[0]

    if not pwd_context.verify(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Get company name
    companies = sb_get("companies", {"select": "name", "id": f"eq.{user['company_id']}"})
    company_name = companies[0]["name"] if companies else "Unknown"

    # Update last login
    try:
        sb_patch("users", {"id": f"eq.{user['id']}"}, {"last_login_at": datetime.utcnow().isoformat()})
    except Exception:
        pass

    token = jwt.encode({
        "user_id": user["id"],
        "company_id": user["company_id"],
        "role": user["role"],
        "exp": datetime.utcnow() + timedelta(days=TOKEN_EXPIRE_DAYS),
    }, SECRET_KEY, algorithm=ALGORITHM)

    return {
        "token": token,
        "company_name": company_name,
        "role": user["role"],
    }

@app.post("/auth/register")
async def register(req: RegisterRequest):
    # Look up company by slug via REST
    companies = sb_get("companies", {"select": "id", "slug": f"eq.{req.company_code}", "is_active": "eq.true"})
    if not companies:
        raise HTTPException(status_code=404, detail="Invalid registration code")
    company_id = companies[0]["id"]

    # Check email not taken
    existing = sb_get("users", {"select": "id", "email": f"eq.{req.email}"})
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    password_hash = pwd_context.hash(req.password)
    sb_post("users", {
        "company_id": company_id,
        "email": req.email,
        "password_hash": password_hash,
        "first_name": req.first_name,
        "last_name": req.last_name,
        "role": "user",
    })

    return {"status": "success", "message": "User created. Please login."}

# ============================================================
# CALIBRATION AGENT ENDPOINTS
# ============================================================

@app.post("/cal/upload")
async def upload_cert(
    file: UploadFile = File(...),
    auth: dict = Depends(verify_token),
):
    company_id = auth["company_id"]

    # Save file
    upload_dir = Path(f"/app/uploads/{company_id}")
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_id = str(uuid.uuid4())
    file_path = upload_dir / f"{file_id}_{file.filename}"

    content = await file.read()
    file_path.write_bytes(content)

    # Load kernel and extract data
    kernel = load_tenant_kernel(None, company_id)
    prompt = f"""Extract calibration data from this uploaded certificate.
Filename: {file.filename}
File size: {len(content)} bytes

Return ONLY a valid JSON object:
{{
    "tool_number": "string - the tool/instrument number or ID",
    "calibration_date": "YYYY-MM-DD",
    "next_due_date": "YYYY-MM-DD",
    "technician": "string - technician name if available, else empty",
    "result": "pass or fail",
    "comments": "string - any relevant notes"
}}"""

    agent_response = call_agent(kernel, prompt)

    try:
        data = json.loads(agent_response["text"])
    except json.JSONDecodeError:
        text_resp = agent_response["text"]
        start = text_resp.find("{")
        end = text_resp.rfind("}") + 1
        if start >= 0 and end > start:
            data = json.loads(text_resp[start:end])
        else:
            return {"status": "error", "message": "Could not parse certificate data. Please enter manually."}

    # Look up tool via REST
    tools = sb_get("tools", {
        "select": "id",
        "company_id": f"eq.{company_id}",
        "asset_tag": f"eq.{data.get('tool_number', '')}",
    })

    if not tools:
        return {
            "status": "warning",
            "message": f"Tool '{data.get('tool_number')}' not found in registry. Please add it first.",
            "extracted_data": data,
        }

    tool_id = tools[0]["id"]

    # Insert calibration record via REST
    cal_record = sb_post("calibrations", {
        "cert_number": f"CAL-{datetime.utcnow().strftime('%Y%m%d')}-{tool_id}",
        "tool_id": tool_id,
        "calibration_date": data.get("calibration_date"),
        "result": data.get("result", "pass"),
        "next_calibration_date": data.get("next_due_date"),
        "performed_by": data.get("technician", ""),
        "notes": data.get("comments", ""),
    })

    # Insert attachment record via REST
    sb_post("attachments", {
        "tool_id": tool_id,
        "calibration_id": cal_record.get("id"),
        "filename": f"{file_id}_{file.filename}",
        "original_name": file.filename,
        "file_size": len(content),
        "mime_type": file.content_type or "application/octet-stream",
    })

    # Update tool's last calibration date via REST
    sb_patch("tools", {"id": f"eq.{tool_id}"}, {
        "last_calibration_date": data.get("calibration_date"),
        "next_due_date": data.get("next_due_date"),
        "calibration_status": "current",
    })

    return {
        "status": "success",
        "message": f"Calibration cert for {data['tool_number']} processed. Next due {data.get('next_due_date', 'unknown')}.",
        "data": data,
    }

# Schema reference for Claude's SQL tool
CAL_SCHEMA_REF = """
Available tables (all in cal schema, always filter by company_id = :cid):

cal.tools — Equipment registry
  id, company_id, asset_tag (tool identifier), tool_name (equipment name/description),
  tool_type (equipment category: Snap Gage, Micrometer, Caliper, Gaussmeter, etc.),
  calibration_method (In-House Calibrated or Vendor Calibrated),
  calibrating_entity (lab or entity that calibrates this tool),
  cal_vendor_id (FK→vendors.id — link to approved calibration provider),
  manufacturer, model, serial_number, location, building,
  cal_interval_days (integer), calibration_status (current/expiring_soon/critical/overdue),
  active (boolean), last_calibration_date, next_due_date, notes

cal.calibrations — Calibration records
  id, cert_number, tool_id (FK→tools.id), calibration_date, result (pass/fail),
  next_calibration_date, performed_by (technician or vendor), notes,
  result_score, cost, vendor_id (FK→vendors.id)

cal.vendors — Approved calibration vendors (NIST traceable)
  id, company_id, vendor_name, contact_email, phone,
  accreditation (general), accreditation_number (ISO/IEC 17025 cert #),
  accreditation_body (A2LA, NVLAP, ANAB, etc.),
  nist_traceable (boolean — confirms NIST traceability chain),
  scope_of_accreditation (what they can calibrate),
  approved (boolean), notes

cal.attachments — Uploaded certificates
  id, tool_id, calibration_id, filename, original_name, file_size, mime_type, uploaded_at

cal.email_log — Inbound/outbound email tracking
  id, company_id, direction, from_address, to_address, subject, body_text,
  status, processing_result, tool_id, calibration_id, message_id, received_at

IMPORTANT:
- tool_type contains equipment category (e.g., 'Snap Gage', 'Micrometer', 'Gaussmeter')
- Use tool_type for category filtering: WHERE tool_type = 'Snap Gage'
- Use tool_name ILIKE for fuzzy name search: WHERE tool_name ILIKE '%digital%'
- calibrating_entity shows who calibrates the tool (lab name or 'In-House')
- JOIN cal.vendors via cal_vendor_id for NIST traceability details
- Always include WHERE company_id = :cid for tools/email_log, or JOIN through tools for calibrations.
- Only SELECT queries allowed. Never UPDATE/DELETE/INSERT.
"""

# Claude tools definition for SQL lookup
CAL_SQL_TOOL = {
    "name": "query_calibration_db",
    "description": "Run a read-only SQL query against the calibration database to find equipment, calibration records, or email logs. Use ILIKE for fuzzy text matching. Always filter by company_id.",
    "input_schema": {
        "type": "object",
        "properties": {
            "sql": {
                "type": "string",
                "description": "A SELECT query against cal.tools, cal.calibrations, cal.attachments, or cal.email_log. Always include company_id filter."
            },
            "explanation": {
                "type": "string",
                "description": "Brief explanation of what this query looks for"
            }
        },
        "required": ["sql", "explanation"]
    }
}


def execute_safe_sql(db, sql: str, company_id: int) -> str:
    """Execute a read-only SQL query via Supabase RPC, return formatted results."""
    stripped = sql.strip().upper()
    if not stripped.startswith("SELECT"):
        return "ERROR: Only SELECT queries are allowed."
    for forbidden in ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "CREATE"]:
        if f" {forbidden} " in f" {stripped} " or stripped.startswith(forbidden):
            return f"ERROR: {forbidden} operations are not allowed."

    try:
        rows = sb_rpc("execute_readonly_sql", {"query": sql, "company_id": company_id})
        if not rows:
            return "No results found."

        columns = list(rows[0].keys())
        lines = [" | ".join(columns)]
        lines.append("-" * len(lines[0]))
        for row in rows[:50]:
            lines.append(" | ".join(str(row.get(c, "") or "") for c in columns))
        if len(rows) > 50:
            lines.append(f"... ({len(rows)} total rows, showing first 50)")
        return "\n".join(lines)
    except Exception as e:
        return f"SQL error: {str(e)}"


@app.post("/cal/question")
async def ask_question(
    req: QuestionRequest,
    auth: dict = Depends(verify_token),
):
    company_id = auth["company_id"]

    # Load kernels
    kernel = load_tenant_kernel(None, company_id)

    # Load FAQ knowledge base
    faq_path = Path("/app/kernels/cal-faq.md")
    faq_knowledge = faq_path.read_text() if faq_path.exists() else ""

    # Load conversation memory for this company via REST
    try:
        memories = sb_get("conversation_memory", {
            "select": "question,answer,feedback",
            "company_id": f"eq.{company_id}",
            "order": "used_count.desc,created_at.desc",
            "limit": "20",
        })
        memory_context = "\n".join([
            f"Previous Q: {m['question']}\nA: {m['answer']}" + (f" (feedback: {m['feedback']})" if m.get('feedback') else "")
            for m in memories
        ]) if memories else ""
    except Exception:
        memory_context = ""

    system_prompt = f"""{kernel}

---
{faq_knowledge}

---
DATABASE SCHEMA:
{CAL_SCHEMA_REF}

{f"CONVERSATION MEMORY (past interactions with this tenant):{chr(10)}{memory_context}" if memory_context else ""}

TODAY: {date.today().isoformat()}

INSTRUCTIONS:
- You are Cal, speaking conversationally in first person. Keep responses concise for voice output.
- CRITICAL GROUNDING RULE: You MUST call query_calibration_db BEFORE answering ANY question about equipment, counts, dates, status, or compliance. NEVER answer from memory or the equipment list above — ALWAYS verify with a live query. If you answer without querying first, you will give wrong data.
- Today's date is {date.today().isoformat()}. Use this for all date calculations and comparisons. Do NOT assume any other year.
- Use tool_type for equipment category (e.g., WHERE tool_type = 'Caliper' or tool_type = 'Snap Gage').
- Use tool_name ILIKE for fuzzy name search. Use asset_tag for tool ID lookup.
- If the user asks about specific equipment, search by asset_tag, tool_type, tool_name, or manufacturer.
- Always cite specific data from query results — never make up numbers or dates.
- If no data is found, say so honestly. Do NOT guess or reference the equipment list — only trust query results.
- Short sentences. This is spoken aloud, not a report.
"""

    # Call Claude with tool use (agentic loop)
    messages = [{"role": "user", "content": req.question}]
    max_turns = 5
    final_text = ""

    for _ in range(max_turns):
        response = anthropic_client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=2000,
            system=system_prompt,
            tools=[CAL_SQL_TOOL],
            messages=messages,
        )

        # Process response blocks
        tool_calls = []
        for block in response.content:
            if block.type == "text":
                final_text += block.text
            elif block.type == "tool_use":
                tool_calls.append(block)

        if response.stop_reason == "end_turn" or not tool_calls:
            break

        # Execute tool calls and feed results back
        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for tc in tool_calls:
            if tc.name == "query_calibration_db":
                sql_result = execute_safe_sql(None, tc.input.get("sql", ""), company_id)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tc.id,
                    "content": sql_result,
                })

        messages.append({"role": "user", "content": tool_results})

    # Store Q&A in conversation memory for learning via REST
    try:
        # Try upsert via RPC (handles ON CONFLICT logic)
        sb_rpc("upsert_conversation_memory", {
            "p_company_id": company_id,
            "p_question": req.question,
            "p_answer": final_text[:2000],
        })
    except Exception:
        pass

    return {"status": "success", "answer": final_text}

@app.post("/cal/upload-logo")
async def upload_logo(
    file: UploadFile = File(...),
    auth: dict = Depends(verify_token),
):
    """Upload tenant logo for branded reports."""
    if auth["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin only")

    companies = sb_get("companies", {"select": "slug", "id": f"eq.{auth['company_id']}"})
    if not companies:
        raise HTTPException(status_code=404, detail="Company not found")

    slug = companies[0]["slug"]
    logo_dir = Path(f"/app/uploads/tenants/{slug}")
    logo_dir.mkdir(parents=True, exist_ok=True)

    tenant_kernel_path = Path(f"/app/kernels/tenants/{slug}.ttc.md")
    logo_filename = "logo.png"
    if tenant_kernel_path.exists():
        content = tenant_kernel_path.read_text()
        match = re.search(r'logo_file\s*:=\s*(\S+)', content)
        if match:
            logo_filename = match.group(1)

    file_path = logo_dir / logo_filename
    file_content = await file.read()
    file_path.write_bytes(file_content)

    return {"status": "success", "message": f"Logo uploaded as {logo_filename}", "path": str(file_path)}


@app.post("/cal/download")
async def generate_evidence(
    req: DownloadRequest,
    auth: dict = Depends(verify_token),
):
    from fastapi.responses import Response
    company_id = auth["company_id"]

    # Fetch tools via REST
    params = {
        "select": "asset_tag,tool_name,tool_type,manufacturer,serial_number,last_calibration_date,next_due_date,calibration_status,location",
        "company_id": f"eq.{company_id}",
        "order": "tool_type,asset_tag",
    }
    if req.evidence_type == "overdue":
        params["calibration_status"] = "eq.overdue"
    elif req.evidence_type == "expiring_soon":
        params["calibration_status"] = "eq.expiring_soon"

    tools = sb_get("tools", params)

    records = [
        {
            "asset_tag": t.get("asset_tag", ""), "tool_type": t.get("tool_type", ""),
            "tool_name": t.get("tool_name", ""),
            "manufacturer": t.get("manufacturer", ""),
            "serial_number": t.get("serial_number", ""),
            "last_calibration_date": str(t["last_calibration_date"]) if t.get("last_calibration_date") else "",
            "next_due_date": str(t["next_due_date"]) if t.get("next_due_date") else "",
            "calibration_status": t.get("calibration_status", ""),
            "location": t.get("location", ""), "result": "",
        }
        for t in tools
    ]

    kernel = load_tenant_kernel(None, company_id)
    prompt = f"""Generate an audit evidence package summary for these calibration records.
Include:
- Executive summary of calibration program health
- Items requiring immediate attention (overdue or expiring)
- Recommendations organized by priority

Evidence type requested: {req.evidence_type}
Total records: {len(records)}

Records:
""" + "\n".join([
        f"- {r['asset_tag']} ({r['tool_type']}, {r['manufacturer']}): {r['tool_name']} | Cal {r['last_calibration_date']}, Due {r['next_due_date']}, Status: {r['calibration_status']}"
        for r in records
    ])

    agent_response = call_agent(kernel, prompt)

    if req.format == "pdf":
        branding = load_tenant_branding(company_id)
        pdf_bytes = generate_branded_pdf(branding, records, req.evidence_type, agent_response["text"])
        filename = f"cal_evidence_{req.evidence_type}_{datetime.utcnow().strftime('%Y%m%d')}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    return {
        "status": "success",
        "package_description": agent_response["text"],
        "record_count": len(records),
        "generated_at": datetime.utcnow().isoformat(),
    }

# ============================================================
# EQUIPMENT MANAGEMENT
# ============================================================

@app.get("/cal/equipment")
async def list_equipment(
    auth: dict = Depends(verify_token),
):
    company_id = auth["company_id"]

    tools = sb_get("tools", {
        "select": "id,asset_tag,tool_name,tool_type,calibration_method,calibrating_entity,cal_vendor_id,manufacturer,model,serial_number,location,building,cal_interval_days,notes,calibration_status,active,last_calibration_date,next_due_date",
        "company_id": f"eq.{company_id}",
        "order": "tool_type,asset_tag",
    })

    return {
        "equipment": [
            {
                "id": t["id"], "asset_tag": t.get("asset_tag", ""),
                "tool_name": t.get("tool_name", ""), "tool_type": t.get("tool_type", ""),
                "calibration_method": t.get("calibration_method", ""),
                "calibrating_entity": t.get("calibrating_entity", ""),
                "manufacturer": t.get("manufacturer", ""),
                "model": t.get("model", ""), "serial_number": t.get("serial_number", ""),
                "location": t.get("location", ""), "building": t.get("building", ""),
                "cal_interval_days": t.get("cal_interval_days"),
                "notes": t.get("notes", ""),
                "calibration_status": t.get("calibration_status", ""),
                "active": t.get("active", True),
                "last_cal_date": str(t["last_calibration_date"]) if t.get("last_calibration_date") else None,
                "next_due_date": str(t["next_due_date"]) if t.get("next_due_date") else None,
            }
            for t in tools
        ],
        "total": len(tools),
    }

@app.post("/cal/equipment")
async def add_equipment(
    eq: EquipmentCreate,
    auth: dict = Depends(verify_token),
):
    company_id = auth["company_id"]

    sb_post("tools", {
        "company_id": company_id,
        "asset_tag": eq.asset_tag,
        "tool_name": eq.tool_name,
        "tool_type": eq.tool_type,
        "calibration_method": eq.calibration_method,
        "calibrating_entity": eq.calibrating_entity,
        "manufacturer": eq.manufacturer,
        "model": eq.model,
        "serial_number": eq.serial_number,
        "location": eq.location,
        "building": eq.building,
        "cal_interval_days": eq.cal_interval_days,
        "notes": eq.notes,
        "active": True,
    })

    return {"status": "success", "message": f"Tool {eq.asset_tag} added."}

# ============================================================
# DASHBOARD DATA
# ============================================================

@app.get("/cal/dashboard")
async def dashboard(
    auth: dict = Depends(verify_token),
):
    company_id = auth["company_id"]

    # Get all tools for this company
    all_tools = sb_get("tools", {
        "select": "id,asset_tag,tool_name,tool_type,manufacturer,calibration_status,next_due_date",
        "company_id": f"eq.{company_id}",
        "order": "next_due_date.asc.nullslast",
    })

    tool_count = len(all_tools)

    # Count by status
    status_counts = {}
    for t in all_tools:
        s = t.get("calibration_status") or "unknown"
        status_counts[s] = status_counts.get(s, 0) + 1

    # Categorize by date
    from datetime import date
    today = date.today()
    upcoming = []
    overdue_list = []
    for t in all_tools:
        ndd = t.get("next_due_date")
        if not ndd:
            if t.get("calibration_status") == "overdue":
                overdue_list.append(t)
            continue
        try:
            due = date.fromisoformat(str(ndd)[:10])
            days_until = (due - today).days
        except (ValueError, TypeError):
            continue
        if days_until < 0 or t.get("calibration_status") == "overdue":
            overdue_list.append(t)
        elif days_until <= 60:
            upcoming.append(t)

    # Calibration count via RPC (needs a count query)
    try:
        cal_result = sb_rpc("execute_readonly_sql", {
            "query": f"SELECT COUNT(*) as cnt FROM cal.calibrations c JOIN cal.tools t ON c.tool_id = t.id WHERE t.company_id = :cid",
            "company_id": company_id,
        })
        cal_count = cal_result[0]["cnt"] if cal_result else 0
    except Exception:
        cal_count = 0

    return {
        "tool_count": tool_count,
        "calibration_count": cal_count,
        "status_summary": status_counts,
        "upcoming_expirations": [
            {"asset_tag": t.get("asset_tag", ""), "tool_type": t.get("tool_type", ""), "tool_name": t.get("tool_name", ""),
             "manufacturer": t.get("manufacturer", ""),
             "next_due_date": str(t["next_due_date"]), "status": t.get("calibration_status", "")}
            for t in upcoming
        ],
        "overdue": [
            {"asset_tag": t.get("asset_tag", ""), "tool_type": t.get("tool_type", ""), "tool_name": t.get("tool_name", ""),
             "manufacturer": t.get("manufacturer", ""),
             "next_due_date": str(t["next_due_date"]) if t.get("next_due_date") else None,
             "status": t.get("calibration_status", "")}
            for t in overdue_list
        ],
    }

# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "product": "cal.gp3.app",
        "version": "2.5.0",
        "timestamp": datetime.utcnow().isoformat(),
    }

# ============================================================
# AUTONOMOUS ENFORCEMENT — Scheduled Jobs
# ============================================================

MAILGUN_API_KEY = os.getenv("MAILGUN_API_KEY", "")
MAILGUN_DOMAIN = os.getenv("MAILGUN_DOMAIN", "gp3.app")
CAL_SERVICE_KEY = os.getenv("SECRET_KEY", "")  # reuse SECRET_KEY for cron auth

def _send_mailgun(sender: str, to: str, subject: str, body: str, cc: str = "") -> bool:
    """Send email via Mailgun. Returns True on success."""
    if not MAILGUN_API_KEY:
        logger.warning("MAILGUN_API_KEY not set — skipping email")
        return False
    data = {"from": sender, "to": to, "subject": subject, "html": body}
    if cc:
        data["cc"] = cc
    try:
        r = httpx.post(
            f"https://api.mailgun.net/v3/{MAILGUN_DOMAIN}/messages",
            auth=("api", MAILGUN_API_KEY),
            data=data,
            timeout=15,
        )
        return r.status_code == 200
    except Exception as e:
        logger.error(f"Mailgun send failed: {e}")
        return False

def _log_email(company_id: int, sender: str, to: str, subject: str, body: str, status: str):
    """Log outbound email to cal.email_log."""
    try:
        sb_post("email_log", {
            "company_id": company_id,
            "direction": "outbound",
            "from_address": sender,
            "to_address": to,
            "subject": subject,
            "body_text": body[:2000],
            "status": status,
        })
    except Exception:
        pass

def _build_tool_table_html(tools: list) -> str:
    """Build an HTML table of tools for email."""
    rows = ""
    for t in tools:
        ndd = t.get("next_due_date") or t.get("next_calibration_date") or "N/A"
        if isinstance(ndd, str) and len(ndd) > 10:
            ndd = ndd[:10]
        rows += f"<tr><td>{t.get('asset_tag','')}</td><td>{t.get('tool_name','')}</td><td>{t.get('tool_type','')}</td><td>{t.get('calibrating_entity','')}</td><td>{ndd}</td></tr>\n"
    return f"""<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;font-family:Helvetica,sans-serif;font-size:13px;">
<tr style="background:#003366;color:white;"><th>Asset Tag</th><th>Tool Name</th><th>Type</th><th>Calibrating Entity</th><th>Due Date</th></tr>
{rows}</table>"""

def refresh_statuses():
    """Recalculate calibration_status for all active tools across all companies."""
    companies = sb_get("companies", {"select": "id"})
    today = date.today()
    updated = 0
    for co in companies:
        cid = co["id"]
        tools = sb_get("tools", {
            "select": "id,next_due_date,calibration_status",
            "company_id": f"eq.{cid}",
            "active": "eq.true",
        })
        for t in tools:
            ndd = t.get("next_due_date")
            if not ndd:
                continue
            try:
                due = date.fromisoformat(str(ndd)[:10])
                days = (due - today).days
            except (ValueError, TypeError):
                continue
            if days < 0:
                new_status = "overdue"
            elif days <= 7:
                new_status = "critical"
            elif days <= 30:
                new_status = "expiring_soon"
            else:
                new_status = "current"
            if t.get("calibration_status") != new_status:
                sb_patch("tools", {"id": f"eq.{t['id']}"}, {"calibration_status": new_status})
                updated += 1
    logger.info(f"[CRON] refresh_statuses: updated {updated} tools")
    return updated

def enforcement_scan():
    """Scan all companies for overdue/expiring tools and send enforcement emails."""
    companies = sb_get("companies", {"select": "id,name,slug"})
    today = date.today()
    total_emails = 0

    for co in companies:
        cid, co_name, slug = co["id"], co["name"], co["slug"]
        sender = f"Cal - {co_name} <cal@{slug}.gp3.app>"

        # Load tenant kernel for routing config
        kernel_path = Path(f"/app/kernels/tenants/{slug}.ttc.md")
        if not kernel_path.exists():
            continue  # no kernel = not onboarded

        tools = sb_get("tools", {
            "select": "id,asset_tag,tool_name,tool_type,calibration_method,calibrating_entity,calibration_status,next_due_date",
            "company_id": f"eq.{cid}",
            "active": "eq.true",
            "order": "next_due_date.asc.nullslast",
        })

        overdue = []
        critical = []
        warning = []
        for t in tools:
            ndd = t.get("next_due_date")
            if not ndd:
                continue
            try:
                due = date.fromisoformat(str(ndd)[:10])
                days = (due - today).days
            except (ValueError, TypeError):
                continue
            if days < 0:
                overdue.append(t)
            elif days <= 7:
                critical.append(t)
            elif days <= 30:
                warning.append(t)

        # --- OVERDUE: Demand immediate removal from service ---
        if overdue:
            table_html = _build_tool_table_html(overdue)
            body = f"""<div style="font-family:Helvetica,sans-serif;">
<h2 style="color:#CC0000;">[ACTION REQUIRED] {len(overdue)} Overdue Calibrations</h2>
<p>The following tools have <strong>expired calibrations</strong> and must be <strong>removed from service immediately</strong> per ISO 9001 and company policy.</p>
{table_html}
<p style="margin-top:16px;"><strong>Required actions:</strong></p>
<ul>
<li>Remove all listed tools from service NOW</li>
<li>Tag with red "OUT OF CALIBRATION" labels</li>
<li>Schedule calibration with approved vendor immediately</li>
<li>Document removal in quality records</li>
</ul>
<p style="color:#666;font-size:11px;margin-top:24px;">— Cal | {co_name} Calibration Agent<br>This is an automated enforcement notice. Do not reply to this email.</p>
</div>"""
            # Bunting routing: overdue → Ryan + Brandon
            to = "rlinton@buntingmagnetics.com"
            cc = "bdick@buntingmagnetics.com"
            sent = _send_mailgun(sender, to, f"[ACTION REQUIRED] {len(overdue)} Overdue Calibrations — Remove From Service", body, cc)
            _log_email(cid, sender, to, f"[ACTION REQUIRED] {len(overdue)} Overdue Calibrations", body, "sent" if sent else "failed")
            if sent:
                total_emails += 1

        # --- CRITICAL: Due within 7 days ---
        if critical:
            table_html = _build_tool_table_html(critical)
            body = f"""<div style="font-family:Helvetica,sans-serif;">
<h2 style="color:#CC6600;">[URGENT] {len(critical)} Calibrations Due Within 7 Days</h2>
<p>The following tools require calibration within the next 7 days:</p>
{table_html}
<p><strong>Action:</strong> Schedule these calibrations immediately to avoid overdue status.</p>
<p style="color:#666;font-size:11px;margin-top:24px;">— Cal | {co_name} Calibration Agent</p>
</div>"""
            to = "bdick@buntingmagnetics.com"
            sent = _send_mailgun(sender, to, f"[URGENT] {len(critical)} Calibrations Due Within 7 Days", body)
            _log_email(cid, sender, to, f"[URGENT] {len(critical)} Calibrations Due Within 7 Days", body, "sent" if sent else "failed")
            if sent:
                total_emails += 1

        # --- WARNING: Due within 30 days ---
        if warning:
            table_html = _build_tool_table_html(warning)
            # Split vendor-calibrated tools for purchasing notification
            vendor_tools = [t for t in warning if t.get("calibration_method", "").lower().startswith("vendor")]
            body = f"""<div style="font-family:Helvetica,sans-serif;">
<h2 style="color:#003366;">[NOTICE] {len(warning)} Calibrations Due Within 30 Days</h2>
<p>Plan ahead — the following tools need calibration soon:</p>
{table_html}
<p style="color:#666;font-size:11px;margin-top:24px;">— Cal | {co_name} Calibration Agent</p>
</div>"""
            to = "dsanchez@buntingmagnetics.com"
            cc = "bdick@buntingmagnetics.com"
            sent = _send_mailgun(sender, to, f"[NOTICE] {len(warning)} Calibrations Due Within 30 Days", body, cc)
            _log_email(cid, sender, to, f"[NOTICE] {len(warning)} Calibrations Due Within 30 Days", body, "sent" if sent else "failed")
            if sent:
                total_emails += 1

            # --- PURCHASING: Vendor-calibrated tools need PO ---
            if vendor_tools:
                vendor_table = _build_tool_table_html(vendor_tools)
                po_body = f"""<div style="font-family:Helvetica,sans-serif;">
<h2 style="color:#003366;">[CAL REQUEST] {len(vendor_tools)} Tools Need Vendor Calibration</h2>
<p>The following vendor-calibrated tools are due within 30 days. Please initiate purchase orders with the listed calibrating entities:</p>
{vendor_table}
<p><strong>Contact the Quality Department for vendor details and shipping instructions.</strong></p>
<p style="color:#666;font-size:11px;margin-top:24px;">— Cal | {co_name} Calibration Agent</p>
</div>"""
                to = "purchasing@buntingmagnetics.com"
                cc = "bdick@buntingmagnetics.com"
                sent = _send_mailgun(sender, to, f"[CAL REQUEST] {len(vendor_tools)} Tools Need Vendor Calibration", po_body, cc)
                _log_email(cid, sender, to, f"[CAL REQUEST] {len(vendor_tools)} Vendor Calibrations", po_body, "sent" if sent else "failed")
                if sent:
                    total_emails += 1

    logger.info(f"[CRON] enforcement_scan: sent {total_emails} emails")
    return total_emails

def weekly_summary():
    """Send weekly compliance summary to quality managers."""
    companies = sb_get("companies", {"select": "id,name,slug"})
    today = date.today()
    total_emails = 0

    for co in companies:
        cid, co_name, slug = co["id"], co["name"], co["slug"]
        sender = f"Cal - {co_name} <cal@{slug}.gp3.app>"

        kernel_path = Path(f"/app/kernels/tenants/{slug}.ttc.md")
        if not kernel_path.exists():
            continue

        tools = sb_get("tools", {
            "select": "id,calibration_status,next_due_date,tool_type",
            "company_id": f"eq.{cid}",
            "active": "eq.true",
        })

        total = len(tools)
        counts = {"current": 0, "expiring_soon": 0, "critical": 0, "overdue": 0, "unknown": 0}
        for t in tools:
            s = t.get("calibration_status") or "unknown"
            counts[s] = counts.get(s, 0) + 1

        compliant = counts.get("current", 0)
        compliance_pct = round(compliant * 100.0 / max(total, 1), 1)

        # Type breakdown
        type_counts = {}
        for t in tools:
            tt = t.get("tool_type") or "Uncategorized"
            type_counts[tt] = type_counts.get(tt, 0) + 1
        type_rows = "".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in sorted(type_counts.items(), key=lambda x: -x[1]))

        body = f"""<div style="font-family:Helvetica,sans-serif;">
<h2 style="color:#003366;">Weekly Calibration Summary — {co_name}</h2>
<p><strong>Week of {today.isoformat()}</strong></p>

<table border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse;font-size:14px;margin:16px 0;">
<tr style="background:#003366;color:white;"><th>Metric</th><th>Value</th></tr>
<tr><td>Total Active Tools</td><td><strong>{total}</strong></td></tr>
<tr><td>Current (Compliant)</td><td style="color:green;"><strong>{counts['current']}</strong></td></tr>
<tr><td>Expiring Soon (≤30d)</td><td style="color:orange;">{counts['expiring_soon']}</td></tr>
<tr><td>Critical (≤7d)</td><td style="color:red;">{counts['critical']}</td></tr>
<tr><td>Overdue</td><td style="color:red;font-weight:bold;">{counts['overdue']}</td></tr>
<tr><td>Unknown / No Date</td><td>{counts['unknown']}</td></tr>
<tr style="background:#f0f0f0;"><td><strong>Compliance Rate</strong></td><td><strong>{compliance_pct}%</strong></td></tr>
</table>

<h3>Equipment by Type</h3>
<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;font-size:13px;">
<tr style="background:#003366;color:white;"><th>Type</th><th>Count</th></tr>
{type_rows}
</table>

<p style="color:#666;font-size:11px;margin-top:24px;">— Cal | {co_name} Calibration Agent<br>{co_name} Quality Department</p>
</div>"""
        to = "rlinton@buntingmagnetics.com"
        cc = "bdick@buntingmagnetics.com"
        sent = _send_mailgun(sender, to, f"Weekly Calibration Summary — {compliance_pct}% Compliant", body, cc)
        _log_email(cid, sender, to, f"Weekly Calibration Summary", body, "sent" if sent else "failed")
        if sent:
            total_emails += 1

    logger.info(f"[CRON] weekly_summary: sent {total_emails} emails")
    return total_emails

# --- Scheduler setup ---
from apscheduler.schedulers.background import BackgroundScheduler
from contextlib import asynccontextmanager

scheduler = BackgroundScheduler(timezone="America/Chicago")

@asynccontextmanager
async def lifespan(app):
    # Startup: schedule autonomous jobs
    scheduler.add_job(refresh_statuses, "cron", hour=5, minute=0, id="refresh_statuses", replace_existing=True)
    scheduler.add_job(enforcement_scan, "cron", hour=6, minute=0, id="enforcement_scan", replace_existing=True)
    scheduler.add_job(weekly_summary, "cron", day_of_week="mon", hour=7, minute=0, id="weekly_summary", replace_existing=True)
    scheduler.start()
    logger.info("[SCHEDULER] Started — refresh@05:00, enforce@06:00, summary@Mon07:00 CT")
    yield
    # Shutdown
    scheduler.shutdown(wait=False)

app.router.lifespan_context = lifespan

# --- Manual trigger endpoint (service-key auth) ---
@app.post("/api/cron/daily")
async def cron_daily(req: dict = {}):
    """Manual trigger for daily enforcement. Auth via service key in body."""
    key = req.get("service_key", "")
    if key != CAL_SERVICE_KEY:
        raise HTTPException(status_code=403, detail="Invalid service key")

    statuses_updated = refresh_statuses()
    emails_sent = enforcement_scan()
    return {
        "status": "completed",
        "statuses_updated": statuses_updated,
        "emails_sent": emails_sent,
        "timestamp": datetime.utcnow().isoformat(),
    }

@app.post("/api/cron/weekly")
async def cron_weekly(req: dict = {}):
    """Manual trigger for weekly summary. Auth via service key in body."""
    key = req.get("service_key", "")
    if key != CAL_SERVICE_KEY:
        raise HTTPException(status_code=403, detail="Invalid service key")

    emails_sent = weekly_summary()
    return {"status": "completed", "emails_sent": emails_sent}

# ============================================================
# TTS PROXY (ElevenLabs)
# ============================================================

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

class TTSRequest(BaseModel):
    text: str
    voice_id: str = "EXAVITQu4vr4xnSDxMaL"

@app.post("/api/tts")
async def text_to_speech(req: TTSRequest):
    from fastapi.responses import Response
    import httpx

    if not ELEVENLABS_API_KEY:
        raise HTTPException(status_code=503, detail="TTS not configured")

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{req.voice_id}/stream",
            headers={"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"},
            json={
                "text": req.text,
                "model_id": "eleven_turbo_v2_5",
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
            },
            timeout=30.0,
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail="TTS service error")
        return Response(content=resp.content, media_type="audio/mpeg")

# ============================================================
# WEBSOCKET — AGENT PROACTIVE EVENTS
# ============================================================

from fastapi import WebSocket, WebSocketDisconnect

# In-memory connection registry
_ws_connections: dict[str, list[WebSocket]] = {}

@app.websocket("/ws/agent-events")
async def agent_events(ws: WebSocket, agent_id: str = "cal"):
    await ws.accept()
    _ws_connections.setdefault(agent_id, []).append(ws)
    try:
        while True:
            await ws.receive_text()  # Keep-alive, client can send pings
    except WebSocketDisconnect:
        _ws_connections[agent_id].remove(ws)

async def push_agent_event(agent_id: str, event: dict):
    """Push a proactive event to all connected clients for an agent."""
    for ws in _ws_connections.get(agent_id, []):
        try:
            await ws.send_text(json.dumps(event))
        except Exception:
            pass

@app.post("/api/proactive/check")
async def check_proactive(
    auth: dict = Depends(verify_token),
):
    """Check for conditions that should trigger avatar walk-up."""
    company_id = auth["company_id"]

    overdue_tools = sb_get("tools", {
        "select": "asset_tag,tool_type,tool_name,next_due_date",
        "company_id": f"eq.{company_id}",
        "calibration_status": "eq.overdue",
        "order": "next_due_date.asc",
        "limit": "5",
    })
    overdue = overdue_tools

    alerts_sent = 0
    if overdue:
        tool_list = ", ".join([f"{r.get('asset_tag','')} ({r.get('tool_type','')})" for r in overdue[:3]])
        message = (
            f"Hey, I need your attention. We have {len(overdue)} overdue calibrations. "
            f"The most urgent ones are: {tool_list}. "
            f"Can you collect these and get them ready for calibration?"
        )
        await push_agent_event("calibration", {
            "type": "attention_needed",
            "agent_id": "calibration",
            "message": message,
            "priority": "high",
        })
        alerts_sent = 1

    return {"checked": True, "overdue_count": len(overdue), "alerts_sent": alerts_sent}

# ============================================================
# EMAIL INGESTION — cal@{tenant}.gp3.app
# ============================================================

# Webhook secret for email provider (Cloudflare/Mailgun)
EMAIL_WEBHOOK_SECRET = os.getenv("EMAIL_WEBHOOK_SECRET", "")

class EmailWebhook(BaseModel):
    """Generic inbound email webhook payload.
    Works with Cloudflare Email Workers, Mailgun, SendGrid.
    The email worker normalizes the provider format to this shape.
    """
    from_address: str
    to_address: str
    cc: str = ""
    subject: str = ""
    body_text: str = ""
    body_html: str = ""
    message_id: str = ""
    in_reply_to: str = ""
    attachments: list[dict] = []  # [{filename, content_type, size, url_or_base64}]
    webhook_secret: str = ""

def extract_tenant_from_email(to_address: str) -> str | None:
    """Extract tenant slug from cal@{slug}.gp3.app format."""
    match = re.match(r'cal@([^.]+)\.gp3\.app', to_address.lower().strip())
    return match.group(1) if match else None

@app.post("/api/email/ingest")
async def ingest_email(payload: EmailWebhook):
    """Receive inbound email for Cal agent.
    Called by email webhook (Cloudflare Email Workers / Mailgun).
    No JWT auth — secured by webhook secret.
    """
    # Verify webhook secret
    if EMAIL_WEBHOOK_SECRET and payload.webhook_secret != EMAIL_WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    # Extract tenant from recipient address
    tenant_slug = extract_tenant_from_email(payload.to_address)
    if not tenant_slug:
        return {"status": "ignored", "reason": f"Unrecognized recipient: {payload.to_address}"}

    # Look up company via REST
    companies = sb_get("companies", {"select": "id", "slug": f"eq.{tenant_slug}", "is_active": "eq.true"})
    if not companies:
        return {"status": "ignored", "reason": f"Unknown tenant: {tenant_slug}"}

    company_id = companies[0]["id"]

    # Dedup check by Message-ID via REST
    if payload.message_id:
        existing = sb_get("email_log", {"select": "id", "message_id": f"eq.{payload.message_id}"})
        if existing:
            return {"status": "duplicate", "email_log_id": existing[0]["id"]}

    # Log the email via REST
    email_record = sb_post("email_log", {
        "company_id": company_id,
        "direction": "inbound",
        "from_address": payload.from_address,
        "to_address": payload.to_address,
        "cc_addresses": payload.cc,
        "subject": payload.subject,
        "body_text": payload.body_text,
        "body_html": payload.body_html,
        "has_attachments": len(payload.attachments) > 0,
        "attachment_count": len(payload.attachments),
        "message_id": payload.message_id or None,
        "in_reply_to": payload.in_reply_to or None,
        "status": "received",
    })
    email_log_id = email_record.get("id") if email_record else None

    # --- CLASSIFY AND PROCESS ---
    context = f"""Inbound email to calibration agent:
From: {payload.from_address}
Subject: {payload.subject}
Body: {payload.body_text[:2000]}
Attachments: {len(payload.attachments)} files ({', '.join(a.get('filename','?') for a in payload.attachments)})
"""

    classification_prompt = """Classify this email into one of these categories:
1. CERTIFICATE — Contains a calibration certificate (PDF/image attachment)
2. PO_NOTIFICATION — Purchase order or shipping notification for calibration services
3. STATUS_UPDATE — Status update on equipment sent for calibration
4. QUESTION — Someone asking a calibration-related question
5. OTHER — Unrelated or spam

Return ONLY a JSON object: {"category": "CATEGORY", "summary": "1-sentence summary", "tool_numbers": ["CAL-XXXX"] or [], "action": "suggested next action"}"""

    try:
        kernel = load_tenant_kernel(None, company_id)
        classification = call_agent(kernel, classification_prompt, context)
        result_data = json.loads(classification["text"]) if classification["text"].strip().startswith("{") else {"category": "OTHER", "summary": classification["text"][:200]}
    except Exception:
        result_data = {"category": "OTHER", "summary": "Could not classify", "error": True}

    # Update email log with classification via REST
    if email_log_id:
        sb_patch("email_log", {"id": f"eq.{email_log_id}"}, {
            "status": "processed",
            "processing_result": json.dumps(result_data),
        })

    # --- ACT ON CLASSIFICATION ---
    actions_taken = []

    if result_data.get("category") == "CERTIFICATE" and payload.attachments:
        # Process PDF attachments as calibration certificates
        for att in payload.attachments:
            if att.get("content_type", "").startswith(("application/pdf", "image/")):
                actions_taken.append(f"Certificate attachment '{att.get('filename')}' queued for processing")
                # TODO: decode base64 attachment, run through existing upload/extraction flow

    elif result_data.get("category") == "PO_NOTIFICATION":
        actions_taken.append("PO notification logged — Cal will track expected return")

    elif result_data.get("category") == "STATUS_UPDATE":
        actions_taken.append("Status update logged — Cal will update equipment records")

    # Push proactive event to avatar if user is connected
    if actions_taken:
        summary = result_data.get("summary", "New email processed")
        await push_agent_event("calibration", {
            "type": "attention_needed",
            "agent_id": "calibration",
            "message": f"I just received an email from {payload.from_address}. {summary}",
            "priority": "medium",
        })

    return {
        "status": "processed",
        "email_log_id": email_log_id,
        "classification": result_data,
        "actions": actions_taken,
    }

@app.post("/api/email/send")
async def send_email(
    req: dict,
    auth: dict = Depends(verify_token),
):
    """Cal sends an outbound email from cal@{tenant}.gp3.app.
    Uses Mailgun or SMTP relay configured via env vars.
    """
    import httpx

    company_id = auth["company_id"]

    # Get company slug for sender address via REST
    companies = sb_get("companies", {"select": "slug,name", "id": f"eq.{company_id}"})
    if not companies:
        raise HTTPException(status_code=404, detail="Company not found")

    slug, company_name = companies[0]["slug"], companies[0]["name"]
    sender = f"Cal - {company_name} <cal@{slug}.gp3.app>"
    to_address = req.get("to", "")
    subject = req.get("subject", "")
    body = req.get("body", "")
    cc = req.get("cc", "")

    if not to_address or not subject:
        raise HTTPException(status_code=400, detail="to and subject are required")

    # Send via Mailgun HTTP API
    mailgun_key = os.getenv("MAILGUN_API_KEY")
    mailgun_domain = os.getenv("MAILGUN_DOMAIN", "gp3.app")

    if not mailgun_key:
        raise HTTPException(status_code=503, detail="Email sending not configured")

    async with httpx.AsyncClient() as client:
        data = {
            "from": sender,
            "to": to_address,
            "subject": subject,
            "text": body,
        }
        if cc:
            data["cc"] = cc

        resp = await client.post(
            f"https://api.mailgun.net/v3/{mailgun_domain}/messages",
            auth=("api", mailgun_key),
            data=data,
            timeout=15.0,
        )

    # Log the outbound email via REST
    try:
        sb_post("email_log", {
            "company_id": company_id,
            "direction": "outbound",
            "from_address": sender,
            "to_address": to_address,
            "cc_addresses": cc,
            "subject": subject,
            "body_text": body,
            "status": "sent" if resp.status_code == 200 else "failed",
            "message_id": resp.json().get("id", "") if resp.status_code == 200 else None,
        })
    except Exception:
        pass

    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Email send failed: {resp.text}")

    return {"status": "sent", "to": to_address, "subject": subject}

@app.get("/api/email/log")
async def get_email_log(
    auth: dict = Depends(verify_token),
    limit: int = 50,
):
    """List recent emails for the tenant."""
    company_id = auth["company_id"]
    emails = sb_get("email_log", {
        "select": "id,direction,from_address,to_address,subject,status,processing_result,has_attachments,received_at,processed_at",
        "company_id": f"eq.{company_id}",
        "order": "received_at.desc",
        "limit": str(limit),
    })

    return {
        "emails": [
            {
                "id": e["id"], "direction": e.get("direction", ""),
                "from": e.get("from_address", ""), "to": e.get("to_address", ""),
                "subject": e.get("subject", ""), "status": e.get("status", ""),
                "classification": e.get("processing_result", ""),
                "has_attachments": e.get("has_attachments", False),
                "received_at": str(e["received_at"]) if e.get("received_at") else None,
                "processed_at": str(e["processed_at"]) if e.get("processed_at") else None,
            }
            for e in emails
        ],
    }
