"""
Category 1: Daily Events, Auto-DQ Feed, & Dynamic Daily Challenge Feed (cogs/daily_events.py)
- 1:00 PM (00:00 GT) Daily Reset Scheduler & Self-Healing Poller
- #dq-feed Auto-Detection Listener (Supports Discord Components V2 used by The Lost Nemo!, Embeds, & Plaintext)
- #⚔️daily-challenges Auto-Detection Listener (Parses official Growtopia #🗓daily-challenges 25-hour cycle banners)
- /daily, /set_daily, /set_daily_channel, /set_dq_feed_channel
"""

from __future__ import annotations

from datetime import datetime
import os
import re
import time
from typing import TYPE_CHECKING, Any

import discord
from discord import app_commands
from discord.ext import commands, tasks

from utils.helpers import (
    DAILY_TRIGGER_TIME,
    EVENT_TZ,
    FOOTER_TEXT,
    is_server_manager,
    load_state,
    logger,
    save_state,
)

if TYPE_CHECKING:
    from bot import EventBot

DEFAULT_DC_FEED_CHANNEL_ID = 1567229570237726872

DAILY_CHALLENGE_CATALOG: dict[str, tuple[str, str]] = {
    "doctors-duel": ("Doctor's Duel", "Perform surgeries for points (+30 to +250 pts per surgery)."),
    "fish-frenzy": ("Fish Frenzy", "Catch fish for points (+1 pt per lb of fish caught)."),
    "star-strife": ("Star Strife", "Complete Star Missions for points (+20 to +200 pts per mission)."),
    "chef-showdown": ("Chef Showdown", "Cook food for points without assistance (up to +160 pts per 100% dish)."),
    "crystal-crusher": ("Crystal Crusher", "Harmonize and smash crystals (+1 to +5 pts per crystal)."),
    "card-clash": ("Card Clash", "Defeat Crime-Fighting Supervillains (+50 pts per supervillain)."),
    "treasure-turmoil": ("Treasure Turmoil", "Obtain Map Fragments (+1 pt) and solve Treasure Maps (+50 to +500 pts)."),
    "malady-mash": ("Malady Mash", "Perform surgeries on patients with a Malady (+100 to +230 pts)."),
    "radiation-race": ("Radiation Race", "Find Uranium Blocks in GEIGERHILLS (+1 pt per Uranium Block)."),
    "chemical-conundrum": ("Chemical Conundrum", "Create Synthetic Chemicals without assistance (+100 pts each)."),
    "war-of-wolves": ("War of Wolves", "Complete WOLFWORLD parkours (+1 pt per second remaining)."),
    "battlers-beatdown": ("Battler's Beatdown", "Win Pet Battles against a Pet Trainer (+1 pt per win)."),
    "boo-blast": ("BOO Blast", "Hit (+1 pt) and defeat (+100 pts) Boss Ghosts."),
    "mutant-kitchen": ("Mutant Kitchen", "Cook Mutant Food for points without assistance (up to +160 pts)."),
}


def format_dynamic_challenge_from_feed(slug: str, start_ts: int) -> str:
    """Format the live Daily Challenge status and 25-hour cycle countdown from #⚔️daily-challenges."""
    clean_slug = slug.strip().lower()
    title, desc = DAILY_CHALLENGE_CATALOG.get(
        clean_slug,
        (clean_slug.replace("-", " ").title(), "2-hour in-game competition."),
    )
    now_ts = int(time.time())
    end_ts = start_ts + 7200       # Each Daily Challenge lasts 2 hours
    next_ts = start_ts + 90000     # Next Daily Challenge starts 25 hours after previous start

    if now_ts < end_ts:
        return (
            f"🟢 **LIVE NOW: {title}** — {desc}\n"
            f"⏰ **Ends:** <t:{end_ts}:R>  •  ⏭️ **Next (25h cycle):** <t:{next_ts}:t> (<t:{next_ts}:R>)"
        )
    return (
        f"**{title}** — {desc}\n"
        f"✅ **Last Active:** <t:{start_ts}:R>  •  ⏭️ **Next Challenge (~25h cycle):** <t:{next_ts}:f> (<t:{next_ts}:R>)"
    )


