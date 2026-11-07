"""
Growcom Server Rating & Community Feedback System (src/cogs/server_feedback.py)
- Creates #⭐server-ratings inside the 'Social' category (unlocked for verified 'Member' role).
- Provides both interactive 1-5 Star Buttons (opening a Feedback Modal) AND the /feedback slash command.
- Tracks overall server rating average and displays a '⭐ Leave a Rating' button on every review card!
"""

from __future__ import annotations

from datetime import datetime
import json
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

from utils.helpers import (
    EVENT_TZ,
    FOOTER_TEXT,
    PROJECT_ROOT,
    is_server_manager,
    load_state,
    logger,
    save_state,
)

SOCIAL_CATEGORY_ID = 1567168952444915782
DEFAULT_MEMBER_ROLE_ID = 1568495447067332608
RATINGS_FILE = PROJECT_ROOT / "bots" / "event-bot" / "data" / "server_ratings.json"


def _load_ratings() -> list[dict[str, Any]]:
    if RATINGS_FILE.exists():
        try:
            return json.loads(RATINGS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def _save_ratings(ratings: list[dict[str, Any]]) -> None:
    RATINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    RATINGS_FILE.write_text(json.dumps(ratings, indent=2), encoding="utf-8")


def _record_and_summarize_rating(user_id: int, username: str, stars: int, comment: str) -> tuple[float, int]:
    ratings = _load_ratings()
    # Update existing rating from the same user or append a new one
    updated = False
    for entry in ratings:
        if int(entry.get("user_id", 0)) == user_id:
            entry["stars"] = stars
            entry["username"] = username
            entry["comment"] = comment
            entry["timestamp"] = datetime.now(EVENT_TZ).isoformat()
            updated = True
            break
    if not updated:
        ratings.append(
            {
                "user_id": user_id,
                "username": username,
                "stars": stars,
                "comment": comment,
                "timestamp": datetime.now(EVENT_TZ).isoformat(),
            }
        )
    _save_ratings(ratings)
    total = len(ratings)
    avg = sum(int(r.get("stars", 5)) for r in ratings) / max(1, total)
    return round(avg, 2), total


def _build_review_embed(
    user: discord.User | discord.Member,
    stars: int,
    comment: str,
    favorite_feature: str,
    avg_score: float,
    total_reviews: int,
) -> discord.Embed:
    stars = max(1, min(5, stars))
    star_bar = "⭐" * stars + "☆" * (5 - stars)
    color_map = {
        5: 0xF1C40F,  # Gold
        4: 0x2ECC71,  # Green
        3: 0x3498DB,  # Blue
        2: 0xE67E22,  # Orange
        1: 0xE74C3C,  # Red
    }

    embed = discord.Embed(
        title=f"🌟 Growcom Server Review — {star_bar} ({stars}/5)",
        description=f"### 💬 Member Feedback\n> {comment.strip()}",
        color=color_map.get(stars, 0xF1C40F),
        timestamp=datetime.now(EVENT_TZ),
    )
    embed.add_field(
        name="👤 Reviewed By",
        value=f"{user.mention} (`{user}`)",
        inline=True,
    )
    if favorite_feature and favorite_feature.strip():
        embed.add_field(
            name="🛠️ Favorite Feature / Channel",
            value=favorite_feature.strip(),
            inline=True,
        )
    embed.add_field(
        name="📊 Overall Growcom Rating",
        value=f"⭐ **{avg_score:.2f} / 5.00** *(from `{total_reviews}` member review{'s' if total_reviews != 1 else ''})*",
        inline=False,
    )
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.set_footer(text=FOOTER_TEXT)
    return embed


class ServerFeedbackModal(discord.ui.Modal):
    """Pop-up modal when a player clicks one of the 1-5 Star buttons in #⭐server-ratings."""

    def __init__(self, stars: int) -> None:
        super().__init__(title=f"Rate Growcom Discord ({'⭐' * stars} {stars}/5)")
        self.stars = stars

        self.favorite_input = discord.ui.TextInput(
            label="Favorite Feature or Channel (Optional)",
            placeholder="e.g. Daily Quest alerts, /harvest timer, Business Marketplace...",
            required=False,
            max_length=100,
        )
        self.comment_input = discord.ui.TextInput(
            label="Your Feedback / Suggestions for Growcom",
            style=discord.TextStyle.paragraph,
            placeholder="Tell us what you love about the Growcom server or what features you'd like to see next!",
            required=True,
            min_length=3,
            max_length=800,
        )
        self.add_item(self.favorite_input)
        self.add_item(self.comment_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        comment = self.comment_input.value.strip()
        favorite = self.favorite_input.value.strip()

        avg_score, total_reviews = _record_and_summarize_rating(
            user_id=interaction.user.id,
            username=str(interaction.user),
            stars=self.stars,
            comment=comment,
        )
        embed = _build_review_embed(
            user=interaction.user,
            stars=self.stars,
            comment=comment,
            favorite_feature=favorite,
            avg_score=avg_score,
            total_reviews=total_reviews,
        )
        await interaction.response.send_message(
            content=f"🎉 Thank you for rating **Growcom**, {interaction.user.mention}!",
            embed=embed,
            view=ServerRatingView(),
        )


class ServerRatingView(discord.ui.View):
    """Persistent 1-5 Star rating buttons displayed at the bottom of #⭐server-ratings."""

    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="5 Stars",
        emoji="🌟",
        style=discord.ButtonStyle.success,
        custom_id="growcom:rate_5",
    )
    async def rate_5(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.send_modal(ServerFeedbackModal(stars=5))

    @discord.ui.button(
        label="4 Stars",
        emoji="⭐",
        style=discord.ButtonStyle.primary,
        custom_id="growcom:rate_4",
    )
    async def rate_4(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.send_modal(ServerFeedbackModal(stars=4))

    @discord.ui.button(
        label="3 Stars",
        emoji="⭐",
        style=discord.ButtonStyle.secondary,
        custom_id="growcom:rate_3",
    )
    async def rate_3(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.send_modal(ServerFeedbackModal(stars=3))

    @discord.ui.button(
        label="2 Stars",
        emoji="⭐",
        style=discord.ButtonStyle.secondary,
        custom_id="growcom:rate_2",
    )
    async def rate_2(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.send_modal(ServerFeedbackModal(stars=2))

    @discord.ui.button(
        label="1 Star",
        emoji="⭐",
        style=discord.ButtonStyle.danger,
        custom_id="growcom:rate_1",
    )
    async def rate_1(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.send_modal(ServerFeedbackModal(stars=1))


class ServerFeedbackCog(commands.Cog):
    """Manages #⭐server-ratings channel, persistent star rating buttons, and /feedback command."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._provisioned_guilds: set[int] = set()

    async def cog_load(self) -> None:
        self.bot.add_view(ServerRatingView())

    async def provision_rating_channel(self, guild: discord.Guild) -> discord.TextChannel:
        state = load_state()
        everyone_role = guild.default_role
        bot_member = guild.me

        member_role_id = int(state.get("member_role_id", DEFAULT_MEMBER_ROLE_ID))
        member_role = guild.get_role(member_role_id)

        social_cat: discord.CategoryChannel | None = guild.get_channel(SOCIAL_CATEGORY_ID)  # type: ignore[assignment]
        if not isinstance(social_cat, discord.CategoryChannel):
            for cat in guild.categories:
                if "social" in cat.name.lower():
                    social_cat = cat
                    break

        rating_ch: discord.TextChannel | None = None
        saved_id = state.get("feedback_channel_id")
        if saved_id:
            ch = guild.get_channel(int(saved_id))
            if isinstance(ch, discord.TextChannel):
                rating_ch = ch

        if not rating_ch:
            for ch in guild.text_channels:
                if "server-rating" in ch.name.lower() or "server-feedback" in ch.name.lower():
                    rating_ch = ch
                    break

        overwrites: dict[discord.Role | discord.Member, discord.PermissionOverwrite] = {
            everyone_role: discord.PermissionOverwrite(view_channel=False),
        }
        if member_role:
            overwrites[member_role] = discord.PermissionOverwrite(
                view_channel=True,
                read_message_history=True,
                send_messages=True,
                add_reactions=True,
            )
        if bot_member:
            overwrites[bot_member] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                embed_links=True,
                read_message_history=True,
                manage_messages=True,
            )

        if not rating_ch:
            rating_ch = await guild.create_text_channel(
                name="⭐server-ratings",
                category=social_cat,
                topic="Rate the Growcom Discord Server & Bot! Click a Star button below or run /feedback to share your review.",
                overwrites=overwrites,
                reason="Growcom Server Ratings & Feedback channel setup",
            )
            welcome_embed = discord.Embed(
                title="🌟 Growcom Server Ratings & Community Feedback",
                description=(
                    "We'd love to hear what you think about the **Growcom** Discord server, our Growtopia tools, and marketplace!\n\n"
                    "### ⭐ How to Leave Your Review\n"
                    "- **Option 1 (Fastest):** Click one of the **Star Buttons (`🌟 5 Stars` – `⭐ 1 Star`)** below to open a quick feedback box!\n"
                    "- **Option 2 (Slash Command):** Type **`/feedback`** in this channel.\n\n"
                    "Your rating and suggestions help us keep improving **Growcom** for everyone!"
                ),
                color=0xF1C40F,
                timestamp=datetime.now(EVENT_TZ),
            )
            welcome_embed.set_footer(text=FOOTER_TEXT)
            await rating_ch.send(embed=welcome_embed, view=ServerRatingView())
        else:
            await rating_ch.edit(overwrites=overwrites, reason="Sync #⭐server-ratings permissions")

        state["feedback_channel_id"] = str(rating_ch.id)
        save_state(state)
        self._provisioned_guilds.add(guild.id)
        return rating_ch

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        for guild in self.bot.guilds:
            if guild.id in self._provisioned_guilds:
                continue
            if guild.me and guild.me.guild_permissions.administrator:
                try:
                    ch = await self.provision_rating_channel(guild)
                    logger.info("Configured #⭐server-ratings (%s) in %s", ch.id, guild.name)
                except Exception as exc:
                    logger.warning("Could not configure #⭐server-ratings in %s: %s", guild.name, exc)

    @app_commands.command(
        name="feedback",
        description="Leave a 1-5 Star rating and feedback for the Growcom Discord server!",
    )
    @app_commands.describe(
        stars="Your rating from 1 to 5 stars",
        comment="Your feedback, review, or feature suggestion for Growcom",
        favorite_feature="Your favorite Growcom tool or channel (optional)",
    )
    @app_commands.choices(
        stars=[
            app_commands.Choice(name="⭐⭐⭐⭐⭐ (5/5 — Amazing!)", value=5),
            app_commands.Choice(name="⭐⭐⭐⭐ (4/5 — Great!)", value=4),
            app_commands.Choice(name="⭐⭐⭐ (3/5 — Good)", value=3),
            app_commands.Choice(name="⭐⭐ (2/5 — Needs Work)", value=2),
            app_commands.Choice(name="⭐ (1/5 — Poor)", value=1),
        ]
    )
    async def feedback_cmd(
        self,
        interaction: discord.Interaction,
        stars: app_commands.Choice[int],
        comment: str,
        favorite_feature: str = "",
    ) -> None:
        avg_score, total_reviews = _record_and_summarize_rating(
            user_id=interaction.user.id,
            username=str(interaction.user),
            stars=stars.value,
            comment=comment,
        )
        embed = _build_review_embed(
            user=interaction.user,
            stars=stars.value,
            comment=comment,
            favorite_feature=favorite_feature,
            avg_score=avg_score,
            total_reviews=total_reviews,
        )
        await interaction.response.send_message(
            content=f"🎉 Thank you for rating **Growcom**, {interaction.user.mention}!",
            embed=embed,
            view=ServerRatingView(),
        )

    @app_commands.command(
        name="set_feedback_channel",
        description="Admin: Lock /feedback to a specific channel (e.g. #⭐server-ratings).",
    )
    async def set_feedback_channel(self, interaction: discord.Interaction, channel: discord.TextChannel) -> None:
        if not is_server_manager(interaction):
            await interaction.response.send_message("❌ Admin permission required.", ephemeral=True)
            return
        state = load_state()
        state["feedback_channel_id"] = str(channel.id)
        save_state(state)
        await interaction.response.send_message(
            f"✅ Locked **`/feedback`** to {channel.mention}!",
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ServerFeedbackCog(bot))
