"""
Category 18: Growtopia Gacha Simulator & Per-Category Live Leaderboards (cogs/gacha_simulator.py)
- /gacha (Roll 1x, 10x, 25x, or 50x on 5 iconic Growtopia Gacha events with a 1-minute per-user cooldown)
- Interactive persistent Gacha Hub in #🎰gacha-simulator (1-click Roll 10x buttons for all 5 Gachas)
- Read-only #🏆gacha-leaderboards with sleek Pill-Row Table leaderboards (matching the Mr. Pulsar style)
- 3-Layer Sync Engine:
  1. Instant push update (message.edit) to the specific Gacha category card in #🏆gacha-leaderboards on every roll
  2. Discord-native state recovery on bot startup (parses hidden URL fragment metadata on each table row)
  3. 5-minute background verification loop
"""

from __future__ import annotations

from datetime import datetime
import json
import random
import re
import time
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs, quote, unquote

import discord
from discord import app_commands
from discord.ext import commands, tasks

from utils.helpers import (
    EVENT_TZ,
    FOOTER_TEXT,
    PROJECT_ROOT,
    load_state,
    logger,
    save_state,
)

if TYPE_CHECKING:
    from bot import EventBot

ACTIVITIES_CATEGORY_ID = 1567242649893609512
MEMBER_ROLE_ID = 1568495447067332608
GACHA_COOLDOWN_SECONDS = 60
GACHA_STATS_FILE = PROJECT_ROOT / "bots" / "event-bot" / "data" / "gacha_stats.json"


