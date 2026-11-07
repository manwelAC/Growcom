"""
Category 13: Smart Auto-Moderator & Private DM Warning System (cogs/auto_moderator.py)
- Automatically detects explicit/inappropriate words (English + Tagalog/Filipino + Leetspeak anti-bypass + Free PurgoMalum API check)
- Deletes the inappropriate message from the public channel
- Sends a polite, official private DM warning to the player from Growcom Events by Manwel (no harsh mute!)
- Admin commands: /automod_add, /automod_remove, /automod_list
"""

from __future__ import annotations

from datetime import datetime
import re
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from utils.helpers import (
    EVENT_TZ,
    FOOTER_TEXT,
    is_server_manager,
    load_state,
    logger,
    save_state,
)

if TYPE_CHECKING:
    from bot import EventBot


# Built-in English & Tagalog/Filipino explicit word roots (checked on word boundaries + leetspeak normalization)
DEFAULT_BAD_WORDS: set[str] = {
    # English explicit words & slurs
    "fuck",
    "fucker",
    "fucking",
    "motherfucker",
    "shit",
    "bullshit",
    "bitch",
    "asshole",
    "bastard",
    "dick",
    "cock",
    "pussy",
    "cunt",
    "whore",
    "slut",
    "nigger",
    "nigga",
    "faggot",
    "retard",
    "porn",
    "pornhub",
    "xvideos",
    "blowjob",
    "handjob",
    # Tagalog / Filipino explicit profanity
    "putangina",
    "tangina",
    "tanginamo",
    "putanginamo",
    "puta",
    "gago",
    "gagu",
    "tarantado",
    "ulol",
    "kupal",
    "kantot",
    "kantutan",
    "pokpok",
    "burat",
    "pekpek",
    "punyeta",
    "hindot",
    "pakshet",
    "inutil",
    "bobo",
    "tanga",
}

LEET_MAP = str.maketrans(
    {
        "@": "a",
        "4": "a",
        "3": "e",
        "1": "i",
        "!": "i",
        "0": "o",
        "$": "s",
        "5": "s",
        "7": "t",
        "+": "t",
    }
)


def normalize_token(word: str) -> str:
    """Convert leetspeak symbols (@ -> a, 0 -> o, etc.) and strip non-letters inside a single token."""
    lowered = word.lower().translate(LEET_MAP)
    cleaned = re.sub(r"[^a-z]", "", lowered)
    # Collapse 3+ repeated letters (e.g. "fuuuuck" -> "fuck", "gaaaago" -> "gago")
    cleaned = re.sub(r"(.)\1{2,}", r"\1", cleaned)
    return cleaned


def detect_bad_word_locally(content: str, custom_words: set[str]) -> str | None:
    """
    Check message content against built-in + custom bad words.
    Handles normal words, leetspeak ('g@go', 'f*ck', 'sh1t'), and spaced-out letters ('f u c k').
    """
    all_bad_words = DEFAULT_BAD_WORDS | {w.lower().strip() for w in custom_words if w.strip()}

    # 1. Check word-by-word (with leetspeak normalization)
    raw_tokens = re.findall(r"[A-Za-z0-9@!$+*._\-]+", content)
    for raw_tok in raw_tokens:
        norm = normalize_token(raw_tok)
        if not norm:
            continue
        if norm in all_bad_words:
            return raw_tok
        # Also check compound Tagalog/English swear roots inside longer tokens (length >= 6)
        for bad in (
            "putangina",
            "tangina",
            "motherfuck",
            "tarantado",
            "punyeta",
            "kantot",
            "nigger",
            "faggot",
        ):
            if bad in norm:
                return raw_tok

    # 2. Check spaced-out single letters (e.g. "f u c k" or "g a g o")
    single_letter_runs = re.findall(r"\b(?:[a-zA-Z]\s+){3,}[a-zA-Z]\b", content)
    for run in single_letter_runs:
        collapsed = re.sub(r"\s+", "", run).lower()
        if collapsed in all_bad_words:
            return run

    return None


