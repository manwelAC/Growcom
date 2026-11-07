"""
Growcom Server Rating & Community Feedback System (src/cogs/server_feedback.py)
- Creates #⭐server-ratings inside '🤳Growcom Chats' where members submit reviews via 1-5 Star Buttons or /feedback.
- Creates a locked channel (#📊total-ratings) and locked sidebar counter (🔒 ⭐ Rating: X.XX/5) at the very end
  that automatically updates with the live overall score, star distribution bar chart, and total ratings!
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


def _record_and_summarize_rating(
    user_id: int,
    username: str,
    stars: int,
    comment: str,
    favorite_feature: str = "",
) -> tuple[float, int, list[dict[str, Any]]]:
    ratings = _load_ratings()
    updated = False
    for entry in ratings:
        if int(entry.get("user_id", 0)) == user_id:
            entry["stars"] = stars
            entry["username"] = username
            entry["comment"] = comment
            entry["favorite"] = favorite_feature
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
                "favorite": favorite_feature,
                "timestamp": datetime.now(EVENT_TZ).isoformat(),
            }
        )
    _save_ratings(ratings)
    total = len(ratings)
    avg = sum(int(r.get("stars", 5)) for r in ratings) / max(1, total)
    return round(avg, 2), total, ratings


def _build_total_ratings_dashboard_embed(ratings: list[dict[str, Any]]) -> discord.Embed:
    total = len(ratings)
    if total == 0:
        avg = 0.0
        star_display = "☆☆☆☆☆ (No ratings yet)"
    else:
        avg = round(sum(int(r.get("stars", 5)) for r in ratings) / total, 2)
        full_stars = int(round(avg))
        star_display = "⭐" * full_stars + "☆" * (5 - full_stars) + f" **{avg:.2f} / 5.00**"

    # Build 5-star to 1-star bar chart
    counts = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}
    for r in ratings:
        s = max(1, min(5, int(r.get("stars", 5))))
        counts[s] += 1

    bar_lines = []
    for star_num in (5, 4, 3, 2, 1):
        c = counts[star_num]
        pct = (c / total * 100.0) if total > 0 else 0.0
        filled = int(round((pct / 100.0) * 12))
        bar = "█" * filled + "░" * (12 - filled)
        label = f"{star_num} ⭐"
        bar_lines.append(f"`{label}` `{bar}` **{c}** ({pct:.0f}%)")

    # Latest 5 reviews preview
    recent_lines = []
    for r in reversed(ratings[-5:]):
        s = max(1, min(5, int(r.get("stars", 5))))
        uid = r.get("user_id")
        uname = r.get("username", "Member")
        user_ref = f"<@{uid}>" if uid else f"**{uname}**"
        snippet = (r.get("comment") or "").strip().replace("\n", " ")
        if len(snippet) > 90:
            snippet = snippet[:87] + "..."
        recent_lines.append(f"- {'⭐' * s} by {user_ref}: *\"{snippet}\"*")

    recent_section = (
        "\n".join(recent_lines)
        if recent_lines
        else "*No reviews submitted yet! Head over to `#⭐server-ratings` to be the first!*"
    )

    embed = discord.Embed(
        title="📊 Growcom Official Total Ratings & Community Score",
        description=(
            "This is the **Official Growcom Total Ratings Dashboard**. It updates automatically every time a member "
            "submits a review in **#⭐server-ratings**!\n\n"
            f"### 🏆 Overall Server Rating\n"
            f"> {star_display}\n"
            f"> 📈 **Total Verified Reviews:** `{total}`\n\n"
            f"### 📊 Star Rating Breakdown\n"
            + "\n".join(bar_lines)
            + f"\n\n### 💬 Latest Community Reviews\n{recent_section}"
        ),
        color=0xF1C40F,
        timestamp=datetime.now(EVENT_TZ),
    )
    embed.set_footer(text=FOOTER_TEXT)
    return embed


async def sync_total_ratings_channels(guild: discord.Guild | None, ratings: list[dict[str, Any]]) -> None:
    """Updates the locked #📊total-ratings dashboard embed and the locked sidebar voice counter."""
    if not guild:
        return

    state = load_state()
    total = len(ratings)
    avg = round(sum(int(r.get("stars", 5)) for r in ratings) / max(1, total), 2) if total > 0 else 0.0

    # 1. Update #📊total-ratings locked text channel dashboard
    total_ch_id = state.get("total_ratings_channel_id")
    total_ch: discord.TextChannel | None = None
    if total_ch_id:
        ch = guild.get_channel(int(total_ch_id))
        if isinstance(ch, discord.TextChannel):
            total_ch = ch

    if not total_ch:
        for ch in guild.text_channels:
            if "total-rating" in ch.name.lower():
                total_ch = ch
                state["total_ratings_channel_id"] = str(ch.id)
                save_state(state)
                break

    if total_ch:
        dash_embed = _build_total_ratings_dashboard_embed(ratings)
        msg_id = state.get("total_ratings_message_id")
        dash_msg: discord.Message | None = None
        if msg_id:
            try:
                dash_msg = await total_ch.fetch_message(int(msg_id))
            except Exception:
                dash_msg = None

        if dash_msg:
            await dash_msg.edit(embed=dash_embed)
        else:
            new_msg = await total_ch.send(embed=dash_embed)
            state["total_ratings_message_id"] = str(new_msg.id)
            save_state(state)

    # 2. Update locked voice channel counter at the very end if present
    vc_id = state.get("total_ratings_vc_id")
    if vc_id:
        vc = guild.get_channel(int(vc_id))
        if isinstance(vc, discord.VoiceChannel):
            new_name = (
                f"⭐ Rating: {avg:.2f}/5 ({total})"
                if total > 0
                else "⭐ Rating: N/A (0 Reviews)"
            )
            if vc.name != new_name:
                try:
                    await vc.edit(name=new_name, reason="Auto-update Growcom Total Ratings counter")
                except Exception as exc:
                    logger.warning("Could not rename total ratings VC counter: %s", exc)


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
        5: 0xF1C40F,
        4: 0x2ECC71,
        3: 0x3498DB,
        2: 0xE67E22,
        1: 0xE74C3C,
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

        avg_score, total_reviews, ratings = _record_and_summarize_rating(
            user_id=interaction.user.id,
            username=str(interaction.user),
            stars=self.stars,
            comment=comment,
            favorite_feature=favorite,
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
        await sync_total_ratings_channels(interaction.guild, ratings)


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
    """Manages #⭐server-ratings, locked #📊total-ratings, and /feedback command."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._provisioned_guilds: set[int] = set()

    async def cog_load(self) -> None:
        self.bot.add_view(ServerRatingView())

    async def provision_rating_channel(self, guild: discord.Guild) -> tuple[discord.TextChannel, discord.TextChannel, discord.VoiceChannel]:
        state = load_state()
        everyone_role = guild.default_role
        bot_member = guild.me

        member_role_id = int(state.get("member_role_id", DEFAULT_MEMBER_ROLE_ID))
        member_role = guild.get_role(member_role_id)

        social_cat: discord.CategoryChannel | None = guild.get_channel(SOCIAL_CATEGORY_ID)  # type: ignore[assignment]
        if not isinstance(social_cat, discord.CategoryChannel):
            for cat in guild.categories:
                if "chat" in cat.name.lower() or "social" in cat.name.lower():
                    social_cat = cat
                    break

        # 1. #⭐server-ratings (interactive channel where members submit ratings)
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

        open_overwrites: dict[discord.Role | discord.Member, discord.PermissionOverwrite] = {
            everyone_role: discord.PermissionOverwrite(view_channel=False),
        }
        if member_role:
            open_overwrites[member_role] = discord.PermissionOverwrite(
                view_channel=True,
                read_message_history=True,
                send_messages=True,
                add_reactions=True,
            )
        if bot_member:
            open_overwrites[bot_member] = discord.PermissionOverwrite(
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
                overwrites=open_overwrites,
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
            await rating_ch.edit(overwrites=open_overwrites, reason="Sync #⭐server-ratings permissions")

        state["feedback_channel_id"] = str(rating_ch.id)

        # 2. Place the locked Total Ratings channels outside of any category (standalone)
        locked_text_overwrites: dict[discord.Role | discord.Member, discord.PermissionOverwrite] = {
            everyone_role: discord.PermissionOverwrite(
                view_channel=False,
                send_messages=False,
            ),
        }
        if member_role:
            locked_text_overwrites[member_role] = discord.PermissionOverwrite(
                view_channel=True,
                read_message_history=True,
                send_messages=False,
                add_reactions=False,
            )
        if bot_member:
            locked_text_overwrites[bot_member] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                embed_links=True,
                read_message_history=True,
                manage_messages=True,
            )

        total_ch: discord.TextChannel | None = None
        saved_total_id = state.get("total_ratings_channel_id")
        if saved_total_id:
            ch = guild.get_channel(int(saved_total_id))
            if isinstance(ch, discord.TextChannel):
                total_ch = ch

        if not total_ch:
            for ch in guild.text_channels:
                if "total-rating" in ch.name.lower():
                    total_ch = ch
                    break

        ratings = _load_ratings()
        dash_embed = _build_total_ratings_dashboard_embed(ratings)

        if not total_ch:
            total_ch = await guild.create_text_channel(
                name="🔒📊total-ratings",
                category=None,
                topic="🔒 Locked Official Growcom Total Ratings Dashboard — Automatically updated whenever a member rates in #⭐server-ratings!",
                overwrites=locked_text_overwrites,
                reason="Locked Total Ratings dashboard channel outside any category",
            )
            dash_msg = await total_ch.send(embed=dash_embed)
            state["total_ratings_message_id"] = str(dash_msg.id)
        else:
            await total_ch.edit(
                category=None,
                overwrites=locked_text_overwrites,
                reason="Ensure #🔒📊total-ratings is locked and outside any category",
            )

        state["total_ratings_channel_id"] = str(total_ch.id)

        # 3. Also create a Locked Voice Channel Counter standalone outside any category
        locked_vc_overwrites: dict[discord.Role | discord.Member, discord.PermissionOverwrite] = {
            everyone_role: discord.PermissionOverwrite(
                view_channel=False,
                connect=False,
            ),
        }
        if member_role:
            locked_vc_overwrites[member_role] = discord.PermissionOverwrite(
                view_channel=True,
                connect=False,
                speak=False,
            )
        if bot_member:
            locked_vc_overwrites[bot_member] = discord.PermissionOverwrite(
                view_channel=True,
                connect=True,
                manage_channels=True,
            )

        total_vc: discord.VoiceChannel | None = None
        saved_vc_id = state.get("total_ratings_vc_id")
        if saved_vc_id:
            vc = guild.get_channel(int(saved_vc_id))
            if isinstance(vc, discord.VoiceChannel):
                total_vc = vc

        if not total_vc:
            for vc in guild.voice_channels:
                if "rating:" in vc.name.lower():
                    total_vc = vc
                    break

        total_count = len(ratings)
        avg_val = round(sum(int(r.get("stars", 5)) for r in ratings) / max(1, total_count), 2) if total_count > 0 else 0.0
        vc_name = f"⭐ Rating: {avg_val:.2f}/5 ({total_count})" if total_count > 0 else "⭐ Rating: N/A (0 Reviews)"

        if not total_vc:
            total_vc = await guild.create_voice_channel(
                name=vc_name,
                category=None,
                overwrites=locked_vc_overwrites,
                reason="Locked Total Ratings sidebar counter outside any category",
            )
        else:
            await total_vc.edit(
                category=None,
                overwrites=locked_vc_overwrites,
                reason="Sync locked Total Ratings VC counter outside any category",
            )

        state["total_ratings_vc_id"] = str(total_vc.id)
        save_state(state)
        await sync_total_ratings_channels(guild, ratings)
        self._provisioned_guilds.add(guild.id)
        return rating_ch, total_ch, total_vc

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        for guild in self.bot.guilds:
            if guild.id in self._provisioned_guilds:
                continue
            if guild.me and guild.me.guild_permissions.administrator:
                try:
                    _, total_ch, total_vc = await self.provision_rating_channel(guild)
                    logger.info(
                        "Configured #⭐server-ratings + locked %s (%s) in %s",
                        total_ch.name,
                        total_vc.name,
                        guild.name,
                    )
                except Exception as exc:
                    logger.warning("Could not configure rating channels in %s: %s", guild.name, exc)

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
        avg_score, total_reviews, ratings = _record_and_summarize_rating(
            user_id=interaction.user.id,
            username=str(interaction.user),
            stars=stars.value,
            comment=comment,
            favorite_feature=favorite_feature,
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
        await sync_total_ratings_channels(interaction.guild, ratings)

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
