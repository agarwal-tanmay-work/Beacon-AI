
import urllib.request
import json
import time
import sys

BASE_URL = "http://localhost:8000/api/v1/public/reports"

def post_json(url, data):
    req = urllib.request.Request(
        url, 
        data=json.dumps(data).encode('utf-8'), 
        headers={'Content-Type': 'application/json'}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return response.getcode(), json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8')
    except Exception as e:
        return 0, str(e)

def test_flow():
    print(f"[TEST] Target: {BASE_URL}")
    
    # 1. Create
    print("[TEST] Creating Report...")
    code, data = post_json(f"{BASE_URL}/create", {"client_seed": "native_test"})
    print(f"[TEST] Create Result: {code}")
    
    if code != 200:
        print(f"[TEST] Aborting: {data}")
        return

    report_id = data["report_id"]
    token = data["access_token"]
    print(f"[TEST] Report ID: {report_id}")
    
    # 2. Message
    print("[TEST] Sending Message...")
    start = time.time()
    code, resp = post_json(f"{BASE_URL}/message", {
        "report_id": report_id,
        "access_token": token,
        "content": "This is a native test message to check for hangs."
    })
    duration = time.time() - start
    print(f"[TEST] Message Result: {code} (Time: {duration:.2f}s)")
    print(f"[TEST] Body: {resp}")

if __name__ == "__main__":
    test_flow()
