import requests
import json
import sys

BASE_URL = "http://localhost:8000/api/v1"

def test_flow():
    print(f"Testing connectivity to {BASE_URL}...")
    
    # 1. Create Report
    print("\n[1] Creating Report Session...")
    try:
        res = requests.post(f"{BASE_URL}/public/reports/create", json={"client_seed": "debug-script"})
        print(f"Status: {res.status_code}")
        if res.status_code != 200:
            try:
                detail = res.json().get('detail')
                print(f"Error Detail Head:\n{detail[:300]}")
            except:
                print(f"Error Raw: {res.text[:300]}")
            return
        
        data = res.json()
        report_id = data["report_id"]
        access_token = data["access_token"]
        print(f"Success! Report ID: {report_id}")
    except Exception as e:
        print(f"Failed to connect: {e}")
        return

    # 2. Send Message
    print("\n[2] Sending Message...")
    try:
        payload = {
            "report_id": report_id,
            "access_token": access_token,
            "content": "This is a test corruption report."
        }
        res = requests.post(f"{BASE_URL}/public/reports/message", json=payload)
        print(f"Status: {res.status_code}")
        print(f"Response: {res.json()}")
    except Exception as e:
        print(f"Failed to send message: {e}")
        return

    # 3. Simulate Submission (triggering Case ID)
    print("\n[3] Triggering Submission...")
    try:
        payload = {
            "report_id": report_id,
            "access_token": access_token,
            "content": "Please submit this report now."
        }
        res = requests.post(f"{BASE_URL}/public/reports/message", json=payload)
        print(f"Status: {res.status_code}")
        response_data = res.json()
        print(f"Response: {response_data}")
        
        if response_data.get("next_step") == "SUBMITTED":
            print(f"\n✅ SUBMISSION SUCCESSFUL. Case ID: {response_data.get('case_id')}")
        else:
            print("\n❌ Submission did not trigger.")
            
    except Exception as e:
        print(f"Failed to submit: {e}")

if __name__ == "__main__":
    test_flow()
