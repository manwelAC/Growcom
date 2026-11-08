"""
Category 2: Harvest Timer & Calculator (cogs/harvest_calculator.py)
- /harvest (with HarvestSetupModal, dynamic planted-time parsing, XP/Gems math, and auto-reminder)
- /set_harvest_channel (channel lock + instruction card)
- Background 15-second harvest_reminder_loop
"""

from __future__ import annotations

from datetime import datetime, timedelta
from io import BytesIO
from typing import TYPE_CHECKING, Any

import discord
from discord import app_commands
from discord.ext import commands, tasks

from utils.helpers import (
    EVENT_TZ,
    FOOTER_TEXT,
    format_duration,
    is_server_manager,
    load_reminders,
    load_state,
    logger,
    parse_planted_datetime,
    save_reminders,
    save_state,
)

if TYPE_CHECKING:
    from bot import EventBot


class CancelHarvestReminderView(discord.ui.View):
    def __init__(self, reminder_id: str, owner_id: int) -> None:
        super().__init__(timeout=None)
        self.reminder_id = reminder_id
        self.owner_id = owner_id
        btn = discord.ui.Button(
            label="Cancel Auto-Reminder",
            style=discord.ButtonStyle.secondary,
            emoji="🔕",
            custom_id=f"cancel_harvest:{reminder_id}:{owner_id}",
        )
        self.add_item(btn)


