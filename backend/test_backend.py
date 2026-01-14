
import httpx
import asyncio
import sys
import time
from datetime import datetime

URL = "http://localhost:8000/api/v1/public/reports"

async def test_flow():
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            print("[TEST] Step 1: Creating Report...")
            r1 = await client.post(f"{URL}/create", json={"client_seed": "test_seed_123"})
            print(f"[TEST] Create Response: {r1.status_code}")
            if r1.status_code != 200:
                print(f"[TEST] Error: {r1.text}")
                return
                
            data = r1.json()
            report_id = data["report_id"]
            token = data["access_token"]
            print(f"[TEST] Report ID: {report_id}")
            
            print("[TEST] Step 2: Sending Message...")
            start = time.time()
            r2 = await client.post(f"{URL}/message", json={
                "report_id": report_id,
                "access_token": token,
                "content": "I was asked for a bribe of 500 dollars at the customs office in New York."
            })
            duration = time.time() - start
            
            print(f"[TEST] Message Response: {r2.status_code} (took {duration:.2f}s)")
            print(f"[TEST] Response Body: {r2.text}")
            
        except Exception as e:
            print(f"[TEST] FAILED with exception: {e}")

if __name__ == "__main__":
    asyncio.run(test_flow())
