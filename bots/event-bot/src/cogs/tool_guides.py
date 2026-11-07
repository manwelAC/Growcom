"""
Growcom Tools Master Guide Channel (src/cogs/tool_guides.py)
- Creates read-only #📖tool-guides at the very top of the '🛠️ Growcom Tools' category.
- Sends 11 separate message bubbles (1 dedicated card per tool) so each tool guide is
  clean, easy to read, and never overwhelming!
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

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

TOOLS_CATEGORY_ID = 1567213972283719811
DEFAULT_MEMBER_ROLE_ID = 1568495447067332608

INDIVIDUAL_TOOL_GUIDES: list[dict[str, Any]] = [
    {
        "title": "🌱 Tool 1/11 — Growth Reminder & Harvest Timer (`/harvest`)",
        "color": 0x2ECC71,
        "channel": "<#1567214340291956857>",
        "purpose": (
            "Calculates exact tree ready times and sets an automatic **Discord Reminder** that pings you "
            "(and DMs you) the exact second your trees are ready to harvest!"
        ),
        "how_to_use": (
            "1. Go to <#1567214340291956857> and type **`/harvest`**.\n"
            "2. **Option A (Interactive Modal):** Press Enter with no options to open a clean pop-up box.\n"
            "3. **Option B (Direct Command):** Fill in `item_name`, `planted_at`, `harvester`, or `fickle`."
        ),
        "examples": (
            "- `/harvest` *(Opens the pop-up form)*\n"
            "- `/harvest item_name:Pepper Tree planted_at:10:30 PM`\n"
            "- `/harvest item_name:Laser Grid planted_at:2h 30m ago`\n"
            "- `/harvest item_name:Chandelier planted_at:now harvester:True`"
        ),
    },
    {
        "title": "📦 Tool 2/11 — Official Item Lookup (`/item`)",
        "color": 0x3498DB,
        "channel": "<#1567216131616411738>",
        "purpose": (
            "Searches all **15,904+ official Growtopia v27 items** to display Rarity, Grow Time, Max Gems, "
            "Collision/Block type, and Splicing formula."
        ),
        "how_to_use": (
            "1. Go to <#1567216131616411738> and type **`/item`**.\n"
            "2. Enter the item name in `name`."
        ),
        "examples": (
            "- `/item name:Laser Grid`\n"
            "- `/item name:Chandelier`\n"
            "- `/item name:Diamond Lock`"
        ),
    },
    {
        "title": "🧬 Tool 3/11 — Splicing Recipe Guide (`/recipe`)",
        "color": 0x9B59B6,
        "channel": "<#1567216421593944084>",
        "purpose": (
            "Shows the exact **Seed A + Seed B** splicing combination required to make an item, plus a list of "
            "other items you can splice using that seed!"
        ),
        "how_to_use": (
            "1. Go to <#1567216421593944084> and type **`/recipe`**.\n"
            "2. Enter the item name in `item_name`."
        ),
        "examples": (
            "- `/recipe item_name:Display Box`\n"
            "- `/recipe item_name:Laser Grid`\n"
            "- `/recipe item_name:Angel Wings`"
        ),
    },
    {
        "title": "💰 Tool 4/11 — Trade Rate & WL/DL/BGL Calculator (`/rate`)",
        "color": 0xF1C40F,
        "channel": "<#1567220472859594853>",
        "purpose": (
            "Calculates exact **Blue Gem Lock (BGL), Diamond Lock (DL), and World Lock (WL)** totals "
            "for any Growtopia rate (`200/1`, `40/1 WL`, or `3 WL each`)."
        ),
        "how_to_use": (
            "1. Go to <#1567220472859594853> and type **`/rate`**.\n"
            "2. Leave options blank to open the **Interactive Rate Calculator Modal**, or fill in `quantity` and `rate`."
        ),
        "examples": (
            "- `/rate` *(Opens the pop-up calculator)*\n"
            "- `/rate quantity:2600 rate:40/1 item_name:Laser Grid Seed`\n"
            "- `/rate quantity:200 rate:15 each item_name:Surgery Tool`"
        ),
    },
    {
        "title": "🩺 Tool 5/11 — Surgery & Malady Helper (`/surgery`)",
        "color": 0xE74C3C,
        "channel": "<#1567231718627483688>",
        "purpose": (
            "Step-by-step cure walkthrough for all **27 Growtopia Illnesses & Maladies** (Flu, Broken Bones, "
            "Brain Tumor, Lupus, Moldy Guts, etc.) with interactive **Emergency Complication Buttons**!"
        ),
        "how_to_use": (
            "1. Go to <#1567231718627483688> and type **`/surgery`**.\n"
            "2. Select the patient's illness or malady from the autocomplete list.\n"
            "3. Click the buttons at the bottom (*Heart Stopped, Bleeding, Vision Fading, Fever Rising*) during surgery!"
        ),
        "examples": (
            "- `/surgery malady:Massive Trauma`\n"
            "- `/surgery malady:Brain Tumor`\n"
            "- `/surgery malady:Lupus`"
        ),
    },
    {
        "title": "⚖️ Tool 6/11 — Farmable Profit & Gem Comparator (`/compare_farm`)",
        "color": 0x1ABC9C,
        "channel": "<#1567233119088803941>",
        "purpose": (
            "Compares **any two farmable items side-by-side** (Rarity, Grow Time, Harvest Cycles per Day, "
            "Average Gems per Tree, and Gems per Hour)."
        ),
        "how_to_use": (
            "1. Go to <#1567233119088803941> and type **`/compare_farm`**.\n"
            "2. Enter `first_item` and `second_item`."
        ),
        "examples": (
            "- `/compare_farm first_item:Laser Grid second_item:Chandelier`\n"
            "- `/compare_farm first_item:Pepper Tree second_item:Fish Tank`"
        ),
    },
    {
        "title": "🌳 Tool 7/11 — Mass Production & Splicing Planner (`/mass`)",
        "color": 0x27AE60,
        "channel": "<#1567236019282120836>",
        "purpose": (
            "Builds the complete **multi-step Splicing Family Tree** and calculates the exact **Base Seed Shopping List** "
            "(accounting for `10.8%` extra seed drops) for your target number of trees!"
        ),
        "how_to_use": (
            "1. Go to <#1567236019282120836> and type **`/mass`**.\n"
            "2. Enter the item you want to mass produce (`item_name`) and how many final trees you want (`target_trees`)."
        ),
        "examples": (
            "- `/mass item_name:Display Box target_trees:400`\n"
            "- `/mass item_name:Science Station target_trees:1000`"
        ),
    },
    {
        "title": "🍳 Tool 8/11 — Home Oven Cooking Timer & Helper (`/cook`)",
        "color": 0xE67E22,
        "channel": "<#1567238220972826654>",
        "purpose": (
            "Provides exact second-by-second **Oven Heat & Ingredient Timelines** for all 12 recipes + an interactive "
            "**`🔥 Start Live Oven Timer`** button that pings you in real time before every ingredient drop!"
        ),
        "how_to_use": (
            "1. Go to <#1567238220972826654> and type **`/cook`**.\n"
            "2. Choose your recipe from the autocomplete list.\n"
            "3. Click **`🔥 Start Live Oven Timer`** the moment you ignite your oven in-game!"
        ),
        "examples": (
            "- `/cook dish:Berry Crepes`\n"
            "- `/cook dish:Filet Mignon`\n"
            "- `/cook dish:Friedakh`"
        ),
    },
    {
        "title": "🦸 Tool 9/11 — Crime Wave Supervillain Guide (`/crime`)",
        "color": 0xC0392B,
        "channel": "<#1567240061320171713>",
        "purpose": (
            "Displays the optimal **5-Card Superhero Deck**, Villain Immunities, and Turn-by-Turn Counter Rotations "
            "to beat all **8 Supervillains**!"
        ),
        "how_to_use": (
            "1. Go to <#1567240061320171713> and type **`/crime`**.\n"
            "2. Select the Supervillain you are fighting."
        ),
        "examples": (
            "- `/crime villain:Dr. Destructo`\n"
            "- `/crime villain:Ms. Terry`\n"
            "- `/crime villain:Dragon Hand`"
        ),
    },
    {
        "title": "🎣 Tool 10/11 — Fishing & Fish Port Guide (`/fish`)",
        "color": 0x2980B9,
        "channel": "<#1567240147576291389>",
        "purpose": (
            "Covers all **7 Lures & Baits** (Wiggly Worm, Shiny Flashy Thing, Salmon Egg, Uranium Lure, etc.), "
            "catchable fish weights, Fishing Rods, and **Fish Port** training!"
        ),
        "how_to_use": (
            "1. Go to <#1567240147576291389> and type **`/fish`**.\n"
            "2. Pick a bait/lure or `Fish Port Training` from the autocomplete list."
        ),
        "examples": (
            "- `/fish bait_or_topic:Shiny Flashy Thing`\n"
            "- `/fish bait_or_topic:Salmon Egg`\n"
            "- `/fish bait_or_topic:Fish Port Training`"
        ),
    },
    {
        "title": "🚀 Tool 11/11 — Startopia 2.0 Voyage & Ship Guide (`/startrek`)",
        "color": 0x8E44AD,
        "channel": "<#1567240655774941264>",
        "purpose": (
            "Complete **Startopia 2.0 Ship & Voyage Solver** based on the official Growtopia Wiki! Shows the exact "
            "**step-by-step Star Tool sequence** for all **46+ Star Voyages** (plus Mid-Voyage Encounter popups, "
            "Starship equipment ratings, and **Growlactus / Ascended / Descended** sector guides)."
        ),
        "how_to_use": (
            "1. Go to <#1567240655774941264> and type **`/startrek`**.\n"
            "2. Type the **Mission Name** shown on your Starship Helm (or select **`Ship Setup & Sector Guide`**).\n"
            "3. Click the buttons at the bottom for **Mid-Voyage Encounters** or **Low Hull/Crew/Rep fixes**!"
        ),
        "examples": (
            "- `/startrek station_or_sector:Parasite Hunt`\n"
            "- `/startrek station_or_sector:Growlactus (Boss Voyage)`\n"
            "- `/startrek station_or_sector:Ship Setup & Sector Guide (Startopia 2.0)`"
        ),
    },
]


def build_single_tool_embed(spec: dict[str, Any]) -> discord.Embed:
    embed = discord.Embed(
        title=spec["title"],
        description=f"📍 **Dedicated Channel:** {spec['channel']}\n\n{spec['purpose']}",
        color=spec["color"],
        timestamp=datetime.now(EVENT_TZ),
    )
    embed.add_field(
        name="⌨️ How to Use",
        value=spec["how_to_use"],
        inline=False,
    )
    embed.add_field(
        name="💡 Command Examples",
        value=spec["examples"],
        inline=False,
    )
    embed.set_footer(text=FOOTER_TEXT)
    return embed


class ToolGuidesCog(commands.Cog):
    """Provisions the read-only #📖tool-guides channel and posts 11 separate message bubbles (1 per tool)."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._provisioned_guilds: set[int] = set()

    async def provision_tool_guides_channel(self, guild: discord.Guild, force_repost: bool = False) -> discord.TextChannel:
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

        overwrites: dict[discord.Role | discord.Member, discord.PermissionOverwrite] = {
            everyone_role: discord.PermissionOverwrite(
                view_channel=False,
                send_messages=False,
            ),
        }
        if member_role:
            overwrites[member_role] = discord.PermissionOverwrite(
                view_channel=True,
                read_message_history=True,
                send_messages=False,
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

        guide_ch: discord.TextChannel | None = None
        saved_id = state.get("tool_guides_channel_id")
        if saved_id:
            ch = guild.get_channel(int(saved_id))
            if isinstance(ch, discord.TextChannel):
                guide_ch = ch

        if not guide_ch:
            for ch in guild.text_channels:
                if "tool-guide" in ch.name.lower():
                    guide_ch = ch
                    break

        created_new = False
        if not guide_ch:
            guide_ch = await guild.create_text_channel(
                name="📖tool-guides",
                category=tools_cat,
                position=0,
                topic="📖 Official Growcom Tools Command Guide — Read-only step-by-step tutorial for each of the 11 Growtopia tools.",
                overwrites=overwrites,
                reason="Create read-only #📖tool-guides channel at top of 🛠️ Growcom Tools",
            )
            created_new = True
        else:
            await guide_ch.edit(
                category=tools_cat,
                position=0,
                overwrites=overwrites,
                reason="Ensure #📖tool-guides is read-only and at top of 🛠️ Growcom Tools",
            )

        if created_new or force_repost:
            msg_ids: list[str] = []
            for spec in INDIVIDUAL_TOOL_GUIDES:
                embed = build_single_tool_embed(spec)
                msg = await guide_ch.send(embed=embed)
                msg_ids.append(str(msg.id))
                await asyncio.sleep(0.35)
            state["tool_guides_message_ids"] = msg_ids

        state["tool_guides_channel_id"] = str(guide_ch.id)
        save_state(state)
        self._provisioned_guilds.add(guild.id)
        return guide_ch

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        for guild in self.bot.guilds:
            if guild.id in self._provisioned_guilds:
                continue
            if guild.me and guild.me.guild_permissions.administrator:
                try:
                    ch = await self.provision_tool_guides_channel(guild, force_repost=False)
                    logger.info("Configured read-only %s (%s) in %s", ch.name, ch.id, guild.name)
                except Exception as exc:
                    logger.warning("Could not configure #📖tool-guides in %s: %s", guild.name, exc)

    @app_commands.command(
        name="setup_tool_guides",
        description="Admin: Create or refresh the read-only #📖tool-guides channel in 🛠️ Growcom Tools.",
    )
    async def setup_tool_guides_cmd(self, interaction: discord.Interaction) -> None:
        if not is_server_manager(interaction) or not interaction.guild:
            await interaction.response.send_message("❌ Admin permission required.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        ch = await self.provision_tool_guides_channel(interaction.guild, force_repost=True)
        await interaction.followup.send(
            f"✅ Posted all **11 individual tool guide cards** in read-only {ch.mention}!",
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ToolGuidesCog(bot))
