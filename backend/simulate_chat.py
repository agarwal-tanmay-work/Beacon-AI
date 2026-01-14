
import requests
import os
import json
import time

BASE_URL = "http://localhost:8000/api/v1/public"
IMAGE_PATH = r"C:/Users/priya/.gemini/antigravity/brain/38bf0767-ac56-477f-ba28-b22e254b0acc/uploaded_image_1768419246911.jpg"

def run_chat():
    # 1. Create Report
    print("\n[1] Creating Session...")
    try:
        res = requests.post(f"{BASE_URL}/report/create", json={})
    except Exception as e:
         print(f"Connection Failed: {e}")
         return

    if res.status_code != 200:
        print(f"Failed to create report: {res.text}")
        return
    
    data = res.json()
    report_id = data["report_id"]
    token = data["access_token"]
    print(f"Session Created: {report_id}")
    
    def send_msg(content):
        print(f"\n[USER]: {content}")
        res = requests.post(f"{BASE_URL}/report/message", json={
            "report_id": report_id,
            "access_token": token,
            "content": content
        })
        if res.status_code != 200:
            print(f"Error: {res.text}")
            return ""
        resp_data = res.json()
        sys_msg = resp_data["content"]
        print(f"[AI]: {sys_msg}")
        return sys_msg

    # 2. Chat Flow
    send_msg("hi")
    
    send_msg("hi, I for police officer came to my house about a verification and they demanded 5000 rupees to fix the fee.")
    
    send_msg("master's union said 25 Gurugram")
    
    # 3. CRITICAL TEST: Date Only
    print("\n--- TEST: Sending Date Only ---")
    reply = send_msg("12th January 2026")
    
    if "time" in reply.lower() and "date" not in reply.lower():
            print(">>> PASS: System specifically asked for TIME.")
    elif "time" in reply.lower() and "date" in reply.lower():
            print(">>> WARNING: System asked for Date AND Time (Validation might be loose).")
    else:
            print(">>> FAIL: System did not ask for Time.")

    # Provide Time
    send_msg("2:00 PM")
    
    # Check if it asks for WHO (if missing)
    # It might ask for WHO now.
    
    # 4. CRITICAL TEST: Evidence Upload
    print("\n--- TEST: Evidence Upload ---")
    if os.path.exists(IMAGE_PATH):
        print(f"Uploading file: {IMAGE_PATH}")
        files = {'file': ('evidence.jpg', open(IMAGE_PATH, 'rb'), 'image/jpeg')}
        data = {'report_id': report_id, 'access_token': token}
        
        try:
            res_up = requests.post(f"{BASE_URL}/evidence/upload", data=data, files=files)
            print(f"Upload Status: {res_up.status_code}")
            
            # After upload, send a message to trigger the System Injection reaction
            reply = send_msg("I have uploaded the photo.")
            
            if "location" in reply.lower() or "city" in reply.lower():
                print(">>> FAIL: System Regressed to asking Location.")
            else:
                print(">>> PASS: System acknowledged Evidence without regression.")
        except Exception as e:
            print(f"Upload failed: {e}")
    else:
        print(f"Image file not found at {IMAGE_PATH}")

if __name__ == "__main__":
    run_chat()
