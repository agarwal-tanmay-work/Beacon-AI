import httpx
import asyncio
import sys
import os

# Ensure we can import app code if needed, but we rely on API
sys.path.append(os.getcwd())

BASE_URL = "http://127.0.0.1:8000/api/v1/public/reports"
ADMIN_URL = "http://127.0.0.1:8000/api/v1/admin/reports"

async def run_chat_simulation():
    print("🚀 Starting Verification Simulation...")
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        # 1. Create Report
        print("1. Creating Report...")
        resp = await client.post(f"{BASE_URL}/create", json={"client_seed": "verifier"})
        if resp.status_code != 200:
            print(f"❌ Failed to create report: {resp.text}")
            return
        
        data = resp.json()
        report_id = data["report_id"]
        token = data["access_token"]
        print(f"✅ Report Created: {report_id}")
        
        # 2. Chat Loop
        messages = [
            "I want to report corruption at the city hall.",
            "It happened at the main permit office.",
            "I saw the clerk taking a bribe.",
            "It was yesterday around 2 PM.",
            "The clerk's name was John Doe.",
            "I have a picture of the transaction.", 
            "That's the full story." # Trigger completion hopefully
        ]
        
        case_id = None
        
        for i, msg in enumerate(messages):
            print(f"   User: {msg}")
            payload = {
                "report_id": report_id,
                "access_token": token,
                "content": msg
            }
            resp = await client.post(f"{BASE_URL}/message", json=payload)
            if resp.status_code != 200:
                print(f"❌ Message failed: {resp.text}")
                break
            
            bot_resp = resp.json()
            reply = bot_resp["content"]
            print(f"   Bot: {reply}")
            
            if "BCN" in reply or bot_resp.get("next_step") == "SUBMITTED":
                print("🎉 Case Submitted!")
                if "BCN" in reply:
                     # manual extract if needed, but backend stores it
                     pass
                break
            
            await asyncio.sleep(1)
        
        # 3. Verify Database (via Admin API if exists, or just we trust logs? 
        # or we inspect DB directly? 
        # We don't have auth for admin API easily setup in this script without login.
        # Let's check via a direct sqlite check if possible or trust the logs/console)
        
        print("\n🔎 Verifying Score in Database (Polling for Background Task)...")
        import sqlite3
        
        # Poll for up to 30 seconds
        for attempt in range(10):
            try:
                await asyncio.sleep(3) # Wait 3s between checks
                
                conn = sqlite3.connect("beacon.db")
                cursor = conn.cursor()
                
                cursor.execute("SELECT credibility_score, incident_summary FROM reports WHERE id = ?", (report_id,))
                row = cursor.fetchone()
                
                if row:
                    score, summary = row
                    if score is not None: # Score populated
                        print(f"✅ Report Found in DB. Attempt {attempt+1}")
                        print(f"   Score: {score}")
                        print(f"   Summary: {summary[:100]}..." if summary else "   Summary: N/A")
                        
                        if score > 0:
                             print("✅ SUCCESS: Credibility Score Generated (Background)!")
                             conn.close()
                             return
                    else:
                        print(f"⏳ Attempt {attempt+1}: Score not yet populated...")
                else:
                    print(f"❌ Report not found in DB! (Attempt {attempt+1})")
                    
                conn.close()
                
            except Exception as e:
                print(f"❌ DB Check failed: {e}")
        
        print("❌ TIMEOUT: Score was not generated within 30 seconds.")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_chat_simulation())
