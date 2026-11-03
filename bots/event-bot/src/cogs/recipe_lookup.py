"""
Category 4: Splicing & Recipe Lookup (cogs/recipe_lookup.py)
- /recipe (Seed splicing formula from items.dat + Chemical Combiner / crafting recipes from Growtopia Wiki)
- /set_recipe_channel (channel lock + instruction card)
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


class RecipeLookupCog(commands.Cog, name="Recipe Lookup"):
    def __init__(self, bot: EventBot) -> None:
        self.bot = bot

    async def all_items_autocomplete(
        self,
        _interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        try:
            items = await self.bot.api.search_items(current or "Laser Grid", limit=15, farmable_only=False)
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
        name="set_recipe_channel",
        description="Restrict the /recipe splicing & crafting lookup command exclusively to a dedicated channel",
    )
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(channel="Dedicated channel for /recipe lookups (defaults to current channel)")
    async def set_recipe_channel_command(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel | None = None,
    ) -> None:
        if not is_server_manager(interaction):
            await interaction.response.send_message(
                "❌ Only server admins can use `/set_recipe_channel`.",
                ephemeral=True,
            )
            return
        await interaction.response.defer()
        target_channel = channel or interaction.channel
        if not isinstance(target_channel, discord.TextChannel):
            await interaction.followup.send("❌ Please select a standard text channel.", ephemeral=True)
            return

        state = load_state()
        state["recipe_channel_id"] = target_channel.id
        save_state(state)

        guide_embed = discord.Embed(
            title="🧬 Growcom Splicing & Recipe Lookup",
            description=(
                "Use **`/recipe`** in this channel to find out how to splice, combine, or craft any Growtopia item!\n\n"
                "**What You'll Get:**\n"
                "• 🌱 **Exact Seed Splicing Formula** (`Seed A + Seed B`)\n"
                "• 🧪 **Chemical Combiner / Forge / Cooking Recipes** from the Growtopia Wiki\n"
                "• ⏳ **Grow Time, Rarity & Parent Seed Details**"
            ),
            color=discord.Color.green(),
        )
        guide_embed.set_footer(text=FOOTER_TEXT)
        await target_channel.send(embed=guide_embed)

        await interaction.followup.send(
            f"✅ Locked **`/recipe`** exclusively to {target_channel.mention}! "
            f"Players trying to run `/recipe` anywhere else will be redirected to {target_channel.mention}.",
            ephemeral=True,
        )

    @app_commands.command(
        name="recipe",
        description="Look up seed splicing and crafting/combiner recipes for any Growtopia item!",
    )
    @app_commands.describe(item="Item name to check splicing & crafting recipes for")
    @app_commands.autocomplete(item=all_items_autocomplete)
    async def recipe_command(self, interaction: discord.Interaction, item: str) -> None:
        state = load_state()
        allowed_channel_id = state.get("recipe_channel_id")
        if allowed_channel_id and int(interaction.channel_id or 0) != int(allowed_channel_id):
            await interaction.response.send_message(
                f"❌ The **`/recipe`** lookup tool can only be used inside <#{allowed_channel_id}>!",
                ephemeral=True,
            )
            return

        await interaction.response.defer()
        item_data = await self.bot.api.get_item(item)
        target_name = item_data["name"] if item_data else item
        wiki_data = await self.bot.api.get_wiki_item(target_name)

        if not item_data and not wiki_data:
            await interaction.followup.send(f"❌ Could not find any item matching **`{item}`**.", ephemeral=True)
            return

        title = item_data["name"] if item_data else wiki_data["title"]  # type: ignore[index]
        url = (wiki_data.get("url") if wiki_data else None) or f"https://growtopia.fandom.com/wiki/{title.replace(' ', '_')}"

        recipes: list[str] = []
        if item_data and item_data.get("splice_recipe"):
            recipes.append(f"🌱 **Splicing:** `{item_data['splice_recipe']}`")
        if wiki_data and wiki_data.get("recipes"):
            for r in wiki_data["recipes"]:
                if not any(r.lower() in existing.lower() for existing in recipes):
                    recipes.append(r)

        embed = discord.Embed(
            title=f"🧬 Recipe Lookup — {title}",
            url=url,
            description=(
                "\n\n".join(f"• {r}" for r in recipes)
                if recipes
                else "❌ This item cannot be spliced or has no crafting recipe listed on the Wiki."
            ),
            color=discord.Color.green(),
        )

        if item_data:
            rarity = int(item_data.get("rarity", 0))
            grow_sec = int(item_data.get("grow_time_seconds", 0))
            embed.add_field(
                name="⭐ Rarity",
                value=f"`{rarity}`" if rarity < 999 else "`None (999)`",
                inline=True,
            )
            embed.add_field(
                name="🌱 Tree Grow Time",
                value=f"`{format_duration(grow_sec)}`" if grow_sec > 0 else "`N/A`",
                inline=True,
            )
            embed.add_field(
                name="🆔 Item ID",
                value=f"`#{item_data['id']}`",
                inline=True,
            )

        files: list[discord.File] = []
        sprite_bytes = await self.bot.api.get_item_sprite(title)
        if sprite_bytes:
            files.append(discord.File(BytesIO(sprite_bytes), filename="sprite.png"))
            embed.set_thumbnail(url="attachment://sprite.png")

        embed.set_footer(text=FOOTER_TEXT)
        await interaction.followup.send(embed=embed, files=files)


async def setup(bot: EventBot) -> None:
    await bot.add_cog(RecipeLookupCog(bot))
