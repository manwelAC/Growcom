"""
Category 5: Trade & Rate Calculator (cogs/rate_calculator.py)
- /rate (Calculates exact WL / DL / BGL trade costs and 200-item stack counts)
- /set_rate_channel (channel lock + instruction card)
"""

from __future__ import annotations

from io import BytesIO
import re
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from utils.helpers import (
    FOOTER_TEXT,
    is_server_manager,
    load_state,
    save_state,
)

if TYPE_CHECKING:
    from bot import EventBot


def format_locks(total_wls: float) -> str:
    """Format a World Lock total into BGL (10,000 WL), DL (100 WL), and WL."""
    whole_wls = int(round(total_wls))
    bgls, rem = divmod(whole_wls, 10000)
    dls, wls = divmod(rem, 100)
    parts: list[str] = []
    if bgls > 0:
        parts.append(f"**{bgls:,} BGL**")
    if dls > 0:
        parts.append(f"**{dls:,} DL**")
    if wls > 0 or not parts:
        parts.append(f"**{wls:,} WL**")
    return ", ".join(parts)


def parse_rate_expression(raw_rate: str) -> tuple[float, float, str, str]:
    """
    Parse Growtopia price/rate strings into (items_per_unit, locks_per_unit_in_wl, unit_label, human_rate).
    Supports:
    - '10/1', '10/1 wl', '10/1 dl', '10/1 bgl', '15/2 wl', '200 per wl', '10 blocks / 1 dl'
    - '5 wl', '5 wl each', '2 dl each', '1 bgl each', '3 each'
    """
    text = raw_rate.strip().lower().replace(",", "")
    if not text:
        raise ValueError("Please enter a price rate (e.g. `10/1 WL`, `200/1 DL`, or `5 WL each`).")

    if "bgl" in text:
        unit_mult = 10000.0
        unit_name = "BGL"
    elif "dl" in text:
        unit_mult = 100.0
        unit_name = "DL"
    else:
        unit_mult = 1.0
        unit_name = "WL"

    ratio_match = re.search(r"(\d+(?:\.\d+)?)\s*[a-z\s]*?(?:/|per)\s*(\d+(?:\.\d+)?)", text)
    if ratio_match:
        items_per_lock = float(ratio_match.group(1))
        lock_count = float(ratio_match.group(2))
        if items_per_lock <= 0:
            raise ValueError("Item rate cannot be zero.")
        return items_per_lock, lock_count * unit_mult, unit_name, f"{items_per_lock:g} per {lock_count:g} {unit_name}"

    if "per" in text:
        per_match = re.search(r"(\d+(?:\.\d+)?)", text)
        if per_match:
            items_per_lock = float(per_match.group(1))
            return items_per_lock, 1.0 * unit_mult, unit_name, f"{items_per_lock:g} per 1 {unit_name}"

    num_match = re.search(r"(\d+(?:\.\d+)?)", text)
    if num_match:
        price_each = float(num_match.group(1))
        return 1.0, price_each * unit_mult, unit_name, f"{price_each:g} {unit_name} each"

    raise ValueError(
        f"Could not understand rate `{raw_rate}`. Try formats like `10/1 WL`, `10/1 DL`, `200/1 WL`, or `5 WL each`."
    )


