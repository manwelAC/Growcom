"""
Growcom Official Server Announcement Studio & Dispatch Pipeline.

Features:
- Dedicated control channel #📢・announcement-desk inside 🛡️ Growcom Staff category.
- Pinned interactive Announcement Studio control panel.
- Modal form for composing rich, structured announcements with live Markdown support.
- Real-time Interactive Draft Preview with live color/theme switching.
- Direct broadcast to #🗣️・server-announcement (under 🎤 Growcom Announcements).
- Optional mentions (@everyone, @here, @Member) and optional banner images.
- Auto-reactions (📢, 🔥, 🎉, ❤️) on dispatch.
- Admin slash command: /announce.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from typing import TYPE_CHECKING, Any

import discord
from discord import app_commands
from discord.ext import commands

from utils.helpers import (
    EVENT_TZ,
    FOOTER_TEXT,
    PROJECT_ROOT,
    load_state,
    logger,
    save_state,
)

if TYPE_CHECKING:
    from bot import EventBot

STAFF_CATEGORY_ID = 1568494521036046448
ANNOUNCEMENT_CATEGORY_ID = 1569392019824967800
SERVER_ANNOUNCEMENT_CHANNEL_ID = 1569392202248101959
ADMIN_ROLE_ID = 1568477759422988318
MEMBER_ROLE_ID = 1568495447067332608
BOT_ROLE_ID = 1567194915945848977
CONTROL_CHANNEL_NAME = "📢・announcement-desk"

THEMES: dict[str, dict[str, Any]] = {
    "UPDATE": {
        "name": "Server Update",
        "badge": "⚡ SERVER UPDATE",
        "emoji": "🚀",
        "color": discord.Color.from_rgb(0, 230, 118),  # Emerald Mint
        "bar": "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    },
    "EVENT": {
        "name": "Community Event",
        "badge": "🌟 COMMUNITY EVENT",
        "emoji": "🎉",
        "color": discord.Color.from_rgb(156, 39, 176),  # Royal Purple
        "bar": "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    },
    "GIVEAWAY": {
        "name": "Special Giveaway",
        "badge": "🎁 SPECIAL GIVEAWAY",
        "emoji": "💎",
        "color": discord.Color.from_rgb(255, 215, 0),  # Radiant Gold
        "bar": "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    },
    "NOTICE": {
        "name": "Important Notice",
        "badge": "🚨 IMPORTANT NOTICE",
        "emoji": "📢",
        "color": discord.Color.from_rgb(255, 23, 68),  # Crimson Coral
        "bar": "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    },
    "MAINTENANCE": {
        "name": "Scheduled Maintenance",
        "badge": "🛠️ SCHEDULED MAINTENANCE",
        "emoji": "⚙️",
        "color": discord.Color.from_rgb(255, 145, 0),  # Amber Flame
        "bar": "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    },
    "COMMUNITY": {
        "name": "Community News",
        "badge": "💬 COMMUNITY NEWS",
        "emoji": "✨",
        "color": discord.Color.from_rgb(0, 229, 255),  # Electric Cyan
        "bar": "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    },
}

THEME_KEYS = list(THEMES.keys())


def is_staff(user_or_interaction: discord.Member | discord.User | discord.Interaction) -> bool:
    """Check if a user is the server Owner, an Administrator, or has the Admins role."""
    if isinstance(user_or_interaction, discord.Interaction):
        interaction = user_or_interaction
        if not interaction.guild:
            return False
        if interaction.user.id == interaction.guild.owner_id:
            return True
        if hasattr(interaction, "permissions") and interaction.permissions.administrator:
            return True
        user = interaction.user
    else:
        user = user_or_interaction

    if hasattr(user, "guild") and user.guild and user.id == user.guild.owner_id:
        return True
    if hasattr(user, "guild_permissions") and user.guild_permissions.administrator:
        return True
    if hasattr(user, "roles"):
        return any(r.id == ADMIN_ROLE_ID for r in user.roles)
    return False


def build_announcement_embed(
    title: str,
    body: str,
    category_key: str,
    author: discord.Member | discord.User,
    guild: discord.Guild,
    image_url: str | None = None,
    target_channel_id: int = SERVER_ANNOUNCEMENT_CHANNEL_ID,
) -> discord.Embed:
    """Build the high-end magazine layout Discord embed for official server announcements."""
    norm_key = category_key.upper().strip()
    theme = THEMES.get(norm_key, THEMES["UPDATE"])
    badge = theme["badge"]
    emoji = theme["emoji"]
    color = theme["color"]
    bar = theme["bar"]

    # Sanitize image url
    clean_image: str | None = None
    if image_url:
        cand = image_url.strip()
        if cand.startswith(("http://", "https://")) and (
            any(cand.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp", ".gif"])
            or "discordapp" in cand
            or "imgur.com" in cand
        ):
            clean_image = cand

    desc_content = f"`{bar}`\n\n{body}\n\n`{bar}`"

    embed = discord.Embed(
        title=f"{emoji} {title}",
        description=desc_content,
        color=color,
        timestamp=datetime.now(timezone.utc),
    )

    guild_icon = guild.icon.url if guild.icon else None
    embed.set_author(
        name=f"📢 GROWCOM OFFICIAL ANNOUNCEMENT • [ {badge} ]",
        icon_url=guild_icon,
    )

    now_ts = int(datetime.now(timezone.utc).timestamp())
    embed.add_field(name="📅 Date & Time", value=f"<t:{now_ts}:F>\n*(<t:{now_ts}:R>)*", inline=True)
    author_name = author.display_name if hasattr(author, "display_name") else str(author)
    embed.add_field(name="👤 Announced By", value=f"{author.mention}\n*{author_name}*", inline=True)
    embed.add_field(name="📌 Official Channel", value=f"<#{target_channel_id}>\n*Verified Notice*", inline=True)

    if clean_image:
        embed.set_image(url=clean_image)

    avatar_url = author.display_avatar.url if hasattr(author, "display_avatar") else None
    embed.set_footer(
        text=f"Growcom Network • Official Server Announcement",
        icon_url=avatar_url or guild_icon,
    )
    return embed


def build_studio_control_embed() -> discord.Embed:
    """Build the pinned announcement control panel embed inside #📢・announcement-desk."""
    embed = discord.Embed(
        title="📢 Growcom Official Announcement Studio",
        description=(
            "Welcome to the **Growcom Announcement Studio & Dispatch Pipeline**!\n"
            "Staff and Admins can compose, style, preview, and broadcast official announcements directly "
            f"to <#{SERVER_ANNOUNCEMENT_CHANNEL_ID}>.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "### 🛠️ How It Works:\n"
            "1. **Click `📝 Create Announcement`** below (or run `/announce`).\n"
            "2. **Fill out the form:**\n"
            "   • **Title:** Compelling headline for the announcement\n"
            "   • **Category / Theme:** `UPDATE`, `EVENT`, `GIVEAWAY`, `NOTICE`, `MAINTENANCE`, `COMMUNITY`\n"
            "   • **Content:** Multi-line text (full Markdown: **bold**, *italic*, bullet points, code blocks)\n"
            "   • **Banner Image:** Optional image link (`.png`, `.jpg`, `.gif`)\n"
            "   • **Ping / Mention:** `none`, `@everyone`, `@here`, or `member`\n"
            "3. **Review the Interactive Draft:**\n"
            "   • Inspect your live announcement preview.\n"
            "   • Click **`🎨 Switch Theme`** to instantly change theme colors.\n"
            "   • When satisfied, click **`🚀 Publish Announcement`** to broadcast!\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "🔒 *This studio channel is restricted to Growcom Staff & Admins only.*"
        ),
        color=discord.Color.from_rgb(0, 229, 255),
    )
    embed.set_footer(text=f"{FOOTER_TEXT} • Official Announcement Studio")
    return embed


