#!/usr/bin/env python3
"""Generate Supabase migration SQL from salvaged CSV files."""

import csv
import os

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def clean_ts(val):
    """Strip extra quotes from timestamp values."""
    if not val:
        return None
    val = val.strip('"').strip()
    if not val:
        return None
    return val

def esc(val):
    """Escape single quotes for SQL."""
    if val is None or val == '':
        return 'NULL'
    val = str(val).replace("'", "''")
    return f"'{val}'"

lines = []

# ── HEADER ──────────────────────────────────────────────────
lines.append("-- ============================================================")
lines.append("-- Cal Agent: Schema + Data Migration for Supabase")
lines.append("-- Project: ezlmmegowggujpcnzoda (GP3 / zoda)")
lines.append("-- Run in: SQL Editor → https://supabase.com/dashboard/project/ezlmmegowggujpcnzoda/sql")
lines.append("-- ============================================================")
lines.append("")

# ── SCHEMA ──────────────────────────────────────────────────
lines.append("CREATE SCHEMA IF NOT EXISTS cal;")
lines.append("")

# ── TABLES ──────────────────────────────────────────────────
lines.append("""-- Companies
CREATE TABLE IF NOT EXISTS cal.companies (
    id INTEGER PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    slug VARCHAR(50) UNIQUE NOT NULL,
    subscription_plan VARCHAR(50) DEFAULT 'basic',
    max_users INTEGER DEFAULT 1,
    max_tools INTEGER DEFAULT 50,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);""")
lines.append("")

lines.append("""-- Users
CREATE TABLE IF NOT EXISTS cal.users (
    id INTEGER PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    role VARCHAR(50) DEFAULT 'user',
    company_id INTEGER REFERENCES cal.companies(id),
    is_active BOOLEAN DEFAULT true,
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);""")
lines.append("")

lines.append("""-- Tools (equipment/instruments)
CREATE TABLE IF NOT EXISTS cal.tools (
    id INTEGER PRIMARY KEY,
    company_id INTEGER REFERENCES cal.companies(id),
    number VARCHAR(100),
    serial_number VARCHAR(200),
    manufacturer VARCHAR(200),
    model VARCHAR(200),
    description TEXT,
    type VARCHAR(100),
    frequency VARCHAR(50),
    calibration_status VARCHAR(50),
    tool_status VARCHAR(50) DEFAULT 'active',
    location VARCHAR(200),
    building VARCHAR(100),
    ownership VARCHAR(200),
    last_calibration_date TIMESTAMPTZ,
    next_due_date TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);""")
lines.append("")

lines.append("""-- Calibration records
CREATE TABLE IF NOT EXISTS cal.calibrations (
    id INTEGER PRIMARY KEY,
    record_number VARCHAR(100),
    tool_id INTEGER REFERENCES cal.tools(id),
    calibration_date TIMESTAMPTZ,
    result VARCHAR(50),
    next_due_date TIMESTAMPTZ,
    technician VARCHAR(200),
    comments TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);""")
lines.append("")

lines.append("""-- Attachments
CREATE TABLE IF NOT EXISTS cal.attachments (
    id INTEGER PRIMARY KEY,
    tool_id INTEGER REFERENCES cal.tools(id),
    calibration_id INTEGER REFERENCES cal.calibrations(id),
    filename VARCHAR(255),
    original_name VARCHAR(255),
    file_size INTEGER,
    mime_type VARCHAR(100),
    uploaded_at TIMESTAMPTZ DEFAULT NOW()
);""")
lines.append("")

lines.append("""-- Settings
CREATE TABLE IF NOT EXISTS cal.settings (
    id INTEGER PRIMARY KEY,
    key VARCHAR(100) NOT NULL,
    value TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    company_id INTEGER REFERENCES cal.companies(id)
);""")
lines.append("")

