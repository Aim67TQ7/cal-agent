-- Migration 013: Email safety settings + test routing overrides
-- Adds domain allowlist and dry-run controls per company.
-- Sets test recipients to rclausing@buntingmagnetics.com for safe trial runs.
-- Project: ezlmmegowggujpcnzoda (GP3 / zoda)
-- Run in: Supabase SQL Editor → https://supabase.com/dashboard/project/ezlmmegowggujpcnzoda/sql

-- ============================================================
-- 1. Email safety settings for all companies
--    Uses nextval() because cal.settings.id has no DEFAULT
-- ============================================================

-- Default Company (id=1) — dry-run only, gp3.app domain
INSERT INTO cal.settings (id, key, value, company_id, updated_at)
SELECT nextval('cal.settings_id_seq'), key, value, 1, NOW()
FROM (VALUES
  ('email_allowed_domains', 'gp3.app'),
  ('email_dry_run',         'true')
) AS t(key, value)
WHERE NOT EXISTS (
  SELECT 1 FROM cal.settings s
  WHERE s.key = t.key AND s.company_id = 1
);

-- Demo Company (id=2) — dry-run only, gp3.app domain
INSERT INTO cal.settings (id, key, value, company_id, updated_at)
SELECT nextval('cal.settings_id_seq'), key, value, 2, NOW()
FROM (VALUES
  ('email_allowed_domains', 'gp3.app'),
  ('email_dry_run',         'true')
) AS t(key, value)
WHERE NOT EXISTS (
  SELECT 1 FROM cal.settings s
  WHERE s.key = t.key AND s.company_id = 2
);

-- Bunting Magnetics (id=3) — restricted to internal + gp3.app, dry-run ON for initial testing
INSERT INTO cal.settings (id, key, value, company_id, updated_at)
SELECT nextval('cal.settings_id_seq'), key, value, 3, NOW()
FROM (VALUES
  ('email_allowed_domains', 'buntingmagnetics.com,gp3.app'),
  ('email_dry_run',         'true')
) AS t(key, value)
WHERE NOT EXISTS (
  SELECT 1 FROM cal.settings s
  WHERE s.key = t.key AND s.company_id = 3
);

-- ============================================================
-- 2. Override Bunting notification recipients for TESTING
--    All emails → rclausing@buntingmagnetics.com (primary)
--    CC → robert@gp3.app (internal monitoring)
--    Sender: cal@bunting.gp3.app (already default from slug)
--
--    IMPORTANT: Restore real recipients before production go-live!
--    Real values are preserved in migration 011.
-- ============================================================

UPDATE cal.settings SET value = 'rclausing@buntingmagnetics.com', updated_at = NOW()
WHERE company_id = 3 AND key IN (
  'notify_overdue_to',
  'notify_critical_to',
  'notify_warning_to',
  'notify_purchasing_to',
  'notify_summary_to'
);

UPDATE cal.settings SET value = 'robert@gp3.app', updated_at = NOW()
WHERE company_id = 3 AND key IN (
  'notify_overdue_cc',
  'notify_critical_cc',
  'notify_warning_cc',
  'notify_purchasing_cc',
  'notify_summary_cc'
);

-- ============================================================
-- 3. Verification
-- ============================================================

SELECT key, value, company_id FROM cal.settings
WHERE key LIKE 'email_%' OR key LIKE 'notify_%'
ORDER BY company_id, key;
