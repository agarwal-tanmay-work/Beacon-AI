import asyncio
import httpx
import sys
import os

BASE_URL = "http://127.0.0.1:8000/api/v1"

async def test_flow():
    print("--- STARTING BEACON AI HEADLESS VERIFICATION ---")
    
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        # 1. Create Report
        print("\n[1] Creating New Report Session...")
        try:
            res = await client.post("/public/reports/create", json={"client_seed": "test-verifier"})
            if res.status_code != 200:
                print(f"FATAL: Failed to create report. {res.status_code} - {res.text}")
                return
            
            data = res.json()
            report_id = data["report_id"]
            access_token = data["access_token"]
            print(f"SUCCESS: Report ID: {report_id}")
        except Exception as e:
             print(f"FATAL: Endpoint not reachable. {e}")
             return

        # 2. Send Greeting
        print("\n[2] Sending Initial Greeting ('hello')...")
        payload = {
            "report_id": report_id,
            "access_token": access_token,
            "content": "hello"
        }
        res = await client.post("/public/reports/message", json=payload)
        msg = res.json()
        print(f"LLM RESPONSE: {msg['content']}")
        
        if "unable to process" in msg['content']:
             print("FAIL: Fallback message triggered. Fix did not work.")
        else:
             print("SUCCESS: Natural LLM Response received.")

        # 3. Report Corruption
        print("\n[3] Sending Corruption Report...")
        payload["content"] = "I saw a police officer taking a bribe at the central station."
        res = await client.post("/public/reports/message", json=payload)
        msg = res.json()
        print(f"LLM RESPONSE: {msg['content']}")

    print("\n--- VERIFICATION COMPLETE ---")

if __name__ == "__main__":
    try:
        asyncio.run(test_flow())
    except KeyboardInterrupt:
        pass