def build_daily_reset_embed(data: dict[str, Any]) -> discord.Embed:
    """Build the formatted 1:00 PM Daily Quest, Role Day, and Daily Challenge embed."""
    gt_date = data.get("gt_date", "Today")
    reset_ts = int(data.get("local_reset_timestamp", int(datetime.now(EVENT_TZ).timestamp())))
    next_reset_ts = reset_ts + 86400

    header_lines = [
        f"⏰ **Daily Reset:** <t:{reset_ts}:t> (<t:{reset_ts}:R>)",
        f"⏭️ **Next Reset:** <t:{next_reset_ts}:t> (<t:{next_reset_ts}:R>)",
    ]
    online_users = data.get("online_users")
    wotd_name = data.get("wotd_name")
    if online_users and online_users != "N/A":
        wotd_part = f"  •  🗺️ **WOTD:** `{wotd_name}`" if wotd_name and wotd_name != "N/A" else ""
        header_lines.append(f"🌐 **Online Players:** `{online_users}`{wotd_part}")

    embed = discord.Embed(
        title=f"🌅 Growtopia Daily Reset — {gt_date}",
        description="\n".join(header_lines),
        color=discord.Color.from_rgb(46, 204, 113),
        timestamp=datetime.now(EVENT_TZ),
    )

    # 1. Role Day
    role_day = data.get("role_day", "Unknown")
    role_bonus = data.get("role_day_bonus", "")
    tomorrow_role = data.get("tomorrow_role_day", "Unknown")
    embed.add_field(
        name=f"🛠️ Role Day: {role_day} Day",
        value=f"{role_bonus}\n*⏭️ Tomorrow's Role: **{tomorrow_role}***",
        inline=False,
    )

    # 2. Daily Challenge (Dynamic 25-hour cycle synced from #⚔️daily-challenges)
    daily_challenge = data.get("daily_challenge", "⏳ Syncing from #⚔️daily-challenges...")
    embed.add_field(
        name="🏆 Daily Challenge (25-Hour Cycle)",
        value=daily_challenge,
        inline=False,
    )

    # 3. Daily Quest (Crazy Jim)
    dq_items = data.get("daily_quest_items") or []
    if dq_items:
        lines: list[str] = []
        for idx, item in enumerate(dq_items, start=1):
            qty = item.get("quantity", "?")
            name = item.get("name", "Unknown Item")
            rarity = item.get("rarity")
            rarity_str = f" *(Rarity {rarity})*" if rarity and rarity != "None" else ""
            recipes = item.get("recipe") or []
            recipe_str = f"\n   ↳ 🧬 `{recipes[0]}`" if recipes else ""
            lines.append(f"**{idx}.** `{qty}x` **{name}**{rarity_str}{recipe_str}")
        dq_text = "\n".join(lines)
        first_sprite = dq_items[0].get("sprite_url")
        if first_sprite:
            embed.set_thumbnail(url=first_sprite)
    else:
        dq_text = (
            "⏳ *Waiting for `#dq-feed` (**The Lost Nemo!**) to post today's Crazy Jim items...*\n"
            "*(Auto-updates the second `#dq-feed` posts, or Admins can click **📝 Set Today's DQ** below!)*"
        )

    embed.add_field(
        name="🧪 Daily Quest (Crazy Jim)",
        value=dq_text,
        inline=False,
    )

    embed.set_footer(text=FOOTER_TEXT)
    return embed


def _collect_text_from_raw_dict(obj: Any) -> list[str]:
    """Recursively collect all text strings from Discord raw message JSON (including Components V2 type 17/10)."""
    chunks: list[str] = []
    if isinstance(obj, dict):
        for key in ("content", "title", "description", "name", "value"):
            val = obj.get(key)
            if isinstance(val, str) and val.strip():
                chunks.append(val)
        for list_key in ("embeds", "components", "fields"):
            sub_list = obj.get(list_key)
            if isinstance(sub_list, list):
                for item in sub_list:
                    chunks.extend(_collect_text_from_raw_dict(item))
    elif isinstance(obj, list):
        for item in obj:
            chunks.extend(_collect_text_from_raw_dict(item))
    return chunks


