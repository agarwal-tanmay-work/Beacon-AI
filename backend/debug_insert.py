import asyncio
from app.db.session import AsyncSessionLocal
from sqlalchemy import text
import uuid
from datetime import datetime
import sys
import os

sys.path.append(os.getcwd())

async def test_insert():
    print("Testing Insert...")
    try:
        async with AsyncSessionLocal() as session:
            # Minimal insert raw SQL to bypass model defaults
            uid = uuid.uuid4()
            cid = f"TEST{uid.int}"[:15]
            stmt = text("INSERT INTO beacon (id, reported_at, case_id, created_at, updated_at, analysis_status, analysis_attempts, credibility_score) VALUES (:id, :rat, :cid, :rat, :rat, 'pending', 0, :score)")
            
            # Try 50
            try:
                await session.execute(stmt, {"id": uid, "rat": datetime.now(), "cid": cid, "score": 50})
                await session.commit()
                print("Insert 50 SUCCESS")
            except Exception as e:
                print(f"Insert 50 FAILED: {e}")
                await session.rollback()

            # Try NULL
            try:
                stmt_null = text("INSERT INTO beacon (id, reported_at, case_id, created_at, updated_at, analysis_status, analysis_attempts, credibility_score) VALUES (:id, :rat, :cid, :rat, :rat, 'pending', 0, NULL)")
                uid2 = uuid.uuid4()
                cid2 = f"TEST{uid2.int}"[:15]
                await session.execute(stmt_null, {"id": uid2, "rat": datetime.now(), "cid": cid2})
                await session.commit()
                print("Insert NULL SUCCESS")
            except Exception as e:
                print(f"Insert NULL FAILED: {e}")

    except Exception as e:
        print(f"Connection Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_insert())
