import asyncio
import httpx
from app.config import settings

async def test_bulk_import():
    url = "http://localhost:8028/api/import/eia/crack-spread-bulk"
    params = {"days": 365}
    # No API key in params, should fallback to env
    
    async with httpx.AsyncClient() as client:
        print(f"Triggering bulk import at {url}...")
        response = await client.post(url, params=params, timeout=60.0)
        print(f"Status: {response.status_code}")
        print(f"Body: {response.text}")

if __name__ == "__main__":
    asyncio.run(test_bulk_import())
