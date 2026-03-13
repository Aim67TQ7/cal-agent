-- Migration 012: Schema enhancements for real autonomous agent capabilities
-- Project: ezlmmegowggujpcnzoda (GP3 / zoda)
-- Run in: Supabase SQL Editor → https://supabase.com/dashboard/project/ezlmmegowggujpcnzoda/sql
--
-- Covers:
--   1. Normalize + constrain cal.calibrations.result (Fix 3)
--   2. Vendor turnaround tracking columns (Fix 4)
--   3. Vendor table enrichment (Fix 4)
--   4. Seed Bunting vendors with real SLA data (Fix 4)
-- ============================================================

BEGIN;

-- ============================================================
-- 1. RESULT ENUMERATION (Fix 3)
-- Normalize free-text values first, then enforce constraint.
-- ============================================================

-- Normalize casing + trim
UPDATE cal.calibrations
SET result = LOWER(TRIM(result))
WHERE result IS NOT NULL;

-- Map legacy variants
UPDATE cal.calibrations SET result = 'pass'
WHERE result IN ('passed', 'p', 'ok', 'good', 'yes', 'accept', 'acceptable');

UPDATE cal.calibrations SET result = 'fail'
WHERE result IN ('failed', 'f', 'no', 'reject', 'rejected', 'failure');

UPDATE cal.calibrations SET result = 'adjusted'
WHERE result IN ('adj', 'calibrated', 'adjusted and passed', 'adj/pass');

UPDATE cal.calibrations SET result = 'out_of_tolerance'
WHERE result IN ('oot', 'out of tolerance', 'out-of-tolerance', 'oof');

-- Any remaining non-conforming values → mark as conditional for human review
UPDATE cal.calibrations
SET result = 'conditional'
WHERE result IS NOT NULL
  AND result NOT IN ('pass', 'fail', 'adjusted', 'out_of_tolerance', 'conditional');

-- Add CHECK constraint going forward
ALTER TABLE cal.calibrations
  DROP CONSTRAINT IF EXISTS chk_cal_result;

ALTER TABLE cal.calibrations
  ADD CONSTRAINT chk_cal_result
  CHECK (result IS NULL OR result IN ('pass', 'fail', 'adjusted', 'out_of_tolerance', 'conditional'));

-- ============================================================
-- 2. VENDOR TURNAROUND TRACKING (Fix 4)
-- sent_to_vendor_date + received_from_vendor_date on calibrations
-- ============================================================

ALTER TABLE cal.calibrations
  ADD COLUMN IF NOT EXISTS sent_to_vendor_date DATE;

ALTER TABLE cal.calibrations
  ADD COLUMN IF NOT EXISTS received_from_vendor_date DATE;

-- Index for turnaround queries
CREATE INDEX IF NOT EXISTS idx_cal_calibrations_sent
  ON cal.calibrations(sent_to_vendor_date)
  WHERE sent_to_vendor_date IS NOT NULL;

-- ============================================================
-- 3. VENDOR TABLE ENRICHMENT (Fix 4)
-- Add SLA, accreditation, NIST fields to cal.vendors
-- ============================================================

ALTER TABLE cal.vendors
  ADD COLUMN IF NOT EXISTS sla_days INTEGER DEFAULT 14;

ALTER TABLE cal.vendors
  ADD COLUMN IF NOT EXISTS accreditation_number VARCHAR(100);

ALTER TABLE cal.vendors
  ADD COLUMN IF NOT EXISTS nist_traceable BOOLEAN DEFAULT true;

ALTER TABLE cal.vendors
  ADD COLUMN IF NOT EXISTS scope_of_accreditation TEXT;

ALTER TABLE cal.vendors
  ADD COLUMN IF NOT EXISTS cal_vendor_type VARCHAR(50) DEFAULT 'external';
  -- 'internal' for in-house, 'external' for third-party labs

-- ============================================================
-- 4. SEED BUNTING VENDORS (company_id = 3)
-- Only insert if not already present by vendor_name
-- ============================================================

INSERT INTO cal.vendors (company_id, vendor_name, contact_email, accreditation, accreditation_number,
  nist_traceable, scope_of_accreditation, sla_days, approved, cal_vendor_type)
SELECT 3, v.vendor_name, v.contact_email, v.accreditation, v.accreditation_number,
  v.nist_traceable, v.scope_of_accreditation, v.sla_days, true, v.cal_vendor_type
FROM (VALUES
  (
    'Bunting Magnetics (In-House)',
    'bdick@buntingmagnetics.com',
    'Internal — documented procedure',
    NULL,
    true,
    'Snap gages, go/no-go gages, basic dimensional',
    3,
    'internal'
  ),
  (
    'Precision Calibration Services',
    'info@precisioncal.com',
    'A2LA — ISO/IEC 17025',
    NULL,
    true,
    'Dimensional measurement, force, torque, pressure',
    10,
    'external'
  ),
  (
    'Transcat',
    'calibration@transcat.com',
    'A2LA — ISO/IEC 17025',
    NULL,
    true,
    'Gaussmeters, hardness testers, electrical, complex instruments',
    14,
    'external'
  )
) AS v(vendor_name, contact_email, accreditation, accreditation_number,
       nist_traceable, scope_of_accreditation, sla_days, cal_vendor_type)
WHERE NOT EXISTS (
  SELECT 1 FROM cal.vendors existing
  WHERE existing.company_id = 3 AND existing.vendor_name = v.vendor_name
);

-- ============================================================
-- 5. LINK TOOLS TO VENDORS via cal_vendor_id (Fix 4)
-- Map calibrating_entity text → vendors.id for Bunting tools
-- Only sets cal_vendor_id where it's currently NULL
-- ============================================================

-- In-house tools → Bunting In-House vendor
UPDATE cal.tools t
SET cal_vendor_id = v.id
FROM cal.vendors v
WHERE t.company_id = 3
  AND v.company_id = 3
  AND v.vendor_name = 'Bunting Magnetics (In-House)'
  AND (
    t.calibrating_entity ILIKE '%in-house%'
    OR t.calibrating_entity ILIKE '%bunting%'
    OR t.calibration_method ILIKE '%in-house%'
  )
  AND t.cal_vendor_id IS NULL;

-- Precision Cal tools
UPDATE cal.tools t
SET cal_vendor_id = v.id
FROM cal.vendors v
WHERE t.company_id = 3
  AND v.company_id = 3
  AND v.vendor_name = 'Precision Calibration Services'
  AND t.calibrating_entity ILIKE '%precision%'
  AND t.cal_vendor_id IS NULL;

-- Transcat tools (gaussmeters, hardness testers, complex)
UPDATE cal.tools t
SET cal_vendor_id = v.id
FROM cal.vendors v
WHERE t.company_id = 3
  AND v.company_id = 3
  AND v.vendor_name = 'Transcat'
  AND (
    t.calibrating_entity ILIKE '%transcat%'
    OR t.tool_type IN ('Gaussmeter', 'Hardness Tester', 'Multimeter', 'Oscilloscope')
  )
  AND t.cal_vendor_id IS NULL;

-- ============================================================
-- 6. GRANTS & RLS (vendors already has RLS from 007, ensure sequences covered)
-- ============================================================

GRANT USAGE ON ALL SEQUENCES IN SCHEMA cal TO service_role;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA cal TO authenticator;

COMMIT;