class RateCalculatorModal(discord.ui.Modal):
    def __init__(self, cog: RateCalculatorCog, item_name: str | None = None) -> None:
        title_suffix = f" — {item_name[:22]}" if item_name else ""
        super().__init__(title=f"💰 Rate Calculator{title_suffix}")
        self.cog = cog
        self.item_name = item_name

        self.amount_input = discord.ui.TextInput(
            label="How many items/seeds/blocks?",
            placeholder="e.g. 10000, 2645, 500",
            required=True,
            max_length=15,
        )
        self.rate_input = discord.ui.TextInput(
            label="What is the Price / Rate?",
            placeholder="e.g. 10/1 WL, 10/1 DL, 200/1 WL, or 5 WL each",
            required=True,
            max_length=40,
        )
        self.add_item(self.amount_input)
        self.add_item(self.rate_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self.cog.execute_rate_calculation(
            interaction=interaction,
            amount_raw=self.amount_input.value,
            rate_raw=self.rate_input.value,
            item_query=self.item_name,
        )


class RateCalculatorCog(commands.Cog, name="Rate Calculator"):
    def __init__(self, bot: EventBot) -> None:
        self.bot = bot

    async def all_items_autocomplete(
        self,
        _interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        try:
            items = await self.bot.api.search_items(current or "Pepper Tree", limit=15, farmable_only=False)
            return [
                app_commands.Choice(
                    name=f"{it['name']} (ID #{it['id']} • Rarity {it['rarity']})"[:100],
                    value=it["name"],
                )
                for it in items
            ]
        except Exception:
            return []

    async def execute_rate_calculation(
        self,
        interaction: discord.Interaction,
        amount_raw: str | int,
        rate_raw: str,
        item_query: str | None = None,
    ) -> None:
        if not interaction.response.is_done():
            await interaction.response.defer()

        try:
            amount = int(str(amount_raw).replace(",", "").strip())
            if amount <= 0:
                raise ValueError
        except ValueError:
            await interaction.followup.send(
                "❌ Please enter a valid positive item quantity (e.g. `10000` or `2645`).",
                ephemeral=True,
            )
            return

        try:
            items_per_batch, wls_per_batch, _unit_name, human_rate = parse_rate_expression(rate_raw)
        except ValueError as err:
            await interaction.followup.send(f"❌ {err}", ephemeral=True)
            return

        item_data = await self.bot.api.get_item(item_query) if item_query and item_query.strip() else None
        item_label = (
            item_data["name"]
            if item_data
            else (item_query.strip() if item_query and item_query.strip() else "Items")
        )

        batches = amount / items_per_batch
        total_wls = batches * wls_per_batch
        total_dls = total_wls / 100.0
        total_bgls = total_wls / 10000.0

        max_hold = int(item_data.get("max_hold", 200)) if item_data else 200
        full_stacks, leftover_items = divmod(amount, max_hold)
        stack_str = f"`{full_stacks:,}` stacks of `{max_hold}`" + (
            f" + `{leftover_items}` extra" if leftover_items else ""
        )

        embed = discord.Embed(
            title=f"💰 Trade & Rate Calculator — {item_label}",
            description=(
                f"Calculating price for **`{amount:,}x` {item_label}** at rate **`{human_rate}`**:\n\n"
                f"💎 **Total Cost:** {format_locks(total_wls)}"
            ),
            color=discord.Color.gold(),
        )
        embed.add_field(
            name="📦 Quantity Buying/Selling",
            value=f"**`{amount:,}`** {item_label}\n({stack_str})",
            inline=True,
        )
        embed.add_field(
            name="🏷️ Rate Applied",
            value=f"**`{human_rate}`**",
            inline=True,
        )
        embed.add_field(
            name="🔐 Exact Lock Breakdown",
            value=format_locks(total_wls),
            inline=True,
        )
        embed.add_field(
            name="🌍 In Pure World Locks",
            value=f"`{total_wls:,.2f} WL`".replace(".00 ", " "),
            inline=True,
        )
        embed.add_field(
            name="💎 In Pure Diamond Locks",
            value=f"`{total_dls:,.2f} DL`".replace(".00 ", " "),
            inline=True,
        )
        embed.add_field(
            name="🔷 In Pure Blue Gem Locks",
            value=f"`{total_bgls:,.4f} BGL`".replace(".0000 ", " "),
            inline=True,
        )

        if abs(total_wls - round(total_wls)) > 0.001 and wls_per_batch > 0:
            floor_wls = int(total_wls)
            ceil_wls = floor_wls + 1
            floor_items = int((floor_wls / wls_per_batch) * items_per_batch)
            ceil_items = int((ceil_wls / wls_per_batch) * items_per_batch)
            embed.add_field(
                name="⚖️ Nearest Whole-Lock Amounts",
                value=(
                    f"• **{format_locks(floor_wls)}** (`{floor_wls:,} WL`) = **`{floor_items:,}`** {item_label}\n"
                    f"• **{format_locks(ceil_wls)}** (`{ceil_wls:,} WL`) = **`{ceil_items:,}`** {item_label}"
                ),
                inline=False,
            )

        files: list[discord.File] = []
        if item_data:
            sprite_bytes = await self.bot.api.get_item_sprite(item_data["name"])
            if sprite_bytes:
                files.append(discord.File(BytesIO(sprite_bytes), filename="sprite.png"))
                embed.set_thumbnail(url="attachment://sprite.png")

        embed.set_footer(text=FOOTER_TEXT)
        await interaction.followup.send(embed=embed, files=files)

    @app_commands.command(
        name="set_rate_channel",
        description="Restrict the /rate trade & price calculator exclusively to a dedicated channel",
    )
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(channel="Dedicated channel for /rate calculations (defaults to current channel)")
    async def set_rate_channel_command(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel | None = None,
    ) -> None:
        if not is_server_manager(interaction):
            await interaction.response.send_message(
                "❌ Only server admins can use `/set_rate_channel`.",
                ephemeral=True,
            )
            return
        await interaction.response.defer()
        target_channel = channel or interaction.channel
        if not isinstance(target_channel, discord.TextChannel):
            await interaction.followup.send("❌ Please select a standard text channel.", ephemeral=True)
            return

        state = load_state()
        state["rate_channel_id"] = target_channel.id
        save_state(state)

        guide_embed = discord.Embed(
            title="💰 Growcom Trade & Rate Calculator",
            description=(
                "Use **`/rate`** in this channel whenever you are buying or selling seeds, blocks, or items "
                "to calculate the exact price in **WL**, **DL**, and **BGL**!\n\n"
                "**How to Use:**\n"
                "1️⃣ Type **`/rate`** (optionally pick an item name, or just press Enter).\n"
                "2️⃣ Enter the **Amount** you are buying/selling (e.g. `10000` or `2645`).\n"
                "3️⃣ Enter the **Rate / Price** (e.g. `10/1 WL`, `10/1 DL`, `200/1 WL`, or `5 WL each`).\n"
                "4️⃣ Instantly see the exact cost in **BGL + DL + WL** and how many **200-item stacks** it equals!"
            ),
            color=discord.Color.gold(),
        )
        guide_embed.set_footer(text=FOOTER_TEXT)
        await target_channel.send(embed=guide_embed)

        await interaction.followup.send(
            f"✅ Locked **`/rate`** exclusively to {target_channel.mention}! "
            f"Players trying to run `/rate` anywhere else will be redirected to {target_channel.mention}.",
            ephemeral=True,
        )

    @app_commands.command(
        name="rate",
        description="Calculate exact WL / DL / BGL trade costs and stack counts when buying or selling items!",
    )
    @app_commands.describe(
        item="Optional: Item you are buying/selling (e.g. Pepper Tree, Laser Grid) for sprite & stack info",
        amount="Optional: Quantity of items (leave blank to use the popup calculator!)",
        price_rate="Optional: Rate like '10/1 WL', '10/1 DL', '200/1 WL', or '5 WL each' (leave blank for popup!)",
    )
    @app_commands.autocomplete(item=all_items_autocomplete)
    async def rate_command(
        self,
        interaction: discord.Interaction,
        item: str | None = None,
        amount: int | None = None,
        price_rate: str | None = None,
    ) -> None:
        state = load_state()
        allowed_channel_id = state.get("rate_channel_id")
        if allowed_channel_id and int(interaction.channel_id or 0) != int(allowed_channel_id):
            await interaction.response.send_message(
                f"❌ The **`/rate`** calculator can only be used inside <#{allowed_channel_id}>!",
                ephemeral=True,
            )
            return

        if amount is None or price_rate is None:
            await interaction.response.send_modal(RateCalculatorModal(cog=self, item_name=item))
            return

        await self.execute_rate_calculation(
            interaction=interaction,
            amount_raw=amount,
            rate_raw=price_rate,
            item_query=item,
        )


async def setup(bot: EventBot) -> None:
    await bot.add_cog(RateCalculatorCog(bot))
