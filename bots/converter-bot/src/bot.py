"""
Growcom Converter Bot — Discord Client 2.
Dedicated visual/asset client that sends `.rttex` / `.png` files or sprite requests to the
Central Data API and returns processed `.png` / `.rttex` attachments.
"""

from __future__ import annotations

from io import BytesIO
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
    format="%(asctime)s | %(levelname)-7s | converter-bot | %(message)s",
)
logger = logging.getLogger("growcom.converter_bot")


class ConverterBot(commands.Bot):
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
            logger.info("Synced Converter Bot slash commands to guild %s", self.dev_guild_id)
        else:
            await self.tree.sync()
            logger.info("Synced Converter Bot slash commands globally")

    async def close(self) -> None:
        await self.api.close()
        await super().close()


api_url = os.getenv("CENTRAL_API_URL", "http://127.0.0.1:8000")
api_key = os.getenv("INTERNAL_API_KEY", "")
raw_guild = os.getenv("DEV_GUILD_ID", "").strip()
dev_guild = int(raw_guild) if raw_guild.isdigit() else None

bot = ConverterBot(api_client=CentralDataClient(api_url, api_key), dev_guild_id=dev_guild)


@bot.event
async def on_ready() -> None:
    logger.info("Converter Bot connected as %s (ID: %s)", bot.user, bot.user.id if bot.user else "?")


@bot.tree.command(name="rttex_to_png", description="Convert a Growtopia .rttex texture file into a .png image")
@app_commands.describe(file="Upload a .rttex texture file")
async def rttex_to_png_command(interaction: discord.Interaction, file: discord.Attachment) -> None:
    await interaction.response.defer()
    try:
        raw_bytes = await file.read()
        png_bytes = await bot.api.convert_rttex_to_png(file.filename, raw_bytes)
        out_name = f"{Path(file.filename).stem}.png"
        discord_file = discord.File(BytesIO(png_bytes), filename=out_name)
        embed = discord.Embed(
            title="🖼️ RTTEX → PNG Conversion Complete",
            description=f"Converted **`{file.filename}`** (`{len(raw_bytes):,}` bytes) → **`{out_name}`**",
            color=discord.Color.blurple(),
        )
        embed.set_image(url=f"attachment://{out_name}")
        embed.set_footer(text="Growcom Events by Manwel")
        await interaction.followup.send(embed=embed, file=discord_file)
    except Exception as exc:
        await interaction.followup.send(f"❌ Failed to convert `{file.filename}`: `{exc}`", ephemeral=True)


@bot.tree.command(name="png_to_rttex", description="Pack a .png image into Growtopia's .rttex texture format")
@app_commands.describe(file="Upload a .png image file")
async def png_to_rttex_command(interaction: discord.Interaction, file: discord.Attachment) -> None:
    await interaction.response.defer()
    try:
        raw_bytes = await file.read()
        rttex_bytes = await bot.api.convert_png_to_rttex(file.filename, raw_bytes)
        out_name = f"{Path(file.filename).stem}.rttex"
        discord_file = discord.File(BytesIO(rttex_bytes), filename=out_name)
        await interaction.followup.send(
            content=f"✅ Packed **`{file.filename}`** into **`{out_name}`** (`{len(rttex_bytes):,}` bytes):",
            file=discord_file,
        )
    except Exception as exc:
        await interaction.followup.send(f"❌ Failed to pack `{file.filename}`: `{exc}`", ephemeral=True)


@bot.tree.command(name="sprite", description="Extract and upscale an item's 32x32 sprite via the Central Data API")
@app_commands.describe(query="Item name or ID")
async def sprite_command(interaction: discord.Interaction, query: str) -> None:
    await interaction.response.defer()
    sprite_bytes = await bot.api.get_item_sprite(query)
    if sprite_bytes is None:
        await interaction.followup.send(f"❌ Item **`{query}`** was not found.", ephemeral=True)
        return

    discord_file = discord.File(BytesIO(sprite_bytes), filename="sprite.png")
    embed = discord.Embed(
        title=f"🎨 Sprite: {query}",
        color=discord.Color.gold(),
    )
    embed.set_image(url="attachment://sprite.png")
    embed.set_footer(text="Growcom Events by Manwel")
    await interaction.followup.send(embed=embed, file=discord_file)


def main() -> None:
    token = os.getenv("CONVERTER_BOT_TOKEN", "").strip()
    if not token:
        logger.error("CONVERTER_BOT_TOKEN is not set in .env! Add your token to start the Converter Bot.")
        sys.exit(1)
    bot.run(token)


if __name__ == "__main__":
    main()