def extract_dq_and_role_from_text(full_text: str) -> tuple[list[tuple[str, int]], str | None]:
    """
    Parse ([(item1_name, item1_qty), (item2_name, item2_qty)], role_day) from raw text.
    Supports:
    1. The Lost Nemo! Components V2 Markdown links: `[200 Glass Pane](https://...)`
    2. Standard text / embed lines: `200x Glass Pane`, `200 Glass Pane`, `Glass Pane x200`
    3. Role Day line: `Role Day - <:Chef_Role:...> Chef`
    """
    if not full_text.strip():
        return [], None

    role_day: str | None = None
    role_match = re.search(
        r"Role\s+Day\*?\*?\s*[-:]\s*(?:<a?:[^>]+>\s*|\W+)*(Builder|Surgeon|Fishing|Chef|Star Captain|Farmer)",
        full_text,
        re.IGNORECASE,
    )
    if role_match:
        role_day = role_match.group(1).title()

    link_matches = re.findall(r"\[(\d{1,4})\s+([^\]]+)\]\(https?://[^\)]+\)", full_text)
    if len(link_matches) >= 2:
        items = [(name.strip(), int(qty)) for qty, name in link_matches[:2]]
        return items, role_day

    cleaned_lines: list[str] = []
    for raw_line in full_text.splitlines():
        line = re.sub(r"<a?:[a-zA-Z0-9_]+:\d+>", "", raw_line)
        line = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", line)
        line = re.sub(r"[*_`~>|•]+", " ", line).strip()
        if line:
            cleaned_lines.append(line)

    found: list[tuple[str, int]] = []
    ignore_words = {
        "growtoken",
        "growtokens",
        "gems",
        "wl",
        "wls",
        "world lock",
        "points",
        "xp",
        "day",
        "reset",
        "days",
        "minutes",
    }

    for line in cleaned_lines:
        for segment in re.split(r"\s*·\s*", line):
            seg = re.sub(r"\s+-\s+\d+\s*$", "", segment.strip()).strip("- ").strip()
            m1 = re.match(
                r"^(?:\d+[\.\)]\s*)?(\d{1,4})\s*x?\s+([A-Za-z][A-Za-z0-9'\-\s]{2,40})$",
                seg,
                re.IGNORECASE,
            )
            if m1:
                qty = int(m1.group(1))
                name = m1.group(2).strip()
                if name.lower() not in ignore_words and 1 <= qty <= 2000:
                    found.append((name, qty))
                    continue

            m2 = re.match(
                r"^([A-Za-z][A-Za-z0-9'\-\s]{2,40}?)\s*(?:x|:|\()\s*(\d{1,4})\)?$",
                seg,
                re.IGNORECASE,
            )
            if m2:
                name = m2.group(1).strip()
                qty = int(m2.group(2))
                if name.lower() not in ignore_words and 1 <= qty <= 2000:
                    found.append((name, qty))

    return found[:2], role_day


def extract_dq_items_from_message(message: discord.Message) -> tuple[list[tuple[str, int]], str | None]:
    chunks: list[str] = []
    if message.content:
        chunks.append(message.content)
    for emb in message.embeds:
        if emb.title:
            chunks.append(emb.title)
        if emb.description:
            chunks.append(emb.description)
        for field in emb.fields:
            chunks.append(f"{field.name}\n{field.value}")
    return extract_dq_and_role_from_text("\n".join(chunks))


class DailyUpdateModal(discord.ui.Modal, title="Update 1:00 PM Daily Reset Board"):
    def __init__(self, cog: DailyEventsCog) -> None:
        super().__init__()
        self.cog = cog

    item1 = discord.ui.TextInput(
        label="Daily Quest Item 1 (e.g. 200 Wood Block)",
        placeholder="200 Wood Block",
        required=False,
        max_length=80,
    )
    item2 = discord.ui.TextInput(
        label="Daily Quest Item 2 (e.g. 50 Lava)",
        placeholder="50 Lava",
        required=False,
        max_length=80,
    )
    challenge = discord.ui.TextInput(
        label="Daily Challenge (Optional override)",
        placeholder="e.g. Doctor's Duel / Fish Frenzy",
        required=False,
        max_length=120,
    )
    role = discord.ui.TextInput(
        label="Role Day (Optional calibration)",
        placeholder="Builder, Chef, Farmer, Fishing, Star Captain, or Surgeon",
        required=False,
        max_length=40,
    )

    @staticmethod
    def _parse_qty_and_name(raw: str) -> tuple[str | None, int]:
        text = raw.strip()
        if not text:
            return None, 0
        parts = text.split(maxsplit=1)
        if len(parts) == 2 and parts[0].lower().rstrip("x").isdigit():
            return parts[1].strip(), int(parts[0].lower().rstrip("x"))
        return text, 1

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        item1_name, item1_qty = self._parse_qty_and_name(self.item1.value)
        item2_name, item2_qty = self._parse_qty_and_name(self.item2.value)
        payload = {
            "item1_name": item1_name,
            "item1_qty": item1_qty,
            "item2_name": item2_name,
            "item2_qty": item2_qty,
            "daily_challenge": self.challenge.value.strip() or None,
            "role_day": self.role.value.strip() or None,
        }
        resp = await self.cog.bot.api._client.post("/api/v1/wiki/daily/override", json=payload)
        resp.raise_for_status()

        await self.cog.publish_or_update_daily_board(force_new_message=False)
        await interaction.followup.send(
            content="✅ Updated today's Daily Reset board!",
            ephemeral=True,
        )


