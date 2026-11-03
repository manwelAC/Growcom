"""
Wrapper around `growtopia.itemsdat_parser` (from H-pun/growtopia-api).
Loads, parses, and indexes `items.dat` (including v22–v27 schema extensions for all 16,490+ items)
into memory for O(1) ID and name lookups.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, BinaryIO

from growtopia.itemsdat_parser import (
    STRING,
    STRING_XOR,
    decrypt_item_name,
    field,
    get_generic_template,
    itemsdat_info,
    parse_number,
    parse_string,
)
from app.schemas import ItemRecord

logger = logging.getLogger("growcom.items_parser")

STARTER_FALLBACK_ITEMS: list[dict[str, Any]] = [
    {"id": 0, "name": "Blank", "rarity": 999, "bloom_time": 0, "hardness": 0, "file_name": "tiles_page1.rttex", "tex_x": 0, "tex_y": 0},
    {"id": 2, "name": "Dirt", "rarity": 1, "bloom_time": 31, "hardness": 18, "file_name": "tiles_page1.rttex", "tex_x": 2, "tex_y": 0},
    {"id": 4, "name": "Lava", "rarity": 1, "bloom_time": 30, "hardness": 24, "file_name": "tiles_page1.rttex", "tex_x": 4, "tex_y": 0, "seed1": 2, "seed2": 10},
    {"id": 10, "name": "Rock", "rarity": 1, "bloom_time": 60, "hardness": 36, "file_name": "tiles_page1.rttex", "tex_x": 5, "tex_y": 0},
    {"id": 14, "name": "Cave Background", "rarity": 1, "bloom_time": 23, "hardness": 18, "file_name": "tiles_page1.rttex", "tex_x": 7, "tex_y": 0},
    {"id": 100, "name": "Wood Block", "rarity": 2, "bloom_time": 55, "hardness": 24, "file_name": "tiles_page1.rttex", "tex_x": 1, "tex_y": 3, "seed1": 2, "seed2": 4},
    {"id": 242, "name": "World Lock", "rarity": 999, "bloom_time": 0, "hardness": 72, "file_name": "tiles_page2.rttex", "tex_x": 2, "tex_y": 1},
    {"id": 1796, "name": "Diamond Lock", "rarity": 999, "bloom_time": 0, "hardness": 72, "file_name": "tiles_page5.rttex", "tex_x": 4, "tex_y": 2},
    {"id": 4584, "name": "Pepper Tree", "rarity": 67, "bloom_time": 90953, "hardness": 30, "file_name": "tiles_page10.rttex", "tex_x": 1, "tex_y": 4},
    {"id": 5666, "name": "Laser Grid", "rarity": 73, "bloom_time": 115255, "hardness": 24, "file_name": "tiles_page12.rttex", "tex_x": 3, "tex_y": 5},
    {"id": 7188, "name": "Blue Gem Lock", "rarity": 999, "bloom_time": 0, "hardness": 72, "file_name": "tiles_page15.rttex", "tex_x": 6, "tex_y": 2},
]


def parse_itemsdat_extended(buffer: BinaryIO) -> dict[str, Any]:
    """
    Extend H-pun/growtopia-api's `parse_itemsdat` template to support items.dat v22 through v27+
    (which adds the in-game `description` string and v23–v25 trailing fields).
    """
    info = itemsdat_info(buffer, calculate=False)
    version = info["version"]
    item_count = info["item_count"]
    template = get_generic_template()

    # Extend H-pun's v21 template for Growtopia v22–v27 items.dat
    template["description"] = field(STRING, version=22)
    template["_unk9"] = field(5, version=23)
    template["_unk10"] = field(STRING, version=24)
    template["_unk11"] = field(5, version=24)
    template["_unk12"] = field(STRING, version=25)

    root: dict[str, Any] = {"version": version, "item_count": item_count, "items": []}
    for i in range(item_count):
        item: dict[str, Any] = {}
        for key, value in template.items():
            if value["version"] > version:
                continue
            if "id" in item and item["id"] != i:
                raise AssertionError(
                    f"Item ID mismatch at index {i} (got {item['id']}, version={version})"
                )
            if value["size"] == STRING_XOR and version >= 3:
                field_value: Any = decrypt_item_name(parse_string(buffer), item["id"])
            elif value["size"] == STRING:
                field_value = parse_string(buffer)
            else:
                field_value = parse_number(buffer, value["size"])
            if not key.startswith("_"):
                item[key] = field_value
        root["items"].append(item)
    return root


class ItemsDatIndex:
    """In-memory index over parsed Growtopia `items.dat` records."""

    def __init__(self) -> None:
        self.version: int = 0
        self.items_by_id: dict[int, ItemRecord] = {}
        self.items_by_name: dict[str, ItemRecord] = {}
        self.using_fallback: bool = True

    def load(self, path: Path) -> None:
        """Load and index `items.dat` using `growtopia.itemsdat_parser`."""
        if path.exists() and path.stat().st_size > 0:
            try:
                with path.open("rb") as buffer:
                    parsed = parse_itemsdat_extended(buffer)
                self.version = int(parsed.get("version", 0))
                raw_items = parsed.get("items", [])
                self._index_records(raw_items)
                self.using_fallback = False
                logger.info(
                    "Loaded items.dat v%s with %d items from %s",
                    self.version,
                    len(self.items_by_id),
                    path,
                )
                return
            except Exception as exc:
                logger.warning("Failed to parse %s (%s). Using starter fallback catalog.", path, exc)

        self.version = 0
        self._index_records(STARTER_FALLBACK_ITEMS)
        self.using_fallback = True
        logger.info("Initialized starter fallback catalog (%d items).", len(self.items_by_id))

    def _index_records(self, raw_items: list[dict[str, Any]]) -> None:
        self.items_by_id.clear()
        self.items_by_name.clear()
        for raw in raw_items:
            name = str(raw.get("name", "")).strip()
            if not name or name.startswith("null_item"):
                continue
            # Skip internal "_seed" duplicate records when indexing by name unless requested
            raw_hardness = int(raw.get("hardness", 0) or 0)
            record = ItemRecord(
                id=int(raw.get("id", 0)),
                name=name,
                description=str(raw.get("description", "") or "").strip(),
                rarity=int(raw.get("rarity", 0) or 0),
                grow_time_seconds=int(raw.get("bloom_time", 0) or 0),
                hardness_hits=max(1, raw_hardness // 6) if raw_hardness > 0 else 0,
                file_name=str(raw.get("file_name", "") or ""),
                tex_x=int(raw.get("tex_x", 0) or 0),
                tex_y=int(raw.get("tex_y", 0) or 0),
                item_type=int(raw.get("type", 0) or 0),
                collision_type=int(raw.get("collision_type", 0) or 0),
                clothing_type=int(raw.get("clothing_type", 0) or 0),
                max_hold=int(raw.get("max_hold", 200) or 200),
                seed1=int(raw.get("seed1", 0) or 0),
                seed2=int(raw.get("seed2", 0) or 0),
            )
            self.items_by_id[record.id] = record
            self.items_by_name[record.name.lower()] = record

        # Second pass: resolve seed1 + seed2 into human-readable splice_recipe strings
        # Note: in items.dat, an item's seed stats (bloom_time, rarity, seed1, seed2) are often stored
        # on its companion Seed ID (item.id + 1) if the block itself has bloom_time == 0!
        for item_id, item in list(self.items_by_id.items()):
            seed_entry = self.items_by_id.get(item_id + 1)
            if (
                seed_entry
                and seed_entry.name.lower() == f"{item.name.lower()} seed"
            ):
                if item.grow_time_seconds == 0 and seed_entry.grow_time_seconds > 0:
                    item.grow_time_seconds = seed_entry.grow_time_seconds
                if (item.rarity == 0 or item.rarity == 999) and 0 < seed_entry.rarity < 999:
                    item.rarity = seed_entry.rarity
                if item.seed1 == 0 and seed_entry.seed1 > 0:
                    item.seed1 = seed_entry.seed1
                    item.seed2 = seed_entry.seed2

            if item.seed1 > 0 and item.seed2 > 0:
                s1 = self.items_by_id.get(item.seed1)
                s2 = self.items_by_id.get(item.seed2)
                if s1 and s2:
                    s1_name = s1.name if s1.name.lower().endswith("seed") else f"{s1.name} Seed"
                    s2_name = s2.name if s2.name.lower().endswith("seed") else f"{s2.name} Seed"
                    item.splice_recipe = f"{s1_name} + {s2_name}"

    def lookup(self, query: str) -> ItemRecord | None:
        """Find an item by exact ID, exact name, or closest substring match."""
        q = query.strip()
        if not q:
            return None
        if q.isdigit():
            item_id = int(q)
            if item_id in self.items_by_id:
                return self.items_by_id[item_id]

        q_lower = q.lower()
        aliases = {
            "wl": "world lock",
            "dl": "diamond lock",
            "bgl": "blue gem lock",
            "lgrid": "laser grid",
            "chand": "chandelier",
            "pep": "pepper tree",
            "ftank": "fish tank",
        }
        q_lower = aliases.get(q_lower, q_lower)

        if q_lower in self.items_by_name:
            return self.items_by_name[q_lower]

        matches = self.search(q_lower, limit=1)
        return matches[0] if matches else None

    def search(self, query: str, limit: int = 10, farmable_only: bool = False) -> list[ItemRecord]:
        """Search items by name substring, prioritizing prefix matches and non-seed base items."""
        q_lower = query.strip().lower()
        prefix_matches: list[ItemRecord] = []
        substring_matches: list[ItemRecord] = []

        for name_lower, item in self.items_by_name.items():
            # Prefer showing the base item rather than the duplicate "... Seed" entry
            if name_lower.endswith(" seed") and not q_lower.endswith(" seed"):
                continue
            if farmable_only and item.grow_time_seconds <= 0:
                continue
            if not q_lower or name_lower.startswith(q_lower):
                prefix_matches.append(item)
            elif q_lower in name_lower:
                substring_matches.append(item)

        combined = prefix_matches + substring_matches
        return combined[: max(1, min(limit, 25))]


items_index = ItemsDatIndex()
