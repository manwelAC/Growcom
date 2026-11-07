"""
Growcom Join-to-Create Dynamic Voice Channels (src/cogs/temp_voice.py)
- Creates '➕ Join to Create VC' inside the '📞 Growtalks' category and removes old static VCs.
- Whenever a member joins '➕ Join to Create VC', automatically creates '🔊 {Name}'s Room',
  moves the member into it, and posts an interactive Room Control Panel (Rename, Limit, Lock, Unlock).
- Automatically deletes the temporary voice channel the moment everyone leaves!
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

GROWTALKS_CATEGORY_ID = 1567168952444915785
DEFAULT_MEMBER_ROLE_ID = 1568495447067332608
JTC_LOBBY_NAME = "➕ Join to Create VC"


def _get_temp_vc_owner(channel_id: int) -> int | None:
    state = load_state()
    active_map: dict[str, int] = state.get("active_temp_vcs", {})
    owner_id = active_map.get(str(channel_id))
    return int(owner_id) if owner_id else None


def _check_vc_owner(interaction: discord.Interaction) -> bool:
    if not interaction.channel:
        return False
    owner_id = _get_temp_vc_owner(interaction.channel.id)
    if owner_id and interaction.user.id == owner_id:
        return True
    return is_server_manager(interaction)


class RenameVCModal(discord.ui.Modal, title="Rename Your Voice Room ✏️"):
    new_name = discord.ui.TextInput(
        label="New Room Name",
        placeholder="e.g. BFG Farming Party, Chill Hangout, Trading VC...",
        required=True,
        min_length=2,
        max_length=40,
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if not isinstance(interaction.channel, discord.VoiceChannel):
            await interaction.response.send_message("❌ This can only be used inside a temporary voice room.", ephemeral=True)
            return

        clean = self.new_name.value.strip()
        formatted = clean if clean.startswith("🔊") else f"🔊 {clean}"
        try:
            await interaction.channel.edit(name=formatted, reason=f"Renamed by room owner {interaction.user}")
            await interaction.response.send_message(f"✅ Renamed your voice room to **{formatted}**!", ephemeral=True)
        except discord.HTTPException as exc:
            await interaction.response.send_message(
                f"⏳ Discord limits channel renames to twice every 10 minutes! ({exc})",
                ephemeral=True,
            )


class LimitVCModal(discord.ui.Modal, title="Set Voice Room User Limit 👥"):
    limit_input = discord.ui.TextInput(
        label="Max Players (0 for Unlimited, or 1 to 99)",
        placeholder="e.g. 5 (or 0 to remove limit)",
        required=True,
        min_length=1,
        max_length=2,
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if not isinstance(interaction.channel, discord.VoiceChannel):
            await interaction.response.send_message("❌ This can only be used inside a temporary voice room.", ephemeral=True)
            return

        raw = self.limit_input.value.strip()
        if not raw.isdigit():
            await interaction.response.send_message("❌ Please enter a number between `0` and `99`.", ephemeral=True)
            return

        limit_val = max(0, min(99, int(raw)))
        await interaction.channel.edit(user_limit=limit_val, reason=f"User limit set by {interaction.user}")
        label = "Unlimited (`0`)" if limit_val == 0 else f"`{limit_val}` players max"
        await interaction.response.send_message(f"✅ Set room capacity to **{label}**!", ephemeral=True)


class TempVCControlView(discord.ui.View):
    """Persistent Room Owner controls posted inside each temporary Voice Channel's text chat."""

    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Rename Room",
        emoji="✏️",
        style=discord.ButtonStyle.primary,
        custom_id="growcom:vc_rename",
    )
    async def rename_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not _check_vc_owner(interaction):
            await interaction.response.send_message("❌ Only the **Room Host** (or an Admin) can rename this VC!", ephemeral=True)
            return
        await interaction.response.send_modal(RenameVCModal())

    @discord.ui.button(
        label="User Limit",
        emoji="👥",
        style=discord.ButtonStyle.secondary,
        custom_id="growcom:vc_limit",
    )
    async def limit_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not _check_vc_owner(interaction):
            await interaction.response.send_message("❌ Only the **Room Host** (or an Admin) can change the user limit!", ephemeral=True)
            return
        await interaction.response.send_modal(LimitVCModal())

    @discord.ui.button(
        label="Lock Room",
        emoji="🔒",
        style=discord.ButtonStyle.danger,
        custom_id="growcom:vc_lock",
    )
    async def lock_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not _check_vc_owner(interaction) or not interaction.guild or not isinstance(interaction.channel, discord.VoiceChannel):
            await interaction.response.send_message("❌ Only the **Room Host** (or an Admin) can lock this VC!", ephemeral=True)
            return

        state = load_state()
        member_role = interaction.guild.get_role(int(state.get("member_role_id", DEFAULT_MEMBER_ROLE_ID)))
        if member_role:
            await interaction.channel.set_permissions(
                member_role,
                view_channel=True,
                connect=False,
                speak=True,
                reason=f"Room locked by host {interaction.user}",
            )
        await interaction.response.send_message(
            "🔒 **Room Locked!** Other members can no longer join your room.",
            ephemeral=True,
        )

    @discord.ui.button(
        label="Unlock Room",
        emoji="🔓",
        style=discord.ButtonStyle.success,
        custom_id="growcom:vc_unlock",
    )
    async def unlock_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not _check_vc_owner(interaction) or not interaction.guild or not isinstance(interaction.channel, discord.VoiceChannel):
            await interaction.response.send_message("❌ Only the **Room Host** (or an Admin) can unlock this VC!", ephemeral=True)
            return

        state = load_state()
        member_role = interaction.guild.get_role(int(state.get("member_role_id", DEFAULT_MEMBER_ROLE_ID)))
        if member_role:
            await interaction.channel.set_permissions(
                member_role,
                view_channel=True,
                connect=True,
                speak=True,
                reason=f"Room unlocked by host {interaction.user}",
            )
        await interaction.response.send_message(
            "🔓 **Room Unlocked!** Verified members can now join your room again.",
            ephemeral=True,
        )


