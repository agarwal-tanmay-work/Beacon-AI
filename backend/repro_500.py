
import asyncio
import httpx
import sys

BASE_URL = "http://localhost:8000/api/v1/public/reports"

async def trigger_500():
    async with httpx.AsyncClient(timeout=60.0) as client:
        print("1. Creating Report...")
        try:
            resp = await client.post(f"{BASE_URL}/create", json={"client_seed": "debug_seed_500"})
            if resp.status_code != 200:
                print(f"FAILED: Create Report returned {resp.status_code}: {resp.text}")
                return
            data = resp.json()
            report_id = data["report_id"]
            token = data["access_token"]
            print(f"   Success! Report ID: {report_id}")
        except Exception as e:
            print(f"FAILED: Connection error: {e}")
            return

        # Simulate flow to trigger submission
        messages = [
            "Report corruption.",
            "Bribe at police station.",
            "Mumbai yesterday.",
            "Officer Patil.",
            "No evidence." # Should trigger CASE_ID_PLACEHOLDER -> Submission
        ]

        for i, msg in enumerate(messages):
            print(f"2.{i+1} Sending: '{msg}'")
            payload = {"report_id": report_id, "access_token": token, "content": msg}
            try:
                resp = await client.post(f"{BASE_URL}/message", json=payload)
                if resp.status_code == 500:
                    print("\n✅ SUCCESS: Triggered 500 Error!")
                    return
                elif resp.status_code != 200:
                    print(f"   Response: {resp.status_code}")
            except Exception as e:
                 print(f"FAILED: Connection error during message: {e}")

if __name__ == "__main__":
    asyncio.run(trigger_500())
