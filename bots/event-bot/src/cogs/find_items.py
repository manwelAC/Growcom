"""
Category 14: Find Items by Buff & Multi-Mod Explorer (cogs/find_items.py)

Allows players to search across all 2026 Growtopia items (items.dat v27 + 126+ Official Wiki Mod Categories)
by any buff/effect (e.g. Double Jump, Speedy, Punch Damage, Build Range, Punch Range, Extra Blocks,
Extra Gems, XP Buff, Tree Harvesting, Slow Fall, Charging Geiger Counter, or umbrella groups like
All Punch Buffs).

Features:
- Full 2026 dataset (items.dat v27 through November 2026 + all Growtopia Wiki Mod categories)
- Clearly displays ALL additional buffs on items that possess multiple effects
- Supports searching by a single buff, an umbrella group (e.g. All Punch Buffs), OR combining 2 buffs
- Renders the item list inside embed.description (4,096-char limit) so it never hits Discord's 1,024-char field limit
- Interactive Clothing Slot filter dropdown (Hat, Hair, Face, Chest, Shirt, Pants, Feet, Back, Hand, Artifact)
- Interactive "✨ Multi-Buff Items Only" toggle button & clean pagination
- Immediate 50ms interaction deferral so buttons/dropdowns never time out
- Persistent [growcom:find_items] topic signature so renaming #🔍find-items never recreates the channel

Commands:
- /find-items <buff> [second_buff] [slot] [multi_buff_only]
- /set_find_items_channel [channel] (Admin: lock /find-items tool to dedicated channel)
- /setup_find_items_channel (Admin: auto-provision #🔍find-items under '🛠️ Growcom Tools')
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

import discord
from discord import app_commands
from discord.ext import commands

from utils.helpers import (
    FOOTER_TEXT,
    PROJECT_ROOT,
    is_server_manager,
    load_state,
    save_state,
)

if TYPE_CHECKING:
    from bot import EventBot

logger = logging.getLogger("growcom.find_items")

TOOLS_CATEGORY_ID = 1567213972283719811
DEFAULT_MEMBER_ROLE_ID = 1568495447067332608
BUFFS_DATA_FILE = PROJECT_ROOT / "bots" / "event-bot" / "data" / "item_buffs_2026.json"
ITEMS_PER_PAGE = 8

SLOT_EMOJIS: dict[str, str] = {
    "Hat": "🎩",
    "Hair": "💇",
    "Face": "😎",
    "Chest": "📿",
    "Shirt": "👕",
    "Pants": "👖",
    "Feet": "👟",
    "Back": "🦋",
    "Hand": "✋",
    "Artifact": "🔮",
    "Consumable": "🧪",
    "Block / Misc": "🧱",
    "Clothing": "👚",
}

BUFF_EMOJIS: dict[str, str] = {
    "All Punch Buffs": "🥊",
    "All Jump Buffs": "🚀",
    "All Farming Buffs": "🌾",
    "All Range Buffs": "🎯",
    "All Speed Buffs": "⚡",
    "Double Jump": "🦋",
    "High Jump": "🚀",
    "Low Jump": "🪶",
    "Speedy": "⚡",
    "Speedy in Water": "🌊",
    "Punch Damage": "⛏️",
    "Punch Range": "🥊",
    "Punch Power": "💥",
    "Punch Pull": "🧲",
    "Build Range": "🧱",
    "Extra Blocks": "📦",
    "Extra Gems": "💎",
    "XP Buff": "✨",
    "Tree Harvesting": "🌾",
    "Slow Fall": "🪂",
    "Slow-Fall: Ear Flap": "🪂",
    "Floating!": "☁️",
    "Float on Water": "🛟",
    "Charging Geiger Counter": "☢️",
    "Geiger Counting": "📡",
    "Night Vision": "🦉",
    "Light Source": "💡",
    "Lucky!": "🍀",
    "Fireproof": "🛡️",
    "Ghost Immunity": "👻",
    "Balloon Immunity": "🎈",
    "Damage Reduction": "🛡️",
    "Knock Back Reduction": "⚓",
    "Wall Climbing": "🧗",
    "Skin Color": "🎨",
    "Zombie Weapon": "🧟",
    "Fists O' Fury": "👊",
}

# Umbrella multi-category groups so players can search e.g. "All Punch Buffs" at once
UMBRELLA_BUFF_GROUPS: dict[str, dict[str, Any]] = {
    "All Punch Buffs": {
        "description": "All items that grant any Punch buff (Punch Damage, Punch Range, Punch Power, Punch Pull, or Fists O' Fury).",
        "sub_buffs": ["Punch Damage", "Punch Range", "Punch Power", "Punch Pull", "Fists O' Fury"],
    },
    "All Jump Buffs": {
        "description": "All items that grant any Jumping or Gliding buff (Double Jump, High Jump, Low Jump, Slow Fall).",
        "sub_buffs": ["Double Jump", "High Jump", "Low Jump", "Slow Fall"],
    },
    "All Farming Buffs": {
        "description": "All items that boost Farming, Harvesting, Gems, Blocks, or XP (Extra Blocks, Extra Gems, Tree Harvesting, XP Buff, Lucky!).",
        "sub_buffs": ["Extra Blocks", "Extra Gems", "Tree Harvesting", "XP Buff", "Lucky!"],
    },
    "All Range Buffs": {
        "description": "All items that extend Build Range or Punch Range.",
        "sub_buffs": ["Build Range", "Punch Range", "Long Range"],
    },
    "All Speed Buffs": {
        "description": "All items that increase movement or swimming speed (Speedy, Speedy in Water, Float on Water).",
        "sub_buffs": ["Speedy", "Speedy in Water", "Float on Water"],
    },
}

POPULAR_BUFFS_ORDER: list[str] = [
    "All Punch Buffs",
    "Punch Damage",
    "Punch Range",
    "Punch Power",
    "Punch Pull",
    "Double Jump",
    "Speedy",
    "Build Range",
    "Extra Blocks",
    "Extra Gems",
    "XP Buff",
    "Tree Harvesting",
    "High Jump",
    "Slow Fall",
    "Light Source",
    "All Farming Buffs",
    "All Jump Buffs",
    "All Range Buffs",
    "All Speed Buffs",
    "Fireproof",
    "Float on Water",
    "Speedy in Water",
    "Damage Reduction",
    "Wall Climbing",
    "Lucky!",
]

BUFF_SYNONYMS: dict[str, list[str]] = {
    "punch": ["All Punch Buffs", "Punch Damage", "Punch Range", "Punch Power", "Punch Pull", "Fists O' Fury"],
    "all punch": ["All Punch Buffs", "Punch Damage", "Punch Range", "Punch Power", "Punch Pull"],
    "pickaxe": ["Punch Damage", "All Punch Buffs"],
    "enhanced digging": ["Punch Damage"],
    "digging": ["Punch Damage"],
    "break": ["Punch Damage", "Extra Blocks", "All Punch Buffs"],
    "fast": ["Speedy", "All Speed Buffs", "Speedy in Water", "Punch Damage"],
    "speed": ["Speedy", "All Speed Buffs", "Speedy in Water"],
    "run": ["Speedy", "All Speed Buffs"],
    "walk": ["Speedy", "All Speed Buffs"],
    "swim": ["Speedy in Water", "Float on Water"],
    "range": ["All Range Buffs", "Build Range", "Punch Range", "Long Range"],
    "reach": ["All Range Buffs", "Build Range", "Punch Range", "Long Range"],
    "rayman": ["Punch Range", "Punch Damage", "Extra Blocks"],
    "magplant": ["Build Range", "Punch Range"],
    "harvester": ["Tree Harvesting", "Extra Blocks", "All Farming Buffs"],
    "farm": ["All Farming Buffs", "Extra Blocks", "Extra Gems", "Tree Harvesting", "XP Buff", "Lucky!"],
    "gems": ["Extra Gems", "Lucky!", "All Farming Buffs"],
    "blocks": ["Extra Blocks", "Build Range", "Punch Damage"],
    "xp": ["XP Buff", "All Farming Buffs"],
    "level": ["XP Buff"],
    "exp": ["XP Buff"],
    "jump": ["All Jump Buffs", "Double Jump", "High Jump", "Low Jump", "Slow Fall"],
    "slow-fall": ["Slow Fall", "Slow-Fall: Ear Flap"],
    "slowfall": ["Slow Fall", "Slow-Fall: Ear Flap"],
    "glide": ["Slow Fall", "Floating!"],
    "parachute": ["Slow Fall"],
    "fly": ["Double Jump", "Floating!", "Slow Fall"],
    "wings": ["Double Jump", "High Jump", "Slow Fall"],
    "geiger": ["Charging Geiger Counter", "Geiger Counting"],
    "glow": ["Light Source", "Night Vision"],
    "dark": ["Light Source", "Night Vision"],
    "clover": ["Lucky!", "Extra Gems"],
    "pull": ["Punch Pull", "All Punch Buffs"],
    "knockback": ["Punch Power", "Knock Back Reduction"],
    "ancestral": ["Extra Blocks", "Extra Gems", "XP Buff", "Build Range"],
}

_BUFF_DB_CACHE: dict[str, Any] | None = None
_BUFF_DB_MTIME: float = 0.0


def load_buff_db() -> dict[str, Any]:
    """Load and cache the 2026 item buffs database with automatic mtime hot-reload and umbrella groups."""
    global _BUFF_DB_CACHE, _BUFF_DB_MTIME
    if BUFFS_DATA_FILE.exists():
        mtime = BUFFS_DATA_FILE.stat().st_mtime
        if _BUFF_DB_CACHE is not None and mtime == _BUFF_DB_MTIME:
            return _BUFF_DB_CACHE
        try:
            data = json.loads(BUFFS_DATA_FILE.read_text(encoding="utf-8"))
            buffs = data.setdefault("buffs", {})
            buff_to_items = data.setdefault("buff_to_items", {})

            # Inject Umbrella Buff Groups (e.g. "All Punch Buffs") dynamically
            for u_name, u_info in UMBRELLA_BUFF_GROUPS.items():
                combined_set: set[str] = set()
                for sb in u_info["sub_buffs"]:
                    for item_name in buff_to_items.get(sb, []):
                        combined_set.add(item_name)
                if combined_set:
                    buff_to_items[u_name] = sorted(combined_set)
                    buffs[u_name] = {
                        "name": u_name,
                        "description": u_info["description"],
                        "item_count": len(combined_set),
                    }

            _BUFF_DB_CACHE = data
            _BUFF_DB_MTIME = mtime
            return _BUFF_DB_CACHE
        except Exception as exc:
            logger.warning("Failed to load %s: %s", BUFFS_DATA_FILE, exc)
    return {"version": "items.dat v27 (2026)", "buffs": {}, "buff_to_items": {}, "items": {}}


def resolve_buff_name(query: str, db: dict[str, Any]) -> str | None:
    """Resolve a user buff query or synonym to the canonical buff key."""
    if not query:
        return None
    buffs: dict[str, Any] = db.get("buffs", {})
    q_clean = query.strip()
    if q_clean in buffs:
        return q_clean

    q_lower = q_clean.lower()
    for b_name in buffs:
        if b_name.lower() == q_lower:
            return b_name

    # Exact synonym key match first (e.g. "punch" -> "All Punch Buffs")
    if q_lower in BUFF_SYNONYMS:
        for t in BUFF_SYNONYMS[q_lower]:
            if t in buffs:
                return t

    # Prefix match on buff names
    for b_name in buffs:
        if b_name.lower().startswith(q_lower):
            return b_name

    # Substring synonym match
    for syn_key, targets in BUFF_SYNONYMS.items():
        if syn_key in q_lower:
            for t in targets:
                if t in buffs:
                    return t

    # Substring match on buff names
    for b_name in buffs:
        if q_lower in b_name.lower():
            return b_name
    return None


def filter_matching_items(
    db: dict[str, Any],
    primary_buff: str,
    second_buff: str | None = None,
    slot_filter: str = "ALL",
    multi_buff_only: bool = False,
) -> list[dict[str, Any]]:
    """
    Return all 2026 items matching primary_buff (and optional second_buff, slot_filter, multi_buff_only),
    sorted with multi-buff items and known items.dat IDs first.
    """
    buff_to_items: dict[str, list[str]] = db.get("buff_to_items", {})
    all_items: dict[str, dict[str, Any]] = db.get("items", {})

    primary_list = buff_to_items.get(primary_buff, [])
    if second_buff and second_buff != primary_buff:
        second_set = set(buff_to_items.get(second_buff, []))
        candidate_names = [name for name in primary_list if name in second_set]
    else:
        candidate_names = list(primary_list)

    results: list[dict[str, Any]] = []
    for name in candidate_names:
        item = all_items.get(name)
        if not item:
            continue
        if slot_filter and slot_filter != "ALL":
            if item.get("slot", "").lower() != slot_filter.lower():
                continue
        if multi_buff_only and len(item.get("buffs", [])) < 2:
            continue
        results.append(item)

    results.sort(
        key=lambda x: (
            -len(x.get("buffs", [])),
            1 if int(x.get("id", 0)) == 0 else 0,
            x.get("name", ""),
        )
    )
    return results


def build_find_items_embed(
    db: dict[str, Any],
    primary_buff: str,
    second_buff: str | None,
    slot_filter: str,
    multi_buff_only: bool,
    page: int,
    matched_items: list[dict[str, Any]],
) -> discord.Embed:
    """
    Build a responsive, zero-wrap Argon UI embed.
    Places the item list inside embed.description (which supports 4,096 characters)
    so it NEVER overflows Discord's 1,024-character embed field limit!
    """
    buffs_meta = db.get("buffs", {})
    p_info = buffs_meta.get(primary_buff, {})
    p_emoji = BUFF_EMOJIS.get(primary_buff, "✨")
    p_desc = p_info.get("description", f"Items that grant the {primary_buff} buff.")

    if second_buff and second_buff != primary_buff:
        s_emoji = BUFF_EMOJIS.get(second_buff, "✨")
        title = f"🔍 Growcom 2026 Buff Finder • {p_emoji} {primary_buff} + {s_emoji} {second_buff}"
    else:
        title = f"🔍 Growcom 2026 Buff Finder • {p_emoji} {primary_buff}"

    total_items = len(matched_items)
    total_pages = max(1, (total_items + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
    current_page = max(1, min(page, total_pages))
    start_idx = (current_page - 1) * ITEMS_PER_PAGE
    page_slice = matched_items[start_idx : start_idx + ITEMS_PER_PAGE]

    slot_badge = "All Slots" if slot_filter == "ALL" else f"{SLOT_EMOJIS.get(slot_filter, '👚')} {slot_filter} Only"
    multi_badge = "✨ Multi-Buff Only" if multi_buff_only else "All Items"
    multi_count = sum(1 for it in matched_items if len(it.get("buffs", [])) >= 2)

    desc_blocks: list[str] = [
        f"💡 **Buff Effect:** *{p_desc}*",
    ]
    if second_buff and second_buff != primary_buff:
        s_desc = buffs_meta.get(second_buff, {}).get("description", "")
        if s_desc:
            desc_blocks.append(f"💡 **2nd Buff ({second_buff}):** *{s_desc}*")

    desc_blocks.append(
        f"📊 **Found:** **`{total_items:,}` Items** (`{multi_count:,}` Multi-Buff) • "
        f"**Slot:** `{slot_badge}` • **Mode:** `{multi_badge}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )

    if not page_slice:
        desc_blocks.append(
            "⚠️ **No Matching Items Found for This Filter**\n"
            "Try switching the **Clothing Slot dropdown** below to **`🌟 All Clothing Slots`** "
            "or toggling off **`✨ Multi-Buff Only`**!"
        )
    else:
        is_umbrella = primary_buff in UMBRELLA_BUFF_GROUPS
        umbrella_subs = set(UMBRELLA_BUFF_GROUPS.get(primary_buff, {}).get("sub_buffs", []))
        searched_set = set(umbrella_subs) if is_umbrella else {primary_buff}
        if second_buff:
            searched_set.add(second_buff)

        item_lines: list[str] = []
        for idx, item in enumerate(page_slice, start=start_idx + 1):
            name = item.get("name", "Unknown Item")
            item_id = int(item.get("id", 0) or 0)
            slot = item.get("slot", "Clothing")
            s_emoji = SLOT_EMOJIS.get(slot, "👚")
            all_buffs: list[str] = item.get("buffs", [])

            id_tag = f" • `ID #{item_id}`" if item_id > 0 else ""

            if is_umbrella:
                matched_subs = [b for b in all_buffs if b in umbrella_subs]
                extra_buffs = [b for b in all_buffs if b not in umbrella_subs]
                m_str = " • ".join(f"`{b}`" for b in matched_subs) if matched_subs else f"`{primary_buff}`"
                if extra_buffs:
                    e_str = " • ".join(f"`+{b}`" for b in extra_buffs)
                    buff_line = f"   ╰ 🥊 **Matched:** {m_str} • ✨ **Also Grants:** {e_str}"
                else:
                    buff_line = f"   ╰ 🥊 **Grants:** {m_str}"
            else:
                extra_buffs = [b for b in all_buffs if b not in searched_set]
                if extra_buffs:
                    formatted_extras = " • ".join(f"`+{b}`" for b in extra_buffs)
                    buff_line = f"   ╰ ✨ **Additional Buffs ({len(extra_buffs)}):** {formatted_extras}"
                else:
                    buff_line = f"   ╰ 🔹 *Single Buff:* Grants `{primary_buff}`"

            item_lines.append(
                f"**{idx}.** {s_emoji} **{name}** (`{slot}`{id_tag})\n{buff_line}"
            )

        desc_blocks.append("\n\n".join(item_lines))

    full_description = "\n\n".join(desc_blocks)
    if len(full_description) > 4000:
        full_description = full_description[:3990] + "\n..."

    embed = discord.Embed(
        title=title[:256],
        description=full_description,
        color=0x00E676 if total_items > 0 else 0xFF5252,
    )

    if matched_items:
        slot_counts: dict[str, int] = {}
        for it in matched_items:
            sl = it.get("slot", "Other")
            slot_counts[sl] = slot_counts.get(sl, 0) + 1
        top_slots = sorted(slot_counts.items(), key=lambda x: -x[1])[:7]
        slot_summary = " • ".join(
            f"{SLOT_EMOJIS.get(sl, '👚')} **{sl}:** `{cnt}`" for sl, cnt in top_slots
        )
        embed.add_field(
            name=f"🧩 Clothing Slots Breakdown (Page {current_page} of {total_pages})",
            value=slot_summary[:1000],
            inline=False,
        )

    embed.set_footer(
        text=f"{FOOTER_TEXT} • Synced with {db.get('version', 'items.dat v27 (2026)')} • Page {current_page}/{total_pages}"
    )
    return embed


class SlotFilterSelect(discord.ui.Select["FindItemsView"]):
    """Dropdown allowing players to filter buff items by Clothing Slot (Hat, Shirt, Pants, Feet, Back, Hand, etc.)."""

    def __init__(self, current_slot: str, matched_all_slots: list[dict[str, Any]]) -> None:
        slot_counts: dict[str, int] = {}
        for it in matched_all_slots:
            sl = it.get("slot", "Clothing")
            slot_counts[sl] = slot_counts.get(sl, 0) + 1

        options: list[discord.SelectOption] = [
            discord.SelectOption(
                label=f"🌟 All Clothing Slots ({len(matched_all_slots)} items)",
                value="ALL",
                default=(current_slot == "ALL"),
            )
        ]

        ordered_slots = ["Hat", "Hair", "Face", "Chest", "Shirt", "Pants", "Feet", "Back", "Hand", "Artifact"]
        for sl in ordered_slots:
            cnt = slot_counts.get(sl, 0)
            if cnt > 0 or current_slot == sl:
                em = SLOT_EMOJIS.get(sl, "👚")
                options.append(
                    discord.SelectOption(
                        label=f"{em} {sl} Slot ({cnt} items)",
                        value=sl,
                        default=(current_slot == sl),
                    )
                )

        super().__init__(
            placeholder="🎽 Filter by Clothing Slot (Hat, Wings, Hand, Feet...)",
            min_values=1,
            max_values=1,
            options=options[:25],
            row=0,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        if not self.view:
            return
        self.view.slot_filter = self.values[0]
        self.view.page = 1
        await self.view.refresh_message(interaction)


class FindItemsView(discord.ui.View):
    """Interactive pagination, Clothing Slot filter, and Multi-Buff toggle view."""

    def __init__(
        self,
        primary_buff: str,
        second_buff: str | None = None,
        slot_filter: str = "ALL",
        multi_buff_only: bool = False,
        page: int = 1,
    ) -> None:
        super().__init__(timeout=300.0)
        self.primary_buff = primary_buff
        self.second_buff = second_buff
        self.slot_filter = slot_filter
        self.multi_buff_only = multi_buff_only
        self.page = page
        self._rebuild_components()

    def _rebuild_components(self) -> None:
        self.clear_items()
        db = load_buff_db()

        all_slot_matches = filter_matching_items(
            db=db,
            primary_buff=self.primary_buff,
            second_buff=self.second_buff,
            slot_filter="ALL",
            multi_buff_only=self.multi_buff_only,
        )
        current_matches = filter_matching_items(
            db=db,
            primary_buff=self.primary_buff,
            second_buff=self.second_buff,
            slot_filter=self.slot_filter,
            multi_buff_only=self.multi_buff_only,
        )

        total_pages = max(1, (len(current_matches) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
        self.page = max(1, min(self.page, total_pages))

        # Row 0: Slot filter dropdown
        self.add_item(SlotFilterSelect(self.slot_filter, all_slot_matches))

        # Row 1: Pagination & Multi-Buff Toggle buttons
        prev_btn = discord.ui.Button(
            label="◀ Prev",
            style=discord.ButtonStyle.secondary,
            disabled=(self.page <= 1),
            row=1,
        )
        prev_btn.callback = self._on_prev
        self.add_item(prev_btn)

        page_btn = discord.ui.Button(
            label=f"Page {self.page}/{total_pages}",
            style=discord.ButtonStyle.secondary,
            disabled=True,
            row=1,
        )
        self.add_item(page_btn)

        next_btn = discord.ui.Button(
            label="Next ▶",
            style=discord.ButtonStyle.secondary,
            disabled=(self.page >= total_pages),
            row=1,
        )
        next_btn.callback = self._on_next
        self.add_item(next_btn)

        multi_btn = discord.ui.Button(
            label="✨ Multi-Buff Only: ON" if self.multi_buff_only else "✨ Multi-Buff Only: OFF",
            style=discord.ButtonStyle.success if self.multi_buff_only else discord.ButtonStyle.primary,
            row=1,
        )
        multi_btn.callback = self._on_toggle_multi
        self.add_item(multi_btn)

    async def _on_prev(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        self.page = max(1, self.page - 1)
        await self.refresh_message(interaction)

    async def _on_next(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        self.page += 1
        await self.refresh_message(interaction)

    async def _on_toggle_multi(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        self.multi_buff_only = not self.multi_buff_only
        self.page = 1
        await self.refresh_message(interaction)

    async def refresh_message(self, interaction: discord.Interaction) -> None:
        db = load_buff_db()
        matched = filter_matching_items(
            db=db,
            primary_buff=self.primary_buff,
            second_buff=self.second_buff,
            slot_filter=self.slot_filter,
            multi_buff_only=self.multi_buff_only,
        )
        self._rebuild_components()
        embed = build_find_items_embed(
            db=db,
            primary_buff=self.primary_buff,
            second_buff=self.second_buff,
            slot_filter=self.slot_filter,
            multi_buff_only=self.multi_buff_only,
            page=self.page,
            matched_items=matched,
        )
        await interaction.edit_original_response(embed=embed, view=self)


class FindItemsCog(commands.Cog, name="Find Items by Buff"):
    """Growcom 2026 Item Buff & Multi-Mod Explorer (/find-items)."""

    def __init__(self, bot: EventBot) -> None:
        self.bot = bot
        self._provisioned_guilds: set[int] = set()

    async def buff_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        db = load_buff_db()
        buffs: dict[str, dict[str, Any]] = db.get("buffs", {})
        if not buffs:
            return []

        q = current.strip().lower()
        choices: list[app_commands.Choice[str]] = []
        seen: set[str] = set()

        def _add_choice(b_name: str) -> None:
            if b_name in seen or b_name not in buffs or len(choices) >= 25:
                return
            seen.add(b_name)
            cnt = buffs[b_name].get("item_count", 0)
            emoji = BUFF_EMOJIS.get(b_name, "✨")
            label = f"{emoji} {b_name} ({cnt} items)"[:100]
            choices.append(app_commands.Choice(name=label, value=b_name))

        if not q:
            for pop in POPULAR_BUFFS_ORDER:
                _add_choice(pop)
            for b_name in sorted(buffs.keys()):
                _add_choice(b_name)
            return choices[:25]

        # 1. Exact/Synonym matches first
        for syn_key, targets in BUFF_SYNONYMS.items():
            if q in syn_key or syn_key in q:
                for t in targets:
                    _add_choice(t)

        # 2. Prefix matches
        for b_name in sorted(buffs.keys()):
            if b_name.lower().startswith(q):
                _add_choice(b_name)

        # 3. Substring matches in buff name or description
        for b_name, b_info in sorted(buffs.items()):
            if q in b_name.lower() or q in str(b_info.get("description", "")).lower():
                _add_choice(b_name)

        return choices[:25]

    async def provision_find_items_channel(
        self,
        guild: discord.Guild,
        force_repost: bool = False,
    ) -> discord.TextChannel:
        state = load_state()
        everyone_role = guild.default_role
        bot_member = guild.me

        member_role_id = int(state.get("member_role_id", DEFAULT_MEMBER_ROLE_ID))
        member_role = guild.get_role(member_role_id)

        tools_cat: discord.CategoryChannel | None = guild.get_channel(TOOLS_CATEGORY_ID)  # type: ignore[assignment]
        if not isinstance(tools_cat, discord.CategoryChannel):
            for cat in guild.categories:
                if "tools" in cat.name.lower():
                    tools_cat = cat
                    break

        ch_id = state.get("find_items_channel_id")
        existing_ch = guild.get_channel(int(ch_id)) if ch_id else None

        # 1. Match by persistent topic signature [growcom:find_items] (immune to channel renaming!)
        if not existing_ch:
            for ch in guild.text_channels:
                if ch.topic and "[growcom:find_items]" in ch.topic:
                    existing_ch = ch
                    break

        # 2. Match by known names or fuzzy topic/category keywords
        if not existing_ch:
            for ch in guild.text_channels:
                name_l = ch.name.lower()
                topic_l = (ch.topic or "").lower()
                if (
                    "find-items" in name_l
                    or "find_items" in name_l
                    or "buff-finder" in name_l
                    or "growcom item buff" in topic_l
                ):
                    existing_ch = ch
                    break

        overwrites = {
            everyone_role: discord.PermissionOverwrite(view_channel=False),
            bot_member: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                embed_links=True,
                attach_files=True,
                manage_messages=True,
            ),
        }
        if member_role:
            overwrites[member_role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
            )

        if not existing_ch:
            existing_ch = await guild.create_text_channel(
                name="🔍find-items",
                category=tools_cat,
                overwrites=overwrites,
                topic="Growcom Item Buff & Multi-Mod Explorer [growcom:find_items] — Search 2026 items by buff",
                reason="Auto-provisioned Growcom Tools channel",
            )
            force_repost = True
        else:
            if not existing_ch.topic or "[growcom:find_items]" not in existing_ch.topic:
                new_topic = f"{existing_ch.topic or 'Growcom Item Buff & Multi-Mod Explorer'} [growcom:find_items]".strip()
                try:
                    await existing_ch.edit(topic=new_topic)
                except Exception:
                    pass

            if existing_ch.category_id != (tools_cat.id if tools_cat else None):
                try:
                    await existing_ch.edit(category=tools_cat)
                except Exception:
                    pass

        state["find_items_channel_id"] = existing_ch.id
        save_state(state)

        if force_repost:
            db = load_buff_db()
            guide_embed = discord.Embed(
                title="🔍 Growcom 2026 Item Buff & Multi-Mod Finder",
                description=(
                    "Welcome to **`/find-items`** — the complete 2026 Growtopia Buff & Mod Encyclopedia!\n\n"
                    "Find every item that grants a specific buff, see **all additional buffs** on multi-mod items, "
                    "and filter by **Clothing Slot** (*Hat, Hair, Face, Chest, Shirt, Pants, Feet, Back/Wings, Hand, Artifact*).\n\n"
                    "**How to Use:**\n"
                    "• **`/find-items buff:All Punch Buffs`** — View all Punch Damage, Range, Power & Pull items\n"
                    "• **`/find-items buff:Double Jump`** — Browse all Double Jump items & see extra buffs\n"
                    "• **`/find-items buff:Extra Blocks`** — Find farming & harvesting bonus items\n"
                    "• **`/find-items buff:Build Range second_buff:Punch Range`** — Find items that grant **BOTH** buffs at once!\n\n"
                    f"📦 **Database Coverage:** `{db.get('total_buffs', 126)}+ Buff Categories` • "
                    f"`{db.get('total_modded_items', 1646):,}+ Modded Items` (`{db.get('version', 'items.dat v27 - 2026')}`)"
                ),
                color=0x00E676,
            )
            guide_embed.set_footer(text=FOOTER_TEXT)
            await existing_ch.send(embed=guide_embed)

        return existing_ch

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        for guild in self.bot.guilds:
            if guild.id in self._provisioned_guilds:
                continue
            if guild.me and guild.me.guild_permissions.manage_channels:
                try:
                    ch = await self.provision_find_items_channel(guild, force_repost=False)
                    logger.info("Configured %s (%s) under category: %s", ch.name, ch.id, ch.category)
                    self._provisioned_guilds.add(guild.id)
                except Exception as exc:
                    logger.warning("Could not auto-provision find-items channel in %s: %s", guild.name, exc)

    @app_commands.command(
        name="setup_find_items_channel",
        description="Admin: Create or verify #🔍find-items under category: Growcom Tools",
    )
    async def setup_find_items_channel_cmd(self, interaction: discord.Interaction) -> None:
        if not is_server_manager(interaction) or not interaction.guild:
            await interaction.response.send_message("❌ Admin permission required.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        ch = await self.provision_find_items_channel(interaction.guild, force_repost=True)
        cat_name = ch.category.name if ch.category else "None"
        await interaction.followup.send(
            f"✅ Configured **{ch.mention}** under category **`{cat_name}`**!\n"
            f"The **`/find-items`** tool is ready to use.",
            ephemeral=True,
        )

    @app_commands.command(
        name="set_find_items_channel",
        description="Restrict the /find-items tool exclusively to a designated channel",
    )
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(channel="Dedicated channel for /find-items lookups (defaults to current channel)")
    async def set_find_items_channel_cmd(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel | None = None,
    ) -> None:
        if not is_server_manager(interaction):
            await interaction.response.send_message(
                "❌ Only server admins can use `/set_find_items_channel`.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        target_channel = channel or interaction.channel
        if not isinstance(target_channel, discord.TextChannel):
            await interaction.followup.send("❌ Please select a standard text channel.", ephemeral=True)
            return

        state = load_state()
        state["find_items_channel_id"] = target_channel.id
        save_state(state)

        if not target_channel.topic or "[growcom:find_items]" not in target_channel.topic:
            try:
                new_topic = f"{target_channel.topic or 'Growcom Item Buff & Multi-Mod Explorer'} [growcom:find_items]".strip()
                await target_channel.edit(topic=new_topic)
            except Exception:
                pass

        await interaction.followup.send(
            f"✅ Locked **`/find-items`** exclusively to {target_channel.mention}!",
            ephemeral=True,
        )

    @app_commands.command(
        name="find-items",
        description="Find all 2026 Growtopia items with a specific buff (and see all additional buffs on each item)!",
    )
    @app_commands.describe(
        buff="Primary buff to search for (e.g. All Punch Buffs, Punch Damage, Punch Range, Double Jump, Speedy)",
        second_buff="Optional 2nd buff to find items that grant BOTH buffs at the same time",
        slot="Optional clothing slot filter (Hat, Hair, Face, Chest, Shirt, Pants, Feet, Back, Hand, Artifact)",
        multi_buff_only="Set True to only show items that possess 2 or more buffs",
    )
    @app_commands.choices(
        slot=[
            app_commands.Choice(name="🌟 All Clothing Slots", value="ALL"),
            app_commands.Choice(name="🎩 Hat", value="Hat"),
            app_commands.Choice(name="💇 Hair", value="Hair"),
            app_commands.Choice(name="😎 Face", value="Face"),
            app_commands.Choice(name="📿 Chest / Neck", value="Chest"),
            app_commands.Choice(name="👕 Shirt", value="Shirt"),
            app_commands.Choice(name="👖 Pants", value="Pants"),
            app_commands.Choice(name="👟 Feet / Shoes", value="Feet"),
            app_commands.Choice(name="🦋 Back / Wings", value="Back"),
            app_commands.Choice(name="✋ Hand", value="Hand"),
            app_commands.Choice(name="🔮 Artifact / Ancestral", value="Artifact"),
        ]
    )
    @app_commands.autocomplete(buff=buff_autocomplete, second_buff=buff_autocomplete)
    async def find_items_command(
        self,
        interaction: discord.Interaction,
        buff: str,
        second_buff: str | None = None,
        slot: str = "ALL",
        multi_buff_only: bool = False,
    ) -> None:
        state = load_state()
        allowed_channel_id = state.get("find_items_channel_id")
        if allowed_channel_id and int(interaction.channel_id or 0) != int(allowed_channel_id):
            await interaction.response.send_message(
                f"❌ The **`/find-items`** tool can only be used inside <#{allowed_channel_id}>!",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        try:
            db = load_buff_db()
            canonical_primary = resolve_buff_name(buff, db)
            if not canonical_primary:
                top_list = ", ".join(f"`{b}`" for b in POPULAR_BUFFS_ORDER[:12])
                await interaction.followup.send(
                    f"❌ Could not find a buff matching **`{buff}`**!\n"
                    f"💡 **Popular Buffs:** {top_list}",
                    ephemeral=True,
                )
                return

            canonical_second: str | None = None
            if second_buff:
                canonical_second = resolve_buff_name(second_buff, db)
                if not canonical_second:
                    await interaction.followup.send(
                        f"❌ Could not find a second buff matching **`{second_buff}`**! Please choose from the autocomplete list.",
                        ephemeral=True,
                    )
                    return

            matched_items = filter_matching_items(
                db=db,
                primary_buff=canonical_primary,
                second_buff=canonical_second,
                slot_filter=slot,
                multi_buff_only=multi_buff_only,
            )

            embed = build_find_items_embed(
                db=db,
                primary_buff=canonical_primary,
                second_buff=canonical_second,
                slot_filter=slot,
                multi_buff_only=multi_buff_only,
                page=1,
                matched_items=matched_items,
            )
            view = FindItemsView(
                primary_buff=canonical_primary,
                second_buff=canonical_second,
                slot_filter=slot,
                multi_buff_only=multi_buff_only,
                page=1,
            )

            await interaction.followup.send(embed=embed, view=view)
        except Exception as exc:
            logger.exception("Error in /find-items for buff=%s: %s", buff, exc)
            await interaction.followup.send(
                f"❌ An unexpected error occurred while building results for **`{buff}`**: `{exc}`",
                ephemeral=True,
            )


async def setup(bot: EventBot) -> None:
    await bot.add_cog(FindItemsCog(bot))