class TempVoiceCog(commands.Cog):
    """Manages '➕ Join to Create VC' and auto-created/auto-deleted temporary voice rooms."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._provisioned_guilds: set[int] = set()

    async def cog_load(self) -> None:
        self.bot.add_view(TempVCControlView())

    async def provision_join_to_create(self, guild: discord.Guild) -> discord.VoiceChannel:
        state = load_state()
        everyone_role = guild.default_role
        bot_member = guild.me

        member_role_id = int(state.get("member_role_id", DEFAULT_MEMBER_ROLE_ID))
        member_role = guild.get_role(member_role_id)

        growtalks_cat: discord.CategoryChannel | None = guild.get_channel(GROWTALKS_CATEGORY_ID)  # type: ignore[assignment]
        if not isinstance(growtalks_cat, discord.CategoryChannel):
            for cat in guild.categories:
                if "growtalk" in cat.name.lower():
                    growtalks_cat = cat
                    break

        overwrites: dict[discord.Role | discord.Member, discord.PermissionOverwrite] = {
            everyone_role: discord.PermissionOverwrite(view_channel=False, connect=False),
        }
        if member_role:
            overwrites[member_role] = discord.PermissionOverwrite(
                view_channel=True,
                connect=True,
                speak=True,
            )
        if bot_member:
            overwrites[bot_member] = discord.PermissionOverwrite(
                view_channel=True,
                connect=True,
                move_members=True,
                manage_channels=True,
                manage_permissions=True,
            )

        # Locate or create '➕ Join to Create VC'
        lobby_vc: discord.VoiceChannel | None = None
        saved_lobby_id = state.get("jtc_lobby_vc_id")
        if saved_lobby_id:
            ch = guild.get_channel(int(saved_lobby_id))
            if isinstance(ch, discord.VoiceChannel):
                lobby_vc = ch

        if not lobby_vc:
            for vc in guild.voice_channels:
                if "join to create" in vc.name.lower():
                    lobby_vc = vc
                    break

        if not lobby_vc:
            lobby_vc = await guild.create_voice_channel(
                name=JTC_LOBBY_NAME,
                category=growtalks_cat,
                overwrites=overwrites,
                reason="Growcom Join-to-Create VC Lobby setup",
            )
        else:
            await lobby_vc.edit(
                category=growtalks_cat,
                overwrites=overwrites,
                reason="Sync Join-to-Create VC Lobby permissions",
            )

        state["jtc_lobby_vc_id"] = str(lobby_vc.id)
        if "active_temp_vcs" not in state:
            state["active_temp_vcs"] = {}

        # Remove old empty static growcom-vc-1..7 channels (or leftover empty temp VCs) inside 📞 Growtalks
        if growtalks_cat:
            for vc in list(growtalks_cat.voice_channels):
                if vc.id == lobby_vc.id:
                    continue
                if len(vc.members) == 0:
                    try:
                        await vc.delete(reason="Clean up old/empty VC in 📞 Growtalks for Join-to-Create system")
                        state["active_temp_vcs"].pop(str(vc.id), None)
                    except Exception as exc:
                        logger.warning("Could not delete empty VC %s: %s", vc.name, exc)

        save_state(state)
        self._provisioned_guilds.add(guild.id)
        return lobby_vc

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        for guild in self.bot.guilds:
            if guild.id in self._provisioned_guilds:
                continue
            if guild.me and guild.me.guild_permissions.administrator:
                try:
                    lobby_vc = await self.provision_join_to_create(guild)
                    logger.info("Configured '%s' (%s) in %s", lobby_vc.name, lobby_vc.id, guild.name)
                except Exception as exc:
                    logger.warning("Could not configure Join-to-Create VC in %s: %s", guild.name, exc)

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        if member.bot:
            return

        state = load_state()
        lobby_id = int(state.get("jtc_lobby_vc_id", 0))
        active_temp_vcs: dict[str, int] = state.get("active_temp_vcs", {})

        # 1. Did the member join '➕ Join to Create VC'?
        if after.channel and after.channel.id == lobby_id:
            guild = member.guild
            category = after.channel.category

            everyone_role = guild.default_role
            member_role = guild.get_role(int(state.get("member_role_id", DEFAULT_MEMBER_ROLE_ID)))

            overwrites: dict[discord.Role | discord.Member, discord.PermissionOverwrite] = {
                everyone_role: discord.PermissionOverwrite(view_channel=False, connect=False),
                member: discord.PermissionOverwrite(
                    view_channel=True,
                    connect=True,
                    speak=True,
                    stream=True,
                    move_members=True,
                ),
            }
            if member_role:
                overwrites[member_role] = discord.PermissionOverwrite(
                    view_channel=True,
                    connect=True,
                    speak=True,
                    stream=True,
                )
            if guild.me:
                overwrites[guild.me] = discord.PermissionOverwrite(
                    view_channel=True,
                    connect=True,
                    move_members=True,
                    manage_channels=True,
                    manage_permissions=True,
                )

            room_name = f"🔊 {member.display_name}'s Room"
            try:
                temp_vc = await guild.create_voice_channel(
                    name=room_name[:95],
                    category=category,
                    overwrites=overwrites,
                    reason=f"Join-to-Create temporary room for {member}",
                )
                active_temp_vcs[str(temp_vc.id)] = member.id
                state["active_temp_vcs"] = active_temp_vcs
                save_state(state)

                await member.move_to(temp_vc, reason="Move member to their newly created temporary VC")

                # Send Room Control Panel inside the voice channel's text chat!
                ctrl_embed = discord.Embed(
                    title=f"🎙️ {member.display_name}'s Voice Room Controls",
                    description=(
                        f"Welcome to your personal voice room, {member.mention}!\n\n"
                        f"- **✏️ Rename Room:** Change the name of your VC\n"
                        f"- **👥 User Limit:** Set a max player limit (`0` = Unlimited)\n"
                        f"- **🔒 Lock / 🔓 Unlock:** Make your room private or public\n\n"
                        f"*🗑️ This room will automatically delete itself as soon as everyone leaves!*"
                    ),
                    color=0x2ECC71,
                    timestamp=datetime.now(EVENT_TZ),
                )
                ctrl_embed.set_footer(text=FOOTER_TEXT)
                await temp_vc.send(content=f"👑 **Room Host:** {member.mention}", embed=ctrl_embed, view=TempVCControlView())
            except Exception as exc:
                logger.warning("Failed creating/moving temp VC for %s: %s", member, exc)

        # 2. Did someone leave a temporary VC, leaving it empty?
        if before.channel and before.channel.id != lobby_id:
            ch_id_str = str(before.channel.id)
            is_tracked_temp = ch_id_str in active_temp_vcs
            is_growtalks_temp = (
                before.channel.category_id == GROWTALKS_CATEGORY_ID
                and "join to create" not in before.channel.name.lower()
            )
            if (is_tracked_temp or is_growtalks_temp) and len(before.channel.members) == 0:
                try:
                    await before.channel.delete(reason="Temporary voice room is now empty")
                    if ch_id_str in active_temp_vcs:
                        active_temp_vcs.pop(ch_id_str, None)
                        state["active_temp_vcs"] = active_temp_vcs
                        save_state(state)
                except Exception as exc:
                    logger.warning("Failed deleting empty temp VC %s: %s", before.channel.id, exc)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TempVoiceCog(bot))
