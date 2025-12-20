"""
Test with Google's recommended 45 second wait time
"""
import urllib.request
import urllib.error
import json
import time

API_KEY = "AIzaSyAuXMtZchaq1l-pZ29RN_qTLRlc6GgeEZI"

print("=== TESTING WITH 45 SECOND WAIT ===")
print("Google recommended retryDelay: 45s")
print("Waiting 45 seconds before making request...")
print()

for i in range(45, 0, -5):
    print(f"  {i} seconds remaining...")
    time.sleep(5)

print("\nMaking request now...")

url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={API_KEY}"
payload = {"contents": [{"parts": [{"text": "Hello, say hi back in one word"}]}]}

try:
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    
    with urllib.request.urlopen(req, timeout=30) as response:
        result = json.loads(response.read().decode('utf-8'))
        text = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        print(f"\n✅ SUCCESS!")
        print(f"Response: {text}")
        
except urllib.error.HTTPError as e:
    body = e.read().decode('utf-8')
    print(f"\n❌ HTTP {e.code}")
    try:
        error_data = json.loads(body)
        error_details = error_data.get("error", {})
        print(f"Status: {error_details.get('status')}")
        print(f"Message: {error_details.get('message', '')[:150]}")
        for detail in error_details.get("details", []):
            if "retryDelay" in str(detail):
                print(f"Retry Delay: {detail.get('retryDelay')}")
    except:
        print(f"Body: {body[:300]}")
        
except Exception as e:
    print(f"ERROR: {e}")
