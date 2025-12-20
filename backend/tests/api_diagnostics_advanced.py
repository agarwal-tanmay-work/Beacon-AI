import asyncio
import httpx

API_KEY = "AIzaSyB4Nj2diE2eW0Y070Ov3Z0gQqf4JV2j5HU"
# We'll use gemini-1.5-flash as well, just in case it was a naming issue.
MODELS = ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-2.5-flash"]
VERSIONS = ["v1", "v1beta"]

async def check():
    for version in VERSIONS:
        for model in MODELS:
            print(f"\n--- Testing Endpoint: {version}, Model: {model} ---")
            url = f"https://generativelanguage.googleapis.com/{version}/models/{model}:generateContent?key={API_KEY}"
            payload = {
                "system_instruction": {"parts": [{"text": "You are a helpful assistant."}]},
                "contents": [{"role": "user", "parts": [{"text": "Hello"}]}]
            }
            
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.post(url, json=payload, timeout=10.0)
                    print(f"Status: {resp.status_code}")
                    if resp.status_code == 200:
                        print(f"SUCCESS: {resp.json().get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', 'EMPTY')}")
                    else:
                        print(f"BODY: {resp.text[:200]}")
            except Exception as e:
                print(f"EXCEPTION: {e}")

if __name__ == "__main__":
    asyncio.run(check())
