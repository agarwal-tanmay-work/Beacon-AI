import asyncio
import httpx

API_KEY = "AIzaSyB4Nj2diE2eW0Y070Ov3Z0gQqf4JV2j5HU"

async def test_folded():
    print(f"Testing Folded Contents (1.5-flash on v1)...")
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={API_KEY}"
    
    # Folded structure (exactly as LLMAgent does)
    contents = [
        {"role": "user", "parts": [{"text": "SYSTEM: You are Beacon AI.\n\nUser: hello"}]},
        {"role": "model", "parts": [{"text": "I understand. Hello! How can I help you today?"}]}
    ]
    
    payload = {
        "contents": contents,
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
    asyncio.run(test_folded())
