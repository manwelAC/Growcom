"""
Category 3: Item Stats Lookup (cogs/item_lookup.py)
- /item (ID, Rarity, Grow Time, Fist/Pickaxe Hits, Gems Drop, Chi Element, Sprite)
- /set_item_channel (channel lock + instruction card)
"""

from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING

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


class ItemLookupCog(commands.Cog, name="Item Lookup"):
    def __init__(self, bot: EventBot) -> None:
        self.bot = bot

    async def all_items_autocomplete(
        self,
        _interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        try:
            items = await self.bot.api.search_items(current or "World Lock", limit=15, farmable_only=False)
            return [
                app_commands.Choice(
                    name=f"{it['name']} (ID #{it['id']} • Rarity {it['rarity']})"[:100],
                    value=it["name"],
                )
                for it in items
            ]
        except Exception:
            return []

    @app_commands.command(
        name="set_item_channel",
        description="Restrict the /item stats lookup command exclusively to a dedicated channel",
    )
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(channel="Dedicated channel for /item lookups (defaults to current channel)")
    async def set_item_channel_command(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel | None = None,
    ) -> None:
        if not is_server_manager(interaction):
            await interaction.response.send_message(
                "❌ Only server admins can use `/set_item_channel`.",
                ephemeral=True,
            )
            return
        await interaction.response.defer()
        target_channel = channel or interaction.channel
        if not isinstance(target_channel, discord.TextChannel):
            await interaction.followup.send("❌ Please select a standard text channel.", ephemeral=True)
            return

        state = load_state()
        state["item_channel_id"] = target_channel.id
        save_state(state)

        guide_embed = discord.Embed(
            title="📦 Growcom Item Stats Lookup",
            description=(
                "Use **`/item`** in this channel to look up any of Growtopia's **16,490 items**!\n\n"
                "**What You'll Get:**\n"
                "• 🆔 **Item ID & Rarity**\n"
                "• 🌱 **Exact Grow Time** & **Gems Drop Range**\n"
                "• 👊 **Fist & Pickaxe Break Hits**\n"
                "• 🖼️ **In-Game `.rttex` Sprite** & **Official Description**"
            ),
            color=discord.Color.teal(),
        )
        guide_embed.set_footer(text=FOOTER_TEXT)
        await target_channel.send(embed=guide_embed)

        await interaction.followup.send(
            f"✅ Locked **`/item`** exclusively to {target_channel.mention}! "
            f"Players trying to run `/item` anywhere else will be redirected to {target_channel.mention}.",
            ephemeral=True,
        )

    @app_commands.command(
        name="item",
        description="Look up any Growtopia item's ID, Rarity, Grow Time, Break Hits, Gems Drop, and Sprite!",
    )
    @app_commands.describe(query="Item name, abbreviation (wl, dl, bgl, lgrid), or Item ID")
    @app_commands.autocomplete(query=all_items_autocomplete)
    async def item_command(self, interaction: discord.Interaction, query: str) -> None:
        state = load_state()
        allowed_channel_id = state.get("item_channel_id")
        if allowed_channel_id and int(interaction.channel_id or 0) != int(allowed_channel_id):
            await interaction.response.send_message(
                f"❌ The **`/item`** lookup tool can only be used inside <#{allowed_channel_id}>!",
                ephemeral=True,
            )
            return

        await interaction.response.defer()
        item_data = await self.bot.api.get_item(query)
        wiki_data = await self.bot.api.get_wiki_item(item_data["name"] if item_data else query)

        if not item_data and not wiki_data:
            await interaction.followup.send(f"❌ Could not find any item matching **`{query}`**.", ephemeral=True)
            return

        title = item_data["name"] if item_data else wiki_data["title"]  # type: ignore[index]
        url = (wiki_data.get("url") if wiki_data else None) or f"https://growtopia.fandom.com/wiki/{title.replace(' ', '_')}"
        description = (
            (item_data.get("description") if item_data else None)
            or (wiki_data.get("description") if wiki_data else None)
            or "No description available."
        )

        embed = discord.Embed(
            title=f"📦 {title}",
            url=url,
            description=description,
            color=discord.Color.teal(),
        )

        if item_data:
            rarity = int(item_data.get("rarity", 0))
            fist_hits = int(item_data.get("hardness_hits", 0))
            pickaxe_hits = max(1, (fist_hits * 3 + 3) // 4) if fist_hits > 0 else 0
            grow_sec = int(item_data.get("grow_time_seconds", 0))
            max_gems = max(1, int(round(rarity / 4.0))) if 0 < rarity < 999 else 0

            embed.add_field(name="🆔 Item ID", value=f"`#{item_data['id']}`", inline=True)
            embed.add_field(
                name="⭐ Rarity",
                value=f"`{rarity}`" if rarity < 999 else "`None (999)`",
                inline=True,
            )
            embed.add_field(
                name="🌱 Grow Time",
                value=f"`{format_duration(grow_sec)}`" if grow_sec > 0 else "`Not Farmable`",
                inline=True,
            )
            embed.add_field(
                name="👊 Break Hits",
                value=f"`{fist_hits} Fist` • `{pickaxe_hits} Pickaxe`" if fist_hits > 0 else "`Unbreakable`",
                inline=True,
            )
            embed.add_field(
                name="💎 Gems Drop",
                value=f"`0 – {max_gems} Gems`" if max_gems > 0 else "`None`",
                inline=True,
            )
            embed.add_field(
                name="🗂️ Max Hold",
                value=f"`{item_data.get('max_hold', 200)} per slot`",
                inline=True,
            )

        if wiki_data:
            chi = wiki_data.get("chi")
            if chi and chi != "None":
                embed.add_field(name="🌀 Chi Element", value=f"`{chi}`", inline=True)
            recipes = list(wiki_data.get("recipes") or [])
            if item_data and item_data.get("splice_recipe") and not any(item_data["splice_recipe"].lower() in r.lower() for r in recipes):
                recipes.insert(0, f"🌱 Splicing: {item_data['splice_recipe']}")
            if recipes:
                embed.add_field(
                    name="🧬 Recipe / How to Obtain",
                    value="\n".join(f"• {r}" for r in recipes[:3]),
                    inline=False,
                )

        files: list[discord.File] = []
        sprite_bytes = await self.bot.api.get_item_sprite(title)
        if sprite_bytes:
            files.append(discord.File(BytesIO(sprite_bytes), filename="sprite.png"))
            embed.set_thumbnail(url="attachment://sprite.png")

        embed.set_footer(text=FOOTER_TEXT)
        await interaction.followup.send(embed=embed, files=files)


async def setup(bot: EventBot) -> None:
    await bot.add_cog(ItemLookupCog(bot))
