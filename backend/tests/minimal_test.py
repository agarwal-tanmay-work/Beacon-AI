"""
MINIMAL test - no imports except what's absolutely needed.
This will definitively prove if the API key works.
"""
import urllib.request
import urllib.error
import json

API_KEY = "AIzaSyAuXMtZchaq1l-pZ29RN_qTLRlc6GgeEZI"
URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={API_KEY}"

payload = {
    "contents": [{"parts": [{"text": "Say hello"}]}]
}

print("=== MINIMAL API TEST ===")
print(f"URL: {URL[:60]}...")

try:
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(URL, data=data, headers={'Content-Type': 'application/json'})
    
    with urllib.request.urlopen(req, timeout=30) as response:
        result = json.loads(response.read().decode('utf-8'))
        text = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "No text")
        print(f"STATUS: 200 OK")
        print(f"RESPONSE: {text}")
        print("✅ API KEY IS WORKING!")
        
except urllib.error.HTTPError as e:
    print(f"HTTP ERROR: {e.code}")
    print(f"BODY: {e.read().decode('utf-8')[:500]}")
    
except Exception as e:
    print(f"ERROR: {e}")
