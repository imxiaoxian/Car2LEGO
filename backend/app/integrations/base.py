"""Base HTTP client with retry logic for external API calls."""

import httpx
from app.config import settings


class BaseApiClient:
    """Async HTTP client wrapper with timeout and error handling."""

    def __init__(self, base_url: str, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                headers={"User-Agent": "Car2LEGO/0.1"},
            )
        return self._client

    async def get(self, path: str, params: dict | None = None) -> dict:
        client = await self._get_client()
        url = f"{self.base_url}{path}"
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
