-- Migration 004: Conversation memory for Cal agent continuous learning
-- Run in Supabase SQL Editor (GP3 project: ezlmmegowggujpcnzoda)

CREATE TABLE IF NOT EXISTS cal.conversation_memory (
  id SERIAL PRIMARY KEY,
  company_id INTEGER NOT NULL REFERENCES cal.companies(id),
  question TEXT NOT NULL,
  question_hash TEXT GENERATED ALWAYS AS (md5(lower(trim(question)))) STORED,
  answer TEXT,
  feedback VARCHAR(50),  -- 'helpful', 'wrong', 'incomplete'
  used_count INTEGER DEFAULT 1,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  last_used_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(company_id, question_hash)
);

CREATE INDEX idx_conv_memory_company ON cal.conversation_memory(company_id);
CREATE INDEX idx_conv_memory_usage ON cal.conversation_memory(company_id, used_count DESC);

ALTER TABLE cal.conversation_memory ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Service role bypass for conversation_memory" ON cal.conversation_memory
  FOR ALL USING (true) WITH CHECK (true);
