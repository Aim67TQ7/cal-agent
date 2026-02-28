-- ============================================================
-- Migration 007: Align cal.* schema with TTC template
-- Project: ezlmmegowggujpcnzoda (GP3 / zoda)
-- Run in: SQL Editor → https://supabase.com/dashboard/project/ezlmmegowggujpcnzoda/sql
--
-- ADDITIVE ONLY — old columns remain for rollback safety.
-- Drop old columns via migration 008 after 48hrs clean operation.
-- ============================================================

BEGIN;

-- ============================================================
-- 1. ADD NEW COLUMNS TO cal.tools
-- ============================================================

ALTER TABLE cal.tools ADD COLUMN IF NOT EXISTS tool_name TEXT;
ALTER TABLE cal.tools ADD COLUMN IF NOT EXISTS tool_type VARCHAR(100);
ALTER TABLE cal.tools ADD COLUMN IF NOT EXISTS asset_tag VARCHAR(100);
ALTER TABLE cal.tools ADD COLUMN IF NOT EXISTS calibration_method VARCHAR(50);
ALTER TABLE cal.tools ADD COLUMN IF NOT EXISTS cal_interval_days INTEGER;
ALTER TABLE cal.tools ADD COLUMN IF NOT EXISTS active BOOLEAN DEFAULT true;
ALTER TABLE cal.tools ADD COLUMN IF NOT EXISTS notes TEXT;
ALTER TABLE cal.tools ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

-- ============================================================
-- 2. POPULATE NEW COLUMNS FROM EXISTING DATA (tools)
-- ============================================================

-- tool_name := description (actual equipment name)
UPDATE cal.tools SET tool_name = description WHERE description IS NOT NULL;

-- asset_tag := number (tool identifier like "BM-0042")
UPDATE cal.tools SET asset_tag = number WHERE number IS NOT NULL;

-- calibration_method := type ("In-House Calibrated" / "Vendor Calibrated")
UPDATE cal.tools SET calibration_method = type WHERE type IS NOT NULL;

-- active := derived from tool_status
UPDATE cal.tools SET active = CASE
  WHEN tool_status IS NULL THEN true
  WHEN lower(tool_status) = 'active' THEN true
  ELSE false
END;

-- notes := ownership (preserve data)
UPDATE cal.tools SET notes = ownership WHERE ownership IS NOT NULL AND ownership != '';

-- cal_interval_days := parsed from frequency text
UPDATE cal.tools SET cal_interval_days = CASE
  WHEN lower(frequency) = 'annual' THEN 365
  WHEN lower(frequency) = 'semi-annual' THEN 182
  WHEN lower(frequency) = 'quarterly' THEN 90
  WHEN lower(frequency) = 'monthly' THEN 30
  WHEN lower(frequency) = 'biennial' THEN 730
  WHEN lower(frequency) LIKE '%year%' THEN 365
  WHEN lower(frequency) LIKE '%month%' THEN 30
  ELSE NULL
END;

-- tool_type := parsed from description patterns
UPDATE cal.tools SET tool_type = CASE
  WHEN lower(description) LIKE '%snap gage%' OR lower(description) LIKE '%snap gauge%' THEN 'Snap Gage'
  WHEN lower(description) LIKE '%bore gage%' OR lower(description) LIKE '%bore gauge%' THEN 'Bore Gage'
  WHEN lower(description) LIKE '%blade micrometer%' THEN 'Blade Micrometer'
  WHEN lower(description) LIKE '%disc micrometer%' THEN 'Disc Micrometer'
  WHEN lower(description) LIKE '%flange micrometer%' THEN 'Flange Micrometer'
  WHEN lower(description) LIKE '%thread micrometer%' THEN 'Thread Micrometer'
  WHEN lower(description) LIKE '%inside micrometer%' THEN 'Inside Micrometer'
  WHEN lower(description) LIKE '%outside micrometer%' THEN 'Outside Micrometer'
  WHEN lower(description) LIKE '%depth micrometer%' THEN 'Depth Micrometer'
  WHEN lower(description) LIKE '%micrometer%' THEN 'Micrometer'
  WHEN lower(description) LIKE '%caliper%' THEN 'Caliper'
  WHEN lower(description) LIKE '%gauss%' THEN 'Gaussmeter'
  WHEN lower(description) LIKE '%indicator%' THEN 'Indicator'
  WHEN lower(description) LIKE '%height gage%' OR lower(description) LIKE '%height gauge%' THEN 'Height Gage'
  WHEN lower(description) LIKE '%pin gage%' OR lower(description) LIKE '%pin gauge%' THEN 'Pin Gage'
  WHEN lower(description) LIKE '%thread gage%' OR lower(description) LIKE '%thread gauge%' THEN 'Thread Gage'
  WHEN lower(description) LIKE '%ring gage%' OR lower(description) LIKE '%ring gauge%' THEN 'Ring Gage'
  WHEN lower(description) LIKE '%gage block%' OR lower(description) LIKE '%gauge block%' THEN 'Gage Block Set'
  WHEN lower(description) LIKE '%scale%' OR lower(description) LIKE '%balance%' THEN 'Scale'
  WHEN lower(description) LIKE '%hardness%' OR lower(description) LIKE '%durometer%' THEN 'Hardness Tester'
  WHEN lower(description) LIKE '%force gage%' OR lower(description) LIKE '%force gauge%' THEN 'Force Gage'
  WHEN lower(description) LIKE '%torque%' THEN 'Torque Wrench'
  WHEN lower(description) LIKE '%multimeter%' THEN 'Multimeter'
  WHEN lower(description) LIKE '%oscilloscope%' THEN 'Oscilloscope'
  WHEN lower(description) LIKE '%thermometer%' THEN 'Thermometer'
  WHEN lower(description) LIKE '%pressure%' THEN 'Pressure Gauge'
  WHEN lower(description) LIKE '%power supply%' THEN 'Power Supply'
  WHEN lower(description) LIKE '%clamp meter%' THEN 'Clamp Meter'
  WHEN lower(description) LIKE '%granite%' OR lower(description) LIKE '%surface plate%' THEN 'Surface Plate'
  WHEN lower(description) LIKE '%probe%' THEN 'Probe'
  ELSE NULL
