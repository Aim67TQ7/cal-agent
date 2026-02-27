-- Migration 003: Email log for Cal agent inbound/outbound tracking
-- Run in Supabase SQL Editor (GP3 project: ezlmmegowggujpcnzoda)

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

CREATE INDEX idx_email_log_company ON cal.email_log(company_id);
CREATE INDEX idx_email_log_status ON cal.email_log(status);
CREATE INDEX idx_email_log_message_id ON cal.email_log(message_id);

ALTER TABLE cal.email_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Service role bypass for email_log" ON cal.email_log
  FOR ALL USING (true) WITH CHECK (true);
