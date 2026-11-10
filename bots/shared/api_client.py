"""
Async HTTP client used by the Discord bots to query the Central Data API.
Bots never parse binary files or scrape websites directly; they always call this client.
"""

from __future__ import annotations

from typing import Any
import httpx


class CentralDataClient:
    """Lightweight async wrapper for the Growcom Central Data API."""

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self.base_url = base_url.rstrip("/")
        headers = {"X-Internal-API-Key": api_key} if api_key else {}
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=httpx.Timeout(20.0, connect=5.0),
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def health(self) -> dict[str, Any]:
        resp = await self._client.get("/api/v1/health")
        resp.raise_for_status()
        return resp.json()

    async def get_item(self, query: str) -> dict[str, Any] | None:
        """Fetch parsed item stats by exact/partial name or item ID."""
        resp = await self._client.get("/api/v1/items/lookup", params={"q": query})
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    async def search_items(self, query: str, limit: int = 10, farmable_only: bool = False) -> list[dict[str, Any]]:
        """Search items in items.dat for autocomplete or list results."""
        resp = await self._client.get(
            "/api/v1/items/search",
            params={"q": query, "limit": limit, "farmable_only": farmable_only},
        )
        resp.raise_for_status()
        return resp.json().get("items", [])

    async def get_wiki_item(self, item_name: str) -> dict[str, Any] | None:
        """Fetch scraped Wiki data (description, splice recipe, combiners, info)."""
        resp = await self._client.get("/api/v1/wiki/item", params={"name": item_name})
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    async def get_daily_status(self) -> dict[str, Any]:
        """Fetch today's Role Day, Daily Quest, Daily Challenge, and Server Status."""
        resp = await self._client.get("/api/v1/wiki/daily")
        resp.raise_for_status()
        return resp.json()

    async def convert_rttex_to_png(self, filename: str, raw_bytes: bytes) -> bytes:
        """Send a raw .rttex file to the Central Data API and receive decoded .png bytes."""
        files = {"file": (filename, raw_bytes, "application/octet-stream")}
        resp = await self._client.post("/api/v1/convert/rttex-to-png", files=files)
        resp.raise_for_status()
        return resp.content

    async def convert_png_to_rttex(self, filename: str, raw_bytes: bytes) -> bytes:
        """Send a .png file to the Central Data API and receive encoded .rttex bytes."""
        files = {"file": (filename, raw_bytes, "image/png")}
        resp = await self._client.post("/api/v1/convert/png-to-rttex", files=files)
        resp.raise_for_status()
        return resp.content

    async def get_item_sprite(self, query: str) -> bytes | None:
        """Render and return a PNG sprite for the given item name or ID."""
        resp = await self._client.get("/api/v1/convert/sprite", params={"q": query})
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.content

    async def get_world_render(self, query: str) -> dict[str, Any] | None:
        """Fetch world render metadata and S3 403-bypass URL."""
        resp = await self._client.get("/api/v1/world/render", params={"query": query})
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()
