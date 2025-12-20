import asyncio
import httpx

API_KEY = "AIzaSyB4Nj2diE2eW0Y070Ov3Z0gQqf4JV2j5HU"

async def check():
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={API_KEY}"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=10.0)
            if resp.status_code == 200:
                data = resp.json()
                print("AVAILABLE MODELS:")
                for m in data.get("models", []):
                    print(f" - {m['name']}")
            else:
                print(f"FAIL: {resp.status_code} - {resp.text}")
    except Exception as e:
        print(f"EXCEPTION: {e}")

if __name__ == "__main__":
    asyncio.run(check())
