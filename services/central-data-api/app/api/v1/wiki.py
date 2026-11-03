"""Wiki scraping and 1:00 PM Daily Reset routes."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from app.core.wiki_scraper import wiki_service
from app.schemas import DailyStatusResponse, WikiItemResponse

router = APIRouter(prefix="/wiki", tags=["wiki"])


class DailyOverridePayload(BaseModel):
    daily_challenge: str | None = None
    item1_name: str | None = None
    item1_qty: int = 0
    item2_name: str | None = None
    item2_qty: int = 0
    role_day: str | None = None


@router.get("/item", response_model=WikiItemResponse)
async def get_wiki_item(name: str = Query(..., min_length=1)) -> WikiItemResponse:
    result = await run_in_threadpool(wiki_service.fetch_item, name)
    if result is None:
        raise HTTPException(status_code=404, detail=f"No wiki entry found for '{name}'")
    return result


@router.get("/daily", response_model=DailyStatusResponse)
async def get_daily_status() -> DailyStatusResponse:
    return await run_in_threadpool(wiki_service.get_daily_status)


@router.post("/daily/override", response_model=DailyStatusResponse)
async def override_daily_status(payload: DailyOverridePayload) -> DailyStatusResponse:
    quest_items: list[tuple[str, int]] | None = None
    if payload.item1_name and payload.item2_name:
        quest_items = [
            (payload.item1_name, payload.item1_qty),
            (payload.item2_name, payload.item2_qty),
        ]
    elif payload.item1_name:
        quest_items = [(payload.item1_name, payload.item1_qty)]

    await run_in_threadpool(
        wiki_service.set_daily_override,
        daily_challenge=payload.daily_challenge,
        quest_items=quest_items,
        role_day=payload.role_day,
    )
    return await run_in_threadpool(wiki_service.get_daily_status)
