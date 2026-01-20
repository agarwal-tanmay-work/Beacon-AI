import httpx
import asyncio
import sys
import os
import json
from datetime import datetime

BASE_URL = "http://localhost:8000/api/v1"

async def chat():
    print("========================================")
    print("   BEACON-AI: INTERACTIVE TERMINAL")
    print("========================================")
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        # 1. Initialize Report
        print("\n[SYSTEM] Initializing secure reporting session...")
        try:
            res = await client.post(f"{BASE_URL}/public/reports/create", json={"client_seed": "terminal_user"})
            if res.status_code != 200:
                print(f"FAILED to start session: {res.text}")
                return
            
            data = res.json()
            report_id = data["report_id"]
            access_token = data["access_token"]
            print(f"[SYSTEM] Session started. ID: {report_id}")
            print(f"[AI] {data['message']}")
        except Exception as e:
            print(f"CONNECTION ERROR: {e}")
            return

        # 2. Chat Loop
        while True:
            try:
                user_msg = input("\n[YOU]: ").strip()
                if user_msg.lower() in ["exit", "quit", "bye"]:
                    print("[SYSTEM] Exiting chat.")
                    break
                
                if not user_msg:
                    continue

                # Send message
                msg_payload = {
                    "report_id": report_id,
                    "access_token": access_token,
                    "content": user_msg
                }
                
                print("[SYSTEM] AI is thinking...")
                res = await client.post(f"{BASE_URL}/public/reports/message", json=msg_payload)
                
                if res.status_code != 200:
                    print(f"\n[ERROR] Server returned {res.status_code}: {res.text}")
                    continue
                
                resp_data = res.json()
                ai_content = resp_data.get("content", "")
                next_step = resp_data.get("next_step", "ACTIVE")
                
                print(f"\n[AI]: {ai_content}")
                
                # Check for completion
                if next_step == "COMPLETED" or resp_data.get("case_id"):
                    print("\n" + "="*40)
                    print("         REPORT FINALIZED")
                    print("="*40)
                    print(f"CASE ID:    {resp_data.get('case_id')}")
                    print(f"SECRET KEY: {resp_data.get('secret_key')}")
                    print("="*40)
                    print("Please save these credentials to track your report.")
                    break
                    
            except KeyboardInterrupt:
                print("\n[SYSTEM] Chat interrupted.")
                break
            except Exception as e:
                print(f"\n[ERROR] {e}")
                break

if __name__ == "__main__":
    try:
        asyncio.run(chat())
    except EOFError:
        pass
