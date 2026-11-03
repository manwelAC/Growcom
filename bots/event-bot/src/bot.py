"""
Growcom Event Bot — Main Entrypoint (src/bot.py)
Automatically loads all categorized tool modules from src/cogs/ and enforces
the 2-minute (120s) per-user command cooldown via GrowcomCommandTree.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
import sys
import time

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

SRC_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SRC_DIR.parents[2]
sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(PROJECT_ROOT))

from bots.shared.api_client import CentralDataClient  # noqa: E402
from utils.helpers import (  # noqa: E402
    EVENT_TIMEZONE_NAME,
    RESET_HOUR,
    RESET_MINUTE,
    load_state,
    logger,
)

load_dotenv(PROJECT_ROOT / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | event-bot | %(message)s",
)

USER_COOLDOWN_SECONDS = int(os.getenv("COMMAND_COOLDOWN_SECONDS", "120"))

COMMAND_CHANNEL_KEYS: dict[str, str] = {
    "harvest": "harvest_channel_id",
    "item": "item_channel_id",
    "recipe": "recipe_channel_id",
    "rate": "rate_channel_id",
    "surgery": "surgery_channel_id",
    "compare_farm": "compare_channel_id",
    "mass": "mass_channel_id",
    "cook": "cook_channel_id",
    "crime": "crime_channel_id",
    "fish": "fish_channel_id",
    "startrek": "startrek_channel_id",
}


class GrowcomCommandTree(app_commands.CommandTree):
    """Global slash-command gatekeeper enforcing channel locks and the 2-minute per-user cooldown."""

    def __init__(self, client: commands.Bot) -> None:
        super().__init__(client)
        # Maps (user_id, command_name) -> cooldown expiration unix timestamp
        self._user_cooldowns: dict[tuple[int, str], float] = {}

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.type != discord.InteractionType.application_command or not interaction.command:
            return True

        cmd_name = interaction.command.name

        # Admin /set_... configuration commands are never rate-limited
        if cmd_name.startswith("set_"):
            return True

        # 1. Verify channel lock first so typing in the wrong channel doesn't waste the user's 2-min cooldown
        state_key = COMMAND_CHANNEL_KEYS.get(cmd_name)
        if state_key:
            state = load_state()
            allowed_channel_id = state.get(state_key)
            if allowed_channel_id and int(interaction.channel_id or 0) != int(allowed_channel_id):
                await interaction.response.send_message(
                    f"❌ The **`/{cmd_name}`** tool can only be used inside <#{allowed_channel_id}>!",
                    ephemeral=True,
                )
                return False

        # 2. Enforce 2-minute (120s) per-user cooldown
        now = time.time()
        bucket_key = (interaction.user.id, cmd_name)
        expires_at = self._user_cooldowns.get(bucket_key, 0.0)
        if now < expires_at:
            exp_ts = int(expires_at)
            await interaction.response.send_message(
                f"⏳ **Cooldown Active!** You can use **`/{cmd_name}`** again <t:{exp_ts}:R> (at <t:{exp_ts}:T>).\n"
                f"*(Each tool has a 2-minute rate limit per user to prevent spam!)*",
                ephemeral=True,
            )
            return False

        self._user_cooldowns[bucket_key] = now + USER_COOLDOWN_SECONDS
        return True


class EventBot(commands.Bot):
    def __init__(self, api_client: CentralDataClient, dev_guild_id: int | None = None) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents, tree_cls=GrowcomCommandTree)
        self.api = api_client
        self.dev_guild_id = dev_guild_id

    async def setup_hook(self) -> None:
        # Auto-discover and load all categorized tool Cogs in src/cogs/
        cogs_dir = SRC_DIR / "cogs"
        for cog_file in sorted(cogs_dir.glob("*.py")):
            if cog_file.name.startswith("_"):
                continue
            ext_name = f"cogs.{cog_file.stem}"
            await self.load_extension(ext_name)
            logger.info("Loaded tool module: %s", ext_name)

        if self.dev_guild_id:
            guild = discord.Object(id=self.dev_guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            logger.info("Synced Event Bot slash commands to guild %s", self.dev_guild_id)
        else:
            await self.tree.sync()
            logger.info("Synced Event Bot slash commands globally")

    async def close(self) -> None:
        await self.api.close()
        await super().close()


api_url = os.getenv("CENTRAL_API_URL", "http://127.0.0.1:8000")
api_key = os.getenv("INTERNAL_API_KEY", "")
raw_guild = os.getenv("DEV_GUILD_ID", "").strip()
dev_guild = int(raw_guild) if raw_guild.isdigit() else None

bot = EventBot(api_client=CentralDataClient(api_url, api_key), dev_guild_id=dev_guild)


@bot.event
async def on_ready() -> None:
    logger.info(
        "Event Bot connected as %s | Scheduled daily update at %02d:%02d (%s)",
        bot.user,
        RESET_HOUR,
        RESET_MINUTE,
        EVENT_TIMEZONE_NAME,
    )
    for guild in bot.guilds:
        try:
            bot.tree.copy_global_to(guild=guild)
            await bot.tree.sync(guild=guild)
            logger.info("Instant-synced slash commands to server: %s (%s)", guild.name, guild.id)
        except Exception as exc:
            logger.warning("Could not sync guild %s: %s", guild.id, exc)


@bot.event
async def on_guild_join(guild: discord.Guild) -> None:
    try:
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
        logger.info("Bot joined %s (%s) — synced slash commands immediately!", guild.name, guild.id)
    except Exception as exc:
        logger.warning("Could not sync newly joined guild %s: %s", guild.id, exc)


def main() -> None:
    token = os.getenv("EVENT_BOT_TOKEN", "").strip()
    if not token:
        logger.error("EVENT_BOT_TOKEN is not set in .env! Add your token to start the Event Bot.")
        sys.exit(1)
    bot.run(token)


if __name__ == "__main__":
    main()
