"""
Growcom Parser Bot — Discord Client 1.
Solely fetches structured item stats, wiki descriptions, and splice recipes from the
Central Data API and formats them into clean Discord embeds.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from bots.shared.api_client import CentralDataClient  # noqa: E402

load_dotenv(PROJECT_ROOT / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | parser-bot | %(message)s",
)
logger = logging.getLogger("growcom.parser_bot")


def format_duration(seconds: int) -> str:
    if seconds <= 0:
        return "Instant / N/A"
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if secs:
        parts.append(f"{secs}s")
    return " ".join(parts)


class ParserBot(commands.Bot):
    def __init__(self, api_client: CentralDataClient, dev_guild_id: int | None = None) -> None:
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)
        self.api = api_client
        self.dev_guild_id = dev_guild_id

    async def setup_hook(self) -> None:
        if self.dev_guild_id:
            guild = discord.Object(id=self.dev_guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            logger.info("Synced Parser Bot slash commands to guild %s", self.dev_guild_id)
        else:
            await self.tree.sync()
            logger.info("Synced Parser Bot slash commands globally")

    async def close(self) -> None:
        await self.api.close()
        await super().close()


api_url = os.getenv("CENTRAL_API_URL", "http://127.0.0.1:8000")
api_key = os.getenv("INTERNAL_API_KEY", "")
raw_guild = os.getenv("DEV_GUILD_ID", "").strip()
dev_guild = int(raw_guild) if raw_guild.isdigit() else None

bot = ParserBot(api_client=CentralDataClient(api_url, api_key), dev_guild_id=dev_guild)


@bot.event
async def on_ready() -> None:
    logger.info("Parser Bot connected as %s (ID: %s)", bot.user, bot.user.id if bot.user else "?")


@bot.tree.command(name="item", description="Look up Growtopia item stats and wiki info from the Central Data API")
@app_commands.describe(query="Item name, abbreviation (e.g. wl, dl, lgrid), or item ID")
async def item_command(interaction: discord.Interaction, query: str) -> None:
    await interaction.response.defer()
    item_data = await bot.api.get_item(query)
    wiki_data = await bot.api.get_wiki_item(item_data["name"] if item_data else query)

    if not item_data and not wiki_data:
        await interaction.followup.send(f"❌ Could not find any item matching **`{query}`**.", ephemeral=True)
        return

    title = (item_data["name"] if item_data else wiki_data["title"])  # type: ignore[index]
    url = wiki_data.get("url") if wiki_data else None
    description = (wiki_data.get("description") if wiki_data else None) or "No wiki description available."

    embed = discord.Embed(
        title=f"📦 {title}",
        url=url or None,
        description=description,
        color=discord.Color.teal(),
    )

    if item_data:
        embed.add_field(name="🆔 Item ID", value=f"`{item_data['id']}`", inline=True)
        embed.add_field(name="⭐ Rarity", value=f"`{item_data['rarity']}`", inline=True)
        embed.add_field(
            name="🌱 Grow Time",
            value=f"`{format_duration(item_data['grow_time_seconds'])}`",
            inline=True,
        )
        embed.add_field(
            name="👊 Fist Hits",
            value=f"`{item_data['hardness_hits']} hits`",
            inline=True,
        )
        embed.add_field(
            name="🗂️ Texture Sheet",
            value=f"`{item_data['file_name']}` (`{item_data['tex_x']}, {item_data['tex_y']}`)",
            inline=True,
        )

    if wiki_data:
        if wiki_data.get("chi") and wiki_data["chi"] != "None":
            embed.add_field(name="🌀 Chi Element", value=f"`{wiki_data['chi']}`", inline=True)
        if wiki_data.get("gems_drop"):
            embed.add_field(name="💎 Gems Drop", value=f"`{wiki_data['gems_drop']}`", inline=True)
        if wiki_data.get("recipes"):
            embed.add_field(
                name="🧬 Recipe / Source",
                value="\n".join(f"• {r}" for r in wiki_data["recipes"][:4]),
                inline=False,
            )
        sprite_url = (wiki_data.get("sprites") or {}).get("Item")
        if sprite_url:
            embed.set_thumbnail(url=sprite_url)

    embed.set_footer(text="Growcom Events by Manwel")
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="recipe", description="Look up splicing or crafting recipes for a Growtopia item")
@app_commands.describe(item_name="Name of the item to check recipes for")
async def recipe_command(interaction: discord.Interaction, item_name: str) -> None:
    await interaction.response.defer()
    wiki_data = await bot.api.get_wiki_item(item_name)
    if not wiki_data:
        await interaction.followup.send(f"❌ Could not find a wiki page for **`{item_name}`**.", ephemeral=True)
        return

    recipes = wiki_data.get("recipes") or []
    embed = discord.Embed(
        title=f"🧬 Recipes for {wiki_data['title']}",
        url=wiki_data.get("url") or None,
        color=discord.Color.green(),
    )
    if recipes:
        embed.description = "\n".join(f"• **{r}**" for r in recipes)
    else:
        embed.description = "This item cannot be spliced or has no listed recipe on the Wiki."

    if wiki_data.get("grow_time"):
        embed.add_field(name="🌱 Grow Time", value=f"`{wiki_data['grow_time']}`", inline=True)
    if wiki_data.get("rarity"):
        embed.add_field(name="⭐ Rarity", value=f"`{wiki_data['rarity']}`", inline=True)

    sprite_url = (wiki_data.get("sprites") or {}).get("Seed") or (wiki_data.get("sprites") or {}).get("Item")
    if sprite_url:
        embed.set_thumbnail(url=sprite_url)

    embed.set_footer(text="Growcom Events by Manwel")
    await interaction.followup.send(embed=embed)


def main() -> None:
    token = os.getenv("PARSER_BOT_TOKEN", "").strip()
    if not token:
        logger.error("PARSER_BOT_TOKEN is not set in .env! Add your token to start the Parser Bot.")
        sys.exit(1)
    bot.run(token)


if __name__ == "__main__":
    main()
