import httpx
import asyncio
import sys
import json
from uuid import UUID

BASE_URL = "http://127.0.0.1:8000/api/v1/public/reports"

async def chat():
    print("      \033[1;36m*** BEACON AI - ANONYMOUS REPORTING INTERFACE ***\033[0m")
    print("      \033[0;33mSecure session starting...\033[0m\n")

    async with httpx.AsyncClient(timeout=120.0) as client:
        # 1. Create session
        try:
            resp = await client.post(f"{BASE_URL}/create", json={"client_seed": "cli_user"})
            if resp.status_code != 200:
                print(f"Error creating session: {resp.text}")
                return
            
            data = resp.json()
            report_id = data["report_id"]
            token = data["access_token"]
            welcome_msg = data["message"]
            print(f"[\033[1;32mSYSTEM\033[0m]: {welcome_msg}\n")
        except Exception as e:
            print(f"Connection Error: {e}")
            return

        # 2. Loop chat
        while True:
            try:
                user_input = input("[\033[1;34mUSER\033[0m]: ")
                if not user_input.strip():
                    continue
                if user_input.lower() in ["exit", "quit", "/exit"]:
                    print("Exiting session.")
                    break

                payload = {
                    "report_id": report_id,
                    "access_token": token,
                    "content": user_input
                }
                
                print("[\033[1;32mAI\033[0m]: Thinking...", end="\r")
                resp = await client.post(f"{BASE_URL}/message", json=payload)
                print(" " * 20, end="\r") # Clear thinking line

                if resp.status_code != 200:
                    print(f"[\033[1;31mERROR\033[0m]: {resp.status_code} - {resp.text}")
                    continue
                
                bot_data = resp.json()
                reply = bot_data.get("content", "")
                print(f"[\033[1;32mAI\033[0m]: {reply}\n")
                
                if bot_data.get("next_step") == "SUBMITTED":
                    case_id = bot_data.get("case_id")
                    print(f"\033[1;32m✅ SUCCESS: Your Case ID is {case_id}\033[0m")
                    print("The report has been stored in Supabase. You can exit now.")
                    break
                    
            except KeyboardInterrupt:
                print("\nSession ended by user.")
                break
            except Exception as e:
                print(f"\033[1;31mUnexpected Error\033[0m: {e}")
                break

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(chat())