class QuickDQSetView(discord.ui.View):
    """Persistent button displayed on the Daily Reset card while waiting for #dq-feed to report items."""

    def __init__(self, cog: DailyEventsCog) -> None:
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="Admin: Set Today's DQ Items",
        emoji="📝",
        style=discord.ButtonStyle.secondary,
        custom_id="growcom:quick_set_dq",
    )
    async def quick_set_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not is_server_manager(interaction):
            await interaction.response.send_message(
                "❌ Only **Server Administrators** or the **Server Owner** can manually enter the Daily Quest items!",
                ephemeral=True,
            )
            return
        await interaction.response.send_modal(DailyUpdateModal(self.cog))


class DailyEventsCog(commands.Cog, name="Daily Events"):
    def __init__(self, bot: EventBot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        self.bot.add_view(QuickDQSetView(self))
        self.daily_1pm_task.start()
        self.post_reset_poller.start()

    async def cog_unload(self) -> None:
        self.daily_1pm_task.cancel()
        self.post_reset_poller.cancel()

    async def sync_latest_dc_feed(self) -> bool:
        """
        Reads the latest message from #⚔️daily-challenges (Growtopia #🗓daily-challenges webhook)
        and parses the active/latest 25-hour cycle Daily Challenge banner filename & timestamp.
        """
        state = load_state()
        dc_channel_id = int(state.get("dc_feed_channel_id", DEFAULT_DC_FEED_CHANNEL_ID))
        try:
            route = discord.http.Route(
                "GET",
                "/channels/{channel_id}/messages",
                channel_id=dc_channel_id,
            )
            raw_messages: list[dict[str, Any]] = await self.bot.http.request(route, params={"limit": 3})
            for raw_msg in raw_messages:
                atts = raw_msg.get("attachments") or []
                for att in atts:
                    fname = att.get("filename", "")
                    m = re.search(r"daily-challenge-([a-z0-9-]+)-\d{4}-\d{2}-\d{2}", fname, re.IGNORECASE)
                    if m:
                        slug = m.group(1).lower()
                        msg_dt = datetime.fromisoformat(raw_msg["timestamp"])
                        start_ts = int(msg_dt.timestamp())
                        formatted_dc = format_dynamic_challenge_from_feed(slug, start_ts)
                        await self.bot.api._client.post(
                            "/api/v1/wiki/daily/override",
                            json={"daily_challenge": formatted_dc},
                        )
                        return True
        except Exception as exc:
            logger.debug("Daily Challenge feed sync skipped: %s", exc)
        return False

    async def sync_latest_dq_feed(self, ignore_timestamp: bool = False) -> bool:
        """
        Fetch the latest messages from #dq-feed via raw Discord HTTP (supporting Discord Components V2
        messages from The Lost Nemo!) and update the Central Data API if today's DQ post is present.
        """
        state = load_state()
        feed_channel_id = state.get("dq_feed_channel_id") or os.getenv("DQ_FEED_CHANNEL_ID", "").strip()
        if not feed_channel_id or not str(feed_channel_id).isdigit():
            return False

        try:
            status_data = await self.bot.api.get_daily_status()
            reset_ts = int(status_data.get("local_reset_timestamp", 0))

            route = discord.http.Route(
                "GET",
                "/channels/{channel_id}/messages",
                channel_id=int(feed_channel_id),
            )
            raw_messages: list[dict[str, Any]] = await self.bot.http.request(route, params={"limit": 5})
            for raw_msg in raw_messages:
                author_id = str(raw_msg.get("author", {}).get("id", ""))
                if self.bot.user and author_id == str(self.bot.user.id):
                    continue

                if not ignore_timestamp and reset_ts > 0 and raw_msg.get("timestamp"):
                    msg_dt = datetime.fromisoformat(raw_msg["timestamp"])
                    if int(msg_dt.timestamp()) < (reset_ts - 3600):
                        continue

                full_text = "\n".join(_collect_text_from_raw_dict(raw_msg))
                items, role_day = extract_dq_and_role_from_text(full_text)
                if items:
                    item1_name, item1_qty = items[0]
                    item2_name, item2_qty = items[1] if len(items) > 1 else (None, 0)
                    payload: dict[str, Any] = {
                        "item1_name": item1_name,
                        "item1_qty": item1_qty,
                        "item2_name": item2_name,
                        "item2_qty": item2_qty,
                    }
                    if role_day:
                        payload["role_day"] = role_day
                    await self.bot.api._client.post("/api/v1/wiki/daily/override", json=payload)
                    logger.info(
                        "Synced #dq-feed post (%sx %s, %sx %s | Role: %s)",
                        item1_qty,
                        item1_name,
                        item2_qty,
                        item2_name,
                        role_day,
                    )
                    return True
        except Exception as exc:
            logger.debug("Raw #dq-feed sync skipped: %s", exc)
        return False

    async def publish_or_update_daily_board(self, force_new_message: bool = False) -> discord.Message | None:
        """Fetch daily status from Central Data API and post/update in the configured daily events channel."""
        state = load_state()
        raw_channel_id = os.getenv("DAILY_EVENTS_CHANNEL_ID", "").strip() or str(state.get("configured_channel_id", ""))
        if not raw_channel_id.isdigit():
            logger.warning("Daily events channel is not configured yet. Run /set_daily_channel in Discord.")
            return None

        channel_id = int(raw_channel_id)
        channel = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(channel_id)
        if not isinstance(channel, discord.abc.Messageable):
            return None

        await self.sync_latest_dc_feed()
        data = await self.bot.api.get_daily_status()
        embed = build_daily_reset_embed(data)
        has_dq = bool(data.get("daily_quest_items"))
        view = None if has_dq else QuickDQSetView(self)

        gt_date = data.get("gt_date")
        last_message_id = state.get("last_message_id")
        last_gt_date = state.get("last_gt_date")

        if not force_new_message and last_gt_date == gt_date and last_message_id and state.get("last_channel_id") == channel_id:
            try:
                msg = await channel.fetch_message(int(last_message_id))  # type: ignore[attr-defined]
                await msg.edit(embed=embed, view=view)
                state["dq_populated"] = has_dq
                save_state(state)
                return msg
            except Exception:
                pass

        if not force_new_message and self.bot.user:
            try:
                async for recent in channel.history(limit=10):  # type: ignore[attr-defined]
                    if (
                        recent.author.id == self.bot.user.id
                        and recent.embeds
                        and recent.embeds[0].title
                        and str(gt_date) in recent.embeds[0].title
                    ):
                        await recent.edit(embed=embed, view=view)
                        state.update(
                            {
                                "configured_channel_id": channel_id,
                                "last_gt_date": gt_date,
                                "last_message_id": recent.id,
                                "last_channel_id": channel_id,
                                "dq_populated": has_dq,
                            }
                        )
                        save_state(state)
                        logger.info("Recovered and updated existing Daily Reset board for %s (msg ID %s)", gt_date, recent.id)
                        return recent
            except Exception as exc:
                logger.debug("Channel history scan for existing board skipped: %s", exc)

        ping_role_id = os.getenv("DAILY_EVENTS_PING_ROLE_ID", "").strip()
        content = f"<@&{ping_role_id}>" if ping_role_id.isdigit() else None

        msg = await channel.send(content=content, embed=embed, view=view)
        state.update(
            {
                "configured_channel_id": channel_id,
                "last_gt_date": gt_date,
                "last_message_id": msg.id,
                "last_channel_id": channel_id,
                "dq_populated": has_dq,
            }
        )
        save_state(state)
        logger.info("Published 1:00 PM Daily Reset board for %s (msg ID %s)", gt_date, msg.id)
        return msg

    @tasks.loop(time=DAILY_TRIGGER_TIME)
    async def daily_1pm_task(self) -> None:
        """Fires automatically every day at 1:00 PM (13:00 Asia/Manila)."""
        logger.info("1:00 PM Daily Reset triggered! Publishing new Daily Quest / Role Day / Challenge board...")
        await self.sync_latest_dc_feed()
        await self.sync_latest_dq_feed(ignore_timestamp=False)
        await self.publish_or_update_daily_board(force_new_message=True)

    @daily_1pm_task.before_loop
    async def before_daily_1pm_task(self) -> None:
        await self.bot.wait_until_ready()

    @tasks.loop(minutes=3)
    async def post_reset_poller(self) -> None:
        """Self-healing check + post-1PM poller."""
        try:
            await self.sync_latest_dc_feed()
            data = await self.bot.api.get_daily_status()
            state = load_state()
            if not data.get("daily_quest_items"):
                synced = await self.sync_latest_dq_feed(ignore_timestamp=False)
                if synced:
                    data = await self.bot.api.get_daily_status()

            if state.get("last_gt_date") != data.get("gt_date"):
                await self.publish_or_update_daily_board(force_new_message=False)
            elif not state.get("dq_populated") and data.get("daily_quest_items"):
                await self.publish_or_update_daily_board(force_new_message=False)
                state["dq_populated"] = True
                save_state(state)
        except Exception as exc:
            logger.debug("Background daily poll skipped: %s", exc)

    @post_reset_poller.before_loop
    async def before_post_reset_poller(self) -> None:
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        try:
            await self.sync_latest_dc_feed()
            await self.sync_latest_dq_feed(ignore_timestamp=False)
            await self.publish_or_update_daily_board(force_new_message=False)
        except Exception as exc:
            logger.debug("Startup board refresh skipped: %s", exc)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if self.bot.user and message.author.id == self.bot.user.id:
            return

        state = load_state()

        # 1. Did a new official Daily Challenge land in #⚔️daily-challenges?
        dc_channel_id = int(state.get("dc_feed_channel_id", DEFAULT_DC_FEED_CHANNEL_ID))
        if message.channel.id == dc_channel_id:
            if await self.sync_latest_dc_feed():
                await self.publish_or_update_daily_board(force_new_message=False)
            return

        # 2. Did a new Daily Quest post land in #dq-feed?
        feed_channel_id = state.get("dq_feed_channel_id") or os.getenv("DQ_FEED_CHANNEL_ID", "").strip()
        if feed_channel_id and str(message.channel.id) == str(feed_channel_id):
            synced = await self.sync_latest_dq_feed(ignore_timestamp=True)
            if not synced:
                items, role_day = extract_dq_items_from_message(message)
                if items:
                    item1_name, item1_qty = items[0]
                    item2_name, item2_qty = items[1] if len(items) > 1 else (None, 0)
                    payload: dict[str, Any] = {
                        "item1_name": item1_name,
                        "item1_qty": item1_qty,
                        "item2_name": item2_name,
                        "item2_qty": item2_qty,
                    }
                    if role_day:
                        payload["role_day"] = role_day
                    await self.bot.api._client.post("/api/v1/wiki/daily/override", json=payload)
                    synced = True

            if synced:
                try:
                    await self.publish_or_update_daily_board(force_new_message=False)
                    await message.add_reaction("✅")
                except Exception as exc:
                    logger.warning("Failed to update board after #dq-feed message: %s", exc)

    @app_commands.command(
        name="set_dq_feed_channel",
        description="Set a channel where followed Daily Quest announcements arrive to auto-update your board",
    )
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(channel="The channel where followed DQ announcements land (defaults to current channel)")
    async def set_dq_feed_channel_command(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel | None = None,
    ) -> None:
        if not is_server_manager(interaction):
            await interaction.response.send_message("❌ Only server admins can use `/set_dq_feed_channel`.", ephemeral=True)
            return
        await interaction.response.defer()
        target_channel = channel or interaction.channel
        if not isinstance(target_channel, discord.TextChannel):
            await interaction.followup.send("❌ Please select a standard text channel.", ephemeral=True)
            return

        state = load_state()
        state["dq_feed_channel_id"] = target_channel.id
        save_state(state)

        synced = await self.sync_latest_dq_feed(ignore_timestamp=True)
        if synced:
            await self.publish_or_update_daily_board(force_new_message=False)
            data = await self.bot.api.get_daily_status()
            dq_items = data.get("daily_quest_items") or []
            summary = ", ".join(f"`{it['quantity']}x {it['name']}`" for it in dq_items)
            await interaction.followup.send(
                f"✅ Linked {target_channel.mention} as your **Auto-DQ Feed Channel** AND synced today's quest "
                f"({summary} • Role Day: **{data.get('role_day')}**) — `#📢daily-announcements` has been updated!"
            )
        else:
            await interaction.followup.send(
                f"✅ Linked {target_channel.mention} as your **Auto-DQ Feed Channel**!\n"
                "Whenever a followed announcement channel (like **The Lost Nemo!**) posts Daily Quest items in "
                f"{target_channel.mention}, the bot will automatically update your `#📢daily-announcements` board!"
            )

    @app_commands.command(
        name="set_daily_channel",
        description="Set the channel where the 1:00 PM Daily Quest, Role Day, and Daily Challenge auto-updates",
    )
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(channel="Channel for the 1:00 PM daily reset board (defaults to current channel)")
    async def set_daily_channel_command(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel | None = None,
    ) -> None:
        if not is_server_manager(interaction):
            await interaction.response.send_message("❌ Only server admins can use `/set_daily_channel`.", ephemeral=True)
            return
        await interaction.response.defer()
        target_channel = channel or interaction.channel
        if not isinstance(target_channel, discord.TextChannel):
            await interaction.followup.send("❌ Please choose a standard text channel.", ephemeral=True)
            return

        state = load_state()
        state["configured_channel_id"] = target_channel.id
        save_state(state)

        await self.sync_latest_dc_feed()
        await self.sync_latest_dq_feed(ignore_timestamp=False)
        msg = await self.publish_or_update_daily_board(force_new_message=True)
        if msg:
            await interaction.followup.send(
                f"✅ Configured {target_channel.mention} for the **1:00 PM Daily Reset** and posted today's live board!"
            )
        else:
            await interaction.followup.send(
                f"✅ Saved {target_channel.mention} as the 1:00 PM Daily Reset channel, but check bot permissions to post there."
            )

    @app_commands.command(name="daily", description="View today's Growtopia Role Day, Daily Challenge, and Daily Quest")
    async def daily_command(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        await self.sync_latest_dc_feed()
        data = await self.bot.api.get_daily_status()
        if not data.get("daily_quest_items"):
            if await self.sync_latest_dq_feed(ignore_timestamp=False):
                data = await self.bot.api.get_daily_status()
        embed = build_daily_reset_embed(data)
        await interaction.followup.send(embed=embed)

    @app_commands.command(
        name="set_daily",
        description="Update today's Daily Quest items, Daily Challenge, or Role Day and refresh the channel board",
    )
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(
        item1_name="First Crazy Jim Daily Quest item name",
        item1_qty="Quantity required for the first item",
        item2_name="Second Crazy Jim Daily Quest item name",
        item2_qty="Quantity required for the second item",
        daily_challenge="Optional: Today's active Daily Challenge name/description",
        role_day="Optional: Calibrate today's Role Day (Builder, Chef, Farmer, Fishing, Star Captain, Surgeon)",
    )
    async def set_daily_command(
        self,
        interaction: discord.Interaction,
        item1_name: str | None = None,
        item1_qty: int = 0,
        item2_name: str | None = None,
        item2_qty: int = 0,
        daily_challenge: str | None = None,
        role_day: str | None = None,
    ) -> None:
        if not is_server_manager(interaction):
            await interaction.response.send_message("❌ Only server admins can use `/set_daily`.", ephemeral=True)
            return
        if not any([item1_name, item2_name, daily_challenge, role_day]):
            await interaction.response.send_modal(DailyUpdateModal(self))
            return

        await interaction.response.defer()
        payload = {
            "item1_name": item1_name,
            "item1_qty": item1_qty,
            "item2_name": item2_name,
            "item2_qty": item2_qty,
            "daily_challenge": daily_challenge,
            "role_day": role_day,
        }
        resp = await self.bot.api._client.post("/api/v1/wiki/daily/override", json=payload)
        resp.raise_for_status()
        updated_data = resp.json()

        await self.publish_or_update_daily_board(force_new_message=False)
        embed = build_daily_reset_embed(updated_data)
        await interaction.followup.send(
            content="✅ Updated today's Daily Reset data and synced the live channel board!",
            embed=embed,
        )


async def setup(bot: EventBot) -> None:
    await bot.add_cog(DailyEventsCog(bot))
