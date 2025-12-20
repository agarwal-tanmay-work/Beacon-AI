import asyncio
import httpx

API_KEY = "AIzaSyB4Nj2diE2eW0Y070Ov3Z0gQqf4JV2j5HU"
MODELS = [
    "gemini-1.5-flash", "gemini-1.5-flash-latest", "gemini-1.5-flash-8b", 
    "gemini-1.5-pro", "gemini-1.0-pro", "gemini-pro",
    "gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.0-flash-exp"
]
VERSIONS = ["v1", "v1beta"]

async def check():
    for version in VERSIONS:
        for model in MODELS:
            url = f"https://generativelanguage.googleapis.com/{version}/models/{model}:generateContent?key={API_KEY}"
            payload = {"contents": [{"parts": [{"text": "OK"}]}]}
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.post(url, json=payload, timeout=5.0)
                    if resp.status_code == 200:
                        print(f"WINNER: {version}/{model}")
                    elif resp.status_code == 429:
                        print(f"QUOTA: {version}/{model}")
                    # else: skip 404/400
            except:
                pass

if __name__ == "__main__":
    asyncio.run(check())