# 5 Iconic Growtopia Gacha Pools with realistic weighted probabilities & WL values
GACHA_POOLS: dict[str, dict[str, Any]] = {
    "valentine_gbc": {
        "name": "Valentine's Super GBC",
        "short_name": "Valentine's GBC",
        "emoji": "💘",
        "cost_wl": 5,
        "color": (233, 30, 99),
        "banner_desc": "Open **Super Golden Booty Chests** during Valentine's Week to hunt the legendary **Golden Heart Crystal (GHC)**!",
        "jackpot_item": "Golden Heart Crystal",
        "drops": [
            {"name": "Golden Heart Crystal", "rarity_tier": "🌟 MYTHIC JACKPOT", "short_tier": "MYTHIC", "weight": 0.15, "wl_value": 12500, "emoji": "💎"},
            {"name": "Golden Angel Wings", "rarity_tier": "🔥 ULTRA RARE", "short_tier": "ULTRA RARE", "weight": 0.45, "wl_value": 1800, "emoji": "👼"},
            {"name": "Heartbow", "rarity_tier": "✨ SUPER RARE", "short_tier": "SUPER RARE", "weight": 2.40, "wl_value": 85, "emoji": "🏹"},
            {"name": "Ruby Lock", "rarity_tier": "💜 RARE", "short_tier": "RARE", "weight": 8.00, "wl_value": 15, "emoji": "🔒"},
            {"name": "Lovebird", "rarity_tier": "💙 UNCOMMON", "short_tier": "UNCOMMON", "weight": 18.00, "wl_value": 4, "emoji": "🐦"},
            {"name": "Heartstone Block (x20)", "rarity_tier": "🤍 COMMON", "short_tier": "COMMON", "weight": 35.00, "wl_value": 1, "emoji": "🧱"},
            {"name": "Valentine Candy (x5)", "rarity_tier": "🤍 COMMON", "short_tier": "COMMON", "weight": 36.00, "wl_value": 1, "emoji": "🍬"},
        ],
    },
    "summer_fireworks": {
        "name": "SummerFest Super Fireworks",
        "short_name": "SummerFest Fireworks",
        "emoji": "🎆",
        "cost_wl": 8,
        "color": (255, 152, 0),
        "banner_desc": "Launch **Super Fireworks** & **Summer Artifact Chests** to summon the **Phoenix Wings**!",
        "jackpot_item": "Phoenix Wings",
        "drops": [
            {"name": "Phoenix Wings", "rarity_tier": "🌟 MYTHIC JACKPOT", "short_tier": "MYTHIC", "weight": 0.12, "wl_value": 22000, "emoji": "🦅"},
            {"name": "Phoenix Pacifier", "rarity_tier": "🔥 ULTRA RARE", "short_tier": "ULTRA RARE", "weight": 0.40, "wl_value": 3200, "emoji": "🔥"},
            {"name": "Phoenix Sword", "rarity_tier": "✨ SUPER RARE", "short_tier": "SUPER RARE", "weight": 2.20, "wl_value": 140, "emoji": "⚔️"},
            {"name": "Summer Surprise", "rarity_tier": "💜 RARE", "short_tier": "RARE", "weight": 9.00, "wl_value": 22, "emoji": "🎁"},
            {"name": "Rayman's Fist Token", "rarity_tier": "💙 UNCOMMON", "short_tier": "UNCOMMON", "weight": 17.28, "wl_value": 6, "emoji": "🥊"},
            {"name": "Beach Blast (x5)", "rarity_tier": "🤍 COMMON", "short_tier": "COMMON", "weight": 35.00, "wl_value": 2, "emoji": "🏖️"},
            {"name": "Firecracker (x20)", "rarity_tier": "🤍 COMMON", "short_tier": "COMMON", "weight": 36.00, "wl_value": 1, "emoji": "🧨"},
        ],
    },
    "halloween_growganoth": {
        "name": "Halloween Growganoth Sacrifice",
        "short_name": "Halloween Growganoth",
        "emoji": "🎃",
        "cost_wl": 10,
        "color": (156, 39, 176),
        "banner_desc": "Drop **Dark Tickets** into the Maw of Growganoth for **Nightmare Devil Wings** & **Devil Wings**!",
        "jackpot_item": "Nightmare Devil Wings",
        "drops": [
            {"name": "Nightmare Devil Wings", "rarity_tier": "🌟 MYTHIC JACKPOT", "short_tier": "MYTHIC", "weight": 0.20, "wl_value": 9500, "emoji": "🦇"},
            {"name": "Devil Wings", "rarity_tier": "🔥 ULTRA RARE", "short_tier": "ULTRA RARE", "weight": 0.65, "wl_value": 2400, "emoji": "😈"},
            {"name": "Cursed Spirit Pendant", "rarity_tier": "✨ SUPER RARE", "short_tier": "SUPER RARE", "weight": 2.65, "wl_value": 180, "emoji": "📿"},
            {"name": "Abominable Claws", "rarity_tier": "💜 RARE", "short_tier": "RARE", "weight": 9.50, "wl_value": 28, "emoji": "🐾"},
            {"name": "Vampire Cape", "rarity_tier": "💙 UNCOMMON", "short_tier": "UNCOMMON", "weight": 18.00, "wl_value": 7, "emoji": "🧛"},
            {"name": "Spooky Cobweb (x15)", "rarity_tier": "🤍 COMMON", "short_tier": "COMMON", "weight": 34.00, "wl_value": 2, "emoji": "🕸️"},
            {"name": "Candy Corn (x20)", "rarity_tier": "🤍 COMMON", "short_tier": "COMMON", "weight": 35.00, "wl_value": 1, "emoji": "🌽"},
        ],
    },
    "winter_wish": {
        "name": "WinterFest Royal Winter Chest",
        "short_name": "WinterFest Royal Chest",
        "emoji": "❄️",
        "cost_wl": 6,
        "color": (3, 169, 244),
        "banner_desc": "Crack open **Royal Winter Chests** & **Winter Wishes** for the **Ice Dragon Hand** & **Frost Bow**!",
        "jackpot_item": "Ice Dragon Hand",
        "drops": [
            {"name": "Ice Dragon Hand", "rarity_tier": "🌟 MYTHIC JACKPOT", "short_tier": "MYTHIC", "weight": 0.18, "wl_value": 8200, "emoji": "🐉"},
            {"name": "Winter Frost Bow", "rarity_tier": "🔥 ULTRA RARE", "short_tier": "ULTRA RARE", "weight": 0.55, "wl_value": 1600, "emoji": "🏹"},
            {"name": "Snowy Night Cloak", "rarity_tier": "✨ SUPER RARE", "short_tier": "SUPER RARE", "weight": 2.50, "wl_value": 110, "emoji": "🧥"},
            {"name": "Snowfrost Top Hat", "rarity_tier": "💜 RARE", "short_tier": "RARE", "weight": 8.77, "wl_value": 18, "emoji": "🎩"},
            {"name": "Antler Hat", "rarity_tier": "💙 UNCOMMON", "short_tier": "UNCOMMON", "weight": 18.00, "wl_value": 5, "emoji": "🦌"},
            {"name": "Snowball (x25)", "rarity_tier": "🤍 COMMON", "short_tier": "COMMON", "weight": 35.00, "wl_value": 1, "emoji": "⛄"},
            {"name": "Candy Cane Block (x20)", "rarity_tier": "🤍 COMMON", "short_tier": "COMMON", "weight": 35.00, "wl_value": 1, "emoji": "🍭"},
        ],
    },
    "lunar_well": {
        "name": "Lunar Well of Fortune",
        "short_name": "Lunar Well of Fortune",
        "emoji": "🧧",
        "cost_wl": 6,
        "color": (244, 67, 54),
        "banner_desc": "Toss **Fortune Cookies** & **Lucky Coins** into the Well of Fortune for the **Golden Dragon Statue**!",
        "jackpot_item": "Golden Dragon Statue",
        "drops": [
            {"name": "Golden Dragon Statue", "rarity_tier": "🌟 MYTHIC JACKPOT", "short_tier": "MYTHIC", "weight": 0.16, "wl_value": 9000, "emoji": "🐲"},
            {"name": "Jade Dragon Spear", "rarity_tier": "🔥 ULTRA RARE", "short_tier": "ULTRA RARE", "weight": 0.54, "wl_value": 1750, "emoji": "🔱"},
            {"name": "Lunar Silk Robe", "rarity_tier": "✨ SUPER RARE", "short_tier": "SUPER RARE", "weight": 2.50, "wl_value": 115, "emoji": "👘"},
            {"name": "Red Envelope Surprise", "rarity_tier": "💜 RARE", "short_tier": "RARE", "weight": 8.80, "wl_value": 20, "emoji": "🧧"},
            {"name": "Lucky Lantern", "rarity_tier": "💙 UNCOMMON", "short_tier": "UNCOMMON", "weight": 18.00, "wl_value": 5, "emoji": "🏮"},
            {"name": "BaoBun (x10)", "rarity_tier": "🤍 COMMON", "short_tier": "COMMON", "weight": 35.00, "wl_value": 1, "emoji": "🥟"},
            {"name": "Fortune Cookie Crumbs", "rarity_tier": "🤍 COMMON", "short_tier": "COMMON", "weight": 35.00, "wl_value": 1, "emoji": "🥠"},
        ],
    },
}


