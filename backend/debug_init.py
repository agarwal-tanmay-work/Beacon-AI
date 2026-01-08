import asyncio
import sys
import os
import uuid
from datetime import datetime

# Add the current directory to sys.path to allow importing 'app'
sys.path.append(os.getcwd())

from app.services.report_engine import ReportEngine

async def debug_init():
    report_id = str(uuid.uuid4())
    access_token = f"tk_{uuid.uuid4().hex[:12]}"
    print(f"Testing initialize_report with ID: {report_id}...")
    try:
        await ReportEngine.initialize_report(report_id, access_token)
        print("✅ Success!")
    except Exception as e:
        print(f"❌ Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(debug_init())
