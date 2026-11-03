"""RTTEX <-> PNG conversion and sprite rendering routes."""

from fastapi import APIRouter, File, HTTPException, Query, Response, UploadFile
from starlette.concurrency import run_in_threadpool

from app.config import settings
from app.core.items_parser import items_index
from app.core.rttex_engine import (
    extract_item_sprite_png,
    pack_png_to_rttex_bytes,
    unpack_rttex_to_png_bytes,
)

router = APIRouter(prefix="/convert", tags=["converter"])


@router.post("/rttex-to-png")
async def convert_rttex_to_png(file: UploadFile = File(...)) -> Response:
    raw_bytes = await file.read()
    try:
        png_bytes = await run_in_threadpool(unpack_rttex_to_png_bytes, raw_bytes)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid .rttex file: {exc}") from exc

    return Response(content=png_bytes, media_type="image/png")


@router.post("/png-to-rttex")
async def convert_png_to_rttex(file: UploadFile = File(...)) -> Response:
    raw_bytes = await file.read()
    try:
        rttex_bytes = await run_in_threadpool(pack_png_to_rttex_bytes, raw_bytes)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid .png file: {exc}") from exc

    return Response(content=rttex_bytes, media_type="application/octet-stream")


@router.get("/sprite")
async def get_sprite(q: str = Query(..., min_length=1)) -> Response:
    item = items_index.lookup(q)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Item '{q}' not found")
    png_bytes = await run_in_threadpool(extract_item_sprite_png, item, settings.textures_dir)
    return Response(content=png_bytes, media_type="image/png")
