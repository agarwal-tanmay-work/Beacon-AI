import asyncio
import structlog
from app.core.config import settings
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

# Setup minimal logging
logger = structlog.get_logger()

async def upgrade_db():
    print("🚀 Starting Manual Async DB Upgrade...")
    
    url = settings.DATABASE_URL
    print(f"   Target DB: {url.split('@')[-1]}") # redact auth
    
    engine = create_async_engine(url, echo=True)
    
    columns_to_add = [
        ("incident_summary", "TEXT"),
        ("evidence_analysis", "JSON"), # Postgres uses JSONB usually, but let's try JSON or JSONB based on dialect? 
                                       # Wait, if it's sqlite it stays TEXT/JSON. If PG, JSONB.
                                       # Safer to use generic type or catch exception?
                                       # Let's try "TEXT" for JSON cols if simple, or "JSONB" if PG.
                                       # How to detect? 
                                       # Let's assume PG since asyncpg.
        ("tone_analysis", "JSON"),
        ("consistency_score", "INTEGER"),
        ("fabrication_risk_score", "INTEGER")
    ]
    
    # Adjust types for Postgres
    # If using asyncpg, we are likely on Postgres.
    # We can try to guess dialect or just use 'TEXT' for json fields as fallback? No, report.py uses JSON.
    # In PG, we want 'JSONB' or 'JSON'.
    # I'll use 'JSONB' for asyncpg/pg.
    
    # Check if sqlite
    is_sqlite = "sqlite" in url
    json_type = "TEXT" if is_sqlite else "JSONB"
    
    # Override for verification script simplicity
    cols = [
        ("incident_summary", "TEXT"),
        ("evidence_analysis", json_type),
        ("tone_analysis", json_type),
        ("consistency_score", "INTEGER"),
        ("fabrication_risk_score", "INTEGER")
    ]

    async with engine.begin() as conn:
        for col_name, col_type in cols:
            print(f"   Adding column: {col_name} ({col_type})...")
            try:
                await conn.execute(text(f"ALTER TABLE reports ADD COLUMN {col_name} {col_type};"))
                print(f"   ✅ Added {col_name}")
            except Exception as e:
                # Likely "column already exists"
                print(f"   ⚠️ Could not add {col_name}: {e}")
                
    await engine.dispose()
    print("🎉 Upgrade Complete.")

if __name__ == "__main__":
    if "win32" in str(asyncio.get_event_loop_policy()):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(upgrade_db())
