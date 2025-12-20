import asyncio
import httpx
import re
import sys
import os

# Add backend directory to path
sys.path.append(os.path.abspath("backend"))

from app.db.session import SessionLocal
from app.models.report import Report
from sqlalchemy import select

BASE_URL = "http://127.0.0.1:8000/api/v1"

async def test_full_completion():
    print("--- STARTING BEACON AI COMPLETION VERIFICATION ---")
    
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=60.0) as client:
        # Create Report
        res = await client.post("/public/reports/create", json={"client_seed": "completion-test"})
        data = res.json()
        report_id = data["report_id"]
        access_token = data["access_token"]
        print(f"Report ID: {report_id}")

        # Complete Conversation
        messages = [
            "Hi, I want to report a bribe.",
            "A police officer took 500 dollars from me near the central park yesterday at 4 PM to avoid a traffic ticket. He was a tall man with a mustache named Officer Gupta.",
            "It happened at exactly 123 Main St, Central Park Entrance, Metropolis.",
            "The date was December 19, 2024 at 4:15 PM.",
            "The officer was Head of Traffic Control, Officer Gupta.",
            "I have a video recording of him taking the cash and the ticket number."
        ]
        
        case_id = None
        for text in messages:
            print(f"\n[USER]: {text}")
            payload = {"report_id": report_id, "access_token": access_token, "content": text}
            res = await client.post("/public/reports/message", json=payload)
            msg = res.json()
            content = msg['content']
            print(f"[BEACON AI]: {content}")
            
            match = re.search(r'BCN\d{12}', content)
            if match:
                case_id = match.group(0)
                print(f"✅ DETECTED CASE ID: {case_id}")
                break

        if case_id:
            print("\nChecking database for Case ID...")
            await asyncio.sleep(1) # Wait for commit
            async with SessionLocal() as session:
                stmt = select(Report).where(Report.case_id == case_id)
                db_res = await session.execute(stmt)
                db_report = db_res.scalar_one_or_none()
                if db_report:
                    print(f"✅ SUCCESS: Case ID {case_id} found in database!")
                else:
                    print(f"❌ ERROR: Case ID {case_id} NOT found in database.")
        else:
            print("\n❌ ERROR: Report did not complete, no Case ID generated.")

    print("\n--- VERIFICATION COMPLETE ---")

if __name__ == "__main__":
    asyncio.run(test_full_completion())
