import asyncio
from app.db.session import engine
from sqlalchemy import text

async def upgrade():
    print("🚀 Starting Database Upgrade (Supabase)...")
    async with engine.begin() as conn:
        try:
            # Add credibility_breakdown JSONB
            print("Adding credibility_breakdown column...")
            await conn.execute(text("ALTER TABLE beacon ADD COLUMN IF NOT EXISTS credibility_breakdown JSONB;"))
            
            # Add authority_summary TEXT
            print("Adding authority_summary column...")
            await conn.execute(text("ALTER TABLE beacon ADD COLUMN IF NOT EXISTS authority_summary TEXT;"))
            
            # (Optional) If score_explanation exists and you want to keep it, you can. 
            # But the requirement said authority_summary is stored separately from user-facing data.
            # We already removed score_explanation from the Beacon model.
            
            print("✅ Database Upgrade Successful!")
        except Exception as e:
            print(f"❌ Database Upgrade Failed: {e}")

if __name__ == "__main__":
    asyncio.run(upgrade())
