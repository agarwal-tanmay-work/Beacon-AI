import asyncio
import httpx
import json
import uuid

BASE_URL = "http://localhost:8000/api/v1/public/reports"

async def main():
    print("=== Beacon AI Interactive Test ===")
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        # 1. Create session
        client_seed = str(uuid.uuid4())
        try:
            resp = await client.post(f"{BASE_URL}/create", json={"client_seed": client_seed})
            if resp.status_code != 200:
                print(f"Failed to create session: {resp.text}")
                return
            
            data = resp.json()
            report_id = data["report_id"]
            access_token = data["access_token"]
            print(f"Session Created. ID: {report_id}")
            print("Type 'exit' to quit.\n")
        except Exception as e:
            print(f"Connection Error: {e}")
            return

        # 2. Chat loop
        while True:
            user_input = input("You: ")
            if user_input.lower() in ["exit", "quit"]:
                break
            
            payload = {
                "report_id": report_id,
                "access_token": access_token,
                "content": user_input
            }
            
            try:
                resp = await client.post(f"{BASE_URL}/message", json=payload)
                if resp.status_code == 200:
                    ai_data = resp.json()
                    ai_msg = ai_data.get("content") or ai_data.get("assistant_message") or "N/A"
                    print(f"\nBeacon AI: {ai_msg}\n")
                else:
                    print(f"Error: {resp.status_code} - {resp.text}")
            except Exception as e:
                print(f"Error sending message: {e}")

if __name__ == "__main__":
    asyncio.run(main())
