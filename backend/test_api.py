import httpx
import json
import asyncio

async def test():
    url = "http://127.0.0.1:8000/api/v1/public/reports/create"
    payload = {"client_seed": "test_seed_123"}
    headers = {"Content-Type": "application/json"}

    try:
        # Check Health
        health_url = "http://127.0.0.1:8000/health"
        print(f"GET {health_url}")
        async with httpx.AsyncClient() as client:
            resp = await client.get(health_url)
            print(f"Health Status: {resp.status_code}")
            
            # Check Create
            print(f"POST {url}")
            response = await client.post(url, json=payload, headers=headers)
            print(f"Create Status: {response.status_code}")
            print(f"Body: {response.text}")
    except Exception as e:
        print(f"Failed: {repr(e)}")

if __name__ == "__main__":
    asyncio.run(test())
