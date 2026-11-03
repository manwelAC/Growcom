"""
Category 1: Daily Events & Auto-DQ Feed (cogs/daily_events.py)
- 1:00 PM (00:00 GT) Daily Reset Scheduler & Self-Healing Poller
- #dq-feed Auto-Detection Listener
- /daily, /set_daily, /set_daily_channel, /set_dq_feed_channel
"""

from __future__ import annotations

from datetime import datetime
import os
import re
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

    # 2. Daily Challenge
    daily_challenge = data.get("daily_challenge", "Active In-Game Challenge")
    embed.add_field(
        name="🏆 Daily Challenge",
        value=f"**{daily_challenge}**",
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
            "⏳ *Waiting for today's Crazy Jim items to be reported...*\n"
            "*(Auto-updates as soon as tracked, or use `/set_daily` to post early!)*"
        )

    embed.add_field(
        name="🧪 Daily Quest (Crazy Jim)",
        value=dq_text,
        inline=False,
    )

    embed.set_footer(text=FOOTER_TEXT)
    return embed


def extract_dq_items_from_message(message: discord.Message) -> list[tuple[str, int]]:
    """
    Parse 2 Daily Quest items (name, quantity) from a followed announcement message or embed
    (supports formats like '200x Dirt', '200 Dirt', 'Dirt x200', 'Dirt - 200', or embed fields).
    """
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

    full_text = "\n".join(chunks)
    if not full_text.strip():
        return []

    cleaned_lines: list[str] = []
    for raw_line in full_text.splitlines():
        line = re.sub(r"<a?:[a-zA-Z0-9_]+:\d+>", "", raw_line)
        line = re.sub(r"[*_`~>|•\-]+", " ", line).strip()
        if line:
            cleaned_lines.append(line)

    found: list[tuple[str, int]] = []
    ignore_words = {"growtoken", "growtokens", "gems", "wl", "wls", "world lock", "points", "xp", "day", "reset"}

    for line in cleaned_lines:
        m1 = re.match(r"^(?:\d+[\.\)]\s*)?(\d{1,4})\s*x?\s+([A-Za-z][A-Za-z0-9'\-\s]{2,40})$", line, re.IGNORECASE)
        if m1:
            qty = int(m1.group(1))
            name = m1.group(2).strip()
            if name.lower() not in ignore_words and 1 <= qty <= 2000:
                found.append((name, qty))
                continue

        m2 = re.match(r"^([A-Za-z][A-Za-z0-9'\-\s]{2,40}?)\s*(?:x|:|\()\s*(\d{1,4})\)?$", line, re.IGNORECASE)
        if m2:
            name = m2.group(1).strip()
            qty = int(m2.group(2))
            if name.lower() not in ignore_words and 1 <= qty <= 2000:
                found.append((name, qty))

    return found[:2]


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
        placeholder="Builder, Surgeon, Fishing, Chef, Star Captain, or Farmer",
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
        await interaction.response.defer()
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
        updated_data = resp.json()

        await self.cog.publish_or_update_daily_board(force_new_message=False)
        embed = build_daily_reset_embed(updated_data)
        await interaction.followup.send(
            content="✅ Updated today's Daily Reset data and synced the live channel board!",
            embed=embed,
        )


