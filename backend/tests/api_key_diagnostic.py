import httpx
import asyncio
import os

# The API key from the .env file
API_KEY = "AIzaSyB7rQqyng9PCApbziDXxgqrf1Iz2cFhklM"

async def test_single_model(model_name):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": "Say hello in one word."}]}],
        "generationConfig": {"maxOutputTokens": 10}
    }
    
    print(f"\n--- Testing {model_name} ---")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, timeout=30.0)
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "No text")
                print(f"Response: {text}")
                return True
            else:
                print(f"Error Body: {response.text[:500]}")
                return False
        except Exception as e:
            print(f"Exception: {e}")
            return False

async def main():
    print("=== GEMINI API KEY DIAGNOSTIC ===")
    print(f"Testing key: {API_KEY[:15]}...")
    
    # Test multiple models to find one that works
    models_to_test = [
        "gemini-1.5-flash",
        "gemini-1.5-pro",
        "gemini-pro",  # Older, might have different quota
    ]
    
    working_models = []
    for model in models_to_test:
        success = await test_single_model(model)
        if success:
            working_models.append(model)
        await asyncio.sleep(1)  # Small delay between tests
    
    print("\n=== RESULTS ===")
    if working_models:
        print(f"Working models: {working_models}")
        print(f"Recommended: {working_models[0]}")
    else:
        print("NO MODELS WORKING - API KEY MAY BE EXHAUSTED OR INVALID")
        print("Please provide a new API key or wait for quota reset.")

if __name__ == "__main__":
    asyncio.run(main())
