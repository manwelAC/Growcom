"""Pydantic v2 response schemas for the Central Data API."""

from __future__ import annotations
from typing import Any
from pydantic import BaseModel, Field


class ItemRecord(BaseModel):
    id: int
    name: str
    description: str = ""
    rarity: int = 0
    grow_time_seconds: int = Field(default=0, description="Grow/bloom time in seconds")
    hardness_hits: int = Field(default=0, description="Fist hits required to break")
    file_name: str = ""
    tex_x: int = 0
    tex_y: int = 0
    item_type: int = 0
    collision_type: int = 0
    clothing_type: int = 0
    max_hold: int = 200
    seed1: int = 0
    seed2: int = 0
    splice_recipe: str = ""


class ItemSearchResponse(BaseModel):
    version: int
    total_loaded: int
    items: list[ItemRecord]


class WikiItemResponse(BaseModel):
    title: str
    url: str
    rarity: int | str = "None"
    description: str = ""
    properties: list[str] = Field(default_factory=list)
    item_type: str | list[str] = ""
    chi: str = "None"
    grow_time: str = ""
    gems_drop: str = ""
    hardness: dict[str, int | None] = Field(default_factory=dict)
    recipes: list[str] = Field(default_factory=list)
    sprites: dict[str, str] = Field(default_factory=dict)


class DailyQuestItem(BaseModel):
    name: str
    quantity: int = 0
    rarity: int | str | None = None
    recipe: list[str] = Field(default_factory=list)
    sprite_url: str | None = None


class DailyStatusResponse(BaseModel):
    gt_date: str
    gt_time: str
    local_reset_timestamp: int
    role_day: str
    role_day_bonus: str
    tomorrow_role_day: str
    daily_challenge: str
    daily_quest_items: list[DailyQuestItem] = Field(default_factory=list)
    daily_quest_source: str = "auto"
    wotd_name: str = "UNKNOWN"
    wotd_image_url: str = ""
    online_users: int | str = "N/A"
    extra: dict[str, Any] = Field(default_factory=dict)
