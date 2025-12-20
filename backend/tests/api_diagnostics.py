import asyncio
import httpx

API_KEY = "AIzaSyB4Nj2diE2eW0Y070Ov3Z0gQqf4JV2j5HU"

async def check():
    for version in ["v1", "v1beta"]:
        for model in ["gemini-1.5-flash", "gemini-2.5-flash", "gemini-2.0-flash"]:
            print(f"\n--- Testing Endpoint: {version}, Model: {model} ---")
            url = f"https://generativelanguage.googleapis.com/{version}/models/{model}:generateContent?key={API_KEY}"
            payload = {"contents": [{"parts": [{"text": "Hello"}]}]}
            
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.post(url, json=payload, timeout=10.0)
                    print(f"Status: {resp.status_code}")
                    if resp.status_code != 200:
                        print(f"BODY: {resp.text}")
                    else:
                        print("SUCCESS")
            except Exception as e:
                print(f"EXCEPTION: {e}")

if __name__ == "__main__":
    asyncio.run(check())