class AnnouncementPreviewView(discord.ui.View):
    """Interactive draft review view before broadcasting to #🗣️・server-announcement."""

    def __init__(
        self,
        cog: AnnouncementManagerCog,
        author: discord.Member | discord.User,
        title: str,
        body: str,
        category_key: str,
        image_url: str | None,
        ping_mode: str,
    ) -> None:
        super().__init__(timeout=600)
        self.cog = cog
        self.author = author
        self.title = title
        self.body = body
        self.category_key = category_key.upper().strip()
        if self.category_key not in THEMES:
            self.category_key = "UPDATE"
        self.image_url = image_url
        self.ping_mode = ping_mode.lower().strip()
        self.published = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ Only the staff member who created this draft can control it.",
                ephemeral=True,
            )
            return False
        return True

    @discord.ui.button(label="Publish Announcement", style=discord.ButtonStyle.success, emoji="🚀", row=0)
    async def publish_button(self, interaction: discord.Interaction, _btn: discord.ui.Button) -> None:
        if self.published:
            await interaction.response.send_message("⚠️ This announcement has already been published!", ephemeral=True)
            return

        if not interaction.guild:
            await interaction.response.send_message("❌ Guild context missing.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        target_ch = interaction.guild.get_channel(SERVER_ANNOUNCEMENT_CHANNEL_ID)
        if not isinstance(target_ch, discord.TextChannel):
            try:
                target_ch = await self.cog.bot.fetch_channel(SERVER_ANNOUNCEMENT_CHANNEL_ID)  # type: ignore[assignment]
            except Exception:
                target_ch = None

        if not isinstance(target_ch, discord.TextChannel):
            await interaction.followup.send(
                f"❌ Could not find announcement channel `<#{SERVER_ANNOUNCEMENT_CHANNEL_ID}>`!",
                ephemeral=True,
            )
            return

        # Prepare mention content
        mention_str: str | None = None
        allowed_mentions = discord.AllowedMentions.none()
        if self.ping_mode == "@everyone":
            mention_str = "@everyone"
            allowed_mentions = discord.AllowedMentions(everyone=True)
        elif self.ping_mode == "@here":
            mention_str = "@here"
            allowed_mentions = discord.AllowedMentions(everyone=True)
        elif self.ping_mode in ["member", "@member", "members"]:
            mention_str = f"<@&{MEMBER_ROLE_ID}>"
            allowed_mentions = discord.AllowedMentions(roles=True)

        embed = build_announcement_embed(
            title=self.title,
            body=self.body,
            category_key=self.category_key,
            author=self.author,
            guild=interaction.guild,
            image_url=self.image_url,
            target_channel_id=target_ch.id,
        )

        try:
            pub_msg = await target_ch.send(
                content=mention_str,
                embed=embed,
                allowed_mentions=allowed_mentions,
            )
            self.published = True

            # Add auto-reactions for community engagement
            for emo in ["📢", "🔥", "🎉", "❤️"]:
                try:
                    await pub_msg.add_reaction(emo)
                except Exception:
                    pass

            # Disable all preview buttons
            for child in self.children:
                if isinstance(child, discord.ui.Button):
                    child.disabled = True

            theme_name = THEMES[self.category_key]["name"]
            now_ts = int(datetime.now(timezone.utc).timestamp())
            success_note = (
                f"✅ **Announcement Broadcasted Successfully!**\n\n"
                f"• **Channel:** {target_ch.mention}\n"
                f"• **Category:** `{theme_name}`\n"
                f"• **Mention:** `{self.ping_mode}`\n"
                f"• **Link:** [Click to View Message]({pub_msg.jump_url})\n"
                f"• **Published at:** <t:{now_ts}:F> by {interaction.user.mention}"
            )

            await interaction.edit_original_response(
                content=success_note,
                embed=embed,
                view=self,
            )
            await interaction.followup.send(
                f"🎉 Done! Your announcement is live in {target_ch.mention}: {pub_msg.jump_url}",
                ephemeral=True,
            )
        except Exception as exc:
            logger.error("Failed to publish announcement: %s", exc)
            await interaction.followup.send(f"❌ Failed to post announcement: {exc}", ephemeral=True)

    @discord.ui.button(label="Switch Theme", style=discord.ButtonStyle.primary, emoji="🎨", row=0)
    async def switch_theme_button(self, interaction: discord.Interaction, _btn: discord.ui.Button) -> None:
        if self.published:
            await interaction.response.send_message("⚠️ Already published.", ephemeral=True)
            return

        # Cycle to next theme
        curr_idx = THEME_KEYS.index(self.category_key) if self.category_key in THEME_KEYS else 0
        next_key = THEME_KEYS[(curr_idx + 1) % len(THEME_KEYS)]
        self.category_key = next_key

        if not interaction.guild:
            return

        embed = build_announcement_embed(
            title=self.title,
            body=self.body,
            category_key=self.category_key,
            author=self.author,
            guild=interaction.guild,
            image_url=self.image_url,
        )

        theme_info = THEMES[self.category_key]
        header = (
            f"📋 **ANNOUNCEMENT DRAFT PREVIEW**\n"
            f"• **Target:** <#{SERVER_ANNOUNCEMENT_CHANNEL_ID}>  •  **Theme:** `{theme_info['name']}` ({theme_info['emoji']})  •  **Mention:** `{self.ping_mode}`\n"
            f"*Review the preview below, click **Switch Theme** to cycle colors, or **Publish** when ready!*"
        )
        await interaction.response.edit_message(content=header, embed=embed, view=self)

    @discord.ui.button(label="Discard Draft", style=discord.ButtonStyle.danger, emoji="❌", row=0)
    async def discard_button(self, interaction: discord.Interaction, _btn: discord.ui.Button) -> None:
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        await interaction.response.edit_message(
            content="🗑️ **Announcement draft discarded.** No message was published.",
            embed=None,
            view=self,
        )


class AnnouncementFormModal(discord.ui.Modal, title="📢 Compose Server Announcement"):
    """Interactive pop-up modal for staff to compose an official announcement."""

    ann_title = discord.ui.TextInput(
        label="Announcement Title",
        placeholder="e.g. Server Update v2.5 • WinterFest Drop Event Launch",
        max_length=100,
        required=True,
    )
    ann_category = discord.ui.TextInput(
        label="Category / Theme",
        placeholder="UPDATE, EVENT, GIVEAWAY, NOTICE, MAINTENANCE, COMMUNITY",
        default="UPDATE",
        max_length=30,
        required=False,
    )
    ann_body = discord.ui.TextInput(
        label="Content (Markdown Supported)",
        style=discord.TextStyle.paragraph,
        placeholder="Write announcement details here... (Supports bold, bullet points, quotes, links)",
        max_length=3500,
        required=True,
    )
    ann_image = discord.ui.TextInput(
        label="Banner Image URL (Optional)",
        placeholder="https://.../banner.png or .gif (leave blank if none)",
        max_length=500,
        required=False,
    )
    ann_ping = discord.ui.TextInput(
        label="Ping / Mention (@everyone, @here, none)",
        placeholder="none / @everyone / @here / member",
        default="none",
        max_length=30,
        required=False,
    )

    def __init__(self, cog: AnnouncementManagerCog) -> None:
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            await interaction.response.send_message("❌ This command must be used in a server.", ephemeral=True)
            return

        title_val = self.ann_title.value.strip()
        cat_val = self.ann_category.value.strip().upper()
        if cat_val not in THEMES:
            cat_val = "UPDATE"
        body_val = self.ann_body.value.strip()
        image_val = self.ann_image.value.strip() or None
        ping_val = self.ann_ping.value.strip()

        embed = build_announcement_embed(
            title=title_val,
            body=body_val,
            category_key=cat_val,
            author=interaction.user,
            guild=interaction.guild,
            image_url=image_val,
        )

        theme_info = THEMES[cat_val]
        header = (
            f"📋 **ANNOUNCEMENT DRAFT PREVIEW**\n"
            f"• **Target:** <#{SERVER_ANNOUNCEMENT_CHANNEL_ID}>  •  **Theme:** `{theme_info['name']}` ({theme_info['emoji']})  •  **Mention:** `{ping_val}`\n"
            f"*Review the preview below, click **Switch Theme** to cycle colors, or **Publish** when ready!*"
        )

        view = AnnouncementPreviewView(
            cog=self.cog,
            author=interaction.user,
            title=title_val,
            body=body_val,
            category_key=cat_val,
            image_url=image_val,
            ping_mode=ping_val,
        )
        await interaction.response.send_message(content=header, embed=embed, view=view, ephemeral=True)


class AnnouncementStudioView(discord.ui.View):
    """Persistent control panel view pinned inside #📢・announcement-desk."""

    def __init__(self, cog: AnnouncementManagerCog | None = None) -> None:
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="Create Announcement",
        style=discord.ButtonStyle.primary,
        emoji="📝",
        custom_id="announcement:create",
        row=0,
    )
    async def create_button(self, interaction: discord.Interaction, _btn: discord.ui.Button) -> None:
        try:
            if not is_staff(interaction):
                await interaction.response.send_message(
                    "⛔ **Access Denied:** Only Growcom Staff & Admins can create official announcements.",
                    ephemeral=True,
                )
                return

            cog = self.cog or interaction.client.get_cog("Announcement Manager")
            if isinstance(cog, AnnouncementManagerCog):
                await interaction.response.send_modal(AnnouncementFormModal(cog))
            else:
                await interaction.response.send_message("❌ Announcement system cog not loaded.", ephemeral=True)
        except Exception as exc:
            logger.exception("Error in announcement create_button: %s", exc)
            if not interaction.response.is_done():
                await interaction.response.send_message(f"❌ Error opening announcement form: {exc}", ephemeral=True)

    @discord.ui.button(
        label="View Themes & Guide",
        style=discord.ButtonStyle.secondary,
        emoji="🎨",
        custom_id="announcement:templates",
        row=0,
    )
    async def templates_button(self, interaction: discord.Interaction, _btn: discord.ui.Button) -> None:
        try:
            guide_embed = discord.Embed(
                title="🎨 Growcom Announcement Themes & Markdown Guide",
                description=(
                    "Choose any of the official theme categories when filling in your announcement:\n\n"
                    "• **`UPDATE`** (`#00E676` Emerald): Bot & server feature launches, updates, bugfixes.\n"
                    "• **`EVENT`** (`#9C27B0` Purple): Community activities, drop parties, tournaments.\n"
                    "• **`GIVEAWAY`** (`#FFD700` Gold): World Lock, item, and role giveaways.\n"
                    "• **`NOTICE`** (`#FF1744` Red): Critical alerts, server policy changes, scammer alerts.\n"
                    "• **`MAINTENANCE`** (`#FF9100` Orange): Bot restarts, API downtime, schedule notices.\n"
                    "• **`COMMUNITY`** (`#00E5FF` Cyan): Member milestones, partnerships, general news.\n\n"
                    "### 📝 Markdown Tips:\n"
                    "• `### Headline` -> Bold section title\n"
                    "• `• Item` -> Clean bullet point\n"
                    "• `**Text**` -> Bold, `*Text*` -> Italics\n"
                    "• `> Quote` -> Highlighted quote block\n"
                    "• `<t:TIMESTAMP:R>` -> Dynamic countdown timestamp"
                ),
                color=discord.Color.from_rgb(0, 230, 118),
            )
            guide_embed.set_footer(text=f"{FOOTER_TEXT} • Formatting Reference")
            await interaction.response.send_message(embed=guide_embed, ephemeral=True)
        except Exception as exc:
            logger.exception("Error in templates_button: %s", exc)
            if not interaction.response.is_done():
                await interaction.response.send_message(f"❌ Error: {exc}", ephemeral=True)

    @discord.ui.button(
        label="Refresh Studio",
        style=discord.ButtonStyle.secondary,
        emoji="🔄",
        custom_id="announcement:refresh",
        row=0,
    )
    async def refresh_button(self, interaction: discord.Interaction, _btn: discord.ui.Button) -> None:
        try:
            if not is_staff(interaction):
                await interaction.response.send_message("⛔ Only Growcom Staff can refresh the studio panel.", ephemeral=True)
                return

            embed = build_studio_control_embed()
            await interaction.response.edit_message(embed=embed, view=self)
        except Exception as exc:
            logger.exception("Error in refresh_button: %s", exc)
            if not interaction.response.is_done():
                await interaction.response.send_message(f"❌ Error: {exc}", ephemeral=True)


