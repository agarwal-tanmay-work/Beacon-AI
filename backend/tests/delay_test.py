import httpx
import asyncio

# NEW API KEY
API_KEY = "AIzaSyAuXMtZchaq1l-pZ29RN_qTLRlc6GgeEZI"

async def test_with_delay():
    print("=== TESTING WITH 30 SECOND DELAY ===")
    print("Waiting 30 seconds before making request to allow rate limit reset...")
    await asyncio.sleep(30)
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": "Hi"}]}]
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, timeout=30.0)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "No text")
            print(f"Response: {text}")
            print("✅ SUCCESS!")
            return True
        else:
            print(f"Error: {response.text[:300]}")
            return False

if __name__ == "__main__":
    asyncio.run(test_with_delay())