# ── INDEXES ─────────────────────────────────────────────────
lines.append("-- Indexes")
lines.append("CREATE INDEX IF NOT EXISTS idx_cal_tools_company ON cal.tools(company_id);")
lines.append("CREATE INDEX IF NOT EXISTS idx_cal_tools_status ON cal.tools(tool_status);")
lines.append("CREATE INDEX IF NOT EXISTS idx_cal_tools_number ON cal.tools(company_id, number);")
lines.append("CREATE INDEX IF NOT EXISTS idx_cal_calibrations_tool ON cal.calibrations(tool_id);")
lines.append("CREATE INDEX IF NOT EXISTS idx_cal_calibrations_date ON cal.calibrations(calibration_date);")
lines.append("CREATE INDEX IF NOT EXISTS idx_cal_calibrations_due ON cal.calibrations(next_due_date);")
lines.append("CREATE INDEX IF NOT EXISTS idx_cal_users_company ON cal.users(company_id);")
lines.append("")

# ── RLS ─────────────────────────────────────────────────────
lines.append("-- Row Level Security")
for tbl in ['companies', 'users', 'tools', 'calibrations', 'attachments', 'settings']:
    lines.append(f"ALTER TABLE cal.{tbl} ENABLE ROW LEVEL SECURITY;")
lines.append("")
for tbl in ['companies', 'users', 'tools', 'calibrations', 'attachments', 'settings']:
    lines.append(f'CREATE POLICY "service_role_all" ON cal.{tbl} FOR ALL TO service_role USING (true) WITH CHECK (true);')
lines.append("")

# Postgres role access for the backend connection
lines.append("-- Grant schema access to postgres role (used by direct connection)")
lines.append("GRANT USAGE ON SCHEMA cal TO postgres;")
lines.append("GRANT ALL ON ALL TABLES IN SCHEMA cal TO postgres;")
lines.append("GRANT ALL ON ALL SEQUENCES IN SCHEMA cal TO postgres;")
lines.append("")

# ── SEQUENCES ───────────────────────────────────────────────
lines.append("-- Sequences for future inserts")
lines.append("CREATE SEQUENCE IF NOT EXISTS cal.companies_id_seq START WITH 100;")
lines.append("CREATE SEQUENCE IF NOT EXISTS cal.users_id_seq START WITH 100;")
lines.append("CREATE SEQUENCE IF NOT EXISTS cal.tools_id_seq START WITH 200;")
lines.append("CREATE SEQUENCE IF NOT EXISTS cal.calibrations_id_seq START WITH 200;")
lines.append("CREATE SEQUENCE IF NOT EXISTS cal.attachments_id_seq START WITH 100;")
lines.append("CREATE SEQUENCE IF NOT EXISTS cal.settings_id_seq START WITH 100;")
lines.append("")

# ── SEED DATA ───────────────────────────────────────────────
lines.append("-- ============================================================")
lines.append("-- SEED DATA")
lines.append("-- ============================================================")
lines.append("")

