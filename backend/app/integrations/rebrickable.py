"""Rebrickable API client — LEGO set data, parts catalog, and MOC information.

Rebrickable API v3: https://rebrickable.com/api/v3/
Requires an API key (free tier available).
"""

from app.config import settings
from app.integrations.base import BaseApiClient

REBRICKABLE_BASE_URL = "https://rebrickable.com/api/v3/lego"


class RebrickableClient(BaseApiClient):
    def __init__(self, api_key: str | None = None):
        super().__init__(base_url=REBRICKABLE_BASE_URL, timeout=15.0)
        self.api_key = api_key or settings.rebrickable_api_key

    async def _get_client(self):
        client = await super()._get_client()
        if self.api_key:
            client.headers["Authorization"] = f"key {self.api_key}"
        return client

    async def get_set(self, set_num: str) -> dict | None:
        """Get details for a specific LEGO set."""
        try:
            return await self.get(f"/sets/{set_num}/")
        except Exception:
            return None

    async def get_set_parts(self, set_num: str) -> list[dict]:
        """Get all parts in a LEGO set with quantities and colors."""
        try:
            data = await self.get(f"/sets/{set_num}/parts/", {"page_size": 1000})
            return data.get("results", [])
        except Exception:
            return []

    async def get_part(self, part_num: str) -> dict | None:
        """Get details for a specific part."""
        try:
            return await self.get(f"/parts/{part_num}/")
        except Exception:
            return None

    async def search_sets(self, query: str, page_size: int = 20) -> list[dict]:
        """Search LEGO sets by keyword."""
        try:
            data = await self.get(
                "/sets/",
                {"search": query, "page_size": page_size, "ordering": "-year"},
            )
            return data.get("results", [])
        except Exception:
            return []

    async def get_colors(self) -> list[dict]:
        """Get all LEGO colors."""
        try:
            data = await self.get("/colors/", {"page_size": 500})
            return data.get("results", [])
        except Exception:
            return []


# Singleton
rebrickable_client = RebrickableClient()
