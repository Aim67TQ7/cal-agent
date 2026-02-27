-- Migration 005: RPC function for Cal agent to execute read-only SQL
-- Run in Supabase SQL Editor (GP3 project: ezlmmegowggujpcnzoda)

CREATE OR REPLACE FUNCTION cal.execute_readonly_sql(query text, company_id integer)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = cal, public
AS $$
DECLARE
  result jsonb;
  upper_query text;
BEGIN
  -- Safety: only allow SELECT
  upper_query := upper(trim(query));
  IF NOT (upper_query LIKE 'SELECT%') THEN
    RAISE EXCEPTION 'Only SELECT queries are allowed';
  END IF;

  -- Disallow dangerous keywords
  IF upper_query ~ '(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE)' THEN
    RAISE EXCEPTION 'Mutation queries are not allowed';
  END IF;

  -- Execute with company_id bound as :cid
  EXECUTE format(
    'SELECT jsonb_agg(row_to_json(t)) FROM (%s) t',
    replace(query, ':cid', company_id::text)
  ) INTO result;

  RETURN COALESCE(result, '[]'::jsonb);
END;
$$;

-- Grant execute to service_role only
GRANT EXECUTE ON FUNCTION cal.execute_readonly_sql(text, integer) TO service_role;
