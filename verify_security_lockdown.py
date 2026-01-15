import urllib.request
import urllib.parse
import json
import sys

BASE_URL = "http://localhost:8000/api/v1"

ADMIN_ROUTES = [
    "/admin/reports/",
    "/admin/evidence/",
]

def test_unauthorized_access():
    print("Testing unauthorized access to admin routes...")
    all_passed = True
    for route in ADMIN_ROUTES:
        url = f"{BASE_URL}{route}"
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req) as response:
                print(f"[FAIL] {route} returned {response.status_code} (Expected 401)")
                all_passed = False
        except urllib.error.HTTPError as e:
            if e.code == 401:
                print(f"[PASS] {route} returned 401 Unauthorized")
            else:
                print(f"[FAIL] {route} returned {e.code} (Expected 401)")
                all_passed = False
        except Exception as e:
            print(f"[ERR] Failed to connect to {url}: {e}")
            all_passed = False
    return all_passed

def test_login_and_authorized_access():
    print("\nTesting login and authorized access...")
    login_url = f"{BASE_URL}/admin/auth/login"
    payload = {
        "username": "beaconai",
        "password": "BeaconAI@26"
    }
    data = json.dumps(payload).encode('utf-8')
    
    try:
        req = urllib.request.Request(login_url, data=data, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req) as response:
            if response.status != 200:
                print(f"[FAIL] Login failed with {response.status}")
                return False
            
            res_body = json.loads(response.read().decode('utf-8'))
            token = res_body.get("access_token")
            print(f"[PASS] Login successful, token received.")
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            # Test one admin route with token
            test_route = ADMIN_ROUTES[0]
            req_auth = urllib.request.Request(f"{BASE_URL}{test_route}", headers=headers)
            with urllib.request.urlopen(req_auth) as res_auth:
                if res_auth.status == 200:
                    print(f"[PASS] {test_route} returned 200 OK with valid token")
                    return True
                else:
                    print(f"[FAIL] {test_route} returned {res_auth.status} with valid token")
                    return False
            
    except urllib.error.HTTPError as e:
        print(f"[FAIL] HTTP Error: {e.code} - {e.reason}")
        print(f"Body: {e.read().decode('utf-8')}")
        return False
    except Exception as e:
        print(f"[ERR] Error during authorized test: {e}")
        return False

if __name__ == "__main__":
    unauth_ok = test_unauthorized_access()
    auth_ok = test_login_and_authorized_access()
    
    if unauth_ok and auth_ok:
        print("\n[SUCCESS] All security checks passed.")
        sys.exit(0)
    else:
        print("\n[FAILURE] Some security checks failed.")
        sys.exit(1)
