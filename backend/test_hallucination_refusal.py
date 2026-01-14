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

def test_hallucination_refusal():
    print("--- Testing Hallucination Loop & Refusal Fix ---")
    
    # 1. Start session
    print("[1] Creating session...")
    seed = f"test-hallucination-{int(time.time())}"
    resp = make_request(f"{BASE_URL}/create", {"client_seed": seed})
    report_id = resp["report_id"]
    token = resp["access_token"]
    
    # 2. Complete Info
    messages = [
        "I was bribed by a police officer.",
        "Sector 20, Gurugram, Haryana",
        "Yesterday at 2pm",
        "It was Inspector Singh"
    ]
    
    for i, msg in enumerate(messages):
        print(f"\n[{i+2}] Sending: {msg}")
        resp = make_request(f"{BASE_URL}/message", {
            "report_id": report_id,
            "access_token": token,
            "content": msg
        })
        print(f"RESPONSE: {resp['content']}")

    # 3. Simulate evidence step (saying no)
    print("\n[6] Sending 'I have no files'...")
    resp = make_request(f"{BASE_URL}/message", {
        "report_id": report_id,
        "access_token": token,
        "content": "I have no files"
    })
    print(f"RESPONSE: {resp['content']}")

    # 4. Refuse contact info
    print("\n[7] Sending 'No' to contact info...")
    resp = make_request(f"{BASE_URL}/message", {
        "report_id": report_id,
        "access_token": token,
        "content": "No"
    })
    print(f"RESPONSE: {resp['content']}")
    
    if "CASE_ID_PLACEHOLDER" in resp['content'] or "BCN" in resp.get('case_id', ''):
        print("\nSUCCESS: Case ID generated after refusal.")
    else:
        print("\nFAILURE: Hallucination detected or Case ID missing.")

if __name__ == "__main__":
    test_hallucination_refusal()
