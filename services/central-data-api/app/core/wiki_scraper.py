"""
Wrapper around `growtopia.wiki` and `growtopia.growtopia_info.status` (from H-pun/growtopia-api).
Provides resilient Fandom Wiki item scraping with TTL caching and the 1:00 PM Daily Reset
aggregator (Role Day rotation, Daily Quest, Daily Challenge, and WOTD status).
"""

from __future__ import annotations

import logging
import re
import time
from datetime import date, datetime, time as dt_time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from growtopia.wiki import (
    get_item_description,
    get_item_hardness,
    get_item_properties,
    get_item_rarity,
    get_item_recipes,
    get_item_sprite,
    get_item_title,
    get_simple_item_data,
    search_item as gt_search_item,
)

from app.core.items_parser import items_index
from app.schemas import DailyQuestItem, DailyStatusResponse, WikiItemResponse

logger = logging.getLogger("growcom.wiki_scraper")

# Growtopia's 6-day Role Day rotation (anchored to Growtopia Server Date)
ROLE_ROTATION: list[tuple[str, str]] = [
    ("Builder", "Crafter Role • +Bonus Builder XP & 1x Growtoken on first Role Quest"),
    ("Surgeon", "Supplier Role • +Bonus Surgeon XP & 1x Growtoken on first Role Quest"),
    ("Fishing", "Supplier Role • +Bonus Fishing XP & 1x Growtoken on first Role Quest"),
    ("Chef", "Crafter Role • +Bonus Chef XP & 1x Growtoken on first Role Quest"),
    ("Star Captain", "Supplier Role • +Bonus Star Captain XP & 1x Growtoken on first Role Quest"),
    ("Farmer", "Supplier Role • +Bonus Farmer XP & 1x Growtoken on first Role Quest"),
]
ROLE_ANCHOR_DATE = date(2024, 12, 31)

# Growtopia Daily Challenges rotation with point objectives from the Growtopia Wiki
DAILY_CHALLENGES_ROTATION: list[tuple[str, str]] = [
    ("Doctor's Duel", "Perform surgeries for points (+50 to +250 pts per surgery)."),
    ("Fish Frenzy", "Catch fish for points (+1 pt per lb of fish caught)."),
    ("Star Strife", "Complete Star Missions for points (+20 to +200 pts per mission)."),
    ("Chef Showdown", "Cook food for points without assistance (up to +160 pts per 100% dish)."),
    ("Crystal Crusher", "Harmonize and smash crystals (+1 to +5 pts per crystal)."),
    ("Card Clash", "Defeat Crime-Fighting Supervillains (+50 pts per supervillain)."),
    ("Treasure Turmoil", "Obtain Map Fragments (+1 pt) and solve Treasure Maps (+50 to +500 pts)."),
    ("Malady Mash", "Perform surgeries on patients with a Malady (+100 to +230 pts)."),
    ("Radiation Race", "Find Uranium Blocks in GEIGERHILLS (+1 pt per Uranium Block)."),
    ("Chemical Conundrum", "Create Synthetic Chemicals without assistance (+100 pts each)."),
    ("War of Wolves", "Complete WOLFWORLD parkours (+1 pt per second remaining)."),
    ("Battler's Beatdown", "Win Pet Battles against a Pet Trainer (+1 pt per win)."),
    ("BOO Blast", "Hit (+1 pt) and defeat (+100 pts) Boss Ghosts."),
    ("Mutant Kitchen", "Cook Mutant Food for points without assistance (up to +160 pts)."),
]


