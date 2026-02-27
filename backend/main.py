from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from anthropic import Anthropic
from pydantic import BaseModel
from passlib.context import CryptContext
from jose import jwt, JWTError
from datetime import datetime, timedelta
from pathlib import Path
import os
import re
import io
import uuid
import json

# ============================================================
# APP SETUP
# ============================================================

app = FastAPI(
    title="cal.gp3.app - Calibration Agent",
    description="Multi-tenant calibration management powered by AI",
    version="2.0.0",
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

DATABASE_URL = os.getenv("DATABASE_URL")  # Supabase direct connection string
SECRET_KEY = os.getenv("SECRET_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ENVIRONMENT = os.getenv("ENVIRONMENT", "production")
ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 7

engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=10)
SessionLocal = sessionmaker(bind=engine)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()
anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)

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
    number: str
    type: str = ""
    description: str = ""
    manufacturer: str = ""
    model: str = ""
    serial_number: str = ""
    location: str = ""
    building: str = ""
    frequency: str = "annual"
    ownership: str = ""

# ============================================================
# DEPENDENCIES
# ============================================================

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

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

def load_tenant_kernel(db: Session, company_id: int) -> str:
    """Load two-layer kernel: agent kernel (shared) + tenant kernel (per-customer)."""

    # Layer 1: Agent kernel
    agent_kernel_path = Path("/app/kernels/calibrations_v1.0.ttc.md")
    if agent_kernel_path.exists():
        agent_kernel = agent_kernel_path.read_text()
    else:
        agent_kernel = "You are a calibration management assistant. Help users manage equipment calibration schedules, upload certificates, and generate audit evidence."

    # Get company info
    result = db.execute(text(
        "SELECT name, slug FROM cal.companies WHERE id = :cid"
    ), {"cid": company_id})
    company = result.fetchone()
    company_name = company[0] if company else "Unknown"
    company_slug = company[1] if company else "unknown"

    # Get equipment registry
    result = db.execute(text("""
        SELECT number, type, frequency, ownership, description
        FROM cal.tools WHERE company_id = :cid ORDER BY type, number
    """), {"cid": company_id})
    equipment = result.fetchall()

    equipment_list = "\n".join([
        f"  {eq[0]}: type={eq[1]} | freq={eq[2]} | owner={eq[3]} | {eq[4] or ''}"
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

def load_tenant_branding(db: Session, company_id: int) -> dict:
    """Parse branding block from tenant kernel."""
    result = db.execute(text(
        "SELECT slug, name FROM cal.companies WHERE id = :cid"
    ), {"cid": company_id})
    company = result.fetchone()
    if not company:
        return {"company_name": "Unknown", "slug": "unknown"}

    slug = company[0]
    company_name = company[1]

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
        header = ["Tool #", "Type", "Manufacturer", "Cal Date", "Next Due", "Status", "Result"]
        table_data = [header]
        for r in records:
            status_display = str(r.get("calibration_status") or "").replace("_", " ").title()
            table_data.append([
                str(r.get("number", "")), str(r.get("type", "")),
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
async def login(req: LoginRequest, db: Session = Depends(get_db)):
    result = db.execute(text("""
        SELECT u.id, u.password_hash, u.company_id, u.role, c.name
        FROM cal.users u JOIN cal.companies c ON u.company_id = c.id
        WHERE u.email = :email AND u.is_active = true
    """), {"email": req.email})
    user = result.fetchone()

    if not user or not pwd_context.verify(req.password, user[1]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Update last login
    db.execute(text("UPDATE cal.users SET last_login_at = NOW() WHERE id = :uid"), {"uid": user[0]})
    db.commit()

    token = jwt.encode({
        "user_id": user[0],
        "company_id": user[2],
        "role": user[3],
        "exp": datetime.utcnow() + timedelta(days=TOKEN_EXPIRE_DAYS),
    }, SECRET_KEY, algorithm=ALGORITHM)

    return {
        "token": token,
        "company_name": user[4],
        "role": user[3],
    }

@app.post("/auth/register")
async def register(req: RegisterRequest, db: Session = Depends(get_db)):
    # Look up company by slug
    result = db.execute(text(
        "SELECT id FROM cal.companies WHERE slug = :slug AND is_active = true"
    ), {"slug": req.company_code})
    company = result.fetchone()
    if not company:
        raise HTTPException(status_code=404, detail="Invalid registration code")

    # Check email not taken
    result = db.execute(text("SELECT id FROM cal.users WHERE email = :email"), {"email": req.email})
    if result.fetchone():
        raise HTTPException(status_code=409, detail="Email already registered")

    password_hash = pwd_context.hash(req.password)
    db.execute(text("""
        INSERT INTO cal.users (id, company_id, email, password_hash, first_name, last_name, role)
        VALUES (nextval('cal.users_id_seq'), :cid, :email, :hash, :fname, :lname, 'user')
    """), {
        "cid": company[0], "email": req.email, "hash": password_hash,
        "fname": req.first_name, "lname": req.last_name,
    })
    db.commit()

    return {"status": "success", "message": "User created. Please login."}

# ============================================================
# CALIBRATION AGENT ENDPOINTS
# ============================================================

@app.post("/cal/upload")
async def upload_cert(
    file: UploadFile = File(...),
    auth: dict = Depends(verify_token),
    db: Session = Depends(get_db),
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
    kernel = load_tenant_kernel(db, company_id)
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

    # Look up tool
    result = db.execute(text("""
        SELECT id FROM cal.tools
        WHERE company_id = :cid AND number = :num
    """), {"cid": company_id, "num": data.get("tool_number", "")})
    tool = result.fetchone()

    if not tool:
        return {
            "status": "warning",
            "message": f"Tool '{data.get('tool_number')}' not found in registry. Please add it first.",
            "extracted_data": data,
        }

    # Insert calibration record
    db.execute(text("""
        INSERT INTO cal.calibrations
        (id, record_number, tool_id, calibration_date, result, next_due_date, technician, comments)
        VALUES (nextval('cal.calibrations_id_seq'), :rnum, :tid, :cal_date, :result, :next_due, :tech, :comments)
    """), {
        "rnum": f"CAL-{datetime.utcnow().strftime('%Y%m%d')}-{tool[0]}",
        "tid": tool[0],
        "cal_date": data.get("calibration_date"),
        "result": data.get("result", "pass"),
        "next_due": data.get("next_due_date"),
        "tech": data.get("technician", ""),
        "comments": data.get("comments", ""),
    })

    # Insert attachment record
    db.execute(text("""
        INSERT INTO cal.attachments
        (id, tool_id, calibration_id, filename, original_name, file_size, mime_type)
        VALUES (nextval('cal.attachments_id_seq'), :tid,
                currval('cal.calibrations_id_seq'), :fname, :oname, :fsize, :mime)
    """), {
        "tid": tool[0],
        "fname": f"{file_id}_{file.filename}",
        "oname": file.filename,
        "fsize": len(content),
        "mime": file.content_type or "application/octet-stream",
    })

    # Update tool's last calibration date
    db.execute(text("""
        UPDATE cal.tools
        SET last_calibration_date = :cal_date,
            next_due_date = :next_due,
            calibration_status = 'current'
        WHERE id = :tid
    """), {
        "cal_date": data.get("calibration_date"),
        "next_due": data.get("next_due_date"),
        "tid": tool[0],
    })

    db.commit()

    return {
        "status": "success",
        "message": f"Calibration cert for {data['tool_number']} processed. Next due {data.get('next_due_date', 'unknown')}.",
        "data": data,
    }

@app.post("/cal/question")
async def ask_question(
    req: QuestionRequest,
    auth: dict = Depends(verify_token),
    db: Session = Depends(get_db),
):
    company_id = auth["company_id"]

    # Build context from calibration data
    result = db.execute(text("""
        SELECT t.number, t.type, t.manufacturer,
               c.calibration_date, c.next_due_date, c.technician,
               t.calibration_status, c.result, c.comments
        FROM cal.calibrations c
        JOIN cal.tools t ON c.tool_id = t.id
        WHERE t.company_id = :cid
        ORDER BY c.next_due_date ASC
    """), {"cid": company_id})
    cal_data = result.fetchall()

    context = "Current calibration records:\n" + "\n".join([
        f"- {r[0]} ({r[1]}, mfr={r[2]}): Cal {r[3]}, Due {r[4]}, Tech: {r[5]}, Status: {r[6]}, Result: {r[7]}"
        for r in cal_data
    ]) if cal_data else "No calibration records on file yet."

    # Get equipment summary
    result = db.execute(text("""
        SELECT COUNT(*),
               COUNT(CASE WHEN calibration_status = 'overdue' THEN 1 END),
               COUNT(CASE WHEN calibration_status = 'current' THEN 1 END)
        FROM cal.tools WHERE company_id = :cid
    """), {"cid": company_id})
    eq_counts = result.fetchone()
    context += f"\n\nEquipment summary: {eq_counts[0]} total, {eq_counts[2]} current, {eq_counts[1]} overdue."

    kernel = load_tenant_kernel(db, company_id)
    agent_response = call_agent(kernel, req.question, context)
    db.commit()

    return {"status": "success", "answer": agent_response["text"]}

@app.post("/cal/upload-logo")
async def upload_logo(
    file: UploadFile = File(...),
    auth: dict = Depends(verify_token),
    db: Session = Depends(get_db),
):
    """Upload tenant logo for branded reports."""
    if auth["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin only")

    result = db.execute(text(
        "SELECT slug FROM cal.companies WHERE id = :cid"
    ), {"cid": auth["company_id"]})
    company = result.fetchone()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    slug = company[0]
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
    db: Session = Depends(get_db),
):
    from fastapi.responses import Response
    company_id = auth["company_id"]

    # Build query based on evidence type
    where_extra = ""
    if req.evidence_type == "overdue":
        where_extra = "AND t.calibration_status = 'overdue'"
    elif req.evidence_type == "expiring_soon":
        where_extra = "AND t.calibration_status = 'expiring_soon'"

    result = db.execute(text(f"""
        SELECT t.number, t.type, t.manufacturer, t.serial_number,
               t.last_calibration_date, t.next_due_date, t.calibration_status,
               t.location, c.result
        FROM cal.tools t
        LEFT JOIN LATERAL (
            SELECT result FROM cal.calibrations
            WHERE tool_id = t.id ORDER BY calibration_date DESC LIMIT 1
        ) c ON true
        WHERE t.company_id = :cid {where_extra}
        ORDER BY t.type, t.number
    """), {"cid": company_id})
    rows = result.fetchall()

    records = [
        {
            "number": r[0], "type": r[1], "manufacturer": r[2],
            "serial_number": r[3], "last_calibration_date": str(r[4]) if r[4] else "",
            "next_due_date": str(r[5]) if r[5] else "", "calibration_status": r[6] or "",
            "location": r[7] or "", "result": r[8] or "",
        }
        for r in rows
    ]

    kernel = load_tenant_kernel(db, company_id)
    prompt = f"""Generate an audit evidence package summary for these calibration records.
Include:
- Executive summary of calibration program health
- Items requiring immediate attention (overdue or expiring)
- Recommendations organized by priority

Evidence type requested: {req.evidence_type}
Total records: {len(records)}

Records:
""" + "\n".join([
        f"- {r['number']} ({r['type']}, {r['manufacturer']}): Cal {r['last_calibration_date']}, Due {r['next_due_date']}, Status: {r['calibration_status']}, Result: {r['result']}"
        for r in records
    ])

    agent_response = call_agent(kernel, prompt)
    db.commit()

    if req.format == "pdf":
        branding = load_tenant_branding(db, company_id)
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
    db: Session = Depends(get_db),
):
    company_id = auth["company_id"]

    result = db.execute(text("""
        SELECT t.id, t.number, t.type, t.description, t.manufacturer,
               t.model, t.serial_number, t.location, t.building,
               t.frequency, t.ownership, t.calibration_status, t.tool_status,
               t.last_calibration_date, t.next_due_date
        FROM cal.tools t
        WHERE t.company_id = :cid
        ORDER BY t.type, t.number
    """), {"cid": company_id})

    rows = result.fetchall()
    return {
        "equipment": [
            {
                "id": r[0], "number": r[1], "type": r[2],
                "description": r[3], "manufacturer": r[4], "model": r[5],
                "serial_number": r[6], "location": r[7], "building": r[8],
                "frequency": r[9], "ownership": r[10],
                "calibration_status": r[11], "tool_status": r[12],
                "last_cal_date": str(r[13]) if r[13] else None,
                "next_due_date": str(r[14]) if r[14] else None,
            }
            for r in rows
        ],
        "total": len(rows),
    }

@app.post("/cal/equipment")
async def add_equipment(
    eq: EquipmentCreate,
    auth: dict = Depends(verify_token),
    db: Session = Depends(get_db),
):
    company_id = auth["company_id"]

    db.execute(text("""
        INSERT INTO cal.tools
        (id, company_id, number, type, description, manufacturer,
         model, serial_number, location, building, frequency, ownership)
        VALUES (nextval('cal.tools_id_seq'), :cid, :num, :type, :desc, :mfr,
                :model, :sn, :loc, :bldg, :freq, :own)
    """), {
        "cid": company_id, "num": eq.number, "type": eq.type,
        "desc": eq.description, "mfr": eq.manufacturer, "model": eq.model,
        "sn": eq.serial_number, "loc": eq.location, "bldg": eq.building,
        "freq": eq.frequency, "own": eq.ownership,
    })
    db.commit()

    return {"status": "success", "message": f"Tool {eq.number} added."}

# ============================================================
# DASHBOARD DATA
# ============================================================

@app.get("/cal/dashboard")
async def dashboard(
    auth: dict = Depends(verify_token),
    db: Session = Depends(get_db),
):
    company_id = auth["company_id"]

    tool_count = db.execute(text(
        "SELECT COUNT(*) FROM cal.tools WHERE company_id = :cid"
    ), {"cid": company_id}).scalar()

    status_counts = db.execute(text("""
        SELECT calibration_status, COUNT(*) FROM cal.tools
        WHERE company_id = :cid GROUP BY calibration_status
    """), {"cid": company_id}).fetchall()

    cal_count = db.execute(text("""
        SELECT COUNT(*) FROM cal.calibrations c
        JOIN cal.tools t ON c.tool_id = t.id
        WHERE t.company_id = :cid
    """), {"cid": company_id}).scalar()

    upcoming = db.execute(text("""
        SELECT t.number, t.type, t.manufacturer,
               t.next_due_date, t.calibration_status
        FROM cal.tools t
        WHERE t.company_id = :cid
          AND t.next_due_date <= CURRENT_DATE + INTERVAL '60 days'
          AND t.next_due_date >= CURRENT_DATE
        ORDER BY t.next_due_date ASC
    """), {"cid": company_id}).fetchall()

    overdue = db.execute(text("""
        SELECT t.number, t.type, t.manufacturer,
               t.next_due_date, t.calibration_status
        FROM cal.tools t
        WHERE t.company_id = :cid
          AND (t.calibration_status = 'overdue'
               OR (t.next_due_date IS NOT NULL AND t.next_due_date < CURRENT_DATE))
        ORDER BY t.next_due_date ASC
    """), {"cid": company_id}).fetchall()

    return {
        "tool_count": tool_count,
        "calibration_count": cal_count,
        "status_summary": {r[0]: r[1] for r in status_counts if r[0]},
        "upcoming_expirations": [
            {"number": r[0], "type": r[1], "manufacturer": r[2],
             "next_due_date": str(r[3]), "status": r[4]}
            for r in upcoming
        ],
        "overdue": [
            {"number": r[0], "type": r[1], "manufacturer": r[2],
             "next_due_date": str(r[3]) if r[3] else None, "status": r[4]}
            for r in overdue
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
        "version": "2.1.0",
        "timestamp": datetime.utcnow().isoformat(),
    }

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
    db: Session = Depends(get_db),
):
    """Check for conditions that should trigger avatar walk-up."""
    company_id = auth["company_id"]

    result = db.execute(text("""
        SELECT t.number, t.type, t.next_due_date
        FROM cal.tools t
        WHERE t.company_id = :cid
          AND (t.calibration_status = 'overdue'
               OR (t.next_due_date IS NOT NULL AND t.next_due_date < CURRENT_DATE))
        ORDER BY t.next_due_date ASC LIMIT 5
    """), {"cid": company_id})
    overdue = result.fetchall()

    alerts_sent = 0
    if overdue:
        tool_list = ", ".join([f"{r[0]} ({r[1]})" for r in overdue[:3]])
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
async def ingest_email(payload: EmailWebhook, db: Session = Depends(get_db)):
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

    # Look up company
    result = db.execute(text(
        "SELECT id FROM cal.companies WHERE slug = :slug AND is_active = true"
    ), {"slug": tenant_slug})
    company = result.fetchone()
    if not company:
        return {"status": "ignored", "reason": f"Unknown tenant: {tenant_slug}"}

    company_id = company[0]

    # Dedup check by Message-ID
    if payload.message_id:
        existing = db.execute(text(
            "SELECT id FROM cal.email_log WHERE message_id = :mid"
        ), {"mid": payload.message_id}).fetchone()
        if existing:
            return {"status": "duplicate", "email_log_id": existing[0]}

    # Log the email
    db.execute(text("""
        INSERT INTO cal.email_log
        (company_id, direction, from_address, to_address, cc_addresses,
         subject, body_text, body_html, has_attachments, attachment_count,
         message_id, in_reply_to, status)
        VALUES (:cid, 'inbound', :from_addr, :to_addr, :cc,
                :subject, :body_text, :body_html, :has_att, :att_count,
                :mid, :irt, 'received')
    """), {
        "cid": company_id,
        "from_addr": payload.from_address,
        "to_addr": payload.to_address,
        "cc": payload.cc,
        "subject": payload.subject,
        "body_text": payload.body_text,
        "body_html": payload.body_html,
        "has_att": len(payload.attachments) > 0,
        "att_count": len(payload.attachments),
        "mid": payload.message_id or None,
        "irt": payload.in_reply_to or None,
    })
    db.commit()

    # Get the email_log ID
    log_id = db.execute(text(
        "SELECT id FROM cal.email_log WHERE message_id = :mid ORDER BY id DESC LIMIT 1"
    ), {"mid": payload.message_id or f"noid-{datetime.utcnow().isoformat()}"}).fetchone()
    email_log_id = log_id[0] if log_id else None

    # --- CLASSIFY AND PROCESS ---
    # Use Claude to understand what this email is about
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
        kernel = load_tenant_kernel(db, company_id)
        classification = call_agent(kernel, classification_prompt, context)
        result_data = json.loads(classification["text"]) if classification["text"].strip().startswith("{") else {"category": "OTHER", "summary": classification["text"][:200]}
    except Exception:
        result_data = {"category": "OTHER", "summary": "Could not classify", "error": True}

    # Update email log with classification
    db.execute(text("""
        UPDATE cal.email_log
        SET status = 'processed', processing_result = :result, processed_at = NOW()
        WHERE id = :eid
    """), {"result": json.dumps(result_data), "eid": email_log_id})
    db.commit()

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
    db: Session = Depends(get_db),
):
    """Cal sends an outbound email from cal@{tenant}.gp3.app.
    Uses Mailgun or SMTP relay configured via env vars.
    """
    import httpx

    company_id = auth["company_id"]

    # Get company slug for sender address
    result = db.execute(text(
        "SELECT slug, name FROM cal.companies WHERE id = :cid"
    ), {"cid": company_id})
    company = result.fetchone()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    slug, company_name = company[0], company[1]
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

    # Log the outbound email
    db.execute(text("""
        INSERT INTO cal.email_log
        (company_id, direction, from_address, to_address, cc_addresses,
         subject, body_text, status, message_id)
        VALUES (:cid, 'outbound', :from_addr, :to_addr, :cc,
                :subject, :body, :status, :mid)
    """), {
        "cid": company_id,
        "from_addr": sender,
        "to_addr": to_address,
        "cc": cc,
        "subject": subject,
        "body": body,
        "status": "sent" if resp.status_code == 200 else "failed",
        "mid": resp.json().get("id", "") if resp.status_code == 200 else None,
    })
    db.commit()

    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Email send failed: {resp.text}")

    return {"status": "sent", "to": to_address, "subject": subject}

@app.get("/api/email/log")
async def get_email_log(
    auth: dict = Depends(verify_token),
    db: Session = Depends(get_db),
    limit: int = 50,
):
    """List recent emails for the tenant."""
    company_id = auth["company_id"]
    result = db.execute(text("""
        SELECT id, direction, from_address, to_address, subject,
               status, processing_result, has_attachments,
               received_at, processed_at
        FROM cal.email_log
        WHERE company_id = :cid
        ORDER BY received_at DESC
        LIMIT :lim
    """), {"cid": company_id, "lim": limit})

    return {
        "emails": [
            {
                "id": r[0], "direction": r[1], "from": r[2], "to": r[3],
                "subject": r[4], "status": r[5],
                "classification": r[6], "has_attachments": r[7],
                "received_at": str(r[8]) if r[8] else None,
                "processed_at": str(r[9]) if r[9] else None,
            }
            for r in result.fetchall()
        ],
    }
