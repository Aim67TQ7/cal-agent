-- ============================================================
-- Migration 008: Create execute_readonly_sql RPC function
-- Project: ezlmmegowggujpcnzoda (GP3 / zoda)
-- Run in: SQL Editor → https://supabase.com/dashboard/project/ezlmmegowggujpcnzoda/sql
--
-- This function enables Cal's SQL tool-calling loop.
-- Without it, the LLM cannot query the database and will hallucinate.
-- ============================================================

CREATE OR REPLACE FUNCTION public.execute_readonly_sql(query TEXT, company_id INTEGER)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = cal, public
AS $$
DECLARE
  result JSONB;
  safe_query TEXT;
BEGIN
  -- Validate read-only
  safe_query := UPPER(TRIM(query));
  IF NOT safe_query LIKE 'SELECT%' THEN
    RAISE EXCEPTION 'Only SELECT queries are allowed';
  END IF;

  -- Block write operations
  IF safe_query ~ '(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE)' THEN
    RAISE EXCEPTION 'Write operations are not allowed';
  END IF;

  -- Ensure query references company_id for tenant isolation
  IF query NOT LIKE '%company_id%' THEN
    RAISE EXCEPTION 'Query must filter by company_id for tenant isolation';
  END IF;

  -- Execute and return as JSONB array
  EXECUTE format('SELECT COALESCE(jsonb_agg(row_to_json(t)), ''[]''::jsonb) FROM (%s) t', query)
  INTO result;

  RETURN result;
END;
$$;

-- Grant access to service_role (used by backend) and authenticator
GRANT EXECUTE ON FUNCTION public.execute_readonly_sql(TEXT, INTEGER) TO service_role;
GRANT EXECUTE ON FUNCTION public.execute_readonly_sql(TEXT, INTEGER) TO authenticator;
