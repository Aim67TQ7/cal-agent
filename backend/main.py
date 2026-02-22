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
import uuid
import json

# ============================================================
# APP SETUP
# ============================================================

app = FastAPI(
    title="cal.gp3.app - Calibration Agent",
    description="Multi-tenant calibration management powered by AI",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://cal.gp3.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# CONFIG
# ============================================================

DATABASE_URL = os.getenv("DATABASE_URL")
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
    name: str
    tenant_code: str  # opaque registration code, not slug

class QuestionRequest(BaseModel):
    question: str

class DownloadRequest(BaseModel):
    evidence_type: str = "all_current"

class EquipmentCreate(BaseModel):
    equipment_id: str
    equipment_type: str = ""
    description: str = ""
    manufacturer: str = ""
    model: str = ""
    serial_number: str = ""
    location: str = ""
    cal_frequency_months: int = 12
    lab_name: str = ""
    critical: bool = False

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
            "tenant_id": payload["tenant_id"],
            "role": payload.get("role", "user"),
        }
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

def set_tenant_context(db: Session, tenant_id: str):
    db.execute(text("SET LOCAL app.current_tenant_id = :tid"), {"tid": tenant_id})

# ============================================================
# KERNEL LOADER
# ============================================================

def load_tenant_kernel(db: Session, tenant_id: str) -> str:
    """Load kernel template and inject tenant-specific data."""
    kernel_path = Path("/app/kernels/calibrations_v1.0.ttc")
    if not kernel_path.exists():
        return "You are a calibration management assistant. Help users manage equipment calibration schedules, upload certificates, and generate audit evidence."

    kernel_template = kernel_path.read_text()

    result = db.execute(text("""
        SELECT equipment_id, equipment_type, cal_frequency_months, lab_name, critical
        FROM equipment WHERE tenant_id = :tid ORDER BY equipment_type, equipment_id
    """), {"tid": tenant_id})
    equipment = result.fetchall()

    result = db.execute(text(
        "SELECT company_name FROM tenants WHERE id = :tid"
    ), {"tid": tenant_id})
    tenant = result.fetchone()

    equipment_list = "\n".join([
        f"  {eq[0]}: type={eq[1]} | freq={eq[2]}mo | lab={eq[3]} | critical={eq[4]}"
        for eq in equipment
    ]) or "  No equipment registered yet."

    kernel = kernel_template.replace("{TENANT_NAME}", tenant[0] if tenant else "Unknown")
    kernel = kernel.replace("{EQUIPMENT_LIST}", equipment_list)
    return kernel

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

def log_tokens(db: Session, tenant_id: str, user_id: str, request_type: str, agent_response: dict):
    cost = (agent_response["input_tokens"] * 0.003 / 1000) + (agent_response["output_tokens"] * 0.015 / 1000)
    db.execute(text("""
        INSERT INTO token_usage (tenant_id, user_id, request_type, input_tokens, output_tokens, cost)
        VALUES (:tid, :uid, :rtype, :inp, :out, :cost)
    """), {
        "tid": tenant_id, "uid": user_id, "rtype": request_type,
        "inp": agent_response["input_tokens"], "out": agent_response["output_tokens"], "cost": cost,
    })

# ============================================================
# AUTH ENDPOINTS
# ============================================================