END
WHERE tool_type IS NULL;

-- ============================================================
-- 3. ADD NEW COLUMNS TO cal.calibrations
-- ============================================================

ALTER TABLE cal.calibrations ADD COLUMN IF NOT EXISTS cert_number VARCHAR(100);
ALTER TABLE cal.calibrations ADD COLUMN IF NOT EXISTS performed_by VARCHAR(200);
ALTER TABLE cal.calibrations ADD COLUMN IF NOT EXISTS next_calibration_date TIMESTAMPTZ;
ALTER TABLE cal.calibrations ADD COLUMN IF NOT EXISTS notes TEXT;
ALTER TABLE cal.calibrations ADD COLUMN IF NOT EXISTS result_score NUMERIC(5,2);
ALTER TABLE cal.calibrations ADD COLUMN IF NOT EXISTS cost NUMERIC(10,2);
ALTER TABLE cal.calibrations ADD COLUMN IF NOT EXISTS vendor_id INTEGER;
ALTER TABLE cal.calibrations ADD COLUMN IF NOT EXISTS created_by INTEGER;

-- Populate from existing columns
UPDATE cal.calibrations SET cert_number = record_number WHERE record_number IS NOT NULL;
UPDATE cal.calibrations SET performed_by = technician WHERE technician IS NOT NULL;
UPDATE cal.calibrations SET next_calibration_date = next_due_date WHERE next_due_date IS NOT NULL;
UPDATE cal.calibrations SET notes = comments WHERE comments IS NOT NULL;

-- ============================================================
-- 4. CREATE NEW TABLES (vendors + audit_log)
-- ============================================================

CREATE TABLE IF NOT EXISTS cal.vendors (
  id SERIAL PRIMARY KEY,
  company_id INTEGER NOT NULL REFERENCES cal.companies(id),
  vendor_name VARCHAR(200) NOT NULL,
  contact_email VARCHAR(255),
  phone VARCHAR(50),
  accreditation VARCHAR(200),
  approved BOOLEAN DEFAULT false,
  notes TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS cal.audit_log (
  id SERIAL PRIMARY KEY,
  company_id INTEGER NOT NULL REFERENCES cal.companies(id),
  entity_type VARCHAR(50) NOT NULL,
  entity_id INTEGER NOT NULL,
  action VARCHAR(50) NOT NULL,
  old_values JSONB,
  new_values JSONB,
  performed_by INTEGER,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 5. INDEXES
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_cal_tools_tool_type ON cal.tools(tool_type);
CREATE INDEX IF NOT EXISTS idx_cal_tools_active ON cal.tools(active);
CREATE INDEX IF NOT EXISTS idx_cal_tools_asset_tag ON cal.tools(company_id, asset_tag);
CREATE INDEX IF NOT EXISTS idx_cal_vendors_company ON cal.vendors(company_id);
CREATE INDEX IF NOT EXISTS idx_cal_audit_company ON cal.audit_log(company_id);
CREATE INDEX IF NOT EXISTS idx_cal_audit_entity ON cal.audit_log(entity_type, entity_id);

-- ============================================================
-- 6. RLS + GRANTS
-- ============================================================

ALTER TABLE cal.vendors ENABLE ROW LEVEL SECURITY;
ALTER TABLE cal.audit_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_vendors" ON cal.vendors FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role_audit" ON cal.audit_log FOR ALL TO service_role USING (true) WITH CHECK (true);

GRANT ALL ON cal.vendors TO service_role;
GRANT ALL ON cal.audit_log TO service_role;
GRANT ALL ON cal.vendors TO authenticator;
GRANT ALL ON cal.audit_log TO authenticator;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA cal TO service_role;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA cal TO authenticator;

-- FK from calibrations to vendors
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE constraint_name = 'fk_calibrations_vendor'
  ) THEN
    ALTER TABLE cal.calibrations
      ADD CONSTRAINT fk_calibrations_vendor
      FOREIGN KEY (vendor_id) REFERENCES cal.vendors(id);
  END IF;
END $$;

COMMIT;
