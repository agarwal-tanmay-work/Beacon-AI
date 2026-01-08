import asyncio
from app.db.session import AsyncSessionLocal
from sqlalchemy import text
import sys
import os

sys.path.append(os.getcwd())

async def inspect():
    import logging
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    print("Inspecting Beacon Table...")
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(text(
                "SELECT column_name, is_nullable, data_type FROM information_schema.columns WHERE table_name = 'beacon'"
            ))
            cols = result.fetchall()
            output = "--- SCHEMA START ---\n"
            for c in cols:
                output += f"{c[0]} | {c[1]} | {c[2]}\n"
            output += "--- SCHEMA END ---\n"
            print(output)
            with open("schema_final.txt", "w") as f:
                f.write(output)
    except Exception as e:
        print(f"Inspection Failed: {e}")

if __name__ == "__main__":
    asyncio.run(inspect())
