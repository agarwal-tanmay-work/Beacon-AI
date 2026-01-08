import httpx
import asyncio
import sys

async def test_create():
    print("Testing /create endpoint...")
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post('http://127.0.0.1:8000/api/v1/public/reports/create', json={'client_seed': 'test'})
            print(f"Status Code: {r.status_code}")
            print(f"Response: {r.text}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_create())