class HarvestSetupModal(discord.ui.Modal):
    def __init__(self, cog: HarvestCalculatorCog, item_name: str) -> None:
        super().__init__(title=f"🌱 Harvest Setup — {item_name[:25]}")
        self.cog = cog
        self.item_name = item_name

        self.planted_time_input = discord.ui.TextInput(
            label="What time did you plant the trees?",
            placeholder="e.g. 10:30 PM, 22:30, yesterday 8:00 PM, 2h 30m ago, or now",
            required=True,
            max_length=50,
        )
        self.trees_input = discord.ui.TextInput(
            label="How many trees did you plant?",
            placeholder="e.g. 2645 (full world), 1200, 500",
            default="2645",
            required=True,
            max_length=10,
        )
        self.add_item(self.planted_time_input)
        self.add_item(self.trees_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self.cog.execute_harvest_calculation(
            interaction=interaction,
            item_query=self.item_name,
            planted_time_raw=self.planted_time_input.value,
            trees_raw=self.trees_input.value,
        )


class HarvestCalculatorCog(commands.Cog, name="Harvest Calculator"):
    def __init__(self, bot: EventBot) -> None:
        self.bot = bot
        self._fired_ids: set[str] = set()

    async def cog_load(self) -> None:
        self.harvest_reminder_loop.start()

    async def cog_unload(self) -> None:
        self.harvest_reminder_loop.cancel()

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction) -> None:
        """Persistently handle the 'Cancel Auto-Reminder' button across bot restarts."""
        if interaction.type != discord.InteractionType.component or not interaction.data:
            return
        custom_id = str(interaction.data.get("custom_id", ""))
        if not custom_id.startswith("cancel_harvest:"):
            return

        parts = custom_id.split(":")
        if len(parts) < 3:
            return
        reminder_id = parts[1]
        try:
            owner_id = int(parts[2])
        except ValueError:
            return

        if interaction.user.id != owner_id:
            await interaction.response.send_message(
                "❌ Only the player who started this timer can cancel it.",
                ephemeral=True,
            )
            return

        reminders = load_reminders()
        updated = [r for r in reminders if r.get("id") != reminder_id]
        save_reminders(updated)
        self._fired_ids.add(reminder_id)

        disabled_view = discord.ui.View(timeout=None)
        disabled_view.add_item(
            discord.ui.Button(
                label="Reminder Cancelled",
                style=discord.ButtonStyle.secondary,
                emoji="🔕",
                disabled=True,
                custom_id=f"cancelled_harvest:{reminder_id}",
            )
        )
        await interaction.response.edit_message(view=disabled_view)

    @tasks.loop(seconds=15)
    async def harvest_reminder_loop(self) -> None:
        """Check active harvest timers and DM players once when their trees finish growing."""
        reminders = load_reminders()
        if not reminders:
            return

        now_ts = int(datetime.now(EVENT_TZ).timestamp())
        remaining: list[dict[str, Any]] = []
        changed = False

        for entry in reminders:
            rem_id = str(entry.get("id", ""))
            ready_ts = int(entry.get("ready_timestamp", 0))

            if rem_id in self._fired_ids:
                changed = True
                continue

            # Discard stale reminders (> 10 minutes past ready_timestamp) so restarts never re-fire old timers
            if now_ts - ready_ts > 600:
                self._fired_ids.add(rem_id)
                changed = True
                continue

            if now_ts >= ready_ts:
                self._fired_ids.add(rem_id)
                changed = True
                user_id = int(entry["user_id"])
                channel_id = int(entry["channel_id"])
                item_name = entry.get("item_name", "Farm")
                trees = int(entry.get("trees", 2645))

                # Persist removal BEFORE sending so even a mid-flight restart never double-sends
                current_after_pop = [r for r in load_reminders() if str(r.get("id", "")) not in self._fired_ids]
                save_reminders(current_after_pop)

                dm_embed = discord.Embed(
                    title=f"🌾 Harvest Ready — {item_name}!",
                    description=(
                        f"Hey <@{user_id}>! Your **`{trees:,}x` {item_name}** trees have finished growing "
                        f"(ready at <t:{ready_ts}:t>) and are ready to harvest in Growtopia!"
                    ),
                    color=discord.Color.from_rgb(46, 204, 113),
                    timestamp=datetime.now(EVENT_TZ),
                )
                dm_embed.set_footer(text=FOOTER_TEXT)
                alert_text = (
                    f"🌾 **Harvest Ready!** <@{user_id}> — Your **`{trees:,}x` {item_name}** trees "
                    f"have finished growing and are ready to harvest!"
                )

                dm_sent = False
                try:
                    user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
                    if user:
                        await user.send(content=alert_text, embed=dm_embed)
                        dm_sent = True
                except Exception as exc:
                    logger.debug("Could not DM harvest alert to user %s: %s", user_id, exc)

                if not dm_sent:
                    try:
                        ch = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(channel_id)
                        if isinstance(ch, discord.abc.Messageable):
                            await ch.send(
                                f"{alert_text}\n*(Tip: Enable Server DMs to receive harvest reminders privately in your DMs!)*"
                            )
                    except Exception as exc:
                        logger.debug("Could not send fallback harvest alert to channel %s: %s", channel_id, exc)
            else:
                remaining.append(entry)

        if changed:
            save_reminders(remaining)

    @harvest_reminder_loop.before_loop
    async def before_harvest_reminder_loop(self) -> None:
        await self.bot.wait_until_ready()

    async def harvest_item_autocomplete(
        self,
        _interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        try:
            items = await self.bot.api.search_items(current or "Pepper", limit=15, farmable_only=True)
            return [
                app_commands.Choice(
                    name=f"{it['name']} (Rarity {it['rarity']} • {format_duration(it['grow_time_seconds'])})"[:100],
                    value=it["name"],
                )
                for it in items
            ]
        except Exception:
            return []

    async def execute_harvest_calculation(
        self,
        interaction: discord.Interaction,
        item_query: str,
        planted_time_raw: str,
        trees_raw: int | str,
    ) -> None:
        """Dynamically calculate harvest time, XP, and Gems from the user's planted time & tree count."""
        if not interaction.response.is_done():
            await interaction.response.defer()

        item_data = await self.bot.api.get_item(item_query)
        if not item_data:
            await interaction.followup.send(
                f"❌ Could not find any Growtopia item matching **`{item_query}`**.",
                ephemeral=True,
            )
            return

        grow_time_sec = int(item_data.get("grow_time_seconds", 0))
        if grow_time_sec <= 0:
            await interaction.followup.send(
                f"❌ **{item_data['name']}** does not have a tree grow time (`0s`). Try a farmable/seedable item!",
                ephemeral=True,
            )
            return

        now_dt = datetime.now(EVENT_TZ)
        try:
            planted_dt = parse_planted_datetime(planted_time_raw, now_dt)
        except ValueError as err:
            await interaction.followup.send(f"❌ {err}", ephemeral=True)
            return

        try:
            trees = int(str(trees_raw).replace(",", "").strip())
        except ValueError:
            await interaction.followup.send(
                "❌ Please enter a valid number of trees (e.g. `2645` or `500`).",
                ephemeral=True,
            )
            return
        trees = max(1, min(trees, 100000))

        ready_dt = planted_dt + timedelta(seconds=grow_time_sec)
        planted_ts = int(planted_dt.timestamp())
        ready_ts = int(ready_dt.timestamp())
        now_ts = int(now_dt.timestamp())

        rarity = max(1, int(item_data.get("rarity", 1)))
        xp_per_tree = min(500, 1 + (rarity // 5))
        harvest_xp = trees * xp_per_tree
        est_blocks = int(trees * 2.5)
        smash_xp = est_blocks * xp_per_tree
        total_xp = harvest_xp + smash_xp

        if rarity < 30:
            avg_gems_per_block = rarity / 12.0
        else:
            avg_gems_per_block = rarity / 8.0
        max_gems_per_block = max(1, int(round(rarity / 4.0)))
        est_total_gems = int(est_blocks * avg_gems_per_block)

        already_ready = ready_ts <= now_ts
        reminder_id = f"{interaction.user.id}-{ready_ts}"

        if not already_ready:
            reminders = load_reminders()
            reminders = [r for r in reminders if r.get("id") != reminder_id]
            reminders.append(
                {
                    "id": reminder_id,
                    "user_id": interaction.user.id,
                    "channel_id": interaction.channel_id,
                    "item_name": item_data["name"],
                    "trees": trees,
                    "ready_timestamp": ready_ts,
                }
            )
            save_reminders(reminders)
            status_banner = (
                f"🔔 **DM Auto-Reminder Active:** <@{interaction.user.id}> will receive a **Direct Message (DM)** at "
                f"<t:{ready_ts}:t> (<t:{ready_ts}:R>)!"
            )
        else:
            status_banner = (
                f"✅ **Already Ready to Harvest!** Your trees finished growing <t:{ready_ts}:R> (<t:{ready_ts}:t>)!"
            )

        embed = discord.Embed(
            title=f"🌱 Harvest Timer & Calculator — {item_data['name']}",
            description=f"{item_data.get('description') or ''}\n\n{status_banner}".strip(),
            color=discord.Color.from_rgb(46, 204, 113),
        )
        embed.add_field(
            name="🌱 Time Planted",
            value=f"<t:{planted_ts}:f>\n(<t:{planted_ts}:R>)",
            inline=True,
        )
        embed.add_field(
            name="⏰ Ready to Harvest",
            value=f"<t:{ready_ts}:f>\n(<t:{ready_ts}:R>)",
            inline=True,
        )
        embed.add_field(
            name="⏳ Grow Duration",
            value=f"`{format_duration(grow_time_sec)}`\nRarity `{rarity}` • `{item_data.get('hardness_hits', 0)} hits`",
            inline=True,
        )
        embed.add_field(
            name=f"🌳 Yield ({trees:,} Trees)",
            value=f"~`{est_blocks:,}` blocks",
            inline=True,
        )
        embed.add_field(
            name="✨ Exact XP (Harvest + Smash)",
            value=f"**`{total_xp:,} XP`**\n(`{harvest_xp:,}` tree + `{smash_xp:,}` smash)",
            inline=True,
        )
        embed.add_field(
            name="💎 Est. Gems (Full Farm)",
            value=f"**~`{est_total_gems:,} Gems`**\n(`0–{max_gems_per_block}` gems/block)",
            inline=True,
        )
        if item_data.get("splice_recipe"):
            embed.add_field(
                name="🧬 Splice Recipe",
                value=f"`{item_data['splice_recipe']}`",
                inline=False,
            )

        embed.set_footer(text=FOOTER_TEXT)
        sprite_bytes = await self.bot.api.get_item_sprite(item_data["name"])
        files: list[discord.File] = []
        if sprite_bytes:
            files.append(discord.File(BytesIO(sprite_bytes), filename="sprite.png"))
            embed.set_thumbnail(url="attachment://sprite.png")

        if not already_ready:
            view = CancelHarvestReminderView(reminder_id=reminder_id, owner_id=interaction.user.id)
            await interaction.followup.send(embed=embed, view=view, files=files)
        else:
            await interaction.followup.send(embed=embed, files=files)

    @app_commands.command(
        name="set_harvest_channel",
        description="Restrict the /harvest command and auto-reminders to a dedicated channel",
    )
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(channel="Dedicated channel for /harvest (defaults to current channel)")
    async def set_harvest_channel_command(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel | None = None,
    ) -> None:
        if not is_server_manager(interaction):
            await interaction.response.send_message(
                "❌ Only server admins can use `/set_harvest_channel`.",
                ephemeral=True,
            )
            return
        await interaction.response.defer()
        target_channel = channel or interaction.channel
        if not isinstance(target_channel, discord.TextChannel):
            await interaction.followup.send("❌ Please select a standard text channel.", ephemeral=True)
            return

        state = load_state()
        state["harvest_channel_id"] = target_channel.id
        save_state(state)

        guide_embed = discord.Embed(
            title="🌱 Growcom Harvest Timer & Calculator",
            description=(
                "Use **`/harvest`** in this channel to calculate your farm's exact **Ready Time**, "
                "**XP**, and **Estimated Gems**, and get **automatically pinged** when your trees finish growing!\n\n"
                "**How to Use:**\n"
                "1️⃣ Type **`/harvest`** and select your seed/tree from the autocomplete list.\n"
                "2️⃣ Enter **what time you planted** (e.g. `10:30 PM`, `22:30`, `2h 30m ago`, or `now`) "
                "and **how many trees** you planted.\n"
                "3️⃣ The bot will automatically ping you right here when your farm is ready to harvest!"
            ),
            color=discord.Color.from_rgb(46, 204, 113),
        )
        guide_embed.set_footer(text=FOOTER_TEXT)
        await target_channel.send(embed=guide_embed)

        await interaction.followup.send(
            f"✅ Locked **`/harvest`** exclusively to {target_channel.mention}! "
            f"Players trying to run `/harvest` anywhere else will be redirected to {target_channel.mention}.",
            ephemeral=True,
        )

    @app_commands.command(
        name="harvest",
        description="Asks when you planted your trees, dynamically calculates harvest time/Gems/XP, and auto-reminds you!",
    )
    @app_commands.describe(
        item="Name of the farmable item (e.g. Pepper Tree, Laser Grid, Chandelier, Fish Tank)",
        planted_time="Optional: Time you planted (e.g. '10:30 PM', '2h 30m ago', 'now') — leave blank for popup prompt!",
        trees="Optional: Number of trees planted (leave blank to enter in the popup prompt!)",
    )
    @app_commands.autocomplete(item=harvest_item_autocomplete)
    async def harvest_command(
        self,
        interaction: discord.Interaction,
        item: str,
        planted_time: str | None = None,
        trees: int | None = None,
    ) -> None:
        state = load_state()
        allowed_channel_id = state.get("harvest_channel_id")
        if allowed_channel_id and int(interaction.channel_id or 0) != int(allowed_channel_id):
            await interaction.response.send_message(
                f"❌ The **`/harvest`** calculator can only be used inside <#{allowed_channel_id}>!",
                ephemeral=True,
            )
            return

        if planted_time is None:
            await interaction.response.send_modal(HarvestSetupModal(cog=self, item_name=item))
            return

        await self.execute_harvest_calculation(
            interaction=interaction,
            item_query=item,
            planted_time_raw=planted_time,
            trees_raw=trees if trees is not None else 2645,
        )


async def setup(bot: EventBot) -> None:
    await bot.add_cog(HarvestCalculatorCog(bot))
