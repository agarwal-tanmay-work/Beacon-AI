import httpx
import asyncio

API_KEY = "AIzaSyAuXMtZchaq1l-pZ29RN_qTLRlc6GgeEZI"

async def test_endpoint(name, url, payload):
    print(f"\n--- Testing: {name} ---")
    print(f"URL: {url[:80]}...")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, timeout=30.0)
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "No text")
                print(f"Response: {text[:100]}")
                return name
            else:
                print(f"Error: {response.text[:200]}")
                return None
        except Exception as e:
            print(f"Exception: {e}")
            return None

async def main():
    print("=== COMPREHENSIVE API ENDPOINT DIAGNOSTIC ===")
    
    simple_payload = {
        "contents": [{"parts": [{"text": "Hello"}]}]
    }
    
    # Test different endpoint/model combinations
    tests = [
        ("v1beta + gemini-1.5-flash", 
         f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={API_KEY}",
         simple_payload),
        ("v1beta + gemini-pro", 
         f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={API_KEY}",
         simple_payload),
        ("v1 + gemini-pro", 
         f"https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent?key={API_KEY}",
         simple_payload),
        ("v1beta + gemini-1.5-flash-latest", 
         f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={API_KEY}",
         simple_payload),
        ("v1beta + gemini-2.0-flash", 
         f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={API_KEY}",
         simple_payload),
    ]
    
    working = []
    for name, url, payload in tests:
        result = await test_endpoint(name, url, payload)
        if result:
            working.append(result)
        await asyncio.sleep(0.5)
    
    print("\n=== FINAL RESULTS ===")
    if working:
        print(f"WORKING ENDPOINTS: {working}")
    else:
        print("NO ENDPOINTS WORKING")

if __name__ == "__main__":
    asyncio.run(main())
