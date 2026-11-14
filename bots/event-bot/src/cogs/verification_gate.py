"""
Growcom Member Verification Gate (src/cogs/verification_gate.py)
- Creates #✅verify inside the 'Welcome!' category.
- Hides all server categories/channels from unverified (@everyone) users so they only see
  the Welcome! category (#👋welcome and #✅verify).
- Grants the 'Member' role (unlocking all community, tool, and business channels) as soon as
  a newcomer reacts with ✅ on the verification message OR clicks the Verify button.
"""

from __future__ import annotations

from datetime import datetime

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

WELCOME_CATEGORY_ID = 1567199096148590682
DEFAULT_MEMBER_ROLE_ID = 1568495447067332608
ANNOUNCEMENTS_CATEGORY_ID = 1567193192053481562
STAFF_CATEGORY_ID = 1568494521036046448
DQ_FEED_CHANNEL_ID = 1567206278697062440

READ_ONLY_CHANNEL_SLUGS = (
    "trading-info",
    "scammer-alert",
    "tool-guide",
    "total-rating",
    "undermaintenance",
    "daily-announcements",
    "new-items",
    "locke-location",
    "daily-challenges",
    "ingame-announcements",
)


def _find_member_role(guild: discord.Guild) -> discord.Role | None:
    state = load_state()
    role_id = int(state.get("member_role_id", DEFAULT_MEMBER_ROLE_ID))
    role = guild.get_role(role_id)
    if role:
        return role
    for r in guild.roles:
        if r.name.strip().lower() == "member":
            return r
    return None


class VerifyMemberView(discord.ui.View):
    """Persistent verification button alongside the ✅ reaction."""

    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Verify & Unlock Growcom",
        emoji="✅",
        style=discord.ButtonStyle.success,
        custom_id="growcom:verify_member",
    )
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not interaction.guild:
            return

        member_role = _find_member_role(interaction.guild)
        if not member_role:
            await interaction.response.send_message(
                "⚠️ Could not find the **Member** role! Please ask an Admin to check the server roles.",
                ephemeral=True,
            )
            return

        if isinstance(interaction.user, discord.Member) and member_role in interaction.user.roles:
            await interaction.response.send_message(
                f"✅ You are already verified with the {member_role.mention} role! All Growcom channels are unlocked for you.",
                ephemeral=True,
            )
            return

        try:
            await interaction.client.http.add_role(
                interaction.guild.id,
                interaction.user.id,
                member_role.id,
                reason="Growcom Verification Gate (Button)",
            )
            await interaction.response.send_message(
                f"🎉 **Verification Complete!** You now have the {member_role.mention} role and full access to all **Growcom** channels!",
                ephemeral=True,
            )
        except Exception as exc:
            logger.warning("Failed granting Member role via button to %s: %s", interaction.user.id, exc)
            await interaction.response.send_message(
                "❌ Could not assign the role automatically. Please contact an Admin.",
                ephemeral=True,
            )