class DailyEventsCog(commands.Cog, name="Daily Events"):
    def __init__(self, bot: EventBot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        self.daily_1pm_task.start()
        self.post_reset_poller.start()

    async def cog_unload(self) -> None:
        self.daily_1pm_task.cancel()
        self.post_reset_poller.cancel()

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

        data = await self.bot.api.get_daily_status()
        embed = build_daily_reset_embed(data)

        gt_date = data.get("gt_date")
        last_message_id = state.get("last_message_id")
        last_gt_date = state.get("last_gt_date")

        if not force_new_message and last_gt_date == gt_date and last_message_id and state.get("last_channel_id") == channel_id:
            try:
                msg = await channel.fetch_message(int(last_message_id))  # type: ignore[attr-defined]
                await msg.edit(embed=embed)
                return msg
            except Exception:
                logger.info("Previous daily message not found; sending a new message.")

        ping_role_id = os.getenv("DAILY_EVENTS_PING_ROLE_ID", "").strip()
        content = f"<@&{ping_role_id}>" if ping_role_id.isdigit() else None

        msg = await channel.send(content=content, embed=embed)
        state.update(
            {
                "configured_channel_id": channel_id,
                "last_gt_date": gt_date,
                "last_message_id": msg.id,
                "last_channel_id": channel_id,
                "dq_populated": bool(data.get("daily_quest_items")),
            }
        )
        save_state(state)
        logger.info("Published 1:00 PM Daily Reset board for %s (msg ID %s)", gt_date, msg.id)
        return msg

    @tasks.loop(time=DAILY_TRIGGER_TIME)
    async def daily_1pm_task(self) -> None:
        """Fires automatically every day at 1:00 PM (13:00 Asia/Manila)."""
        logger.info("1:00 PM Daily Reset triggered! Publishing new Daily Quest / Role Day / Challenge board...")
        await self.publish_or_update_daily_board(force_new_message=True)

    @daily_1pm_task.before_loop
    async def before_daily_1pm_task(self) -> None:
        await self.bot.wait_until_ready()

    @tasks.loop(minutes=3)
    async def post_reset_poller(self) -> None:
        """Self-healing check + post-1PM poller."""
        try:
            data = await self.bot.api.get_daily_status()
            state = load_state()
            if state.get("last_gt_date") != data.get("gt_date"):
                await self.publish_or_update_daily_board(force_new_message=True)
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
            await self.publish_or_update_daily_board(force_new_message=False)
        except Exception as exc:
            logger.debug("Startup board refresh skipped: %s", exc)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if self.bot.user and message.author.id == self.bot.user.id:
            return

        state = load_state()
        feed_channel_id = state.get("dq_feed_channel_id") or os.getenv("DQ_FEED_CHANNEL_ID", "").strip()
        if feed_channel_id and str(message.channel.id) == str(feed_channel_id):
            items = extract_dq_items_from_message(message)
            if items:
                item1_name, item1_qty = items[0]
                item2_name, item2_qty = items[1] if len(items) > 1 else (None, 0)
                logger.info(
                    "Auto-detected Daily Quest from #dq-feed: %sx %s, %sx %s",
                    item1_qty,
                    item1_name,
                    item2_qty,
                    item2_name,
                )
                payload = {
                    "item1_name": item1_name,
                    "item1_qty": item1_qty,
                    "item2_name": item2_name,
                    "item2_qty": item2_qty,
                }
                try:
                    await self.bot.api._client.post("/api/v1/wiki/daily/override", json=payload)
                    await self.publish_or_update_daily_board(force_new_message=False)
                    await message.add_reaction("✅")
                except Exception as exc:
                    logger.warning("Failed to process auto-detected DQ feed message: %s", exc)

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

        detected_items: list[tuple[str, int]] = []
        try:
            async for recent_msg in target_channel.history(limit=5):
                if self.bot.user and recent_msg.author.id == self.bot.user.id:
                    continue
                parsed = extract_dq_items_from_message(recent_msg)
                if parsed:
                    detected_items = parsed
                    break
        except Exception as exc:
            logger.debug("History scan in feed channel skipped: %s", exc)

        if detected_items:
            item1_name, item1_qty = detected_items[0]
            item2_name, item2_qty = detected_items[1] if len(detected_items) > 1 else (None, 0)
            await self.bot.api._client.post(
                "/api/v1/wiki/daily/override",
                json={
                    "item1_name": item1_name,
                    "item1_qty": item1_qty,
                    "item2_name": item2_name,
                    "item2_qty": item2_qty,
                },
            )
            await self.publish_or_update_daily_board(force_new_message=False)
            await interaction.followup.send(
                f"✅ Linked {target_channel.mention} as your **Auto-DQ Feed Channel** AND detected today's quest "
                f"(`{item1_qty}x {item1_name}`, `{item2_qty}x {item2_name}`) — `#📢daily-announcements` has been updated!"
            )
        else:
            await interaction.followup.send(
                f"✅ Linked {target_channel.mention} as your **Auto-DQ Feed Channel**!\n"
                "Whenever a followed announcement channel (or anyone) posts Daily Quest items in "
                f"{target_channel.mention} (e.g. `200 Wood Block` and `50 Lava`), the bot will automatically "
                "enrich them via `H-pun/growtopia-api` and update your `#📢daily-announcements` board!"
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
        role_day="Optional: Calibrate today's Role Day (Builder, Surgeon, Fishing, Chef, Star Captain, Farmer)",
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
