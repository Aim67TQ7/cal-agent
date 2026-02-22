-- ============================================================
-- cal.gp3.app - Calibration Agent Database Schema
-- Multi-Tenant from Day 1 with Row-Level Security
-- ============================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable RLS context variable
ALTER DATABASE cal_gp3 SET app.current_tenant_id = '';

-- ============================================================
-- CORE TABLES
-- ============================================================

-- Tenants table
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_slug VARCHAR(50) UNIQUE NOT NULL,
    company_name VARCHAR(200) NOT NULL,
    subscription_status VARCHAR(50) DEFAULT 'active',
    token_budget_daily INTEGER DEFAULT 5000,
    logo_url TEXT,
    primary_color VARCHAR(7) DEFAULT '#1a1a2e',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Users table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    name VARCHAR(200),
    role VARCHAR(50) DEFAULT 'admin',
    last_login TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Equipment registry
CREATE TABLE equipment (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    equipment_id VARCHAR(100) NOT NULL,
    equipment_type VARCHAR(50),
    description TEXT,
    manufacturer VARCHAR(200),
    model VARCHAR(200),
    serial_number VARCHAR(200),
    location VARCHAR(200),
    cal_frequency_months INTEGER,
    lab_name VARCHAR(200),
    critical BOOLEAN DEFAULT false,
    status VARCHAR(50) DEFAULT 'active',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(tenant_id, equipment_id)
);

-- Calibration records
CREATE TABLE calibration_records (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    equipment_id UUID REFERENCES equipment(id) ON DELETE CASCADE,
    cert_file_path TEXT,
    cert_file_name VARCHAR(255),
    calibration_date DATE NOT NULL,
    expiration_date DATE NOT NULL,
    lab_name VARCHAR(200),
    technician VARCHAR(200),
    status VARCHAR(50) DEFAULT 'current',
    pass_fail VARCHAR(10) DEFAULT 'pass',
    notes TEXT,
    extracted_data JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);

-- Events log (timeline tracking)
CREATE TABLE calibration_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    equipment_id UUID REFERENCES equipment(id),
    event_type VARCHAR(50) NOT NULL,
    event_data JSONB DEFAULT '{}',
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Token usage tracking
CREATE TABLE token_usage (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id),
    request_type VARCHAR(50),
    input_tokens INTEGER,
    output_tokens INTEGER,
    cost DECIMAL(10,6),
    model VARCHAR(100) DEFAULT 'claude-sonnet-4-5-20250929',
    timestamp TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- ROW-LEVEL SECURITY
-- ============================================================

ALTER TABLE equipment ENABLE ROW LEVEL SECURITY;
ALTER TABLE calibration_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE calibration_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE token_usage ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_equipment ON equipment
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

CREATE POLICY tenant_isolation_cal_records ON calibration_records
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

CREATE POLICY tenant_isolation_events ON calibration_events
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

CREATE POLICY tenant_isolation_token ON token_usage
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- ============================================================
-- INDEXES
-- ============================================================

CREATE INDEX idx_equipment_tenant ON equipment(tenant_id);
CREATE INDEX idx_equipment_lookup ON equipment(tenant_id, equipment_id);
CREATE INDEX idx_equipment_type ON equipment(tenant_id, equipment_type);
CREATE INDEX idx_cal_records_tenant ON calibration_records(tenant_id);
CREATE INDEX idx_cal_records_expiration ON calibration_records(expiration_date);
CREATE INDEX idx_cal_records_equipment ON calibration_records(equipment_id);
CREATE INDEX idx_cal_records_status ON calibration_records(tenant_id, status);
CREATE INDEX idx_events_tenant ON calibration_events(tenant_id);
CREATE INDEX idx_events_equipment ON calibration_events(equipment_id);
CREATE INDEX idx_token_usage_tenant ON token_usage(tenant_id);
CREATE INDEX idx_token_usage_timestamp ON token_usage(tenant_id, timestamp);
CREATE INDEX idx_users_tenant ON users(tenant_id);

-- ============================================================
-- SEED DATA - First Tenant (Bunting)
-- ============================================================

INSERT INTO tenants (tenant_slug, company_name, subscription_status)
VALUES ('bunting', 'Bunting Magnetics Company', 'active');

-- Note: First user created via API /auth/register endpoint

-- ============================================================
-- HELPER FUNCTIONS
-- ============================================================

-- Auto-update status based on expiration
CREATE OR REPLACE FUNCTION update_calibration_status()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.expiration_date < CURRENT_DATE THEN
        NEW.status := 'overdue';
    ELSIF NEW.expiration_date < CURRENT_DATE + INTERVAL '30 days' THEN
        NEW.status := 'expiring_soon';
    ELSE
        NEW.status := 'current';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_calibration_status
    BEFORE INSERT OR UPDATE ON calibration_records
    FOR EACH ROW
    EXECUTE FUNCTION update_calibration_status();

-- Daily status refresh function (call via cron or app)
CREATE OR REPLACE FUNCTION refresh_calibration_statuses()
RETURNS void AS $$
BEGIN
    UPDATE calibration_records
    SET status = 'overdue'
    WHERE expiration_date < CURRENT_DATE AND status != 'overdue';

    UPDATE calibration_records
    SET status = 'expiring_soon'
    WHERE expiration_date >= CURRENT_DATE
      AND expiration_date < CURRENT_DATE + INTERVAL '30 days'
      AND status != 'expiring_soon';

    UPDATE calibration_records
    SET status = 'current'
    WHERE expiration_date >= CURRENT_DATE + INTERVAL '30 days'
      AND status != 'current';
END;
$$ LANGUAGE plpgsql;