# Companies
lines.append("-- Companies (3 records)")
with open('companies.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        is_active = 'true' if row['is_active'].strip().lower() == 'true' else 'false'
        created = clean_ts(row['created_at'])
        updated = clean_ts(row['updated_at'])
        lines.append(
            f"INSERT INTO cal.companies (id, name, slug, subscription_plan, max_users, max_tools, is_active, created_at, updated_at) "
            f"VALUES ({row['id']}, {esc(row['name'])}, {esc(row['slug'])}, {esc(row['subscription_plan'])}, "
            f"{row['max_users']}, {row['max_tools']}, {is_active}, {esc(created)}, {esc(updated)});"
        )
lines.append("")

# Users
lines.append("-- Users (7 records)")
with open('users.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        is_active = 'true' if row['is_active'].strip().lower() == 'true' else 'false'
        company_id = row['company_id'].strip() if row['company_id'].strip() else 'NULL'
        last_login = clean_ts(row['last_login_at'])
        created = clean_ts(row['created_at'])
        updated = clean_ts(row['updated_at'])
        lines.append(
            f"INSERT INTO cal.users (id, email, password_hash, first_name, last_name, role, company_id, is_active, last_login_at, created_at, updated_at) "
            f"VALUES ({row['id']}, {esc(row['email'])}, {esc(row['password'])}, {esc(row['first_name'])}, "
            f"{esc(row['last_name'])}, {esc(row['role'])}, {company_id}, {is_active}, {esc(last_login)}, {esc(created)}, {esc(updated)});"
        )
lines.append("")

# Tools
lines.append("-- Tools (177 records)")
with open('tools.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        company_id = row['company_id'].strip() if row['company_id'].strip() else 'NULL'
        last_cal = clean_ts(row.get('last_calibration_date', ''))
        next_due = clean_ts(row.get('next_due_date', ''))
        created = clean_ts(row['created_at'])
        lines.append(
            f"INSERT INTO cal.tools (id, company_id, number, serial_number, manufacturer, model, description, type, frequency, "
            f"calibration_status, tool_status, location, building, ownership, last_calibration_date, next_due_date, created_at) "
            f"VALUES ({row['id']}, {company_id}, {esc(row['number'])}, {esc(row['serial_number'])}, "
            f"{esc(row['manufacturer'])}, {esc(row['model'])}, {esc(row['description'])}, {esc(row['type'])}, "
            f"{esc(row['frequency'])}, {esc(row['calibration_status'])}, {esc(row['tool_status'])}, "
            f"{esc(row['location'])}, {esc(row['building'])}, {esc(row['ownership'])}, "
            f"{esc(last_cal)}, {esc(next_due)}, {esc(created)});"
        )
lines.append("")

# Calibrations
lines.append("-- Calibrations (100 records)")
with open('calibrations.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        cal_date = clean_ts(row['calibration_date'])
        next_due = clean_ts(row['next_due_date'])
        created = clean_ts(row['created_at'])
        comments = row.get('comments', '') or ''
        lines.append(
            f"INSERT INTO cal.calibrations (id, record_number, tool_id, calibration_date, result, next_due_date, technician, comments, created_at) "
            f"VALUES ({row['id']}, {esc(row['record_number'])}, {row['tool_id']}, {esc(cal_date)}, "
            f"{esc(row['result'])}, {esc(next_due)}, {esc(row['technician'])}, {esc(comments)}, {esc(created)});"
        )
lines.append("")

# Attachments
lines.append("-- Attachments (3 records)")
with open('attachments.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        uploaded = clean_ts(row['uploaded_at'])
        lines.append(
            f"INSERT INTO cal.attachments (id, tool_id, calibration_id, filename, original_name, file_size, mime_type, uploaded_at) "
            f"VALUES ({row['id']}, {row['tool_id']}, {row['calibration_id']}, {esc(row['filename'])}, "
            f"{esc(row['original_name'])}, {row['file_size']}, {esc(row['mime_type'])}, {esc(uploaded)});"
        )
lines.append("")

# Settings
lines.append("-- Settings (10 records)")
with open('settings.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        company_id = row['company_id'].strip() if row['company_id'].strip() else 'NULL'
        updated = clean_ts(row['updated_at'])
        lines.append(
            f"INSERT INTO cal.settings (id, key, value, updated_at, company_id) "
            f"VALUES ({row['id']}, {esc(row['key'])}, {esc(row['value'])}, {esc(updated)}, {company_id});"
        )
lines.append("")

# ── VERIFICATION ────────────────────────────────────────────
lines.append("-- ============================================================")
lines.append("-- VERIFICATION (run after to confirm)")
lines.append("-- ============================================================")
lines.append("SELECT 'companies' as tbl, count(*) as cnt FROM cal.companies")
lines.append("UNION ALL SELECT 'users', count(*) FROM cal.users")
lines.append("UNION ALL SELECT 'tools', count(*) FROM cal.tools")
lines.append("UNION ALL SELECT 'calibrations', count(*) FROM cal.calibrations")
lines.append("UNION ALL SELECT 'attachments', count(*) FROM cal.attachments")
lines.append("UNION ALL SELECT 'settings', count(*) FROM cal.settings;")

output = '\n'.join(lines)
with open('database/supabase_migration.sql', 'w', encoding='utf-8') as f:
    f.write(output)

print(f"Generated {len(lines)} lines -> database/supabase_migration.sql")

# Count data rows
counts = {'companies': 0, 'users': 0, 'tools': 0, 'calibrations': 0, 'attachments': 0, 'settings': 0}
for line in lines:
    for tbl in counts:
        if f"INSERT INTO cal.{tbl}" in line:
            counts[tbl] += 1
print(f"Data: {counts}")