def load_gacha_stats() -> dict[str, dict[str, dict[str, Any]]]:
    if GACHA_STATS_FILE.exists():
        try:
            data = json.loads(GACHA_STATS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {k: {} for k in GACHA_POOLS}


def save_gacha_stats(stats: dict[str, dict[str, dict[str, Any]]]) -> None:
    GACHA_STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
    GACHA_STATS_FILE.write_text(json.dumps(stats, indent=2), encoding="utf-8")


def _clean_ascii_name(raw_name: str, max_len: int = 14) -> str:
    cleaned = "".join(ch for ch in raw_name if 32 <= ord(ch) <= 126 and ch != "`").strip()
    if not cleaned:
        cleaned = "Player"
    return cleaned[:max_len]


def build_category_leaderboard_embed(pool_key: str, cat_stats: dict[str, dict[str, Any]]) -> discord.Embed:
    """
    Build the sleek Pill-Row Table Leaderboard (matching the Mr. Pulsar reference):
    - Bold inline-code header pill: **`Rank  User            Mythic   Won (WL)    Rolls`**
    - Cyan linked inline-code row pills: [`#1    Manwel          0 (0U)   436 WL      50   `](https://...)
    """
    pool = GACHA_POOLS[pool_key]
    r, g, b = pool["color"]

    total_cat_rolls = sum(int(v.get("rolls", 0)) for v in cat_stats.values())
    total_cat_mythics = sum(int(v.get("mythics", 0)) for v in cat_stats.values())
    total_cat_won = sum(int(v.get("won_wl", 0)) for v in cat_stats.values())

    embed = discord.Embed(
        title=f"{pool['emoji']} {pool['name']}",
        description=(
            f"{pool['banner_desc']}\n"
            f"🎯 **Jackpot:** `{pool['jackpot_item']}`  •  💰 **Cost:** `{pool['cost_wl']} WL/roll`  •  "
            f"🎲 **Total Rolls:** `{total_cat_rolls:,}`"
        ),
        color=discord.Color.from_rgb(r, g, b),
        timestamp=datetime.now(EVENT_TZ),
    )

    header_pill = "**`Rank  User            Mythic   Won (WL)    Rolls`**"
    rows: list[str] = [header_pill]

    if not cat_stats:
        empty_pill = "[`#--   No pulls yet    0 (0U)   0 WL        0    `](https://discord.com/channels/1567168949584658534/1568907253854113855)"
        rows.append(empty_pill)
    else:
        sorted_players = sorted(
            cat_stats.items(),
            key=lambda kv: (
                int(kv[1].get("mythics", 0)),
                int(kv[1].get("won_wl", 0)),
                int(kv[1].get("won_wl", 0)) - int(kv[1].get("spent_wl", 0)),
            ),
            reverse=True,
        )[:10]

        for idx, (uid, pdata) in enumerate(sorted_players):
            rank_col = f"#{idx + 1}"
            raw_name = str(pdata.get("name") or f"User-{str(uid)[-4:]}")
            user_col = _clean_ascii_name(raw_name, 14)
            rolls = int(pdata.get("rolls", 0))
            spent = int(pdata.get("spent_wl", 0))
            won = int(pdata.get("won_wl", 0))
            mythics = int(pdata.get("mythics", 0))
            ultras = int(pdata.get("ultra_rares", 0))
            best_drop = str(pdata.get("best_drop", "None"))
            best_wl = int(pdata.get("best_wl", 0))

            mythic_col = f"{mythics} ({ultras}U)"
            won_col = f"{won:,} WL"
            rolls_col = f"{rolls:,}"

            # 48-character fixed-width pill row (never wraps, aligns identically to Mr. Pulsar)
            row_text = (
                f"{rank_col:<6}"
                f"{user_col:<16}"
                f"{mythic_col:<9}"
                f"{won_col:<12}"
                f"{rolls_col:<5}"
            )
            # Store exact lossless stats inside the URL fragment so startup recovery is 100% invisible & automatic
            frag = (
                f"uid={uid}&name={quote(user_col)}&m={mythics}&u={ultras}"
                f"&won={won}&spent={spent}&rolls={rolls}&best={quote(best_drop)}&bwl={best_wl}"
            )
            url = f"https://discord.com/channels/1567168949584658534/1568907253854113855#{frag}"
            rows.append(f"[`{row_text}`]({url})")

    embed.add_field(
        name=f"🏆 {pool['short_name']} Leaderboard ({total_cat_mythics} Jackpots • {total_cat_won:,} WL Won)",
        value="\n".join(rows),
        inline=False,
    )

    embed.set_footer(text=f"{FOOTER_TEXT} • Auto-Synced Live from #🎰gacha-simulator")
    return embed


class GachaQuickRollView(discord.ui.View):
    """Persistent quick-roll buttons pinned in #🎰gacha-simulator and attached to every roll result."""

    def __init__(self, cog: GachaSimulatorCog) -> None:
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="Valentine GBC (10x)",
        style=discord.ButtonStyle.danger,
        emoji="💘",
        custom_id="gacha_roll:valentine_gbc:10",
        row=0,
    )
    async def roll_valentine(self, interaction: discord.Interaction, _btn: discord.ui.Button) -> None:
        await self.cog.handle_gacha_roll(interaction, "valentine_gbc", 10)

    @discord.ui.button(
        label="Summer Fireworks (10x)",
        style=discord.ButtonStyle.primary,
        emoji="🎆",
        custom_id="gacha_roll:summer_fireworks:10",
        row=0,
    )
    async def roll_summer(self, interaction: discord.Interaction, _btn: discord.ui.Button) -> None:
        await self.cog.handle_gacha_roll(interaction, "summer_fireworks", 10)

    @discord.ui.button(
        label="Halloween Dark Ticket (10x)",
        style=discord.ButtonStyle.secondary,
        emoji="🎃",
        custom_id="gacha_roll:halloween_growganoth:10",
        row=0,
    )
    async def roll_halloween(self, interaction: discord.Interaction, _btn: discord.ui.Button) -> None:
        await self.cog.handle_gacha_roll(interaction, "halloween_growganoth", 10)

    @discord.ui.button(
        label="WinterFest Chest (10x)",
        style=discord.ButtonStyle.primary,
        emoji="❄️",
        custom_id="gacha_roll:winter_wish:10",
        row=1,
    )
    async def roll_winter(self, interaction: discord.Interaction, _btn: discord.ui.Button) -> None:
        await self.cog.handle_gacha_roll(interaction, "winter_wish", 10)

    @discord.ui.button(
        label="Lunar Well (10x)",
        style=discord.ButtonStyle.success,
        emoji="🧧",
        custom_id="gacha_roll:lunar_well:10",
        row=1,
    )
    async def roll_lunar(self, interaction: discord.Interaction, _btn: discord.ui.Button) -> None:
        await self.cog.handle_gacha_roll(interaction, "lunar_well", 10)