class VerificationGateCog(commands.Cog):
    """Manages #✅verify reaction/button verification and locks unverified users out of main channels."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._configured_guilds: set[int] = set()

    async def cog_load(self) -> None:
        self.bot.add_view(VerifyMemberView())

    async def provision_verification_gate(self, guild: discord.Guild) -> dict[str, str]:
        """
        1. Locates the 'Member' role and 'Welcome!' category.
        2. Creates '#✅verify' under 'Welcome!' (visible to @everyone, read-only).
        3. Posts the official verification embed + ✅ reaction + Verify button.
        4. Configures permissions across all other categories/channels so @everyone cannot see
           them until they obtain the 'Member' role!
        """
        state = load_state()
        everyone_role = guild.default_role
        bot_member = guild.me

        member_role = _find_member_role(guild)
        if not member_role:
            member_role = await guild.create_role(
                name="Member",
                color=discord.Color.from_rgb(46, 204, 113),
                hoist=True,
                reason="Growcom Verified Member Role",
            )
        state["member_role_id"] = str(member_role.id)

        # 1. Locate 'Welcome!' category
        welcome_cat: discord.CategoryChannel | None = guild.get_channel(WELCOME_CATEGORY_ID)  # type: ignore[assignment]
        if not isinstance(welcome_cat, discord.CategoryChannel):
            for cat in guild.categories:
                if "welcome" in cat.name.lower():
                    welcome_cat = cat
                    break

        # Make sure 'Welcome!' category is visible to @everyone
        if welcome_cat:
            await welcome_cat.set_permissions(
                everyone_role,
                view_channel=True,
                send_messages=False,
                read_message_history=True,
                reason="Growcom Welcome category visible to unverified users",
            )

        # 2. Create or locate #✅verify inside 'Welcome!'
        verify_ch: discord.TextChannel | None = None
        existing_verify_id = state.get("verify_channel_id")
        if existing_verify_id:
            ch = guild.get_channel(int(existing_verify_id))
            if isinstance(ch, discord.TextChannel):
                verify_ch = ch

        if not verify_ch:
            for ch in guild.text_channels:
                if "verify" in ch.name.lower():
                    verify_ch = ch
                    break

        verify_overwrites: dict[discord.Role | discord.Member, discord.PermissionOverwrite] = {
            everyone_role: discord.PermissionOverwrite(
                view_channel=True,
                read_message_history=True,
                send_messages=False,
                add_reactions=False,
            ),
            member_role: discord.PermissionOverwrite(
                view_channel=True,
                read_message_history=True,
                send_messages=False,
                add_reactions=False,
            ),
        }
        if bot_member:
            verify_overwrites[bot_member] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                embed_links=True,
                add_reactions=True,
                manage_messages=True,
                read_message_history=True,
            )

        if not verify_ch:
            verify_ch = await guild.create_text_channel(
                name="✅verify",
                category=welcome_cat,
                topic="React with ✅ below (or click the Verify button) to receive the Member role and unlock all Growcom channels!",
                overwrites=verify_overwrites,
                reason="Growcom Verification Gate setup",
            )
        else:
            await verify_ch.edit(
                category=welcome_cat,
                overwrites=verify_overwrites,
                reason="Sync #✅verify permissions",
            )

        state["verify_channel_id"] = str(verify_ch.id)

        # 3. Post or verify the Verification Gate message inside #✅verify
        verify_msg: discord.Message | None = None
        verify_msg_id = state.get("verify_message_id")
        if verify_msg_id:
            try:
                verify_msg = await verify_ch.fetch_message(int(verify_msg_id))
            except Exception:
                verify_msg = None

        if not verify_msg:
            async for msg in verify_ch.history(limit=10):
                if msg.author.id == ( self.bot.user.id if self.bot.user else 0 ) and msg.embeds:
                    verify_msg = msg
                    break

        verify_embed = discord.Embed(
            title="🛡️ Welcome to Growcom — Member Verification",
            description=(
                "Welcome to the official **Growcom** community & Growtopia marketplace!\n\n"
                "To protect our server from bots and scammers, all channels are hidden until you verify.\n\n"
                "### 📜 Community Rules\n"
                "1. **Be Respectful:** No hate speech or harassment.\n"
                "2. **Safe Trading Only:** Follow all guidelines in `#📜trading-info` and report scammers with `/report_scammer`.\n"
                "3. **Use Designated Channels:** Keep tool commands (`/harvest`, `/item`, `/recipe`, `/mass`, etc.) in their matching `#🛠️Growcom Tools` channels.\n\n"
                "### ✅ How to Unlock the Server\n"
                "👉 **Click the `✅` reaction below** (or press the **`✅ Verify & Unlock Growcom`** button) to automatically receive the "
                f"{member_role.mention} role and unlock all channels!"
            ),
            color=0x2ECC71,
            timestamp=datetime.now(EVENT_TZ),
        )
        verify_embed.set_footer(text=FOOTER_TEXT)

        if not verify_msg:
            verify_msg = await verify_ch.send(embed=verify_embed, view=VerifyMemberView())
            await verify_msg.add_reaction("✅")
        else:
            await verify_msg.edit(embed=verify_embed, view=VerifyMemberView())
            await verify_msg.add_reaction("✅")

        state["verify_message_id"] = str(verify_msg.id)
        save_state(state)

        # 4. Lock all non-Welcome categories & channels so @everyone cannot see them,
        #    while granting view_channel=True to the 'Member' role!
        locked_count = 0
        for category in guild.categories:
            if welcome_cat and category.id == welcome_cat.id:
                continue
            if category.id == STAFF_CATEGORY_ID or "staff" in category.name.lower():
                # Staff category stays hidden from both @everyone and Member
                await category.set_permissions(everyone_role, view_channel=False)
                await category.set_permissions(member_role, view_channel=False)
                continue

            is_announcement_cat = (
                category.id == ANNOUNCEMENTS_CATEGORY_ID or "announcement" in category.name.lower()
            )
            await category.set_permissions(
                everyone_role,
                view_channel=False,
                send_messages=False if is_announcement_cat else None,
                reason="Hide category from unverified users",
            )
            await category.set_permissions(
                member_role,
                view_channel=True,
                send_messages=False if is_announcement_cat else True,
                read_message_history=True,
                connect=True,
                speak=True,
                reason="Unlock category for verified Member role",
            )
            locked_count += 1

        # Also update individual channels so channel-specific overwrites don't leak to @everyone
        for channel in guild.channels:
            if isinstance(channel, discord.CategoryChannel):
                continue
            if welcome_cat and channel.category_id == welcome_cat.id:
                continue
            if channel.category_id == STAFF_CATEGORY_ID or "scammer-review" in channel.name.lower():
                await channel.set_permissions(everyone_role, view_channel=False)
                await channel.set_permissions(member_role, view_channel=False)
                continue
            if channel.id == DQ_FEED_CHANNEL_ID or channel.name.lower() == "dq-feed":
                await channel.set_permissions(everyone_role, view_channel=False)
                await channel.set_permissions(member_role, view_channel=False)
                continue

            ch_name_lower = channel.name.lower()
            is_read_only = (
                channel.category_id == ANNOUNCEMENTS_CATEGORY_ID
                or any(slug in ch_name_lower for slug in READ_ONLY_CHANNEL_SLUGS)
            )

            await channel.set_permissions(
                everyone_role,
                view_channel=False,
                send_messages=False if is_read_only else None,
                reason="Hide channel from unverified @everyone",
            )
            if isinstance(channel, discord.VoiceChannel):
                await channel.set_permissions(
                    member_role,
                    view_channel=True,
                    connect=True,
                    speak=True,
                    reason="Allow verified Member role in voice channel",
                )
            else:
                await channel.set_permissions(
                    member_role,
                    view_channel=True,
                    read_message_history=True,
                    send_messages=False if is_read_only else True,
                    add_reactions=True,
                    reason="Allow verified Member role in text channel",
                )

        self._configured_guilds.add(guild.id)
        return {
            "verify_channel": verify_ch.mention,
            "member_role": member_role.mention,
            "locked_categories": str(locked_count),
        }

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        for guild in self.bot.guilds:
            if guild.id in self._configured_guilds:
                continue
            if guild.me and guild.me.guild_permissions.administrator:
                try:
                    info = await self.provision_verification_gate(guild)
                    logger.info("Configured Verification Gate in %s: %s", guild.name, info)
                except Exception as exc:
                    logger.warning("Failed configuring Verification Gate in %s: %s", guild.name, exc)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        """Grant the Member role immediately when a user reacts with ✅ in #✅verify."""
        if not payload.guild_id or (self.bot.user and payload.user_id == self.bot.user.id):
            return

        state = load_state()
        verify_channel_id = state.get("verify_channel_id")
        if not verify_channel_id or int(payload.channel_id) != int(verify_channel_id):
            return

        emoji_str = str(payload.emoji)
        if emoji_str not in {"✅", "☑️", "✔️"}:
            return

        guild = self.bot.get_guild(payload.guild_id)
        member_role_id = int(state.get("member_role_id", DEFAULT_MEMBER_ROLE_ID))
        if guild:
            role = _find_member_role(guild)
            if role:
                member_role_id = role.id

        try:
            await self.bot.http.add_role(
                payload.guild_id,
                payload.user_id,
                member_role_id,
                reason="Verified via ✅ reaction in #✅verify",
            )
            logger.info("Granted Member role (%s) to user %s via ✅ reaction", member_role_id, payload.user_id)
        except Exception as exc:
            logger.warning("Could not grant Member role to %s on reaction: %s", payload.user_id, exc)

    @app_commands.command(
        name="setup_verification",
        description="Admin: Set up #✅verify under Welcome! and lock all other channels to the Member role.",
    )
    async def setup_verification_cmd(self, interaction: discord.Interaction) -> None:
        if not is_server_manager(interaction) or not interaction.guild:
            await interaction.response.send_message(
                "❌ Only **Server Administrators** or the **Server Owner** can run `/setup_verification`!",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        info = await self.provision_verification_gate(interaction.guild)
        await interaction.followup.send(
            f"✅ **Verification Gate Active!**\n"
            f"- **Verify Channel:** {info['verify_channel']}\n"
            f"- **Verified Role:** {info['member_role']}\n"
            f"- **Protected Categories:** `{info['locked_categories']}` categories hidden from unverified users!",
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(VerificationGateCog(bot))
