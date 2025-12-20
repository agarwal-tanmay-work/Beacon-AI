"""
Detailed diagnostic - examine the exact 429 response and test variations
"""
import urllib.request
import urllib.error
import json
import time

API_KEY = "AIzaSyAuXMtZchaq1l-pZ29RN_qTLRlc6GgeEZI"

def test_model(model_name):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={API_KEY}"
    payload = {"contents": [{"parts": [{"text": "Hi"}]}]}
    
    print(f"\n--- Testing {model_name} ---")
    try:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
        
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            text = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            print(f"✅ SUCCESS: {text[:50]}...")
            return True
            
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8')
        print(f"HTTP {e.code}")
        
        # Parse the error for details
        try:
            error_data = json.loads(body)
            error_details = error_data.get("error", {})
            print(f"Status: {error_details.get('status')}")
            print(f"Message: {error_details.get('message', '')[:100]}")
            
            # Look for retry delay info
            for detail in error_details.get("details", []):
                if "retryDelay" in str(detail):
                    print(f"Retry Delay: {detail.get('retryDelay', 'unknown')}")
        except:
            print(f"Raw: {body[:200]}")
        return False
        
    except Exception as e:
        print(f"ERROR: {e}")
        return False

print("=== DETAILED API DIAGNOSTIC ===")
print(f"API Key: {API_KEY[:15]}...{API_KEY[-5:]}")
print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")

# Test multiple models
models = [
    "gemini-2.0-flash",
    "gemini-1.5-flash", 
    "gemini-pro",
    "gemini-1.0-pro",  # Older version
]

for model in models:
    test_model(model)
    time.sleep(2)  # Small delay between tests

print("\n=== DIAGNOSTIC COMPLETE ===")
