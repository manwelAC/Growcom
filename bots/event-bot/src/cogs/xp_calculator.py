"""
Category 13: Level & EXP Grind Calculator (cogs/xp_calculator.py)

Deterministic, zero-RNG calculator for Growtopia level grinding.
Calculates exact remaining XP to Level 125 (or custom target) using Growtopia's
official leveling formula, the exact number of blocks needed to break, 200-item inventory
stacks, pickaxe hits, breaking hours, and milestone comparisons (Level 50 Mini-You,
Level 100 Golden Name, Level 125 Max Cap).

Supports:
- Exact in-level progress deduction (e.g. 45000, 45k, 50%)
- Responsive native Discord layout that never wraps or breaks on mobile/desktop
- Interactive milestone buttons (Level 50, Level 100, Level 125)
- Interactive 'Set XP Progress' modal for on-the-fly adjustment

Commands:
- /xp <current_level> <block> [target_level=125] [current_xp="0"]
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


def parse_current_xp(raw: str | int | None, current_level: int) -> int:
    """
    Parse a player's current XP progress in their current level.
    Supports:
    - Raw numbers: '45000' or '45,000'
    - Shorthand: '45k' or '1.2m'
    - Percentages: '50%' (resolves to 50% of the current level's bar)
    - None / empty: defaults to 0
    """
    if raw is None:
        return 0
    if isinstance(raw, (int, float)):
        val = int(raw)
    else:
        text = str(raw).strip().lower().replace(",", "").replace(" ", "")
        if not text or text in ("0", "none"):
            return 0
        if text.endswith("%"):
            try:
                pct = min(99.9, max(0.0, float(text[:-1])))
                lvl_xp = xp_for_level_transition(current_level)
                return int((pct / 100.0) * lvl_xp)
            except ValueError:
                return 0
        if text.endswith("k"):
            try:
                val = int(float(text[:-1]) * 1_000)
            except ValueError:
                return 0
        elif text.endswith("m"):
            try:
                val = int(float(text[:-1]) * 1_000_000)
            except ValueError:
                return 0
        else:
            try:
                val = int(text)
            except ValueError:
                return 0

    max_possible = xp_for_level_transition(current_level) - 1
    return max(0, min(max_possible, val))


def generate_progress_bar(pct: float, length: int = 12) -> str:
    """Generate a clean Unicode progress bar."""
    clamped = max(0.0, min(100.0, pct))
    filled = int(round((clamped / 100.0) * length))
    empty = length - filled
    return f"[{'█' * filled}{'░' * empty}]"


def resolve_item_mechanics(item_data: dict[str, Any]) -> dict[str, Any]:
    """
    Resolve item mechanics, distinguishing standard block breaking from
    Bountiful mature root harvesting and fixing items.dat placeholder artifacts.
    """
    name = str(item_data.get("name", "Unknown Block")).strip()
    raw_rarity = int(item_data.get("rarity", 1) or 1)
    fist_hits = int(item_data.get("hardness_hits", 0) or 0)
    name_lower = name.lower()

    # Check for Pineapple Mature Roots
    if "pineapple" in name_lower and "root" in name_lower:
        xp_per_unit = 6
        fist_hits = 3
        pickaxe_hits = 2
        clean_name = name.replace(" Seed", "").strip()
        if "cutting" in name_lower:
            clean_name = "Mature Pineapple Roots"
        return {
            "display_name": clean_name,
            "is_root": True,
            "unit_plural": "roots",
            "unit_singular": "root",
            "action_title": "🍍 Mature Roots to Harvest",
            "action_header": "Harvest Goal",
            "yield_label": "+6 XP / mature root",
            "yield_sub": "Super Pineapple Harvest",
            "xp_per_unit": xp_per_unit,
            "rarity_display": "Event Root",
            "fist_hits": fist_hits,
            "pickaxe_hits": pickaxe_hits,
        }

    # Check for Bountiful Mature Roots or Root Cuttings
    if ("bountiful" in name_lower or "root" in name_lower) and (
        "mature root" in name_lower or "root cutting" in name_lower or "roots" in name_lower
    ):
        xp_per_unit = 80
        fist_hits = 3
        pickaxe_hits = 2
        clean_name = name.replace(" Seed", "").strip()
        if "root cutting" in name_lower:
            clean_name = clean_name.replace("Root Cutting", "Mature Roots").strip()
        elif clean_name.endswith("Roots") and not clean_name.endswith("Mature Roots"):
            clean_name = clean_name[:-5] + "Mature Roots"
        return {
            "display_name": clean_name,
            "is_root": True,
            "unit_plural": "roots",
            "unit_singular": "root",
            "action_title": "🌾 Mature Roots to Harvest",
            "action_header": "Harvest Goal",
            "yield_label": "+80 XP / mature root",
            "yield_sub": "Level 4/5 Mature Root Harvest",
            "xp_per_unit": xp_per_unit,
            "rarity_display": "Bountiful Root",
            "fist_hits": fist_hits,
            "pickaxe_hits": pickaxe_hits,
        }

    # Standard block break
    if raw_rarity >= 999:
        rarity = 100
        rarity_display = "Special (Capped)"
    else:
        rarity = max(1, raw_rarity)
        rarity_display = f"Rarity {rarity}"

    pickaxe_hits = max(1, (fist_hits * 3 + 3) // 4) if fist_hits > 0 else 1
    xp_per_unit = min(500, max(1, 1 + (rarity // 5)))

    return {
        "display_name": name,
        "is_root": False,
        "unit_plural": "blocks",
        "unit_singular": "block",
        "action_title": "📦 Blocks to Break",
        "action_header": "Target Block",
        "yield_label": f"+{xp_per_unit} XP / block",
        "yield_sub": f"Rarity {rarity}",
        "xp_per_unit": xp_per_unit,
        "rarity_display": rarity_display,
        "fist_hits": fist_hits,
        "pickaxe_hits": pickaxe_hits,
    }


def compute_xp_metrics(
    current_level: int,
    target_level: int,
    current_xp: int,
    item_data: dict[str, Any],
) -> dict[str, Any]:
    """Compute exact, zero-RNG block breaking or root harvesting metrics."""
    target_level = max(current_level + 1, min(MAX_LEVEL_CAP, target_level))
    total_xp_required = total_xp_between_levels(current_level, target_level)
    remaining_xp = max(0, total_xp_required - current_xp)

    mech = resolve_item_mechanics(item_data)
    xp_per_unit = mech["xp_per_unit"]
    pickaxe_hits = mech["pickaxe_hits"]
    fist_hits = mech["fist_hits"]

    units_needed = (remaining_xp + xp_per_unit - 1) // xp_per_unit if remaining_xp > 0 else 0
    stacks_200 = (units_needed + 199) // 200 if units_needed > 0 else 0
    total_pickaxe_hits = units_needed * pickaxe_hits
    total_fist_hits = units_needed * fist_hits

    # Estimate action hours at ~5 hits/sec in continuous breaking/harvesting
    break_hours_pickaxe = (total_pickaxe_hits / (5 * 3600)) if total_pickaxe_hits > 0 else 0.0

    # Overall progress toward Level 125 cap
    total_1_to_125 = total_xp_between_levels(1, MAX_LEVEL_CAP)
    xp_achieved = max(0, total_xp_between_levels(1, current_level) + current_xp)
    overall_progress_pct = min(100.0, (xp_achieved / total_1_to_125) * 100) if total_1_to_125 > 0 else 0.0

    # Level progress (progress in current level)
    curr_level_needed = xp_for_level_transition(current_level)
    curr_level_pct = min(100.0, (current_xp / curr_level_needed) * 100) if curr_level_needed > 0 else 0.0

    # Intermediate milestones
    milestones: list[dict[str, Any]] = []
    for ms_lvl, label in [(50, "Mini-You"), (100, "Golden Name"), (125, "Max Cap")]:
        if current_level < ms_lvl and target_level != ms_lvl:
            ms_xp = max(0, total_xp_between_levels(current_level, ms_lvl) - current_xp)
            ms_units = (ms_xp + xp_per_unit - 1) // xp_per_unit if ms_xp > 0 else 0
            ms_stacks = (ms_units + 199) // 200 if ms_units > 0 else 0
            milestones.append({
                "level": ms_lvl,
                "label": label,
                "xp": ms_xp,
                "units": ms_units,
                "stacks": ms_stacks,
            })

    return {
        "current_level": current_level,
        "target_level": target_level,
        "current_xp": current_xp,
        "curr_level_needed": curr_level_needed,
        "curr_level_pct": curr_level_pct,
        "total_xp_required": total_xp_required,
        "remaining_xp": remaining_xp,
        "item_name": mech["display_name"],
        "item_id": item_data.get("id", 0),
        "is_root": mech["is_root"],
        "unit_plural": mech["unit_plural"],
        "unit_singular": mech["unit_singular"],
        "action_title": mech["action_title"],
        "action_header": mech["action_header"],
        "yield_label": mech["yield_label"],
        "yield_sub": mech["yield_sub"],
        "rarity_display": mech["rarity_display"],
        "xp_per_unit": xp_per_unit,
        "units_needed": units_needed,
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
    """
    Build a sleek, responsive Argon-style level grind summary embed.
    Uses native Discord fields to guarantee 100% responsive rendering with
    zero broken borders or line-wrapping on any screen or device.
    """
    curr_lvl = metrics["current_level"]
    target_lvl = metrics["target_level"]
    item_name = metrics["item_name"]
    xp_per_unit = metrics["xp_per_unit"]
    unit_plural = metrics["unit_plural"]
    unit_singular = metrics["unit_singular"]
    prog_bar = generate_progress_bar(metrics["overall_progress_pct"])

    target_badge = "👑 Max Level Cap" if target_lvl == MAX_LEVEL_CAP else f"Level {target_lvl}"

    embed = discord.Embed(
        title="⚡ Growcom Level & EXP Grind Calculator",
        color=0x00E676,  # Argon Emerald Mint
    )

    # Top Overview Section
    desc_lines = [
        f"🎯 **Target Goal:** **Level {target_lvl}** `({target_badge})`",
        f"🧱 **{metrics['action_header']}:** **{item_name}** • `{metrics['rarity_display']}` (`+{xp_per_unit} XP/{unit_singular}`)",
    ]

    if metrics["current_xp"] > 0:
        desc_lines.append(
            f"📊 **Progress:** **Level {curr_lvl}** `(+{metrics['current_xp']:,} XP)` • `{metrics['overall_progress_pct']:.1f}%`"
        )
    else:
        desc_lines.append(
            f"📊 **Progress:** **Level {curr_lvl}** • `{metrics['overall_progress_pct']:.1f}%`"
        )

    desc_lines.append(f"`{prog_bar}`")
    desc_lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    embed.description = "\n".join(desc_lines)

    # Core Stat Cards (Inline fields render cleanly across 3 columns on desktop, 1 on mobile)
    embed.add_field(
        name="✨ Remaining EXP",
        value=f"**`{metrics['remaining_xp']:,} XP`**",
        inline=True,
    )
    embed.add_field(
        name=metrics["action_title"],
        value=f"**`{metrics['units_needed']:,}`** {unit_plural}\n*({metrics['stacks_200']:,} stacks)*",
        inline=True,
    )
    embed.add_field(
        name="⛏️ Pickaxe Hits" if not metrics["is_root"] else "⛏️ Tool / Punch Hits",
        value=f"**`{metrics['total_pickaxe_hits']:,}`** hits\n*({metrics['pickaxe_hits']} hits/{unit_singular})*",
        inline=True,
    )
    embed.add_field(
        name="⏱️ Est. Punch Time" if not metrics["is_root"] else "⏱️ Est. Harvest Time",
        value=f"**`~{metrics['break_hours_pickaxe']:.1f} hours`**\n*(at ~5 hits/sec)*",
        inline=True,
    )
    embed.add_field(
        name="⚡ Yield / Rate",
        value=f"**`{metrics['yield_label']}`**\n*({metrics['yield_sub']})*",
        inline=True,
    )

    if metrics["current_xp"] > 0:
        embed.add_field(
            name="🌟 Current Level Progress",
            value=f"**`{metrics['current_xp']:,} / {metrics['curr_level_needed']:,} XP`**\n*({metrics['curr_level_pct']:.1f}% to Lvl {curr_lvl + 1})*",
            inline=True,
        )
    else:
        embed.add_field(
            name="🎒 Inventory Stacks",
            value=f"**`{metrics['stacks_200']:,}`** full stacks\n*(200 items each)*",
            inline=True,
        )

    # Milestone Checkpoints
    if metrics["milestones"]:
        ms_lines = []
        for ms in metrics["milestones"]:
            ms_lines.append(
                f"• **Level {ms['level']} ({ms['label']}):** "
                f"**`{ms['units']:,}`** {unit_plural} `({ms['stacks']:,} stacks)` • `{ms['xp']:,} XP left`"
            )
        embed.add_field(
            name="🏆 Milestone Checkpoints",
            value="\n".join(ms_lines),
            inline=False,
        )

    embed.set_footer(text=f"{FOOTER_TEXT} • 100% Deterministic Engine")
    return embed


class SetCurrentXPModal(discord.ui.Modal):
    """Interactive modal allowing the user to update their in-level XP progress on the fly."""

    def __init__(self, view: XPCalculatorView) -> None:
        super().__init__(title=f"Set Level {view.current_level} Progress")
        self.view_ref = view
        lvl_needed = xp_for_level_transition(view.current_level)
        self.xp_input = discord.ui.TextInput(
            label=f"Current XP in Lvl {view.current_level} (max {lvl_needed:,} XP)",
            placeholder="e.g. 45000, 45k, or 50%",
            required=True,
            max_length=20,
            default=str(view.current_xp) if view.current_xp > 0 else "",
        )
        self.add_item(self.xp_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.view_ref.author_id:
            await interaction.response.send_message(
                "❌ This calculator session belongs to another user. Use **`/xp`** to calculate your own!",
                ephemeral=True,
            )
            return

        parsed = parse_current_xp(self.xp_input.value, self.view_ref.current_level)
        self.view_ref.current_xp = parsed
        self.view_ref._sync_buttons()
        metrics = compute_xp_metrics(
            self.view_ref.current_level,
            self.view_ref.target_level,
            self.view_ref.current_xp,
            self.view_ref.item_data,
        )
        embed = build_xp_embed(metrics)
        await interaction.response.edit_message(embed=embed, view=self.view_ref)


class XPCalculatorView(discord.ui.View):
    """Interactive Argon control view with milestone jump buttons and Set XP Progress modal."""

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

        # Set XP Progress modal button
        edit_btn = discord.ui.Button(
            label="Set XP Progress",
            emoji="✏️",
            style=discord.ButtonStyle.secondary,
            custom_id="xp_set_progress",
        )
        edit_btn.callback = self._edit_progress_callback
        self.add_item(edit_btn)

    async def _edit_progress_callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "❌ This calculator session belongs to another user. Use **`/xp`** to calculate your own!",
                ephemeral=True,
            )
            return
        await interaction.response.send_modal(SetCurrentXPModal(self))

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
            items = await self.bot.api.search_items(current or "Laser Grid", limit=25, farmable_only=False)
            choices: list[app_commands.Choice[str]] = []
            seen_values: set[str] = set()

            for it in items:
                name = str(it.get("name", "")).strip()
                if not name or name.startswith("null_item"):
                    continue
                name_lower = name.lower()

                # Filter out seeds and clothing
                if it.get("item_type") == 19 or name_lower.endswith(" seed"):
                    continue
                if int(it.get("clothing_type", 0) or 0) > 0 or it.get("item_type") in (20, 26, 32):
                    continue
                # Filter out intermediate non-mature roots
                if name_lower.endswith(" roots") and not name_lower.endswith("mature roots"):
                    continue

                # Check for root mechanics
                if "pineapple" in name_lower and "root" in name_lower:
                    clean_val = "Mature Pineapple Roots"
                    label = f"🍍 {clean_val} (Root Harvest • 6 XP/harvest)"[:100]
                    val = clean_val
                elif "bountiful" in name_lower and ("mature root" in name_lower or "root cutting" in name_lower):
                    clean_val = name.replace("Root Cutting", "Mature Roots").strip()
                    label = f"🌾 {clean_val} (Root Harvest • 80 XP/harvest)"[:100]
                    val = clean_val
                elif "bountiful" in name_lower:
                    rarity = max(1, int(it.get("rarity", 1) or 1))
                    xp = min(500, max(1, 1 + (rarity // 5)))
                    label = f"🧱 {name} (Block Break • {xp} XP/block • Rarity {rarity})"[:100]
                    val = name
                else:
                    rarity = int(it.get("rarity", 0) or 0)
                    if rarity >= 999 or rarity <= 0:
                        continue  # Skip dummy 999 non-root items
                    xp = min(500, max(1, 1 + (rarity // 5)))
                    label = f"🧱 {name} (Rarity {rarity} • {xp} XP/block)"[:100]
                    val = name

                if val not in seen_values:
                    seen_values.add(val)
                    choices.append(app_commands.Choice(name=label, value=val))
                    if len(choices) >= 25:
                        break

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
                    "• **`/xp current_level:60 block:Laser Grid`** — Calculate blocks to Level 125\n"
                    "• **`/xp current_level:60 block:Laser Grid current_xp:45k`** — Deduct in-level XP progress\n"
                    "• **`/xp current_level:60 block:Laser Grid current_xp:50%`** — Deduct percentage progress\n"
                    "• **`/xp current_level:40 block:Chandelier target_level:50`** — Custom target level\n\n"
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
                "• **Milestones:** Quick progress comparison to Level 50, 100, and 125\n"
                "• **Live Progress Adjustment:** Supports exact XP, k-shorthand, or percentages"
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
        current_xp="Optional XP progress in current level (e.g. 45000, 45k, or 50%)",
    )
    @app_commands.autocomplete(block=block_autocomplete)
    async def xp_command(
        self,
        interaction: discord.Interaction,
        current_level: int,
        block: str,
        target_level: int = MAX_LEVEL_CAP,
        current_xp: str | None = None,
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

        parsed_xp = parse_current_xp(current_xp, current_level)

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
            current_xp=parsed_xp,
            item_data=item_data,
        )

        embed = build_xp_embed(metrics)
        view = XPCalculatorView(
            cog=self,
            author_id=interaction.user.id,
            current_level=current_level,
            target_level=target_level,
            current_xp=parsed_xp,
            item_data=item_data,
        )

        await interaction.followup.send(embed=embed, view=view)


async def setup(bot: EventBot) -> None:
    await bot.add_cog(XPCalculatorCog(bot))
