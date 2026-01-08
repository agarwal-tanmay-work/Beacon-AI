-- Migration: Add Secret Key Tracking and Updates
-- Run this in your Supabase SQL Editor

-- 1. Add new columns to beacon table
ALTER TABLE beacon 
ADD COLUMN IF NOT EXISTS secret_key_hash TEXT,
ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'Received' NOT NULL,
ADD COLUMN IF NOT EXISTS last_updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL;

-- 2. Create beacon_update table for status updates
CREATE TABLE IF NOT EXISTS beacon_update (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id TEXT NOT NULL REFERENCES beacon(case_id),
    raw_update TEXT NOT NULL,
    public_update TEXT NOT NULL,
    updated_by TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

-- 3. Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_beacon_update_case_id ON beacon_update(case_id);
CREATE INDEX IF NOT EXISTS idx_beacon_status ON beacon(status);
