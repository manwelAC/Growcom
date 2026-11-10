"""
Category 12: World Render & 403 Bypass Tool (cogs/world_render.py)
- /render <world_or_url> (Fetches world render directly from S3, bypassing 403 Forbidden)
- /set_render_channel (Admin channel lock)
- /setup_render_channel (Admin auto-provisioner under '🛠️ Growcom Tools' category)
- Auto-listener for broken growtopiagame.com/worlds/ links in chat
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

import discord
from discord import app_commands
from discord.ext import commands
import httpx

from utils.helpers import (
    FOOTER_TEXT,
    is_server_manager,
    load_state,
    save_state,
)

if TYPE_CHECKING:
    from bot import EventBot

logger = logging.getLogger("growcom.world_render")

S3_BASE_URL = "https://s3.amazonaws.com/world.growtopiagame.com"
TOOLS_CATEGORY_ID = 1567213972283719811
DEFAULT_MEMBER_ROLE_ID = 1568495447067332608

WORLD_LINK_REGEX = re.compile(
    r"https?://(?:www\.)?growtopiagame\.com/worlds/([A-Za-z0-9_-]+)(?:\.png)?",
    re.IGNORECASE,
)


def extract_world_name(raw: str) -> str | None:
    """Extract clean uppercase world name from raw text, chat string, or URL."""
    cleaned = raw.strip()
    match = WORLD_LINK_REGEX.search(cleaned)
    if match:
        return match.group(1).upper()

    s3_match = re.search(r"world\.growtopiagame\.com/([A-Za-z0-9_-]+)(?:\.png)?", cleaned, re.IGNORECASE)
    if s3_match:
        return s3_match.group(1).upper()

    parsed = re.sub(r"[^A-Za-z0-9_-]", "", cleaned)
    return parsed.upper() if parsed else None


def format_bytes(num_bytes: int | None) -> str:
    """Format bytes into human-readable string (KB, MB)."""
    if num_bytes is None or num_bytes <= 0:
        return "Unknown size"
    kb = num_bytes / 1024.0
    if kb < 1024.0:
        return f"{kb:.1f} KB"
    mb = kb / 1024.0
    return f"{mb:.2f} MB"


class WorldRenderView(discord.ui.View):
    """Interactive view providing a direct browser link to the full-resolution S3 render."""

    def __init__(self, s3_url: str) -> None:
        super().__init__(timeout=None)
        self.add_item(
            discord.ui.Button(
                label="🌐 Open Full Resolution",
                url=s3_url,
                style=discord.ButtonStyle.link,
            )
        )


class WorldRenderCog(commands.Cog, name="World Render"):
    def __init__(self, bot: EventBot) -> None:
        self.bot = bot
        self._provisioned_guilds: set[int] = set()

    async def check_world_render(self, world_name: str) -> dict[str, Any]:
        """
        Check if the world render exists on S3.
        First tries the Central Data API client; falls back to direct async HTTP HEAD request.
        """
        try:
            api_res = await self.bot.api.get_world_render(world_name)
            if api_res:
                return api_res
        except Exception:
            pass

        s3_key = f"{world_name.lower()}.png"
        s3_url = f"{S3_BASE_URL}/{s3_key}"

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.head(s3_url)
                if resp.status_code == 200:
                    length = resp.headers.get("content-length")
                    return {
                        "world_name": world_name,
                        "s3_url": s3_url,
                        "exists": True,
                        "content_length": int(length) if length and length.isdigit() else None,
                        "last_modified": resp.headers.get("last-modified"),
                        "etag": resp.headers.get("etag", "").strip('"'),
                    }
                return {
                    "world_name": world_name,
                    "s3_url": s3_url,
                    "exists": False,
                    "status_code": resp.status_code,
                }
            except Exception as exc:
                return {
                    "world_name": world_name,
                    "s3_url": s3_url,
                    "exists": False,
                    "error": str(exc),
                }

    async def provision_render_channel(
        self,
        guild: discord.Guild,
        force_repost: bool = False,
    ) -> discord.TextChannel:
        """
        Provision or verify the #🌍world-render channel specifically under the
        '🛠️ Growcom Tools' category.
        """
        state = load_state()
        everyone_role = guild.default_role
        bot_member = guild.me

        member_role_id_raw = state.get("member_role_id", DEFAULT_MEMBER_ROLE_ID)
        member_role_id = int(member_role_id_raw) if str(member_role_id_raw).isdigit() else DEFAULT_MEMBER_ROLE_ID
        member_role = guild.get_role(member_role_id)

        # 1. Locate the '🛠️ Growcom Tools' category
        tools_cat: discord.CategoryChannel | None = guild.get_channel(TOOLS_CATEGORY_ID)  # type: ignore[assignment]
        if not isinstance(tools_cat, discord.CategoryChannel):
            for cat in guild.categories:
                if "growcom tools" in cat.name.lower() or "tools" in cat.name.lower():
                    tools_cat = cat
                    break

        if not tools_cat and bot_member and bot_member.guild_permissions.manage_channels:
            try:
                tools_cat = await guild.create_category(
                    name="🛠️ Growcom Tools",
                    reason="Create Growcom Tools category for tool channels",
                )
            except Exception as exc:
                logger.warning("Could not create '🛠️ Growcom Tools' category: %s", exc)

        # 2. Configure permissions for the channel
        overwrites: dict[discord.Role | discord.Member, discord.PermissionOverwrite] = {
            everyone_role: discord.PermissionOverwrite(
                view_channel=True,
                read_message_history=True,
                send_messages=True,
                use_application_commands=True,
                embed_links=True,
                attach_files=True,
            ),
        }
        if member_role:
            overwrites[member_role] = discord.PermissionOverwrite(
                view_channel=True,
                read_message_history=True,
                send_messages=True,
                use_application_commands=True,
                embed_links=True,
                attach_files=True,
            )
        if bot_member:
            overwrites[bot_member] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                embed_links=True,
                attach_files=True,
                read_message_history=True,
                manage_messages=True,
            )

        # 3. Locate or create #🌍world-render
        render_ch: discord.TextChannel | None = None
        saved_id = state.get("render_channel_id")
        if saved_id:
            ch = guild.get_channel(int(saved_id))
            if isinstance(ch, discord.TextChannel):
                render_ch = ch

        if not render_ch and tools_cat:
            for ch in tools_cat.text_channels:
                if "render" in ch.name.lower():
                    render_ch = ch
                    break

        if not render_ch:
            for ch in guild.text_channels:
                if "world-render" in ch.name.lower() or "render" in ch.name.lower():
                    render_ch = ch
                    break

        created_new = False
        topic_text = (
            "🌍 Official Growtopia World Render & 403 Bypass Tool — "
            "Use /render <world_or_url> to view high-resolution world maps without 403 Forbidden!"
        )

        if not render_ch:
            render_ch = await guild.create_text_channel(
                name="🌍world-render",
                category=tools_cat,
                topic=topic_text,
                overwrites=overwrites,
                reason="Create #🌍world-render under category: Growcom Tools",
            )
            created_new = True
        else:
            if render_ch.category != tools_cat and tools_cat is not None:
                await render_ch.edit(
                    category=tools_cat,
                    topic=topic_text,
                    overwrites=overwrites,
                    reason="Move #🌍world-render under category: Growcom Tools",
                )

        # 4. Post pinned instruction embed if freshly created or force requested
        if created_new or force_repost:
            intro_embed = discord.Embed(
                title="🌍 Growcom World Render & 403 Bypass Tool",
                description=(
                    "Welcome to **#🌍world-render**! When players type `/renderworld` in Growtopia, "
                    "the official website links (`growtopiagame.com/worlds/...`) often return a "
                    "**403 Forbidden** error because direct web access is restricted.\n\n"
                    "This tool **bypasses the 403 block** by pulling the raw world render directly "
                    "from official Amazon S3 storage, embedding the full map image right here in Discord!\n\n"
                    "**Available Commands:**\n"
                    "• **`/render world_or_url:<name_or_link>`** — View the high-res render for any world.\n"
                    "• **Auto-Link Bypass** — Paste any `growtopiagame.com/worlds/...` link in chat, and "
                    "the bot will automatically reply with the bypassed image!"
                ),
                color=0x16A085,
            )
            intro_embed.add_field(
                name="💡 How to Render In-Game First",
                value=(
                    "1. Visit your world in Growtopia.\n"
                    "2. Type **`/renderworld`** in the in-game chat.\n"
                    "3. Wait 15–30 seconds for the game servers to render the map.\n"
                    "4. Come back here and run **`/render <world_name>`** to view your fresh map!"
                ),
                inline=False,
            )
            intro_embed.set_footer(text=FOOTER_TEXT)
            msg = await render_ch.send(embed=intro_embed)
            try:
                await msg.pin(reason="Pin World Render introduction & guide")
            except Exception:
                pass

        state["render_channel_id"] = render_ch.id
        save_state(state)
        self._provisioned_guilds.add(guild.id)
        return render_ch

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Automatically ensure #🌍world-render exists under '🛠️ Growcom Tools' on bot startup."""
        for guild in self.bot.guilds:
            if guild.id in self._provisioned_guilds:
                continue
            if guild.me and guild.me.guild_permissions.manage_channels:
                try:
                    ch = await self.provision_render_channel(guild, force_repost=False)
                    logger.info("Configured %s (%s) under category: %s", ch.name, ch.id, ch.category)
                except Exception as exc:
                    logger.warning("Could not auto-provision world render channel in %s: %s", guild.name, exc)

    @app_commands.command(
        name="setup_render_channel",
        description="Admin: Create or verify #🌍world-render under category: Growcom Tools",
    )
    async def setup_render_channel_cmd(self, interaction: discord.Interaction) -> None:
        if not is_server_manager(interaction) or not interaction.guild:
            await interaction.response.send_message("❌ Admin permission required.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        ch = await self.provision_render_channel(interaction.guild, force_repost=True)
        cat_name = ch.category.name if ch.category else "None"
        await interaction.followup.send(
            f"✅ Configured **{ch.mention}** under category **`{cat_name}`**!\n"
            f"The **`/render`** tool is ready to use.",
            ephemeral=True,
        )

    @app_commands.command(
        name="set_render_channel",
        description="Restrict the /render tool exclusively to a designated channel",
    )
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(channel="Dedicated channel for /render lookups (defaults to current channel)")
    async def set_render_channel_cmd(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel | None = None,
    ) -> None:
        if not is_server_manager(interaction):
            await interaction.response.send_message("❌ Only server admins can use `/set_render_channel`.", ephemeral=True)
            return

        await interaction.response.defer()
        target_channel = channel or interaction.channel
        if not isinstance(target_channel, discord.TextChannel):
            await interaction.followup.send("❌ Please select a standard text channel.", ephemeral=True)
            return

        state = load_state()
        state["render_channel_id"] = target_channel.id
        save_state(state)

        embed = discord.Embed(
            title="🌍 Growcom World Render Channel",
            description=(
                "Use **`/render`** in this channel to look up and display high-resolution Growtopia world maps!\n\n"
                "• Bypasses the official **403 Forbidden** error\n"
                "• Supports world names (e.g. `FRIENDSY`, `START`) and full URLs\n"
                "• Displays direct full-resolution image embeds"
            ),
            color=0x16A085,
        )
        embed.set_footer(text=FOOTER_TEXT)
        await target_channel.send(embed=embed)

        await interaction.followup.send(
            f"✅ Locked **`/render`** exclusively to {target_channel.mention}!",
            ephemeral=True,
        )

    @app_commands.command(
        name="render",
        description="View any Growtopia world render with automatic 403 Forbidden bypass!",
    )
    @app_commands.describe(
        world_or_url="World name (e.g. FRIENDSY, START) or official growtopiagame.com render URL",
    )
    async def render_command(self, interaction: discord.Interaction, world_or_url: str) -> None:
        state = load_state()
        allowed_channel_id = state.get("render_channel_id")
        if allowed_channel_id and int(interaction.channel_id or 0) != int(allowed_channel_id):
            await interaction.response.send_message(
                f"❌ The **`/render`** tool can only be used inside <#{allowed_channel_id}>!",
                ephemeral=True,
            )
            return

        world_name = extract_world_name(world_or_url)
        if not world_name:
            await interaction.response.send_message(
                "❌ Please provide a valid world name (e.g. `FRIENDSY`) or render URL.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()
        data = await self.check_world_render(world_name)

        if not data.get("exists"):
            not_found_embed = discord.Embed(
                title=f"❌ World Not Rendered Yet: {world_name}",
                description=(
                    f"No active render found on Amazon S3 for world **`{world_name}`**.\n\n"
                    "**How to render it in Growtopia:**\n"
                    f"1. Enter the world **`{world_name}`** in-game.\n"
                    "2. Type **`/renderworld`** in the in-game chat.\n"
                    "3. Wait 15–30 seconds for the servers to generate the map.\n"
                    f"4. Come back here and run **`/render world_or_url:{world_name}`** again!"
                ),
                color=discord.Color.red(),
            )
            not_found_embed.set_footer(text=f"{FOOTER_TEXT} • 403 Bypass Engine")
            await interaction.followup.send(embed=not_found_embed)
            return

        s3_url = data["s3_url"]
        content_length = data.get("content_length")
        last_modified = data.get("last_modified") or "Unknown"

        embed = discord.Embed(
            title=f"🌍 World Render: {world_name}",
            description=(
                f"⚡ **403 Forbidden Bypassed!** High-resolution render loaded directly from Amazon S3.\n\n"
                f"🔗 **Direct S3 Link:** [Open Image in Browser]({s3_url})"
            ),
            color=0x16A085,
        )
        embed.set_image(url=s3_url)
        embed.add_field(name="📁 World Name", value=f"`{world_name}`", inline=True)
        embed.add_field(name="📦 Image Size", value=format_bytes(content_length), inline=True)
        embed.add_field(name="🕒 Last Rendered", value=str(last_modified), inline=False)
        embed.add_field(
            name="💡 In-Game Refresh",
            value=f"Want an updated render? Go to **`{world_name}`** in-game and type **`/renderworld`**!",
            inline=False,
        )
        embed.set_footer(text=f"{FOOTER_TEXT} • Tool 12/12")

        view = WorldRenderView(s3_url)
        await interaction.followup.send(embed=embed, view=view)

    @commands.Cog.listener("on_message")
    async def on_render_link_posted(self, message: discord.Message) -> None:
        """
        Auto-listener: When a player posts a broken growtopiagame.com/worlds/... link
        in chat, auto-fetch the S3 image and reply with the working preview.
        """
        if message.author.bot or not message.content:
            return

        match = WORLD_LINK_REGEX.search(message.content)
        if not match:
            return

        world_name = match.group(1).upper()
        data = await self.check_world_render(world_name)
        if not data.get("exists"):
            return

        s3_url = data["s3_url"]
        embed = discord.Embed(
            title=f"🌍 403 Bypassed: World Render for {world_name}",
            description=(
                f"Growtopia's direct web links are blocked by a 403 Forbidden error.\n"
                f"Here is the working full-resolution render from Amazon S3!\n\n"
                f"🔗 [Direct S3 Link]({s3_url})"
            ),
            color=0x16A085,
        )
        embed.set_image(url=s3_url)
        embed.set_footer(text=f"{FOOTER_TEXT} • Auto-Bypass")

        view = WorldRenderView(s3_url)
        try:
            await message.reply(embed=embed, view=view, mention_author=False)
        except Exception as exc:
            logger.warning("Could not reply with bypassed render embed: %s", exc)


async def setup(bot: EventBot) -> None:
    await bot.add_cog(WorldRenderCog(bot))
