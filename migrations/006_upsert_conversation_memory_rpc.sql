-- Migration 006: RPC function for upserting conversation memory
-- Run in Supabase SQL Editor (GP3 project: ezlmmegowggujpcnzoda)

CREATE OR REPLACE FUNCTION cal.upsert_conversation_memory(
  p_company_id integer,
  p_question text,
  p_answer text
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = cal, public
AS $$
BEGIN
  INSERT INTO cal.conversation_memory (company_id, question, answer)
  VALUES (p_company_id, p_question, p_answer)
  ON CONFLICT (company_id, question_hash)
  DO UPDATE SET
    used_count = cal.conversation_memory.used_count + 1,
    last_used_at = NOW(),
    answer = EXCLUDED.answer;
END;
$$;

GRANT EXECUTE ON FUNCTION cal.upsert_conversation_memory(integer, text, text) TO service_role;
