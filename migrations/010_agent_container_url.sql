-- Migration 010: Add container_url to agent_instances for iframe integration
-- Run in Supabase SQL Editor (GP3 project: ezlmmegowggujpcnzoda)

-- Add column for agent container URLs (iframe mode)
ALTER TABLE agent_instances ADD COLUMN IF NOT EXISTS container_url TEXT;

-- Set Cal agent's container URL for Bunting
UPDATE agent_instances
SET container_url = 'https://cal.gp3.app'
WHERE tenant_id = 'bunting'
  AND agent_type = 'calibration';
