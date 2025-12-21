"""
Migration Script: Create Beacon Table in Supabase.

Run this script to create the beacon table:
    python create_beacon_table.py

This creates the table with:
- reported_at: TIMESTAMP WITH TIME ZONE NOT NULL
- case_id: VARCHAR(15) UNIQUE NOT NULL (BCN + 12 digits)
- incident_summary: TEXT
- credibility_score: INTEGER (1-100)
- score_explanation: TEXT
- evidence_files: JSONB DEFAULT '[]'
"""

import psycopg2
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv("backend_config.env")

# Supabase Connection URL (sync driver for migration)
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://postgres:TanmayAg@db.myvmzqrkitrqxummzhjw.supabase.co:5432/postgres"
).replace("postgresql+asyncpg://", "postgresql://")

# Add SSL if needed
if "supabase" in DATABASE_URL and "sslmode=" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL + ("&" if "?" in DATABASE_URL else "?") + "sslmode=require"

CREATE_TABLE_SQL = """
-- Drop table if exists (for fresh start)
-- DROP TABLE IF EXISTS beacon;

-- Create Beacon Table
CREATE TABLE IF NOT EXISTS beacon (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Required: Set on initial INSERT
    reported_at TIMESTAMP WITH TIME ZONE NOT NULL,
    case_id VARCHAR(15) UNIQUE NOT NULL,
    
    -- Generated: Set via UPDATE after processing
    incident_summary TEXT,
    credibility_score INTEGER CHECK (credibility_score >= 1 AND credibility_score <= 100),
    score_explanation TEXT,
    
    -- Evidence: JSONB with Base64 encoded files
    evidence_files JSONB DEFAULT '[]'::jsonb,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create unique index on case_id for fast lookups
CREATE UNIQUE INDEX IF NOT EXISTS idx_beacon_case_id ON beacon(case_id);

-- Create index on reported_at for date-based queries
CREATE INDEX IF NOT EXISTS idx_beacon_reported_at ON beacon(reported_at);

-- Comment for documentation
COMMENT ON TABLE beacon IS 'Final case storage: exactly ONE row per case';
COMMENT ON COLUMN beacon.case_id IS 'Format: BCN + 12 digits, unique and immutable';
COMMENT ON COLUMN beacon.credibility_score IS 'Integer 1-100, generated once and stored permanently';
COMMENT ON COLUMN beacon.evidence_files IS 'JSONB array with file_name, mime_type, size_bytes, content_base64';
"""


def main():
    print(f"Connecting to: {DATABASE_URL.split('@')[-1]}")
    
    try:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        cur = conn.cursor()
        
        print("Creating beacon table...")
        cur.execute(CREATE_TABLE_SQL)
        
        # Verify table exists
        cur.execute("""
            SELECT column_name, data_type, is_nullable 
            FROM information_schema.columns 
            WHERE table_name = 'beacon' 
            ORDER BY ordinal_position;
        """)
        
        columns = cur.fetchall()
        print("\n✅ Beacon table created successfully!")
        print("\nColumns:")
        for col in columns:
            print(f"  - {col[0]}: {col[1]} (nullable: {col[2]})")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        raise


if __name__ == "__main__":
    main()