class AutoModeratorCog(commands.Cog, name="Auto Moderator"):
    def __init__(self, bot: EventBot) -> None:
        self.bot = bot

    @staticmethod
    def _get_custom_bad_words() -> set[str]:
        state = load_state()
        words = state.get("custom_bad_words") or []
        return {str(w).lower().strip() for w in words if str(w).strip()}

    @staticmethod
    def _save_custom_bad_words(words: set[str]) -> None:
        state = load_state()
        state["custom_bad_words"] = sorted(words)
        save_state(state)

    async def _check_purgomalum_api(self, text: str) -> bool:
        """Fallback check against the free PurgoMalum Profanity REST API (no API key required)."""
        try:
            resp = await self.bot.api._client.get(
                "https://www.purgomalum.com/service/containsprofanity",
                params={"text": text[:400]},
                timeout=2.5,
            )
            if resp.status_code == 200:
                return resp.text.strip().lower() == "true"
        except Exception:
            pass
        return False

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        # Ignore bots, DMs, or empty messages
        if message.author.bot or not message.guild or not message.content.strip():
            return

        # Ignore the #dq-feed channel
        state = load_state()
        feed_channel_id = state.get("dq_feed_channel_id")
        if feed_channel_id and str(message.channel.id) == str(feed_channel_id):
            return

        custom_words = self._get_custom_bad_words()
        matched_word = detect_bad_word_locally(message.content, custom_words)

        # Optional free API check if local check passed
        if not matched_word and len(message.content) >= 4:
            if await self._check_purgomalum_api(message.content):
                matched_word = "explicit language"

        if not matched_word:
            return

        # 1. Delete the inappropriate message from the server channel (if bot has permission)
        deleted = False
        try:
            await message.delete()
            deleted = True
        except Exception as exc:
            logger.debug("AutoMod could not delete message in #%s: %s", message.channel, exc)

        # 2. Send a polite, official private DM to the player
        channel_mention = message.channel.mention if hasattr(message.channel, "mention") else f"#{message.channel}"
        dm_embed = discord.Embed(
            title="⚠️ Growcom Community Moderation Notice",
            description=(
                f"Hey **{message.author.display_name}**, your recent message in {channel_mention} "
                f"on **{message.guild.name}** was flagged by our Auto-Moderator for containing "
                f"inappropriate or explicit language.\n\n"
                "🌱 **Friendly Reminder:**\n"
                "Please keep all conversations in **growcom** respectful, clean, and welcoming for all Growtopians!"
            ),
            color=discord.Color.from_rgb(231, 76, 60),
            timestamp=datetime.now(EVENT_TZ),
        )
        dm_embed.add_field(
            name="📍 Channel",
            value=channel_mention,
            inline=True,
        )
        dm_embed.add_field(
            name="🛡️ Action Taken",
            value="Message Removed & Private Notice Sent" if deleted else "Private Warning Notice Sent",
            inline=True,
        )
        dm_embed.set_footer(text=FOOTER_TEXT)

        try:
            await message.author.send(embed=dm_embed)
            logger.info(
                "AutoMod: Removed message & DM'd %s (%s) in #%s",
                message.author,
                message.author.id,
                message.channel,
            )
        except discord.Forbidden:
            # If the player has DMs disabled in their privacy settings, send a brief 8-second self-deleting notice in channel
            try:
                fallback_msg = await message.channel.send(
                    f"⚠️ {message.author.mention}, please keep chat clean and respectful! "
                    f"*(Your message contained inappropriate language and was removed.)*",
                    delete_after=8.0,
                )
                _ = fallback_msg
            except Exception:
                pass

    @app_commands.command(
        name="automod_add",
        description="Add a custom blocked word to Growcom Auto-Moderator (Admin Only)",
    )
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(word="The word you want the bot to automatically remove & warn players about")
    async def automod_add_command(self, interaction: discord.Interaction, word: str) -> None:
        if not is_server_manager(interaction):
            await interaction.response.send_message(
                "❌ Only server admins can use `/automod_add`.",
                ephemeral=True,
            )
            return
        clean = word.strip().lower()
        if len(clean) < 2:
            await interaction.response.send_message("❌ Word must be at least 2 characters long.", ephemeral=True)
            return

        words = self._get_custom_bad_words()
        words.add(clean)
        self._save_custom_bad_words(words)
        await interaction.response.send_message(
            f"✅ Added **`{clean}`** to the Growcom Auto-Moderator word filter! ({len(words)} custom words active)",
            ephemeral=True,
        )

    @app_commands.command(
        name="automod_remove",
        description="Remove a custom word from the Growcom Auto-Moderator filter (Admin Only)",
    )
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(word="The custom word to remove from the filter")
    async def automod_remove_command(self, interaction: discord.Interaction, word: str) -> None:
        if not is_server_manager(interaction):
            await interaction.response.send_message(
                "❌ Only server admins can use `/automod_remove`.",
                ephemeral=True,
            )
            return
        clean = word.strip().lower()
        words = self._get_custom_bad_words()
        if clean not in words:
            await interaction.response.send_message(
                f"ℹ️ **`{clean}`** is not in your custom word list.",
                ephemeral=True,
            )
            return

        words.remove(clean)
        self._save_custom_bad_words(words)
        await interaction.response.send_message(
            f"✅ Removed **`{clean}`** from your custom Auto-Moderator filter.",
            ephemeral=True,
        )

    @app_commands.command(
        name="automod_list",
        description="View your custom Auto-Moderator blocked words and filter status (Admin Only)",
    )
    @app_commands.default_permissions(manage_guild=True)
    async def automod_list_command(self, interaction: discord.Interaction) -> None:
        if not is_server_manager(interaction):
            await interaction.response.send_message(
                "❌ Only server admins can use `/automod_list`.",
                ephemeral=True,
            )
            return
        custom_words = sorted(self._get_custom_bad_words())
        custom_str = ", ".join(f"`{w}`" for w in custom_words) if custom_words else "*None added yet (using built-in English & Tagalog filter + PurgoMalum API)*"

        embed = discord.Embed(
            title="🛡️ Growcom Auto-Moderator Status",
            description=(
                "• **Built-in Filter:** Active (`English` + `Tagalog/Filipino` + `Leetspeak Anti-Bypass`)\n"
                "• **Free Profanity API:** Active (`PurgoMalum REST API`)\n"
                "• **Action on Detection:** Deletes offending message & sends a **Private DM Notice** to the player."
            ),
            color=discord.Color.from_rgb(46, 204, 113),
        )
        embed.add_field(
            name=f"📝 Custom Blocked Words ({len(custom_words)})",
            value=custom_str,
            inline=False,
        )
        embed.set_footer(text=FOOTER_TEXT)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: EventBot) -> None:
    await bot.add_cog(AutoModeratorCog(bot))
