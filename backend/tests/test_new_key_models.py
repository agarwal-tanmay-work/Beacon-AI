import httpx
import asyncio
import os

API_KEY = "AIzaSyB7rQqyng9PCApbziDXxgqrf1Iz2cFhklM"

async def test_model(model_name):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": "Hello, how are you today?"}]}]
    }
    
    print(f"--- Testing {model_name} ---")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, timeout=10.0)
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                print("Response OK")
                return True
            else:
                print(f"Error: {response.text}")
                return False
        except Exception as e:
            print(f"Exception: {e}")
            return False

async def main():
    models = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash-exp"]
    for m in models:
        await test_model(m)
        await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(main())