@app.post("/auth/login")
async def login(req: LoginRequest, db: Session = Depends(get_db)):
    result = db.execute(text("""
        SELECT u.id, u.password_hash, u.tenant_id, u.role, t.company_name
        FROM users u JOIN tenants t ON u.tenant_id = t.id
        WHERE u.email = :email
    """), {"email": req.email})
    user = result.fetchone()

    if not user or not pwd_context.verify(req.password, user[1]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Update last login
    db.execute(text("UPDATE users SET last_login = NOW() WHERE id = :uid"), {"uid": user[0]})
    db.commit()

    token = jwt.encode({
        "user_id": str(user[0]),
        "tenant_id": str(user[2]),
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
    # Look up tenant by slug (used only at registration, never in URLs)
    result = db.execute(text(
        "SELECT id FROM tenants WHERE tenant_slug = :slug AND subscription_status = 'active'"
    ), {"slug": req.tenant_code})
    tenant = result.fetchone()
    if not tenant:
        raise HTTPException(status_code=404, detail="Invalid registration code")

    # Check email not taken
    result = db.execute(text("SELECT id FROM users WHERE email = :email"), {"email": req.email})
    if result.fetchone():
        raise HTTPException(status_code=409, detail="Email already registered")

    password_hash = pwd_context.hash(req.password)
    db.execute(text("""
        INSERT INTO users (tenant_id, email, password_hash, name, role)
        VALUES (:tid, :email, :hash, :name, 'admin')
    """), {"tid": tenant[0], "email": req.email, "hash": password_hash, "name": req.name})
    db.commit()

    return {"status": "success", "message": "User created. Please login."}

# ============================================================
# CALIBRATION AGENT ENDPOINTS — tenant derived from JWT only
# ============================================================

@app.post("/cal/upload")
async def upload_cert(
    file: UploadFile = File(...),
    auth: dict = Depends(verify_token),
    db: Session = Depends(get_db),
):
    set_tenant_context(db, auth["tenant_id"])

    # Save file
    upload_dir = Path(f"/app/uploads/{auth['tenant_id']}")
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_id = str(uuid.uuid4())
    file_path = upload_dir / f"{file_id}_{file.filename}"

    content = await file.read()
    file_path.write_bytes(content)

    # Load kernel and extract data
    kernel = load_tenant_kernel(db, auth["tenant_id"])
    prompt = f"""Extract calibration data from this uploaded certificate.
Filename: {file.filename}
File size: {len(content)} bytes

Return ONLY a valid JSON object:
{{
    "equipment_id": "string - the equipment/instrument ID",
    "calibration_date": "YYYY-MM-DD",
    "expiration_date": "YYYY-MM-DD",
    "lab_name": "string - calibration lab name",
    "technician": "string - technician name if available, else empty",
    "pass_fail": "pass or fail",
    "notes": "string - any relevant notes"
}}"""

    agent_response = call_agent(kernel, prompt)
    log_tokens(db, auth["tenant_id"], auth["user_id"], "upload", agent_response)

    try:
        data = json.loads(agent_response["text"])
    except json.JSONDecodeError:
        text_resp = agent_response["text"]
        start = text_resp.find("{")
        end = text_resp.rfind("}") + 1
        if start >= 0 and end > start:
            data = json.loads(text_resp[start:end])
        else:
            db.commit()
            return {"status": "error", "message": "Could not parse certificate data. Please enter manually."}

    # Look up equipment
    result = db.execute(text("""
        SELECT id FROM equipment
        WHERE tenant_id = :tid AND equipment_id = :eid
    """), {"tid": auth["tenant_id"], "eid": data.get("equipment_id", "")})
    equipment = result.fetchone()

    if not equipment:
        db.commit()
        return {
            "status": "warning",
            "message": f"Equipment '{data.get('equipment_id')}' not found in registry. Please add it first.",
            "extracted_data": data,
        }

    # Insert calibration record
    db.execute(text("""
        INSERT INTO calibration_records
        (tenant_id, equipment_id, cert_file_path, cert_file_name,
         calibration_date, expiration_date, lab_name, technician, pass_fail, notes, extracted_data)
        VALUES (:tid, :eid, :path, :fname, :cal_date, :exp_date, :lab, :tech, :pf, :notes, :edata)
    """), {
        "tid": auth["tenant_id"], "eid": equipment[0],
        "path": str(file_path), "fname": file.filename,
        "cal_date": data.get("calibration_date"),
        "exp_date": data.get("expiration_date"),
        "lab": data.get("lab_name", ""),
        "tech": data.get("technician", ""),
        "pf": data.get("pass_fail", "pass"),
        "notes": data.get("notes", ""),
        "edata": json.dumps(data),
    })

    # Log event
    db.execute(text("""
        INSERT INTO calibration_events (tenant_id, equipment_id, event_type, event_data, created_by)
        VALUES (:tid, :eid, 'cert_uploaded', :edata, :uid)
    """), {
        "tid": auth["tenant_id"], "eid": equipment[0],
        "edata": json.dumps({"file": file.filename, "extracted": data}),
        "uid": auth["user_id"],
    })

    db.commit()

    return {
        "status": "success",
        "message": f"Calibration cert for {data['equipment_id']} processed. Expires {data.get('expiration_date', 'unknown')}.",
        "data": data,
    }

@app.post("/cal/question")
async def ask_question(
    req: QuestionRequest,
    auth: dict = Depends(verify_token),
    db: Session = Depends(get_db),
):
    set_tenant_context(db, auth["tenant_id"])

    # Build context from calibration data
    result = db.execute(text("""
        SELECT e.equipment_id, e.equipment_type, e.critical,
               cr.calibration_date, cr.expiration_date, cr.lab_name, cr.status, cr.pass_fail
        FROM calibration_records cr
        JOIN equipment e ON cr.equipment_id = e.id
        WHERE cr.tenant_id = :tid
        ORDER BY cr.expiration_date ASC
    """), {"tid": auth["tenant_id"]})
    cal_data = result.fetchall()

    context = "Current calibration records:\n" + "\n".join([
        f"- {r[0]} ({r[1]}, critical={r[2]}): Cal {r[3]}, Expires {r[4]}, Lab: {r[5]}, Status: {r[6]}, Result: {r[7]}"
        for r in cal_data
    ]) if cal_data else "No calibration records on file yet."

    # Get equipment summary
    result = db.execute(text("""
        SELECT COUNT(*), COUNT(CASE WHEN critical THEN 1 END)
        FROM equipment WHERE tenant_id = :tid
    """), {"tid": auth["tenant_id"]})
    eq_counts = result.fetchone()
    context += f"\n\nEquipment summary: {eq_counts[0]} total, {eq_counts[1]} critical."

    kernel = load_tenant_kernel(db, auth["tenant_id"])
    agent_response = call_agent(kernel, req.question, context)
    log_tokens(db, auth["tenant_id"], auth["user_id"], "question", agent_response)
    db.commit()

    return {"status": "success", "answer": agent_response["text"]}

@app.post("/cal/download")
async def generate_evidence(
    req: DownloadRequest,
    auth: dict = Depends(verify_token),
    db: Session = Depends(get_db),
):
    set_tenant_context(db, auth["tenant_id"])

    # Build query based on evidence type
    where_clause = ""
    if req.evidence_type == "overdue":
        where_clause = "AND cr.status = 'overdue'"
    elif req.evidence_type == "expiring_soon":
        where_clause = "AND cr.status = 'expiring_soon'"

    result = db.execute(text(f"""
        SELECT e.equipment_id, e.equipment_type, e.critical,
               cr.calibration_date, cr.expiration_date, cr.lab_name, cr.status,
               cr.cert_file_name, cr.pass_fail
        FROM calibration_records cr
        JOIN equipment e ON cr.equipment_id = e.id
        WHERE cr.tenant_id = :tid {where_clause}
        ORDER BY e.equipment_type, e.equipment_id
    """), {"tid": auth["tenant_id"]})
    records = result.fetchall()

    kernel = load_tenant_kernel(db, auth["tenant_id"])
    prompt = f"""Generate an audit evidence package summary for these calibration records.
Include:
- Cover sheet: total equipment, compliance rate, date generated
- Records organized by equipment type
- Items requiring immediate attention (overdue or expiring)
- Recommendation summary

Evidence type requested: {req.evidence_type}
Total records: {len(records)}

Records:
""" + "\n".join([
        f"- {r[0]} ({r[1]}, critical={r[2]}): Cal {r[3]}, Exp {r[4]}, Lab: {r[5]}, Status: {r[6]}, Result: {r[8]}"
        for r in records
    ])

    agent_response = call_agent(kernel, prompt)
    log_tokens(db, auth["tenant_id"], auth["user_id"], "download", agent_response)
    db.commit()

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
    set_tenant_context(db, auth["tenant_id"])

    result = db.execute(text("""
        SELECT e.id, e.equipment_id, e.equipment_type, e.description, e.manufacturer,
               e.model, e.serial_number, e.location, e.cal_frequency_months,
               e.lab_name, e.critical, e.status,
               cr.calibration_date AS last_cal_date,
               cr.expiration_date AS next_exp_date,
               cr.status AS cal_status
        FROM equipment e
        LEFT JOIN LATERAL (
            SELECT calibration_date, expiration_date, status
            FROM calibration_records
            WHERE equipment_id = e.id
            ORDER BY calibration_date DESC LIMIT 1
        ) cr ON true
        WHERE e.tenant_id = :tid
        ORDER BY e.equipment_type, e.equipment_id
    """), {"tid": auth["tenant_id"]})

    rows = result.fetchall()
    return {
        "equipment": [
            {
                "id": str(r[0]), "equipment_id": r[1], "equipment_type": r[2],
                "description": r[3], "manufacturer": r[4], "model": r[5],
                "serial_number": r[6], "location": r[7], "cal_frequency_months": r[8],
                "lab_name": r[9], "critical": r[10], "status": r[11],
                "last_cal_date": str(r[12]) if r[12] else None,
                "next_exp_date": str(r[13]) if r[13] else None,
                "cal_status": r[14],
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
    set_tenant_context(db, auth["tenant_id"])

    db.execute(text("""
        INSERT INTO equipment
        (tenant_id, equipment_id, equipment_type, description, manufacturer,
         model, serial_number, location, cal_frequency_months, lab_name, critical)
        VALUES (:tid, :eid, :etype, :desc, :mfr, :model, :sn, :loc, :freq, :lab, :crit)
    """), {
        "tid": auth["tenant_id"], "eid": eq.equipment_id, "etype": eq.equipment_type,
        "desc": eq.description, "mfr": eq.manufacturer, "model": eq.model,
        "sn": eq.serial_number, "loc": eq.location, "freq": eq.cal_frequency_months,
        "lab": eq.lab_name, "crit": eq.critical,
    })
    db.commit()

    return {"status": "success", "message": f"Equipment {eq.equipment_id} added."}

# ============================================================
# DASHBOARD DATA
# ============================================================

@app.get("/cal/dashboard")
async def dashboard(
    auth: dict = Depends(verify_token),
    db: Session = Depends(get_db),
):
    set_tenant_context(db, auth["tenant_id"])

    eq_count = db.execute(text(
        "SELECT COUNT(*) FROM equipment WHERE tenant_id = :tid"
    ), {"tid": auth["tenant_id"]}).scalar()

    status_counts = db.execute(text("""
        SELECT status, COUNT(*) FROM calibration_records
        WHERE tenant_id = :tid GROUP BY status
    """), {"tid": auth["tenant_id"]}).fetchall()

    upcoming = db.execute(text("""
        SELECT e.equipment_id, e.equipment_type, e.critical,
               cr.expiration_date, cr.status
        FROM calibration_records cr
        JOIN equipment e ON cr.equipment_id = e.id
        WHERE cr.tenant_id = :tid
          AND cr.expiration_date <= CURRENT_DATE + INTERVAL '60 days'
          AND cr.expiration_date >= CURRENT_DATE
        ORDER BY cr.expiration_date ASC
    """), {"tid": auth["tenant_id"]}).fetchall()

    token_usage = db.execute(text("""
        SELECT COALESCE(SUM(input_tokens + output_tokens), 0),
               COALESCE(SUM(cost), 0)
        FROM token_usage
        WHERE tenant_id = :tid
          AND timestamp >= DATE_TRUNC('month', CURRENT_DATE)
    """), {"tid": auth["tenant_id"]}).fetchone()

    events = db.execute(text("""
        SELECT ce.event_type, ce.event_data, ce.created_at, e.equipment_id
        FROM calibration_events ce
        LEFT JOIN equipment e ON ce.equipment_id = e.id
        WHERE ce.tenant_id = :tid
        ORDER BY ce.created_at DESC LIMIT 10
    """), {"tid": auth["tenant_id"]}).fetchall()

    return {
        "equipment_count": eq_count,
        "status_summary": {r[0]: r[1] for r in status_counts},
        "upcoming_expirations": [
            {"equipment_id": r[0], "type": r[1], "critical": r[2],
             "expiration_date": str(r[3]), "status": r[4]}
            for r in upcoming
        ],
        "token_usage": {"tokens": token_usage[0], "cost": float(token_usage[1])},
        "recent_events": [
            {"type": r[0], "data": r[1], "timestamp": r[2].isoformat(), "equipment_id": r[3]}
            for r in events
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
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
    }
