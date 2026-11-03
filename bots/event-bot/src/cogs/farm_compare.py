"""
Category 7: Farmable Profit & Effort Comparator (cogs/farm_compare.py)
- /compare_farm (Side-by-side comparison of 2 farmables: Rarity, Grow Time, Fist/Pickaxe Hits, Total Gems, Total XP, and Verdict)
- /set_compare_channel (Admin channel lock + instruction card)
"""

from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING, Any

import discord
from discord import app_commands
from discord.ext import commands

from utils.helpers import (
    FOOTER_TEXT,
    format_duration,
    is_server_manager,
    load_state,
    save_state,
)

if TYPE_CHECKING:
    from bot import EventBot


def compute_farm_metrics(item_data: dict[str, Any], trees: int) -> dict[str, Any]:
    """Compute exact Growtopia farm statistics for a given item and tree count."""
    rarity = max(1, int(item_data.get("rarity", 1)))
    grow_sec = int(item_data.get("grow_time_seconds", 0))
    fist_hits = int(item_data.get("hardness_hits", 0))
    pickaxe_hits = max(1, (fist_hits * 3 + 3) // 4) if fist_hits > 0 else 0

    est_blocks = int(trees * 2.5)
    xp_per_action = min(500, 1 + (rarity // 5))
    harvest_xp = trees * xp_per_action
    smash_xp = est_blocks * xp_per_action
    total_xp = harvest_xp + smash_xp

    avg_gems_per_block = (rarity / 12.0) if rarity < 30 else (rarity / 8.0)
    max_gems_per_block = max(1, int(round(rarity / 4.0)))
    est_gems = int(est_blocks * avg_gems_per_block)

    total_fist_punches = est_blocks * fist_hits
    total_pickaxe_punches = est_blocks * pickaxe_hits
    # At ~5 punches/second in Growtopia, estimate pure breaking time in minutes
    break_minutes_pickaxe = max(1, round(total_pickaxe_punches / 300))

    return {
        "name": item_data["name"],
        "id": item_data["id"],
        "rarity": rarity,
        "grow_sec": grow_sec,
        "grow_str": format_duration(grow_sec),
        "fist_hits": fist_hits,
        "pickaxe_hits": pickaxe_hits,
        "est_blocks": est_blocks,
        "harvest_xp": harvest_xp,
        "smash_xp": smash_xp,
        "total_xp": total_xp,
        "est_gems": est_gems,
        "max_gems_per_block": max_gems_per_block,
        "total_pickaxe_punches": total_pickaxe_punches,
        "break_minutes_pickaxe": break_minutes_pickaxe,
        "splice_recipe": item_data.get("splice_recipe"),
    }


class FarmCompareCog(commands.Cog, name="Farm Comparator"):
    def __init__(self, bot: EventBot) -> None:
        self.bot = bot

    async def farmable_autocomplete(
        self,
        _interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        try:
            items = await self.bot.api.search_items(current or "Laser Grid", limit=15, farmable_only=True)
            return [
                app_commands.Choice(
                    name=f"{it['name']} (Rarity {it['rarity']} • {format_duration(it['grow_time_seconds'])})"[:100],
                    value=it["name"],
                )
                for it in items
            ]
        except Exception:
            return []

    @app_commands.command(
        name="set_compare_channel",
        description="Restrict the /compare_farm tool exclusively to a dedicated channel",
    )
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(channel="Dedicated channel for /compare_farm (defaults to current channel)")
    async def set_compare_channel_command(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel | None = None,
    ) -> None:
        if not is_server_manager(interaction):
            await interaction.response.send_message(
                "❌ Only server admins can use `/set_compare_channel`.",
                ephemeral=True,
            )
            return
        await interaction.response.defer()
        target_channel = channel or interaction.channel
        if not isinstance(target_channel, discord.TextChannel):
            await interaction.followup.send("❌ Please select a standard text channel.", ephemeral=True)
            return

        state = load_state()
        state["compare_channel_id"] = target_channel.id
        save_state(state)

        guide_embed = discord.Embed(
            title="⚖️ Growcom Farmable Profit & Effort Comparator",
            description=(
                "Use **`/compare_farm`** in this channel to compare any two Growtopia farmables side-by-side "
                "(e.g. **Laser Grid vs Pepper Tree**, **Chandelier vs Sorcerer Stone**, **Fish Tank vs Pinball Bumper**)!\n\n"
                "**What It Compares:**\n"
                "• 💎 **Estimated Gems per Full Harvest** (`2,645` trees default)\n"
                "• ✨ **Total XP Gained (Harvest + Smash)**\n"
                "• ⏳ **Exact Tree Grow Time**\n"
                "• 👊 **Fist & Pickaxe Hits + Total Punches to Break**\n"
                "• 🏆 **Smart Verdict** (Best for Gems/XP, Fastest Cycle, & Easiest Break)"
            ),
            color=discord.Color.purple(),
        )
        guide_embed.set_footer(text=FOOTER_TEXT)
        await target_channel.send(embed=guide_embed)

        await interaction.followup.send(
            f"✅ Locked **`/compare_farm`** exclusively to {target_channel.mention}! "
            f"Players trying to run `/compare_farm` anywhere else will be redirected to {target_channel.mention}.",
            ephemeral=True,
        )

    @app_commands.command(
        name="compare_farm",
        description="Compare two Growtopia farmables side-by-side (Gems, XP, Grow Time, Break Hits, and Verdict)!",
    )
    @app_commands.describe(
        item1="First farmable item (e.g. Laser Grid, Pepper Tree, Chandelier)",
        item2="Second farmable item to compare against (e.g. Chandelier, Fish Tank, Sorcerer Stone)",
        trees="Optional: Number of trees to compare (defaults to 2,645 for a full farm world)",
    )
    @app_commands.autocomplete(item1=farmable_autocomplete, item2=farmable_autocomplete)
    async def compare_farm_command(
        self,
        interaction: discord.Interaction,
        item1: str,
        item2: str,
        trees: app_commands.Range[int, 1, 100000] = 2645,
    ) -> None:
        state = load_state()
        allowed_channel_id = state.get("compare_channel_id")
        if allowed_channel_id and int(interaction.channel_id or 0) != int(allowed_channel_id):
            await interaction.response.send_message(
                f"❌ The **`/compare_farm`** tool can only be used inside <#{allowed_channel_id}>!",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        data1 = await self.bot.api.get_item(item1)
        data2 = await self.bot.api.get_item(item2)

        if not data1:
            await interaction.followup.send(f"❌ Could not find item **`{item1}`**.", ephemeral=True)
            return
        if not data2:
            await interaction.followup.send(f"❌ Could not find item **`{item2}`**.", ephemeral=True)
            return

        if int(data1.get("grow_time_seconds", 0)) <= 0:
            await interaction.followup.send(
                f"❌ **{data1['name']}** is not a growable farm item (`0s` grow time).",
                ephemeral=True,
            )
            return
        if int(data2.get("grow_time_seconds", 0)) <= 0:
            await interaction.followup.send(
                f"❌ **{data2['name']}** is not a growable farm item (`0s` grow time).",
                ephemeral=True,
            )
            return

        m1 = compute_farm_metrics(data1, trees)
        m2 = compute_farm_metrics(data2, trees)

        # Winners per category
        gems_winner = (
            f"🏆 **{m1['name']}** (`+{m1['est_gems'] - m2['est_gems']:,} Gems`)"
            if m1["est_gems"] > m2["est_gems"]
            else (
                f"🏆 **{m2['name']}** (`+{m2['est_gems'] - m1['est_gems']:,} Gems`)"
                if m2["est_gems"] > m1["est_gems"]
                else "🤝 **Tie** (Same Gems & XP)"
            )
        )
        speed_winner = (
            f"⚡ **{m1['name']}** (`{format_duration(m2['grow_sec'] - m1['grow_sec'])}` faster)"
            if m1["grow_sec"] < m2["grow_sec"]
            else (
                f"⚡ **{m2['name']}** (`{format_duration(m1['grow_sec'] - m2['grow_sec'])}` faster)"
                if m2["grow_sec"] < m1["grow_sec"]
                else "🤝 **Tie** (Same Grow Time)"
            )
        )
        effort_winner = (
            f"👊 **{m1['name']}** (`{m1['pickaxe_hits']}` vs `{m2['pickaxe_hits']}` Pickaxe hits)"
            if m1["pickaxe_hits"] < m2["pickaxe_hits"]
            else (
                f"👊 **{m2['name']}** (`{m2['pickaxe_hits']}` vs `{m1['pickaxe_hits']}` Pickaxe hits)"
                if m2["pickaxe_hits"] < m1["pickaxe_hits"]
                else "🤝 **Tie** (Same Break Effort)"
            )
        )

        embed = discord.Embed(
            title=f"⚖️ Farm Comparison: {m1['name']} vs {m2['name']}",
            description=(
                f"Comparing a **`{trees:,}`-tree farm** (~`{m1['est_blocks']:,}` harvested blocks) side-by-side:"
            ),
            color=discord.Color.purple(),
        )

        # Column 1: Item 1 Breakdown
        embed.add_field(
            name=f"🌱 1. {m1['name']}",
            value=(
                f"• **Rarity:** `{m1['rarity']}`\n"
                f"• **Grow Time:** `{m1['grow_str']}`\n"
                f"• **Break Hits:** `{m1['fist_hits']} Fist` (`{m1['pickaxe_hits']} Pickaxe`)\n"
                f"• **Total Punches:** `{m1['total_pickaxe_punches']:,}` w/ Pickaxe\n"
                f"• **Est. Gems:** **`~{m1['est_gems']:,} Gems`** (`0–{m1['max_gems_per_block']}`/blk)\n"
                f"• **Total XP:** **`{m1['total_xp']:,} XP`**"
            ),
            inline=True,
        )

        # Column 2: Item 2 Breakdown
        embed.add_field(
            name=f"🌿 2. {m2['name']}",
            value=(
                f"• **Rarity:** `{m2['rarity']}`\n"
                f"• **Grow Time:** `{m2['grow_str']}`\n"
                f"• **Break Hits:** `{m2['fist_hits']} Fist` (`{m2['pickaxe_hits']} Pickaxe`)\n"
                f"• **Total Punches:** `{m2['total_pickaxe_punches']:,}` w/ Pickaxe\n"
                f"• **Est. Gems:** **`~{m2['est_gems']:,} Gems`** (`0–{m2['max_gems_per_block']}`/blk)\n"
                f"• **Total XP:** **`{m2['total_xp']:,} XP`**"
            ),
            inline=True,
        )

        # Verdict summary row
        embed.add_field(
            name="🏆 Head-to-Head Verdict",
            value=(
                f"💎 **Most Gems & XP per Harvest:** {gems_winner}\n"
                f"⏰ **Fastest Grow Cycle:** {speed_winner}\n"
                f"🔨 **Easiest to Break (Pickaxe):** {effort_winner}"
            ),
            inline=False,
        )

        files: list[discord.File] = []
        sprite_bytes = await self.bot.api.get_item_sprite(m1["name"])
        if sprite_bytes:
            files.append(discord.File(BytesIO(sprite_bytes), filename="sprite.png"))
            embed.set_thumbnail(url="attachment://sprite.png")

        embed.set_footer(text=FOOTER_TEXT)
        await interaction.followup.send(embed=embed, files=files)


async def setup(bot: EventBot) -> None:
    await bot.add_cog(FarmCompareCog(bot))
