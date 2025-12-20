import psycopg2
from app.core.config import settings
import structlog

# Setup
# Hardcoding for migration script to ensure correctness bypass config loading issues
URL = "postgresql://postgres:TanmayAg@db.myvmzqrkitrqxummzhjw.supabase.co:5432/postgres?sslmode=require"

print(f"Connecting to Supabase: {URL.split('@')[-1]}")

def migrate():
    conn = psycopg2.connect(URL)
    cursor = conn.cursor()
    
    # 1. Enable UUID extension
    print("Enable uuid-ossp extension...")
    cursor.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
    
    # 2. Create Reports Table with 5 requested columns + metadata
    # - created_at
    # - incident_summary
    # - credibility_score
    # - score_explanation (justification)
    # - evidence (JSON relation or path, usually separate table, but here we CREATE TABLES)
    
    print("Creating tables...")
    
    # Schema matches Report model roughly
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reports (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        case_id VARCHAR(15) UNIQUE,
        access_token_hash VARCHAR(255) UNIQUE NOT NULL,
        status VARCHAR(50) DEFAULT 'NEW',
        priority VARCHAR(50) DEFAULT 'LOW',
        
        -- The 5 Columns Logic
        created_at TIMESTAMPTZ DEFAULT NOW(),
        incident_summary TEXT,
        credibility_score INTEGER,
        score_explanation TEXT,
        
        -- Extra Analysis fields
        evidence_analysis JSONB,
        tone_analysis JSONB,
        consistency_score INTEGER,
        fabrication_risk_score INTEGER,
        
        -- Metadata
        categories JSONB DEFAULT '[]',
        location_meta JSONB,
        is_archived BOOLEAN DEFAULT FALSE,
        updated_at TIMESTAMPTZ DEFAULT NOW()
    );
    """)
    
    # Evidence Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS evidence_files (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        report_id UUID REFERENCES reports(id) ON DELETE CASCADE,
        file_name VARCHAR(255),
        file_path VARCHAR(512),
        file_type VARCHAR(50),
        mime_type VARCHAR(100),
        file_size INTEGER,
        metadata JSONB,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    """)
    
    # Conversation Table (for chat history)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS report_conversations (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        report_id UUID REFERENCES reports(id) ON DELETE CASCADE,
        sender VARCHAR(50), -- user / bot
        content TEXT, -- encrypted
        content_redacted TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    """)
    
    # Tracking
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS report_state_tracking (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        report_id UUID REFERENCES reports(id) ON DELETE CASCADE,
        current_step VARCHAR(50),
        data_collected JSONB DEFAULT '{}',
        is_complete BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    );
    """)
    
    conn.commit()
    print("✅ Tables Created Successfully!")
    
    # Verify
    cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'reports';")
    cols = [row[0] for row in cursor.fetchall()]
    print("Columns in 'reports':", cols)
    
    conn.close()

if __name__ == "__main__":
    migrate()
