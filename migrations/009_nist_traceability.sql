-- ============================================================
-- Migration 009: NIST Traceability + Calibrating Entity
-- Project: ezlmmegowggujpcnzoda (GP3 / zoda)
-- Run in: SQL Editor → https://supabase.com/dashboard/project/ezlmmegowggujpcnzoda/sql
--
-- Adds calibrating entity tracking to tools and
-- accreditation/NIST traceability fields to vendors.
-- Seeds Bunting's 3 calibration providers.
-- ============================================================

BEGIN;

-- ============================================================
-- 1. NEW COLUMNS ON cal.tools
-- ============================================================

ALTER TABLE cal.tools ADD COLUMN IF NOT EXISTS calibrating_entity VARCHAR(200);
ALTER TABLE cal.tools ADD COLUMN IF NOT EXISTS cal_vendor_id INTEGER;

-- FK to vendors (only if not already present)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE constraint_name = 'fk_tools_cal_vendor'
  ) THEN
    ALTER TABLE cal.tools
      ADD CONSTRAINT fk_tools_cal_vendor
      FOREIGN KEY (cal_vendor_id) REFERENCES cal.vendors(id);
  END IF;
END $$;

-- ============================================================
-- 2. NEW COLUMNS ON cal.vendors
-- ============================================================

ALTER TABLE cal.vendors ADD COLUMN IF NOT EXISTS accreditation_number VARCHAR(100);
ALTER TABLE cal.vendors ADD COLUMN IF NOT EXISTS accreditation_body VARCHAR(200);
ALTER TABLE cal.vendors ADD COLUMN IF NOT EXISTS nist_traceable BOOLEAN DEFAULT true;
ALTER TABLE cal.vendors ADD COLUMN IF NOT EXISTS scope_of_accreditation TEXT;

-- ============================================================
-- 3. SEED BUNTING VENDORS (company_id = 3)
-- ============================================================

INSERT INTO cal.vendors (company_id, vendor_name, contact_email, accreditation_body, accreditation_number, nist_traceable, approved, scope_of_accreditation, notes)
VALUES
  (3, 'Bunting Magnetics (In-House)', NULL, NULL, NULL, true, true,
   'Snap gages, go/no-go gages, basic dimensional',
   'NIST traceable via certified master gage block sets'),
  (3, 'Precision Calibration Services', NULL, 'A2LA', NULL, true, true,
   'Dimensional measurement, force, torque, pressure',
   'Primary external lab — Newton KS area'),
  (3, 'Transcat', NULL, 'A2LA', NULL, true, true,
   'Complex instruments, gaussmeters, hardness testers, electrical',
   'National lab — used for specialized instruments')
ON CONFLICT DO NOTHING;

-- ============================================================
-- 4. POPULATE calibrating_entity FROM calibration_method
-- ============================================================

-- In-house tools
UPDATE cal.tools
SET calibrating_entity = 'Bunting Magnetics (In-House)',
    cal_vendor_id = (SELECT id FROM cal.vendors WHERE company_id = 3 AND vendor_name = 'Bunting Magnetics (In-House)' LIMIT 1)
WHERE company_id = 3
  AND calibration_method ILIKE '%In-House%'
  AND calibrating_entity IS NULL;

-- Vendor-calibrated tools default to Precision Cal (primary lab)
UPDATE cal.tools
SET calibrating_entity = 'Precision Calibration Services',
    cal_vendor_id = (SELECT id FROM cal.vendors WHERE company_id = 3 AND vendor_name = 'Precision Calibration Services' LIMIT 1)
WHERE company_id = 3
  AND calibration_method ILIKE '%Vendor%'
  AND calibrating_entity IS NULL;

-- Gaussmeters + hardness testers go to Transcat (specialized)
UPDATE cal.tools
SET calibrating_entity = 'Transcat',
    cal_vendor_id = (SELECT id FROM cal.vendors WHERE company_id = 3 AND vendor_name = 'Transcat' LIMIT 1)
WHERE company_id = 3
  AND tool_type IN ('Gaussmeter', 'Hardness Tester', 'Probe')
  AND calibration_method ILIKE '%Vendor%';

-- ============================================================
-- 5. INDEXES
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_cal_tools_cal_vendor ON cal.tools(cal_vendor_id);
CREATE INDEX IF NOT EXISTS idx_cal_tools_calibrating_entity ON cal.tools(calibrating_entity);

COMMIT;