class WikiService:
    """Cached wrapper around H-pun/growtopia-api's wiki & status modules."""

    def __init__(self, cache_ttl_seconds: int = 1800) -> None:
        self.cache_ttl = cache_ttl_seconds
        self._item_cache: dict[str, tuple[float, WikiItemResponse]] = {}
        self._manual_daily_override: dict[str, Any] = {}

    def fetch_item(self, query: str) -> WikiItemResponse | None:
        """Fetch item details, splice recipes, and sprites from the Growtopia Wiki."""
        key = query.strip().lower()
        now = time.time()
        if key in self._item_cache:
            ts, cached = self._item_cache[key]
            if now - ts < self.cache_ttl:
                return cached

        # Fetch via Fandom MediaWiki API (avoids Fandom 403 on direct /wiki/ HTML URLs)
        # and run H-pun/growtopia-api's wiki field extractors with per-field fault tolerance.
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Growcom/1.0"}
            search_resp = requests.get(
                "https://growtopia.fandom.com/api.php",
                params={
                    "action": "query",
                    "srlimit": 10,
                    "list": "search",
                    "srsearch": query,
                    "format": "json",
                },
                headers=headers,
                timeout=10,
            )
            search_resp.raise_for_status()
            raw_results = search_resp.json().get("query", {}).get("search", [])
            matches = [
                {"Title": item["title"], "Url": f"https://growtopia.fandom.com/wiki/{item['title'].replace(' ', '_')}"}
                for item in raw_results
                if not any(kw in item["title"].lower() for kw in ["category:", "update", "disambiguation", "week", "mods/"])
            ]
            if not matches:
                return None

            # Prefer exact case-insensitive match if present
            exact = [m for m in matches if m["Title"].lower() == query.strip().lower()]
            target = exact[0] if exact else matches[0]
            page_title = target["Title"]
            url = target["Url"]

            api_resp = requests.get(
                "https://growtopia.fandom.com/api.php",
                params={"action": "parse", "page": page_title, "prop": "text", "format": "json"},
                headers=headers,
                timeout=10,
            )
            api_resp.raise_for_status()
            html_raw = api_resp.json().get("parse", {}).get("text", {}).get("*", "")
            if not html_raw:
                return None

            soup = BeautifulSoup(html_raw, "html.parser")
            card = soup.select_one(".gtw-card.item-card") or soup.select_one(".gtw-card") or soup

            def _safe(fn, *args, default=None):
                try:
                    val = fn(*args)
                    return val if val is not None else default
                except Exception:
                    return default

            title = _safe(get_item_title, card, default=page_title) or page_title
            rarity = _safe(get_item_rarity, soup, default="None")

            descriptions = [
                d.get_text(" ", strip=True)
                for d in soup.select("div.card-text")
                if "info box has been turned off" not in d.get_text(" ", strip=True).lower()
            ]
            description = descriptions[0] if descriptions else (_safe(get_item_description, card, default="") or "").strip()

            raw_props = _safe(get_item_properties, soup, default=[]) or []
            properties = [p.strip() for p in raw_props if p and p.strip()]
            item_type = _safe(get_simple_item_data, soup, 1, " - ", default="")
            chi = str(_safe(get_simple_item_data, soup, 2, default="None") or "None")
            hardness = _safe(get_item_hardness, soup, default={}) or {}
            grow_time = str(_safe(get_simple_item_data, soup, 7, default="") or "")
            gems_drop = str(_safe(get_simple_item_data, soup, 8, default="") or "")

            recipes: list[str] = []
            for rb in soup.select("div.recipebox"):
                rb_text = rb.get_text(" ", strip=True).replace("\ufffd", "x")
                # Format Splicing recipe boxes cleanly with a '+' between the two seeds
                seed_links = [
                    a.get_text(" ", strip=True)
                    for a in rb.select("a")
                    if "seed" in a.get_text(" ", strip=True).lower()
                ]
                if "splicing" in rb_text.lower() and len(seed_links) >= 2:
                    recipes.append(f"🌱 Splicing: {seed_links[0]} + {seed_links[1]}")
                elif rb_text:
                    recipes.append(rb_text)
            if not recipes:
                recipes = _safe(get_item_recipes, soup, default=[]) or []

            local_item = items_index.lookup(title)
            if local_item and local_item.seed1 and local_item.seed2:
                s1 = items_index.items_by_id.get(local_item.seed1)
                s2 = items_index.items_by_id.get(local_item.seed2)
                if s1 and s2:
                    splice_str = f"Splice: {s1.name} Seed + {s2.name} Seed"
                    if not any(splice_str.lower() in r.lower() for r in recipes):
                        recipes.insert(0, splice_str)

            sprites: dict[str, str] = _safe(get_item_sprite, soup, default={}) or {}
            if not sprites:
                header_img = soup.select_one("div.card-header img")
                if header_img and header_img.get("src"):
                    sprites["Item"] = header_img["src"]
                seed_img = soup.select_one("td.seedColor img")
                if seed_img and seed_img.get("src"):
                    sprites["Seed"] = seed_img["src"]

            response = WikiItemResponse(
                title=title,
                url=url,
                rarity=rarity,
                description=description,
                properties=properties,
                item_type=item_type,
                chi=chi,
                grow_time=grow_time,
                gems_drop=gems_drop,
                hardness=hardness,
                recipes=recipes,
                sprites=sprites,
            )
            self._item_cache[key] = (now, response)
            return response
        except Exception as err:
            logger.warning("Wiki lookup failed for '%s': %s", query, err)
            return None

    def get_role_day_for_date(self, target_date: date) -> tuple[str, str, str]:
        """Return (today_role, today_bonus_desc, tomorrow_role) for the given GT date."""
        delta_days = (target_date - ROLE_ANCHOR_DATE).days
        offset = int(self._manual_daily_override.get("role_offset", 0))
        idx = (delta_days + offset) % len(ROLE_ROTATION)
        today_role, today_bonus = ROLE_ROTATION[idx]
        tomorrow_role, _ = ROLE_ROTATION[(idx + 1) % len(ROLE_ROTATION)]
        return today_role, today_bonus, tomorrow_role

    def scrape_wiki_daily_events(self) -> dict[str, Any]:
        """
        Attempt to scrape the Growtopia Wiki Main Page / Daily Quest templates
        for today's Daily Challenge and Crazy Jim's Daily Quest items.
        """
        result: dict[str, Any] = {
            "daily_challenge": None,
            "daily_quest_items": [],
        }
        try:
            resp = requests.get(
                "https://growtopia.fandom.com/api.php",
                params={"action": "parse", "page": "Main_Page", "prop": "text", "format": "json"},
                timeout=8,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Growcom/1.0"},
            )
            if resp.status_code != 200:
                return result
            html_raw = resp.json().get("parse", {}).get("text", {}).get("*", "")
            soup = BeautifulSoup(html_raw, "html.parser")
            text_blob = soup.get_text("\n", strip=True)

            dc_match = re.search(r"Daily Challenge[:\s]+([^\n]+)", text_blob, re.IGNORECASE)
            if dc_match:
                result["daily_challenge"] = dc_match.group(1).strip()
        except Exception as exc:
            logger.debug("Main page scrape skipped: %s", exc)
        return result

    def set_daily_override(
        self,
        *,
        daily_challenge: str | None = None,
        quest_items: list[tuple[str, int]] | None = None,
        role_day: str | None = None,
    ) -> None:
        """Allow staff or automated webhook feeds to update today's Daily Quest & Challenge."""
        gt_today = self._current_gt_date().isoformat()
        if self._manual_daily_override.get("date") != gt_today:
            self._manual_daily_override = {"date": gt_today}

        if daily_challenge:
            self._manual_daily_override["daily_challenge"] = daily_challenge

        if quest_items is not None:
            enriched: list[DailyQuestItem] = []
            for item_name, qty in quest_items:
                parsed = items_index.lookup(item_name)
                wiki = self.fetch_item(parsed.name if parsed else item_name)
                enriched.append(
                    DailyQuestItem(
                        name=parsed.name if parsed else (wiki.title if wiki else item_name),
                        quantity=qty,
                        rarity=parsed.rarity if parsed else (wiki.rarity if wiki else None),
                        recipe=wiki.recipes if wiki else [],
                        sprite_url=wiki.sprites.get("Item") if wiki else None,
                    )
                )
            self._manual_daily_override["daily_quest_items"] = enriched
            self._manual_daily_override["source"] = "verified"

        if role_day:
            for idx, (r_name, _) in enumerate(ROLE_ROTATION):
                if r_name.lower() == role_day.strip().lower():
                    delta_days = (self._current_gt_date() - ROLE_ANCHOR_DATE).days
                    self._manual_daily_override["role_offset"] = (idx - delta_days) % len(ROLE_ROTATION)
                    break

    @staticmethod
    def _current_gt_date() -> date:
        """
        Growtopia's daily reset occurs at 1:00 PM Asia/Manila (UTC+8) every day.
        Before 1:00 PM UTC+8, the active GT day is still the previous day's reset cycle.
        """
        manila_tz = ZoneInfo("Asia/Manila")
        now_manila = datetime.now(manila_tz)
        if now_manila.time() < dt_time(13, 0):
            return (now_manila - timedelta(days=1)).date()
        return now_manila.date()

    @staticmethod
    def _today_reset_unix_timestamp() -> int:
        manila_tz = ZoneInfo("Asia/Manila")
        now_manila = datetime.now(manila_tz)
        reset_dt = datetime.combine(now_manila.date(), dt_time(13, 0), tzinfo=manila_tz)
        if now_manila < reset_dt:
            reset_dt -= timedelta(days=1)
        return int(reset_dt.timestamp())

    @staticmethod
    def _fetch_game_status() -> dict[str, Any]:
        """Fetch online user count and WOTD from growtopiagame.com/detail with proper headers."""
        try:
            resp = requests.get(
                "https://www.growtopiagame.com/detail",
                timeout=6,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Growcom/1.0"},
            )
            if resp.status_code != 200:
                return {}
            payload = resp.json()
            wotd_link = payload.get("world_day_images", {}).get("full_size", "")
            wotd_name = wotd_link.replace("https://www.growtopiagame.com/worlds/", "").replace(".png", "").upper()
            return {
                "Online_User": payload.get("online_user", "N/A"),
                "WOTDLink": wotd_link,
                "WOTDName": wotd_name or "N/A",
            }
        except Exception:
            return {}

    def get_daily_status(self) -> DailyStatusResponse:
        """Aggregate Role Day, Daily Challenge, Daily Quest, and live Growtopia status."""
        gt_date_obj = self._current_gt_date()
        today_role, today_bonus, tomorrow_role = self.get_role_day_for_date(gt_date_obj)

        # Fetch live WOTD + online player count with a proper User-Agent
        game_data = self._fetch_game_status()
        online_users = game_data.get("Online_User") or "N/A"
        wotd_name = game_data.get("WOTDName") or "N/A"
        wotd_link = game_data.get("WOTDLink") or ""
        gt_time_str = datetime.now(ZoneInfo("America/New_York")).strftime("%H:%M:%S")

        scraped = self.scrape_wiki_daily_events()
        is_same_day = self._manual_daily_override.get("date") == gt_date_obj.isoformat()

        delta_days = (gt_date_obj - ROLE_ANCHOR_DATE).days
        dc_name, dc_desc = DAILY_CHALLENGES_ROTATION[delta_days % len(DAILY_CHALLENGES_ROTATION)]
        default_dc = f"{dc_name} — {dc_desc}"

        daily_challenge = (
            (self._manual_daily_override.get("daily_challenge") if is_same_day else None)
            or scraped.get("daily_challenge")
            or default_dc
        )

        dq_items: list[DailyQuestItem] = (
            (self._manual_daily_override.get("daily_quest_items") if is_same_day else None)
            or scraped.get("daily_quest_items")
            or []
        )
        dq_source = (
            self._manual_daily_override.get("source", "auto")
            if is_same_day and dq_items
            else ("wiki" if dq_items else "pending_reset")
        )

        return DailyStatusResponse(
            gt_date=gt_date_obj.isoformat(),
            gt_time=gt_time_str,
            local_reset_timestamp=self._today_reset_unix_timestamp(),
            role_day=today_role,
            role_day_bonus=today_bonus,
            tomorrow_role_day=tomorrow_role,
            daily_challenge=daily_challenge,
            daily_quest_items=dq_items,
            daily_quest_source=dq_source,
            wotd_name=wotd_name,
            wotd_image_url=wotd_link,
            online_users=online_users,
        )


wiki_service = WikiService()