class GachaSimulatorCog(commands.Cog, name="Gacha Simulator"):
    def __init__(self, bot: EventBot) -> None:
        self.bot = bot
        self._cooldowns: dict[int, float] = {}
        self._startup_synced: bool = False

    async def cog_load(self) -> None:
        self.bot.add_view(GachaQuickRollView(self))
        self.leaderboard_sync_loop.start()

    async def cog_unload(self) -> None:
        self.leaderboard_sync_loop.cancel()

    def check_user_cooldown(self, user_id: int) -> int | None:
        """Enforce the 1-minute (60s) rate limit per user across both /gacha and quick-roll buttons."""
        now = time.time()
        expires_at = self._cooldowns.get(user_id, 0.0)
        if now < expires_at:
            return int(expires_at)
        self._cooldowns[user_id] = now + GACHA_COOLDOWN_SECONDS
        return None

    async def recover_stats_from_discord(self, guild: discord.Guild) -> None:
        """
        Discord-as-Database Recovery:
        Parses hidden URL fragments (`#uid=...&won=...&rolls=...`) inside the Pill-Row Table links
        in #🏆gacha-leaderboards so container restarts never wipe player scores!
        """
        state = load_state()
        lb_channel_id = state.get("gacha_leaderboard_channel_id")
        if not lb_channel_id:
            return

        lb_channel = guild.get_channel(int(lb_channel_id))
        if not isinstance(lb_channel, discord.TextChannel):
            try:
                lb_channel = await self.bot.fetch_channel(int(lb_channel_id))  # type: ignore[assignment]
            except Exception:
                return

        if not isinstance(lb_channel, discord.TextChannel):
            return

        stats = load_gacha_stats()
        frag_pattern = re.compile(r"#(uid=\d+&[^\)]+)\)")

        try:
            async for msg in lb_channel.history(limit=20):
                if msg.author.id != (self.bot.user.id if self.bot.user else 0) or not msg.embeds:
                    continue
                emb = msg.embeds[0]
                title = emb.title or ""
                matched_pool_key: str | None = None
                for pk, pinfo in GACHA_POOLS.items():
                    if pinfo["name"] in title:
                        matched_pool_key = pk
                        break
                if not matched_pool_key:
                    continue

                msg_map = state.get("gacha_leaderboard_message_ids", {})
                if msg_map.get(matched_pool_key) != msg.id:
                    msg_map[matched_pool_key] = msg.id
                    state["gacha_leaderboard_message_ids"] = msg_map
                    save_state(state)

                for field in emb.fields:
                    for line in (field.value or "").splitlines():
                        m_frag = frag_pattern.search(line)
                        if not m_frag:
                            continue
                        qs = parse_qs(m_frag.group(1))
                        uid = (qs.get("uid") or [""])[0]
                        if not uid:
                            continue
                        pname = unquote((qs.get("name") or ["Player"])[0])
                        mythics = int((qs.get("m") or ["0"])[0])
                        ultras = int((qs.get("u") or ["0"])[0])
                        won = int((qs.get("won") or ["0"])[0])
                        spent = int((qs.get("spent") or ["0"])[0])
                        rolls = int((qs.get("rolls") or ["0"])[0])
                        best_drop = unquote((qs.get("best") or ["None"])[0])
                        best_wl = int((qs.get("bwl") or ["0"])[0])

                        cat_bucket = stats.setdefault(matched_pool_key, {})
                        existing = cat_bucket.get(uid)
                        if not existing or int(existing.get("rolls", 0)) < rolls:
                            cat_bucket[uid] = {
                                "name": pname,
                                "rolls": rolls,
                                "spent_wl": spent,
                                "won_wl": won,
                                "mythics": mythics,
                                "ultra_rares": ultras,
                                "best_drop": best_drop,
                                "best_wl": best_wl,
                            }
            save_gacha_stats(stats)
        except Exception as exc:
            logger.warning("Failed to recover gacha stats from Discord history: %s", exc)

    async def update_leaderboard_card(self, guild: discord.Guild, pool_key: str) -> None:
        """Immediately push-update the specific Gacha category's leaderboard embed in #🏆gacha-leaderboards."""
        state = load_state()
        lb_channel_id = state.get("gacha_leaderboard_channel_id")
        if not lb_channel_id:
            return

        lb_channel = guild.get_channel(int(lb_channel_id))
        if not isinstance(lb_channel, discord.TextChannel):
            try:
                lb_channel = await self.bot.fetch_channel(int(lb_channel_id))  # type: ignore[assignment]
            except Exception:
                return

        if not isinstance(lb_channel, discord.TextChannel):
            return

        stats = load_gacha_stats()
        cat_stats = stats.get(pool_key, {})
        embed = build_category_leaderboard_embed(pool_key, cat_stats)

        msg_map: dict[str, int] = state.get("gacha_leaderboard_message_ids", {})
        msg_id = msg_map.get(pool_key)

        if msg_id:
            try:
                msg = await lb_channel.fetch_message(int(msg_id))
                await msg.edit(embed=embed)
                return
            except discord.NotFound:
                pass
            except Exception as exc:
                logger.warning("Could not edit gacha leaderboard message %s: %s", msg_id, exc)
                return

        try:
            new_msg = await lb_channel.send(embed=embed)
            msg_map[pool_key] = new_msg.id
            state["gacha_leaderboard_message_ids"] = msg_map
            save_state(state)
        except Exception as exc:
            logger.warning("Could not create gacha leaderboard message for %s: %s", pool_key, exc)

    @tasks.loop(minutes=5)
    async def leaderboard_sync_loop(self) -> None:
        """Self-healing 5-minute background sync to guarantee #🏆gacha-leaderboards stays 100% in sync."""
        for guild in self.bot.guilds:
            if not self._startup_synced:
                await self.recover_stats_from_discord(guild)
                self._startup_synced = True
            for pool_key in GACHA_POOLS:
                await self.update_leaderboard_card(guild, pool_key)

    @leaderboard_sync_loop.before_loop
    async def before_leaderboard_sync_loop(self) -> None:
        await self.bot.wait_until_ready()

    async def handle_gacha_roll(
        self,
        interaction: discord.Interaction,
        pool_key: str,
        count: int,
        from_slash: bool = False,
    ) -> None:
        state = load_state()
        allowed_channel_id = state.get("gacha_channel_id")
        if allowed_channel_id and int(interaction.channel_id or 0) != int(allowed_channel_id):
            await interaction.response.send_message(
                f"❌ The Gacha Simulator can only be used inside <#{allowed_channel_id}>!",
                ephemeral=True,
            )
            return

        exp_ts = self.check_user_cooldown(interaction.user.id)
        if exp_ts is not None:
            await interaction.response.send_message(
                f"⏳ **Gacha Cooldown Active!** You can roll again <t:{exp_ts}:R> (at <t:{exp_ts}:T>).\n"
                f"*(Gacha Simulator has a **1-minute** rate limit per player!)*",
                ephemeral=True,
            )
            return

        if not interaction.response.is_done():
            await interaction.response.defer()

        if interaction.guild and not self._startup_synced:
            await self.recover_stats_from_discord(interaction.guild)
            self._startup_synced = True

        pool = GACHA_POOLS.get(pool_key, GACHA_POOLS["valentine_gbc"])
        count = max(1, min(count, 50))
        drops_list = pool["drops"]
        weights = [float(d["weight"]) for d in drops_list]

        rolled_items = random.choices(drops_list, weights=weights, k=count)

        spent_wl = count * int(pool["cost_wl"])
        won_wl = sum(int(d["wl_value"]) for d in rolled_items)
        net_wl = won_wl - spent_wl

        tally: dict[str, dict[str, Any]] = {}
        mythics_pulled = 0
        ultras_pulled = 0
        best_single_item = rolled_items[0]

        for item in rolled_items:
            if int(item["wl_value"]) > int(best_single_item["wl_value"]):
                best_single_item = item
            if "MYTHIC" in item["rarity_tier"]:
                mythics_pulled += 1
            elif "ULTRA" in item["rarity_tier"]:
                ultras_pulled += 1

            entry = tally.setdefault(
                item["name"],
                {
                    "count": 0,
                    "wl_value": int(item["wl_value"]),
                    "rarity_tier": item["rarity_tier"],
                    "short_tier": item.get("short_tier", "COMMON"),
                    "emoji": item["emoji"],
                },
            )
            entry["count"] += 1

        # Update persistent player stats for this Gacha category
        stats = load_gacha_stats()
        cat_bucket = stats.setdefault(pool_key, {})
        uid_str = str(interaction.user.id)
        pstats = cat_bucket.setdefault(
            uid_str,
            {
                "name": interaction.user.display_name,
                "rolls": 0,
                "spent_wl": 0,
                "won_wl": 0,
                "mythics": 0,
                "ultra_rares": 0,
                "best_drop": "None",
                "best_wl": 0,
            },
        )
        pstats["name"] = interaction.user.display_name
        pstats["rolls"] = int(pstats.get("rolls", 0)) + count
        pstats["spent_wl"] = int(pstats.get("spent_wl", 0)) + spent_wl
        pstats["won_wl"] = int(pstats.get("won_wl", 0)) + won_wl
        pstats["mythics"] = int(pstats.get("mythics", 0)) + mythics_pulled
        pstats["ultra_rares"] = int(pstats.get("ultra_rares", 0)) + ultras_pulled
        if int(best_single_item["wl_value"]) >= int(pstats.get("best_wl", 0)):
            pstats["best_wl"] = int(best_single_item["wl_value"])
            pstats["best_drop"] = best_single_item["name"]

        save_gacha_stats(stats)

        # Build Roll Result Embed with Pill-Row Unbox Table matching the reference image
        r, g, b = pool["color"]
        if mythics_pulled > 0:
            r, g, b = (255, 215, 0)

        sorted_tally = sorted(tally.items(), key=lambda kv: kv[1]["wl_value"], reverse=True)
        u_rows: list[str] = ["**`Qty    Item Unboxed            Tier         Value   `**"]
        for iname, info in sorted_tally:
            sub_val = info["count"] * info["wl_value"]
            qty_col = f"{info['count']}x"
            item_col = _clean_ascii_name(iname, 22)
            tier_col = _clean_ascii_name(info.get("short_tier", "COMMON"), 11)
            val_col = f"{sub_val:,} WL"
            row_txt = f"{qty_col:<7}{item_col:<24}{tier_col:<13}{val_col:<8}"
            u_rows.append(
                f"[`{row_txt}`](https://discord.com/channels/1567168949584658534/1568907256467169381)"
            )

        net_emoji = "📈" if net_wl >= 0 else "📉"
        net_str = f"+{net_wl:,} WL" if net_wl >= 0 else f"{net_wl:,} WL"

        jackpot_banner = ""
        if mythics_pulled > 0:
            jackpot_banner = (
                f"🚨 **MYTHIC JACKPOT UNBOXED!!** <@{interaction.user.id}> just pulled "
                f"**`{mythics_pulled}x` {pool['jackpot_item']}**!!\n\n"
            )

        embed = discord.Embed(
            title=f"{pool['emoji']} {pool['name']} — {count}x Gacha Roll",
            description=(
                f"{jackpot_banner}"
                f"👤 **Roller:** <@{interaction.user.id}>\n"
                f"💸 **Spent:** `{spent_wl:,} WL`  •  💎 **Value Unboxed:** `{won_wl:,} WL`  •  "
                f"{net_emoji} **Net Profit:** `{net_str}`"
            ),
            color=discord.Color.from_rgb(r, g, b),
            timestamp=datetime.now(EVENT_TZ),
        )
        embed.add_field(
            name="🎁 Items Unboxed",
            value="\n".join(u_rows),
            inline=False,
        )

        lifetime_net = int(pstats["won_wl"]) - int(pstats["spent_wl"])
        lifetime_net_str = f"+{lifetime_net:,} WL" if lifetime_net >= 0 else f"{lifetime_net:,} WL"
        lb_ch_id = state.get("gacha_leaderboard_channel_id")
        lb_mention = f"<#{lb_ch_id}>" if lb_ch_id else "`#🏆gacha-leaderboards`"

        embed.add_field(
            name=f"📊 Your Lifetime {pool['short_name']} Stats (Synced to {lb_mention})",
            value=(
                f"• **Total Rolls:** `{pstats['rolls']:,}`  •  **Mythic Jackpots:** `{pstats['mythics']}`\n"
                f"• **Lifetime Won:** `{pstats['won_wl']:,} WL` (`Net: {lifetime_net_str}`)  •  **Best Pull:** `{pstats['best_drop']}`"
            ),
            inline=False,
        )
        embed.set_footer(text=f"{FOOTER_TEXT} • 1-Minute Cooldown • Live Leaderboard Auto-Updated")

        await interaction.followup.send(embed=embed, view=GachaQuickRollView(self))

        if interaction.guild:
            await self.update_leaderboard_card(interaction.guild, pool_key)

    @app_commands.command(
        name="gacha",
        description="Roll Growtopia Gacha boxes (Valentine GBC, Summer Fireworks, Growganoth, WinterFest, Lunar Well)!",
    )
    @app_commands.describe(
        category="Choose which Growtopia Gacha event to roll",
        rolls="Number of rolls to open at once (1x, 10x, 25x, or 50x)",
    )
    @app_commands.choices(
        category=[
            app_commands.Choice(name="💘 Valentine's Super GBC (Hunt Golden Heart Crystal)", value="valentine_gbc"),
            app_commands.Choice(name="🎆 SummerFest Super Fireworks (Hunt Phoenix Wings)", value="summer_fireworks"),
            app_commands.Choice(name="🎃 Halloween Growganoth Dark Ticket (Hunt Nightmare Devil Wings)", value="halloween_growganoth"),
            app_commands.Choice(name="❄️ WinterFest Royal Winter Chest (Hunt Ice Dragon Hand)", value="winter_wish"),
            app_commands.Choice(name="🧧 Lunar New Year Well of Fortune (Hunt Golden Dragon Statue)", value="lunar_well"),
        ],
        rolls=[
            app_commands.Choice(name="1x Single Roll", value=1),
            app_commands.Choice(name="10x Multi-Roll (Recommended)", value=10),
            app_commands.Choice(name="25x Mega Roll", value=25),
            app_commands.Choice(name="50x Whale Roll (Max)", value=50),
        ],
    )
    async def gacha_command(
        self,
        interaction: discord.Interaction,
        category: str = "valentine_gbc",
        rolls: int = 10,
    ) -> None:
        await self.handle_gacha_roll(interaction, category, rolls, from_slash=True)


async def setup(bot: EventBot) -> None:
    await bot.add_cog(GachaSimulatorCog(bot))
