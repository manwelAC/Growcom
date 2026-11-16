"""
Category 13: Level & EXP Grind Calculator (cogs/xp_calculator.py)

Deterministic, zero-RNG calculator for Growtopia level grinding.
Calculates exact remaining XP to Level 125 (or custom target) using Growtopia's
official leveling formula, the exact number of blocks needed to break, 200-item inventory
stacks, pickaxe hits, breaking hours, and milestone comparisons (Level 50 Mini-You,
Level 100 Golden Name, Level 125 Max Cap).

Commands:
- /xp <current_level> <block> [target_level=125] [current_xp=0]
- /set_xp_channel [channel] (Admin: lock /xp tool to dedicated channel)
- /setup_xp_channel (Admin: auto-provision #✨xp-calculator under '🛠️ Growcom Tools')
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import discord
from discord import app_commands
from discord.ext import commands

from utils.helpers import (
    FOOTER_TEXT,
    is_server_manager,
    load_state,
    save_state,
)

if TYPE_CHECKING:
    from bot import EventBot

logger = logging.getLogger("growcom.xp_calculator")

TOOLS_CATEGORY_ID = 1567213972283719811
DEFAULT_MEMBER_ROLE_ID = 1568495447067332608
MAX_LEVEL_CAP = 125


def xp_for_level_transition(lvl: int) -> int:
    """XP required to transition from level L to level L + 1."""
    return 50 * (lvl**2 + 2)


def total_xp_between_levels(curr: int, target: int) -> int:
    """Cumulative XP required to progress from curr to target level."""
    if target <= curr:
        return 0
    return sum(xp_for_level_transition(lvl) for lvl in range(curr, target))


def generate_progress_bar(pct: float, length: int = 14) -> str:
    """Generate a clean Unicode progress bar."""
    clamped = max(0.0, min(100.0, pct))
    filled = int(round((clamped / 100.0) * length))
    empty = length - filled
    return f"[{'█' * filled}{'░' * empty}] {clamped:.1f}%"


def compute_xp_metrics(
    current_level: int,
    target_level: int,
    current_xp: int,
    item_data: dict[str, Any],
) -> dict[str, Any]:
    """Compute exact, zero-RNG block breaking and XP metrics."""
    target_level = max(current_level + 1, min(MAX_LEVEL_CAP, target_level))
    total_xp_required = total_xp_between_levels(current_level, target_level)
    remaining_xp = max(0, total_xp_required - current_xp)

    rarity = max(1, int(item_data.get("rarity", 1)))
    fist_hits = int(item_data.get("hardness_hits", 0))
    pickaxe_hits = max(1, (fist_hits * 3 + 3) // 4) if fist_hits > 0 else 0

    xp_per_block = min(500, max(1, 1 + (rarity // 5)))
    blocks_needed = (remaining_xp + xp_per_block - 1) // xp_per_block if remaining_xp > 0 else 0
    stacks_200 = (blocks_needed + 199) // 200 if blocks_needed > 0 else 0
    total_pickaxe_hits = blocks_needed * pickaxe_hits
    total_fist_hits = blocks_needed * fist_hits

    # Estimate pure breaking hours at 5 punches/sec in continuous breaking / BFG
    break_hours_pickaxe = (total_pickaxe_hits / (5 * 3600)) if total_pickaxe_hits > 0 else 0.0

    # Overall progress toward Level 125 cap
    total_1_to_125 = total_xp_between_levels(1, MAX_LEVEL_CAP)
    xp_achieved = max(0, total_xp_between_levels(1, current_level) + current_xp)
    overall_progress_pct = min(100.0, (xp_achieved / total_1_to_125) * 100) if total_1_to_125 > 0 else 0.0

    # Intermediate milestones
    milestones: list[dict[str, Any]] = []
    for ms_lvl, label in [(50, "Mini-You"), (100, "Golden Name"), (125, "Max Cap")]:
        if current_level < ms_lvl and target_level != ms_lvl:
            ms_xp = max(0, total_xp_between_levels(current_level, ms_lvl) - current_xp)
            ms_blocks = (ms_xp + xp_per_block - 1) // xp_per_block if ms_xp > 0 else 0
            ms_stacks = (ms_blocks + 199) // 200 if ms_blocks > 0 else 0
            milestones.append({
                "level": ms_lvl,
                "label": label,
                "xp": ms_xp,
                "blocks": ms_blocks,
                "stacks": ms_stacks,
            })

    return {
        "current_level": current_level,
        "target_level": target_level,
        "current_xp": current_xp,
        "total_xp_required": total_xp_required,
        "remaining_xp": remaining_xp,
        "item_name": item_data.get("name", "Unknown Block"),
        "item_id": item_data.get("id", 0),
        "rarity": rarity,
        "xp_per_block": xp_per_block,
        "blocks_needed": blocks_needed,
        "stacks_200": stacks_200,
        "fist_hits": fist_hits,
        "pickaxe_hits": pickaxe_hits,
        "total_pickaxe_hits": total_pickaxe_hits,
        "total_fist_hits": total_fist_hits,
        "break_hours_pickaxe": break_hours_pickaxe,
        "overall_progress_pct": overall_progress_pct,
        "milestones": milestones,
    }


def build_xp_embed(metrics: dict[str, Any]) -> discord.Embed:
    """Build the Argon-style level grind summary embed."""
    curr_lvl = metrics["current_level"]
    target_lvl = metrics["target_level"]
    item_name = metrics["item_name"]
    rarity = metrics["rarity"]
    xp_per_block = metrics["xp_per_block"]
    prog_bar = generate_progress_bar(metrics["overall_progress_pct"])

    target_badge = "👑 Max Level Cap" if target_lvl == 125 else f"Level {target_lvl}"

    # Build ASCII monospace box
    table_lines = [
        "┌────────────────────────────────────────────────────────────┐",
        f"│ ✨ Remaining EXP    : {metrics['remaining_xp']:>14,d} XP                    │",
        f"│ 📦 Blocks to Break  : {metrics['blocks_needed']:>14,d} blocks                │",
        f"│ 🎒 Stacks (200)     : {metrics['stacks_200']:>14,d} stacks                │",
        f"│ ⛏️ Pickaxe Hits     : {metrics['total_pickaxe_hits']:>14,d} hits ({metrics['pickaxe_hits']} hits/block)   │",
        f"│ ⏱️ Est. Punch Time  : {metrics['break_hours_pickaxe']:>14.1f} hours (~5 hits/sec)    │",
        "└────────────────────────────────────────────────────────────┘",
    ]
    box_str = "\n".join(table_lines)

    embed = discord.Embed(
        title="⚡ Growcom Level & EXP Grind Calculator",
        color=0x00E676,  # Argon Emerald Mint
    )

    embed.description = (
        f"🎯 **Target Goal:** **Level {target_lvl}** `({target_badge})`\n"
        f"📊 **Current Progress:** **Level {curr_lvl}** • `{prog_bar}`\n"
        f"🧱 **Target Block:** **{item_name}** `(Rarity {rarity} • {xp_per_block} XP/block)`\n\n"
        f"```text\n{box_str}\n```"
    )

    if metrics["milestones"]:
        ms_text = []
        for ms in metrics["milestones"]:
            ms_text.append(
                f"• **To Level {ms['level']} ({ms['label']}):** "
                f"`{ms['blocks']:,d}` blocks `({ms['stacks']:,d} stacks)` • `{ms['xp']:,d} XP`"
            )
        embed.add_field(
            name="🏆 Milestone Checkpoints",
            value="\n".join(ms_text),
            inline=False,
        )

    embed.set_footer(text=f"{FOOTER_TEXT} • 100% Deterministic Engine")
    return embed


class XPCalculatorView(discord.ui.View):
    """Interactive Argon control view with milestone jump buttons."""

    def __init__(
        self,
        cog: XPCalculatorCog,
        author_id: int,
        current_level: int,
        target_level: int,
        current_xp: int,
        item_data: dict[str, Any],
    ) -> None:
        super().__init__(timeout=180.0)
        self.cog = cog
        self.author_id = author_id
        self.current_level = current_level
        self.target_level = target_level
        self.current_xp = current_xp
        self.item_data = item_data
        self._sync_buttons()

    def _sync_buttons(self) -> None:
        self.clear_items()
        for lvl, label, emoji in [
            (50, "Level 50", "🎯"),
            (100, "Level 100", "🌟"),
            (125, "Level 125", "👑"),
        ]:
            if self.current_level < lvl:
                btn = discord.ui.Button(
                    label=label,
                    emoji=emoji,
                    style=discord.ButtonStyle.primary if self.target_level == lvl else discord.ButtonStyle.secondary,
                    custom_id=f"xp_milestone:{lvl}",
                    disabled=(self.target_level == lvl),
                )
                btn.callback = self._make_milestone_callback(lvl)
                self.add_item(btn)

    def _make_milestone_callback(self, new_target: int):
        async def callback(interaction: discord.Interaction) -> None:
            if interaction.user.id != self.author_id:
                await interaction.response.send_message(
                    "❌ This calculator session belongs to another user. Use **`/xp`** to calculate your own!",
                    ephemeral=True,
                )
                return

            self.target_level = new_target
            self._sync_buttons()
            metrics = compute_xp_metrics(
                self.current_level,
                self.target_level,
                self.current_xp,
                self.item_data,
            )
            embed = build_xp_embed(metrics)
            await interaction.response.edit_message(embed=embed, view=self)

        return callback


class XPCalculatorCog(commands.Cog, name="Level & EXP Calculator"):
    def __init__(self, bot: EventBot) -> None:
        self.bot = bot
        self._provisioned_guilds: set[int] = set()

    async def block_autocomplete(
        self,
        _interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        try:
            items = await self.bot.api.search_items(current or "Laser Grid", limit=15, farmable_only=False)
            choices: list[app_commands.Choice[str]] = []
            for it in items:
                rarity = int(it.get("rarity", 0) or 0)
                xp_per_block = min(500, max(1, 1 + (rarity // 5)))
                name = it.get("name", "")
                if not name or rarity <= 0:
                    continue
                label = f"{name} (Rarity {rarity} • {xp_per_block} XP/block)"[:100]
                choices.append(app_commands.Choice(name=label, value=name))
            return choices
        except Exception:
            return []

    async def provision_xp_channel(self, guild: discord.Guild, force_repost: bool = False) -> discord.TextChannel:
        state = load_state()
        everyone_role = guild.default_role
        bot_member = guild.me

        member_role_id = int(state.get("member_role_id", DEFAULT_MEMBER_ROLE_ID))
        member_role = guild.get_role(member_role_id)

        tools_cat: discord.CategoryChannel | None = guild.get_channel(TOOLS_CATEGORY_ID)  # type: ignore[assignment]
        if not isinstance(tools_cat, discord.CategoryChannel):
            for cat in guild.categories:
                if "tools" in cat.name.lower():
                    tools_cat = cat
                    break

        ch_id = state.get("xp_channel_id")
        existing_ch = guild.get_channel(int(ch_id)) if ch_id else None

        if not existing_ch:
            for ch in guild.text_channels:
                if ch.name in ("✨xp-calculator", "xp-calculator", "level-calculator"):
                    existing_ch = ch
                    break

        overwrites = {
            everyone_role: discord.PermissionOverwrite(view_channel=False),
            bot_member: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                embed_links=True,
                attach_files=True,
                manage_messages=True,
            ),
        }
        if member_role:
            overwrites[member_role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
            )

        if not existing_ch:
            existing_ch = await guild.create_text_channel(
                name="✨xp-calculator",
                category=tools_cat,
                overwrites=overwrites,
                topic="Growcom Level & EXP Grind Calculator — Exact block requirements to Level 125",
                reason="Auto-provisioned Growcom Tools channel",
            )
            force_repost = True
        else:
            if existing_ch.category_id != (tools_cat.id if tools_cat else None):
                try:
                    await existing_ch.edit(category=tools_cat)
                except Exception:
                    pass

        state["xp_channel_id"] = existing_ch.id
        save_state(state)

        if force_repost:
            guide_embed = discord.Embed(
                title="✨ Growcom Level & EXP Grind Calculator",
                description=(
                    "Welcome to the **Level & EXP Calculator**!\n\n"
                    "Calculate the **100% exact** remaining XP and number of blocks you need to break "
                    "to reach **Level 125** (or any intermediate milestone like Level 50 or 100).\n\n"
                    "**Available Commands:**\n"
                    "• **`/xp current_level:62 block:Laser Grid`** — Calculate blocks to Level 125\n"
                    "• **`/xp current_level:40 block:Chandelier target_level:50`** — Custom target level\n"
                    "• **`/xp current_level:85 block:Pepper Tree current_xp:50000`** — Include current level XP progress\n\n"
                    "*(Powered by Growtopia's official $50 \\times (L^2 + 2)$ formula and items.dat v27)*"
                ),
                color=0x00E676,
            )
            guide_embed.set_footer(text=FOOTER_TEXT)
            await existing_ch.send(embed=guide_embed)

        return existing_ch

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        for guild in self.bot.guilds:
            if guild.id in self._provisioned_guilds:
                continue
            if guild.me and guild.me.guild_permissions.manage_channels:
                try:
                    ch = await self.provision_xp_channel(guild, force_repost=False)
                    logger.info("Configured %s (%s) under category: %s", ch.name, ch.id, ch.category)
                    self._provisioned_guilds.add(guild.id)
                except Exception as exc:
                    logger.warning("Could not auto-provision xp channel in %s: %s", guild.name, exc)

    @app_commands.command(
        name="setup_xp_channel",
        description="Admin: Create or verify #✨xp-calculator under category: Growcom Tools",
    )
    async def setup_xp_channel_cmd(self, interaction: discord.Interaction) -> None:
        if not is_server_manager(interaction) or not interaction.guild:
            await interaction.response.send_message("❌ Admin permission required.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        ch = await self.provision_xp_channel(interaction.guild, force_repost=True)
        cat_name = ch.category.name if ch.category else "None"
        await interaction.followup.send(
            f"✅ Configured **{ch.mention}** under category **`{cat_name}`**!\n"
            f"The **`/xp`** tool is ready to use.",
            ephemeral=True,
        )

    @app_commands.command(
        name="set_xp_channel",
        description="Restrict the /xp tool exclusively to a designated channel",
    )
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(channel="Dedicated channel for /xp lookups (defaults to current channel)")
    async def set_xp_channel_cmd(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel | None = None,
    ) -> None:
        if not is_server_manager(interaction):
            await interaction.response.send_message("❌ Only server admins can use `/set_xp_channel`.", ephemeral=True)
            return

        await interaction.response.defer()
        target_channel = channel or interaction.channel
        if not isinstance(target_channel, discord.TextChannel):
            await interaction.followup.send("❌ Please select a standard text channel.", ephemeral=True)
            return

        state = load_state()
        state["xp_channel_id"] = target_channel.id
        save_state(state)

        guide_embed = discord.Embed(
            title="✨ Growcom Level & EXP Grind Calculator",
            description=(
                "Use **`/xp`** in this channel to calculate exact block requirements to Level 125!\n\n"
                "• **100% Exact Math:** Based on Growtopia's $50 \\times (L^2 + 2)$ formula\n"
                "• **Block Requirements:** Calculates exact blocks, 200-item stacks, and pickaxe punches\n"
                "• **Milestones:** Quick progress comparison to Level 50, 100, and 125"
            ),
            color=0x00E676,
        )
        guide_embed.set_footer(text=FOOTER_TEXT)
        await target_channel.send(embed=guide_embed)

        await interaction.followup.send(
            f"✅ Locked **`/xp`** exclusively to {target_channel.mention}!",
            ephemeral=True,
        )

    @app_commands.command(
        name="xp",
        description="Calculate exact XP and blocks needed to reach Level 125 (or custom target)!",
    )
    @app_commands.describe(
        current_level="Your current Growtopia level (1–124)",
        block="The block you plan to break (e.g. Laser Grid, Chandelier, Pepper Tree, Dirt)",
        target_level="Target level to reach (default: 125 - Max Cap)",
        current_xp="Optional XP points already earned in your current level (default: 0)",
    )
    @app_commands.autocomplete(block=block_autocomplete)
    async def xp_command(
        self,
        interaction: discord.Interaction,
        current_level: int,
        block: str,
        target_level: int = MAX_LEVEL_CAP,
        current_xp: int = 0,
    ) -> None:
        state = load_state()
        allowed_channel_id = state.get("xp_channel_id")
        if allowed_channel_id and int(interaction.channel_id or 0) != int(allowed_channel_id):
            await interaction.response.send_message(
                f"❌ The **`/xp`** calculator can only be used inside <#{allowed_channel_id}>!",
                ephemeral=True,
            )
            return

        if current_level < 1 or current_level >= MAX_LEVEL_CAP:
            await interaction.response.send_message(
                f"❌ Invalid `current_level`! Please enter a level between **1** and **{MAX_LEVEL_CAP - 1}**.",
                ephemeral=True,
            )
            return

        if target_level <= current_level:
            await interaction.response.send_message(
                f"❌ `target_level` ({target_level}) must be higher than your `current_level` ({current_level})!",
                ephemeral=True,
            )
            return

        if target_level > MAX_LEVEL_CAP:
            await interaction.response.send_message(
                f"❌ Max level in Growtopia is **{MAX_LEVEL_CAP}**! Please enter a target level $\\le {MAX_LEVEL_CAP}$.",
                ephemeral=True,
            )
            return

        if current_xp < 0:
            current_xp = 0

        await interaction.response.defer()

        # Query item data from Central Data API
        item_data = await self.bot.api.get_item(block)
        if not item_data:
            # Fallback search if exact name didn't hit
            results = await self.bot.api.search_items(block, limit=1)
            if results:
                item_data = results[0]

        if not item_data:
            await interaction.followup.send(
                f"❌ Could not find block **`{block}`** in items.dat! Please check the name or use the autocomplete.",
                ephemeral=True,
            )
            return

        metrics = compute_xp_metrics(
            current_level=current_level,
            target_level=target_level,
            current_xp=current_xp,
            item_data=item_data,
        )

        embed = build_xp_embed(metrics)
        view = XPCalculatorView(
            cog=self,
            author_id=interaction.user.id,
            current_level=current_level,
            target_level=target_level,
            current_xp=current_xp,
            item_data=item_data,
        )

        await interaction.followup.send(embed=embed, view=view)


async def setup(bot: EventBot) -> None:
    await bot.add_cog(XPCalculatorCog(bot))
