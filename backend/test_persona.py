import urllib.request
import json
import time

BASE_URL = "http://127.0.0.1:8000/api/v1/public/reports"

def make_request(url, payload):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        print(f"Request Error: {e}")
        return {"content": "Error"}

def test_full_flow():
    print("--- Testing Granular Data Collection ---")
    
    # 1. Start session
    print("[1] Creating session...")
    seed = f"test-{int(time.time())}"
    resp = make_request(f"{BASE_URL}/create", {"client_seed": seed})
    report_id = resp["report_id"]
    token = resp["access_token"]
    
    # 2. What
    print("\n[2] Sending 'I was bribed'...")
    resp = make_request(f"{BASE_URL}/message", {
        "report_id": report_id,
        "access_token": token,
        "content": "I was bribed by a police officer while coming home."
    })
    print(f"RESPONSE: {resp['content']}")
    
    # 3. Where (Partial)
    print("\n[3] Sending Partial Location 'Sector 20'...")
    resp = make_request(f"{BASE_URL}/message", {
        "report_id": report_id,
        "access_token": token,
        "content": "It happened at Sector 20"
    })
    print(f"RESPONSE: {resp['content']}")
    
    # 4. Where (Complete)
    print("\n[4] Sending City 'Gurugram'...")
    resp = make_request(f"{BASE_URL}/message", {
        "report_id": report_id,
        "access_token": token,
        "content": "It's in Gurugram city"
    })
    print(f"RESPONSE: {resp['content']}")

    # 5. When (Partial)
    print("\n[5] Sending Date 'Yesterday'...")
    resp = make_request(f"{BASE_URL}/message", {
        "report_id": report_id,
        "access_token": token,
        "content": "It happened yesterday"
    })
    print(f"RESPONSE: {resp['content']}")
    
    # 6. When (Complete)
    print("\n[6] Sending Time 'at 2pm'...")
    resp = make_request(f"{BASE_URL}/message", {
        "report_id": report_id,
        "access_token": token,
        "content": "it was around 2pm"
    })
    print(f"RESPONSE: {resp['content']}")

    # 7. Who
    print("\n[7] Sending Officer details...")
    resp = make_request(f"{BASE_URL}/message", {
        "report_id": report_id,
        "access_token": token,
        "content": "I don't know the name but he was a traffic inspector."
    })
    print(f"RESPONSE: {resp['content']}")

    # 8. Evidence
    print("\n[8] Sending Evidence status...")
    resp = make_request(f"{BASE_URL}/message", {
        "report_id": report_id,
        "access_token": token,
        "content": "I have no proof."
    })
    print(f"RESPONSE: {resp['content']}")

    # 9. Anonymous/Submit
    print("\n[9] Sending Anonymous...")
    resp = make_request(f"{BASE_URL}/message", {
        "report_id": report_id,
        "access_token": token,
        "content": "Keep me anonymous"
    })
    print(f"RESPONSE: {resp['content']}")
    if "case_id" in resp:
        print(f"CASE ID: {resp['case_id']}")

if __name__ == "__main__":
    test_full_flow()
