import asyncio
import httpx

API_KEY = "AIzaSyB4Nj2diE2eW0Y070Ov3Z0gQqf4JV2j5HU"

async def test_exp():
    print(f"Testing Experimental Model (2.0-flash-exp on v1beta)...")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent?key={API_KEY}"
    
    payload = {
        "system_instruction": {
            "parts": [{"text": "You are Beacon AI, a helpful assistant."}]
        },
        "contents": [
            {"role": "user", "parts": [{"text": "hello"}]}
        ],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 2048
        }
    }
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, timeout=15.0)
            print(f"Status: {resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                print(f"SUCCESS: {text}")
            else:
                print(f"ERROR: {resp.text}")
    except Exception as e:
        print(f"EXCEPTION: {e}")

if __name__ == "__main__":
    asyncio.run(test_exp())
