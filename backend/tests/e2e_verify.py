import asyncio
import httpx
import sys
import os

BASE_URL = "http://127.0.0.1:8000/api/v1"

async def test_complete_flow():
    print("--- STARTING BEACON AI END-TO-END VERIFICATION ---")
    
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=60.0) as client:
        # 1. Create Report
        print("\n[1] Creating New Report Session...")
        res = await client.post("/public/reports/create", json={"client_seed": "e2e-test"})
        if res.status_code != 200:
            print(f"FATAL: Failed to create report. {res.status_code}")
            return
        
        data = res.json()
        report_id = data["report_id"]
        access_token = data["access_token"]
        print(f"SUCCESS: Report ID: {report_id}")

        # 2. Simulate Conversation
        messages = [
            "hello",
            "I saw an official taking a bribe for a building permit.",
            "It happened at the City Municipal Office yesterday.",
            "I was waiting in the lobby when a contractor handed over an envelope full of cash to the Head of Permits."
        ]
        
        for i, text in enumerate(messages):
            print(f"\n[USER]: {text}")
            payload = {
                "report_id": report_id,
                "access_token": access_token,
                "content": text
            }
            res = await client.post("/public/reports/message", json=payload)
            if res.status_code != 200:
                print(f"ERROR: {res.status_code} - {res.text}")
                continue
                
            msg = res.json()
            response_content = msg['content']
            print(f"[BEACON AI]: {response_content}")
            
            # Check for case ID at the end (usually happens after several turns)
            if "BCN" in response_content and i > 1:
                print("\n✅ CASE ID DETECTED!")
                if len(re.search(r'BCN[A-Z0-9]{12}', response_content).group(0)) == 15:
                    print("✅ CASE ID FORMAT IS CORRECT (15 CHARS)")
                else:
                    print("❌ CASE ID FORMAT IS INCORRECT")

    print("\n--- VERIFICATION COMPLETE ---")

if __name__ == "__main__":
    import re
    asyncio.run(test_complete_flow())