class AnnouncementManagerCog(commands.Cog, name="Announcement Manager"):
    """Manages the official Growcom Announcement Studio, control panel, and dispatch pipeline."""

    def __init__(self, bot: EventBot) -> None:
        self.bot = bot
        self._initialized: bool = False

    async def cog_load(self) -> None:
        self.bot.add_view(AnnouncementStudioView(self))

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        if not self._initialized:
            self._initialized = True
            for guild in self.bot.guilds:
                await self.provision_announcement_studio(guild)

    async def provision_announcement_studio(self, guild: discord.Guild) -> None:
        """Ensure #📢・announcement-desk exists in 🛡️ Growcom Staff and has the pinned studio panel."""
        state = load_state()

        # Find 🛡️ Growcom Staff category
        staff_cat = guild.get_channel(STAFF_CATEGORY_ID)
        if not isinstance(staff_cat, discord.CategoryChannel):
            for cat in guild.categories:
                if "staff" in cat.name.lower():
                    staff_cat = cat
                    break

        if not isinstance(staff_cat, discord.CategoryChannel):
            logger.warning("Could not find Staff category for Announcement Studio.")
            return

        # Check existing channel from state
        ch_id = state.get("announcement_control_channel_id")
        ctrl_ch: discord.TextChannel | None = None
        if ch_id:
            found = guild.get_channel(int(ch_id))
            if isinstance(found, discord.TextChannel):
                ctrl_ch = found

        if not ctrl_ch:
            # Check by name in staff category
            for ch in staff_cat.text_channels:
                if "announcement" in ch.name.lower():
                    ctrl_ch = ch
                    break

        # Create channel if not found
        if not ctrl_ch:
            admin_role = guild.get_role(ADMIN_ROLE_ID)
            member_role = guild.get_role(MEMBER_ROLE_ID)
            bot_role = guild.get_role(BOT_ROLE_ID)

            overwrites: dict[discord.Role | discord.Member, discord.PermissionOverwrite] = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
            }
            if member_role:
                overwrites[member_role] = discord.PermissionOverwrite(view_channel=False)
            if admin_role:
                overwrites[admin_role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                )
            if bot_role:
                overwrites[bot_role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    embed_links=True,
                    manage_messages=True,
                    attach_files=True,
                )

            try:
                ctrl_ch = await guild.create_text_channel(
                    name=CONTROL_CHANNEL_NAME,
                    category=staff_cat,
                    topic="Growcom Staff Announcement Studio • Compose, preview, and dispatch announcements to #🗣️・server-announcement.",
                    overwrites=overwrites,
                    reason="Provision Growcom Announcement Studio channel for staff",
                )
                logger.info("Created Announcement Studio channel: #%s (%s)", ctrl_ch.name, ctrl_ch.id)
            except Exception as exc:
                logger.warning("Could not create #%s: %s", CONTROL_CHANNEL_NAME, exc)
                return

        state["announcement_control_channel_id"] = ctrl_ch.id
        state["announcement_channel_id"] = SERVER_ANNOUNCEMENT_CHANNEL_ID
        save_state(state)

        # Check or pin the Studio Control Panel
        msg_id = state.get("announcement_control_message_id")
        studio_embed = build_studio_control_embed()
        studio_view = AnnouncementStudioView(self)

        if msg_id:
            try:
                msg = await ctrl_ch.fetch_message(int(msg_id))
                await msg.edit(embed=studio_embed, view=studio_view)
                return
            except discord.NotFound:
                pass
            except Exception as exc:
                logger.warning("Could not edit studio control message %s: %s", msg_id, exc)

        try:
            new_msg = await ctrl_ch.send(embed=studio_embed, view=studio_view)
            try:
                await new_msg.pin(reason="Pin Growcom Announcement Studio Control Panel")
            except Exception:
                pass
            state["announcement_control_message_id"] = new_msg.id
            save_state(state)
            logger.info("Pinned Announcement Studio Panel (msg %s)", new_msg.id)
        except Exception as exc:
            logger.warning("Could not post Announcement Studio Panel: %s", exc)

    @app_commands.command(
        name="announce",
        description="Launch the Growcom Announcement Studio to draft and post an announcement.",
    )
    @app_commands.default_permissions(administrator=True)
    async def announce_command(self, interaction: discord.Interaction) -> None:
        """Slash command to trigger the Announcement form modal."""
        try:
            if not is_staff(interaction):
                await interaction.response.send_message(
                    "⛔ **Access Denied:** Only Growcom Staff & Admins can use `/announce`.",
                    ephemeral=True,
                )
                return

            await interaction.response.send_modal(AnnouncementFormModal(self))
        except Exception as exc:
            logger.exception("Error in /announce command: %s", exc)
            if not interaction.response.is_done():
                await interaction.response.send_message(f"❌ Error opening announcement form: {exc}", ephemeral=True)


async def setup(bot: EventBot) -> None:
    await bot.add_cog(AnnouncementManagerCog(bot))
