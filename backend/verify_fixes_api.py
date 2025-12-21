
import requests

BASE_URL = "http://localhost:8004/api/v1"

def verify_fixes():
    print("=" * 50)
    print("1. Creating Report Session...")
    print("=" * 50)
    try:
        res = requests.post(f"{BASE_URL}/public/reports/create", json={"client_seed": "test-verify-v2"})
        if res.status_code != 200:
            print(f"FAIL: Session creation returned {res.status_code}")
            print(res.text)
            return
        
        data = res.json()
        report_id = data["report_id"]
        access_token = data["access_token"]
        print(f"PASS: Session Created - {report_id}")
    except Exception as e:
        print(f"FAIL: Connection error - {e}")
        return

    data_form = {"report_id": report_id, "access_token": access_token}

    print("\n" + "=" * 50)
    print("2. Testing Large Upload (>5MB) - Should return 413")
    print("=" * 50)
    large_content = b"0" * (6 * 1024 * 1024)
    files = {"file": ("large_file.bin", large_content, "application/octet-stream")}
    try:
        res_upload = requests.post(f"{BASE_URL}/public/evidence/upload", data=data_form, files=files)
        print(f"Status Code: {res_upload.status_code}")
        if res_upload.status_code == 413:
            print("PASS: Large upload correctly rejected with 413.")
        else:
            print(f"FAIL: Expected 413, got {res_upload.status_code}")
            print(f"Response: {res_upload.text}")
    except Exception as e:
        print(f"FAIL: Request error - {e}")

    print("\n" + "=" * 50)
    print("3. Testing Small Upload (<5MB) - Should return 200")
    print("=" * 50)
    small_content = b"test content for small file"
    files_small = {"file": ("test.txt", small_content, "text/plain")}
    try:
        res_small = requests.post(f"{BASE_URL}/public/evidence/upload", data=data_form, files=files_small)
        print(f"Status Code: {res_small.status_code}")
        if res_small.status_code == 200:
            print("PASS: Small upload accepted.")
        else:
            print(f"FAIL: Expected 200, got {res_small.status_code}")
            print(f"Response: {res_small.text}")
    except Exception as e:
        print(f"FAIL: Request error - {e}")

    print("\n" + "=" * 50)
    print("4. Testing Chat Message")
    print("=" * 50)
    msg_payload = {
        "report_id": report_id,
        "access_token": access_token,
        "content": "Test message."
    }
    try:
        res_msg = requests.post(f"{BASE_URL}/public/reports/message", json=msg_payload)
        print(f"Status Code: {res_msg.status_code}")
        if res_msg.status_code == 200:
            print("PASS: Chat message sent.")
        else:
            print(f"FAIL: Expected 200, got {res_msg.status_code}")
            print(f"Response: {res_msg.text}")
    except Exception as e:
        print(f"FAIL: Request error - {e}")
        
if __name__ == "__main__":
    verify_fixes()
