"""Item lookup and search routes backed by H-pun/growtopia-api's items.dat parser."""

from fastapi import APIRouter, HTTPException, Query
from app.core.items_parser import items_index
from app.schemas import ItemRecord, ItemSearchResponse

router = APIRouter(prefix="/items", tags=["items"])


@router.get("/lookup", response_model=ItemRecord)
async def lookup_item(q: str = Query(..., min_length=1, description="Item name or ID")) -> ItemRecord:
    item = items_index.lookup(q)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Item '{q}' not found in items.dat")
    return item


@router.get("/search", response_model=ItemSearchResponse)
async def search_items(
    q: str = Query(default="", description="Search substring"),
    limit: int = Query(default=10, ge=1, le=25),
    farmable_only: bool = Query(default=False, description="Only return items with grow_time > 0"),
) -> ItemSearchResponse:
    results = items_index.search(q, limit=limit, farmable_only=farmable_only)
    return ItemSearchResponse(
        version=items_index.version,
        total_loaded=len(items_index.items_by_id),
        items=results,
    )
