-- Migration 011: Email log + per-company notification routing settings
-- Ensures email_log exists (003 may not have been applied) and seeds
-- Bunting notification recipients into cal.settings for autonomous enforcement.
-- Project: ezlmmegowggujpcnzoda (GP3 / zoda)
-- Run in: Supabase SQL Editor → https://supabase.com/dashboard/project/ezlmmegowggujpcnzoda/sql

-- ============================================================
-- 1. Ensure cal.email_log table exists (idempotent)
-- ============================================================

CREATE TABLE IF NOT EXISTS cal.email_log (
  id SERIAL PRIMARY KEY,
  company_id INTEGER NOT NULL REFERENCES cal.companies(id),
  direction VARCHAR(10) NOT NULL DEFAULT 'inbound',
  from_address VARCHAR(500),
  to_address VARCHAR(500),
  cc_addresses TEXT,
  subject VARCHAR(1000),
  body_text TEXT,
  body_html TEXT,
  has_attachments BOOLEAN DEFAULT false,
  attachment_count INTEGER DEFAULT 0,
  status VARCHAR(50) DEFAULT 'received',
  processing_result JSONB,
  tool_id INTEGER REFERENCES cal.tools(id),
  calibration_id INTEGER REFERENCES cal.calibrations(id),
  message_id VARCHAR(500),
  in_reply_to VARCHAR(500),
  received_at TIMESTAMPTZ DEFAULT NOW(),
  processed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_email_log_company    ON cal.email_log(company_id);
CREATE INDEX IF NOT EXISTS idx_email_log_status     ON cal.email_log(status);
CREATE INDEX IF NOT EXISTS idx_email_log_message_id ON cal.email_log(message_id);
CREATE INDEX IF NOT EXISTS idx_email_log_received   ON cal.email_log(received_at DESC);

ALTER TABLE cal.email_log ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename='email_log' AND schemaname='cal'
      AND policyname='Service role bypass for email_log'
  ) THEN
    CREATE POLICY "Service role bypass for email_log" ON cal.email_log
      FOR ALL USING (true) WITH CHECK (true);
  END IF;
END $$;

GRANT ALL ON cal.email_log TO service_role;
GRANT ALL ON cal.email_log TO authenticator;
GRANT USAGE ON SEQUENCE cal.email_log_id_seq TO service_role;
GRANT USAGE ON SEQUENCE cal.email_log_id_seq TO authenticator;

-- ============================================================
-- 2. Seed Bunting notification settings (company_id = 3)
-- Keys:
--   notify_overdue_to/cc   → ACTION REQUIRED: remove from service (→ Quality Manager)
--   notify_critical_to/cc  → URGENT: due within 7 days (→ Quality Tech Lead)
--   notify_warning_to/cc   → NOTICE: due within 30 days (→ Technician + Tech Lead)
--   notify_purchasing_to/cc → PO alert for vendor-calibrated tools
--   notify_summary_to/cc   → Weekly compliance summary (→ Quality Manager)
-- ============================================================

INSERT INTO cal.settings (id, key, value, company_id, updated_at)
SELECT
  (SELECT COALESCE(MAX(id), 0) FROM cal.settings) + ROW_NUMBER() OVER (),
  t.key, t.value, 3, NOW()
FROM (VALUES
  ('notify_overdue_to',    'rlinton@buntingmagnetics.com'),
  ('notify_overdue_cc',    'bdick@buntingmagnetics.com'),
  ('notify_critical_to',   'bdick@buntingmagnetics.com'),
  ('notify_critical_cc',   ''),
  ('notify_warning_to',    'dsanchez@buntingmagnetics.com'),
  ('notify_warning_cc',    'bdick@buntingmagnetics.com'),
  ('notify_purchasing_to', 'purchasing@buntingmagnetics.com'),
  ('notify_purchasing_cc', 'bdick@buntingmagnetics.com'),
  ('notify_summary_to',    'rlinton@buntingmagnetics.com'),
  ('notify_summary_cc',    'bdick@buntingmagnetics.com')
) AS t(key, value)
WHERE NOT EXISTS (
  SELECT 1 FROM cal.settings s
  WHERE s.key = t.key AND s.company_id = 3
);
