"""Growtopia World Render and 403 bypass routes."""

from __future__ import annotations

import re
from typing import Any
from fastapi import APIRouter, HTTPException, Query
import httpx

router = APIRouter(prefix="/world", tags=["world"])

S3_BASE_URL = "https://s3.amazonaws.com/world.growtopiagame.com"


def extract_world_name(raw: str) -> str | None:
    raw_str = raw.strip()
    match = re.search(
        r"(?:growtopiagame\.com/worlds/|world\.growtopiagame\.com/)([A-Za-z0-9_-]+)",
        raw_str,
        re.IGNORECASE,
    )
    if match:
        name = match.group(1).strip()
    else:
        name = re.sub(r"[^A-Za-z0-9_-]", "", raw_str).strip()
    return name.upper() if name else None


@router.get("/render")
async def get_world_render(query: str = Query(..., description="World name or render URL")) -> dict[str, Any]:
    world_name = extract_world_name(query)
    if not world_name:
        raise HTTPException(status_code=400, detail="Invalid world name or URL.")

    s3_key = f"{world_name.lower()}.png"
    s3_url = f"{S3_BASE_URL}/{s3_key}"

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            head_resp = await client.head(s3_url)
            if head_resp.status_code == 200:
                length = head_resp.headers.get("content-length")
                return {
                    "world_name": world_name,
                    "s3_url": s3_url,
                    "exists": True,
                    "content_length": int(length) if length and length.isdigit() else None,
                    "last_modified": head_resp.headers.get("last-modified"),
                    "etag": head_resp.headers.get("etag", "").strip('"'),
                }
            return {
                "world_name": world_name,
                "s3_url": s3_url,
                "exists": False,
                "status_code": head_resp.status_code,
            }
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Failed to check world render: {exc}") from exc
