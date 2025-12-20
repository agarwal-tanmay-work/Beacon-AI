import asyncio
import httpx

# LATEST NEW API KEY
API_KEY = "AIzaSyB4Nj2diE2eW0Y070Ov3Z0gQqf4JV2j5HU"

async def check():
    print(f"Testing Newest API Key: {API_KEY[:10]}...")
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={API_KEY}"
    payload = {"contents": [{"parts": [{"text": "Hello, say just 'OK' please"}]}]}
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, timeout=15.0)
            print(f"Status: {resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                if "candidates" in data:
                    text = data["candidates"][0]["content"]["parts"][0]["text"]
                    print(f"SUCCESS: LLM said: {text}")
                else:
                    print(f"ERROR: No candidates. {data}")
            else:
                print(f"ERROR: {resp.text[:500]}")
    except Exception as e:
        print(f"EXCEPTION: {e}")

if __name__ == "__main__":
    asyncio.run(check())
