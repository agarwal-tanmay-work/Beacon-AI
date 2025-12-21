import httpx
import asyncio
import sys
import os
import json
from datetime import datetime

# Ensure we can import app code
sys.path.append(os.path.join(os.getcwd(), "backend"))

BASE_URL = "http://127.0.0.1:8001/api/v1/public/reports"

async def verify_e2e():
    print("🚀 Starting End-to-End Credibility Engine Verification...")
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        # 1. Create Report Session
        print("1. Creating Report Session...")
        try:
            resp = await client.post(f"{BASE_URL}/create", json={"client_seed": "e2e_verifier"})
            if resp.status_code != 200:
                print(f"❌ Failed to create session: {resp.text}")
                return
            
            data = resp.json()
            report_id = data["report_id"]
            token = data["access_token"]
            print(f"✅ Session Created: {report_id}")
        except Exception as e:
            print(f"❌ Connection Error: {e}")
            return

        # 2. Chat Simulation
        messages = [
            "I need to report a bribe taken by a traffic officer.",
            "It happened yesterday near the Sector 62 metro station at 4 PM.",
            "Officer Rajesh Kumar (Badge 5521) asked for 2000 INR to not tow my incorrectly parked bike.",
            "I paid him in cash because I was in a hurry. He didn't give any receipt.",
            "I've shared everything I know. Officer Rajesh was wearing a standard traffic police uniform and had a nameplate. I am anonymizing myself for safety.",
            "I am ready to officially submit this report now. Please finalize and give me my Case ID."
        ]
        
        case_id = None
        print("2. Simulating Chat...")
        for msg in messages:
            payload = {"report_id": report_id, "access_token": token, "content": msg}
            try:
                resp = await client.post(f"{BASE_URL}/message", json=payload)
                if resp.status_code != 200:
                    print(f"❌ Message Error: {resp.status_code} - {resp.text}")
                    break
                
                bot_data = resp.json()
                reply = bot_data.get("content", "")
                print(f"   [AI]: {reply[:100]}...")
                
                if "BCN" in reply or bot_data.get("next_step") == "SUBMITTED":
                    case_id = bot_data.get("case_id")
                    print(f"🎉 Report Submitted! Case ID: {case_id}")
                    break
            except Exception as e:
                print(f"❌ Error sending message: {e}")
                break
        
        if not case_id:
            print("❌ Verification Failed: Case ID never generated.")
            return

        # 3. Wait for Phase 2 Analysis
        print("\n3. Waiting for Phase 2 Analysis (Scoring)...")
        await asyncio.sleep(15) # Give it time to hit Groq and update Supabase

        # 4. Verify Supabase via DB Session
        print("4. Verifying Supabase Data...")
        from app.db.session import AsyncSessionLocal
        from app.models.beacon import Beacon
        from sqlalchemy import select
        
        async with AsyncSessionLocal() as session:
            stmt = select(Beacon).where(Beacon.case_id == case_id)
            result = await session.execute(stmt)
            beacon = result.scalar_one_or_none()
            
            if not beacon:
                print(f"❌ Error: Case {case_id} not found in Supabase 'beacon' table.")
                return
            
            print(f"✅ Case found in Supabase.")
            print(f"   Status: {beacon.analysis_status}")
            print(f"   Score: {beacon.credibility_score}")
            print(f"   Breakdown: {json.dumps(beacon.credibility_breakdown, indent=2)}")
            print(f"   Authority Summary: {beacon.authority_summary}")
            
            # Final Assertions
            if beacon.analysis_status == "completed" and beacon.credibility_score is not None:
                if beacon.credibility_breakdown and len(beacon.credibility_breakdown) == 8:
                    print("\n⭐⭐⭐ E2E VERIFICATION SUCCESSFUL ⭐⭐⭐")
                else:
                    print("\n⚠️ Partial Success: Score exists but breakdown might be malformed.")
            else:
                print(f"\n❌ Verification Failed: Analysis status is '{beacon.analysis_status}' and score is {beacon.credibility_score}")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(verify_e2e())
