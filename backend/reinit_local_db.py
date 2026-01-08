import asyncio
import sys
import os

# Add the current directory to sys.path to allow importing 'app'
sys.path.append(os.getcwd())

from app.db.local_db import init_local_db, LOCAL_DB_PATH

async def run_init():
    print(f"Re-initializing local database at {LOCAL_DB_PATH}...")
    if os.path.exists(LOCAL_DB_PATH):
        print("Existing database found. Deleting for fresh start...")
        try:
            os.remove(LOCAL_DB_PATH)
        except Exception as e:
            print(f"Error deleting database: {e}")
            # If we can't delete it, just try to initialize (which might fail)
    
    try:
        await init_local_db()
        print("✅ Local database initialized successfully!")
    except Exception as e:
        print(f"❌ Initialization failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_init())
