import httpx
import asyncio

# NEW API KEY FROM USER
API_KEY = "AIzaSyAuXMtZchaq1l-pZ29RN_qTLRlc6GgeEZI"

async def test_api():
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": "Say hello in one word."}]}],
        "generationConfig": {"maxOutputTokens": 10}
    }
    
    print("=== TESTING NEW API KEY ===")
    print(f"Key: {API_KEY[:15]}...")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, timeout=30.0)
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "No text")
                print(f"Response: {text}")
                print("\n✅ API KEY IS WORKING!")
                return True
            else:
                print(f"Error: {response.text[:500]}")
                print("\n❌ API KEY FAILED")
                return False
        except Exception as e:
            print(f"Exception: {e}")
            return False

if __name__ == "__main__":
    asyncio.run(test_api())
