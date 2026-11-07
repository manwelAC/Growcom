"""
Growcom Tools Master Guide Channel (src/cogs/tool_guides.py)
- Creates read-only #📖tool-guides at the very top of the '🛠️ Growcom Tools' category.
- Posts comprehensive, categorized guide cards teaching every single Growcom tool command,
  its parameters, example usage, and clickable channel links.
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

TOOLS_CATEGORY_ID = 1567213972283719811
DEFAULT_MEMBER_ROLE_ID = 1568495447067332608


def build_tool_guide_embeds() -> list[discord.Embed]:
    now = datetime.now(EVENT_TZ)

    # Embed 1: Overview, Farming, Economy, & Item Database Tools (Tools 1–6)
    embed_farming = discord.Embed(
        title="🛠️ Growcom Tools — Complete Command Guide (Part 1: Farming & Economy)",
        description=(
            "Welcome to **Growcom Tools**! Every tool has its own dedicated channel to keep the server organized.\n"
            "> ⏳ **Cooldown Note:** Each tool command has a **2-minute (`120s`) cooldown per user** to prevent spam.\n\n"
            "---"
        ),
        color=0x2ECC71,
        timestamp=now,
    )
    embed_farming.add_field(
        name="1️⃣ 🌱 Growth Reminder & Harvest Timer — `/harvest`",
        value=(
            "📍 **Channel:** <#1567214340291956857>\n"
            "📖 **What it does:** Calculates exact tree ready times and sets an automatic **Discord Reminder** that pings you (and DMs you) the exact second your trees are ready to harvest!\n"
            "⌨️ **How to use:**\n"
            "- Type **`/harvest`** *(leave blank to open the interactive pop-up form!)*\n"
            "- Or type: `/harvest item_name:Pepper Tree planted_at:10:30 PM`\n"
            "- Supports clock times (`10:30 PM`, `yesterday 8:00 PM`), relative times (`2h 30m ago`), `now`, and **Harvester / Fickle Being** buffs!"
        ),
        inline=False,
    )
    embed_farming.add_field(
        name="2️⃣ 📦 Official Item Lookup — `/item`",
        value=(
            "📍 **Channel:** <#1567216131616411738>\n"
            "📖 **What it does:** Searches all **15,904+ official Growtopia v27 items** for Rarity, Grow Time, Max Gems, Seed colors, and Splicing formulas.\n"
            "⌨️ **How to use:**\n"
            "- `/item name:Laser Grid`\n"
            "- `/item name:Diamond Lock`"
        ),
        inline=False,
    )
    embed_farming.add_field(
        name="3️⃣ 🧬 Splicing Recipe Guide — `/recipe`",
        value=(
            "📍 **Channel:** <#1567216421593944084>\n"
            "📖 **What it does:** Shows the exact **Seed A + Seed B** splicing combination to create an item, plus every recipe where that item is used as an ingredient!\n"
            "⌨️ **How to use:**\n"
            "- `/recipe item_name:Chandelier`\n"
            "- `/recipe item_name:Display Box`"
        ),
        inline=False,
    )
    embed_farming.add_field(
        name="4️⃣ 💰 Trade Rate & WL/DL/BGL Calculator — `/rate`",
        value=(
            "📍 **Channel:** <#1567220472859594853>\n"
            "📖 **What it does:** Converts any Growtopia rate (`200/1 WL`, `40/1`, `3 WL each`) into exact **BGL + DL + WL** totals and leftover items.\n"
            "⌨️ **How to use:**\n"
            "- Type **`/rate`** *(opens the interactive calculator modal)*\n"
            "- Or type: `/rate quantity:2600 rate:40/1 item_name:Laser Grid Seed`"
        ),
        inline=False,
    )
    embed_farming.add_field(
        name="5️⃣ ⚖️ Farmable Profit & Gem Comparator — `/compare_farm`",
        value=(
            "📍 **Channel:** <#1567233119088803941>\n"
            "📖 **What it does:** Compares **two farmables side-by-side** (Rarity, Grow Time, Harvests per Day, Average Gems per Tree, and Gems per Hour).\n"
            "⌨️ **How to use:**\n"
            "- `/compare_farm first_item:Laser Grid second_item:Chandelier`"
        ),
        inline=False,
    )
    embed_farming.add_field(
        name="6️⃣ 🌳 Mass Production & Splicing Tree Planner — `/mass`",
        value=(
            "📍 **Channel:** <#1567236019282120836>\n"
            "📖 **What it does:** Builds the full **multi-step Splicing Family Tree** and calculates the exact **Base Seed Shopping List** (including `10.8%` extra seed drops) for your target tree count!\n"
            "⌨️ **How to use:**\n"
            "- `/mass item_name:Display Box target_trees:400`"
        ),
        inline=False,
    )
    embed_farming.set_footer(text=FOOTER_TEXT)

    # Embed 2: Role Quests, Mini-Games, & Community Commands (Tools 7–11)
    embed_roles = discord.Embed(
        title="🎮 Growcom Tools — Complete Command Guide (Part 2: Role Quests & Mini-Games)",
        description="Master Surgery, Home Oven Cooking, Crime Wave, Fishing, and Star Captain with interactive step-by-step assistants!",
        color=0x3498DB,
        timestamp=now,
    )
    embed_roles.add_field(
        name="7️⃣ 🩺 Surgery & Malady Helper — `/surgery`",
        value=(
            "📍 **Channel:** <#1567231718627483688>\n"
            "📖 **What it does:** Covers all **27 Growtopia Illnesses & Maladies** (Flu,Broken Bones, Brain Tumor, Lupus, Moldy Guts, etc.) with exact tool order + **Emergency Complication Buttons** (*Heart Stopped, Incisions Bleeding, Vision Fading, Fever Rising*).\n"
            "⌨️ **How to use:**\n"
            "- `/surgery malady:Massive Trauma` *(has autocomplete as you type!)*"
        ),
        inline=False,
    )
    embed_roles.add_field(
        name="8️⃣ 🍳 Home Oven Cooking Timer & Helper — `/cook`",
        value=(
            "📍 **Channel:** <#1567238220972826654>\n"
            "📖 **What it does:** Displays exact second-by-second **Oven Heat & Ingredient Timelines** (Berry Crepes, Filet Mignon, Friedakh, etc.) + a **`🔥 Start Live Oven Timer`** button that pings you in real time before every step!\n"
            "⌨️ **How to use:**\n"
            "- `/cook dish:Berry Crepes` *(then click **Start Live Oven Timer** when you press Cook!)*"
        ),
        inline=False,
    )
    embed_roles.add_field(
        name="9️⃣ 🦸 Crime Wave Supervillain Guide — `/crime`",
        value=(
            "📍 **Channel:** <#1567240061320171713>\n"
            "📖 **What it does:** Shows the best **5-Card Superhero Deck**, Villain Immunities, and Turn-by-Turn Counter Rotations for all **8 Supervillains** (*Ms. Terry, Dr. Destructo, Dragon Hand, Big Bertha*, etc.).\n"
            "⌨️ **How to use:**\n"
            "- `/crime villain:Dr. Destructo`"
        ),
        inline=False,
    )
    embed_roles.add_field(
        name="🔟 🎣 Fishing & Fish Port Guide — `/fish`",
        value=(
            "📍 **Channel:** <#1567240147576291389>\n"
            "📖 **What it does:** Lists all **7 Lures & Baits** (Wiggly Worm, Shiny Flashy Thing, Salmon Egg, Uranium Lure, etc.), target fish weights, Rods, and **Fish Port** training.\n"
            "⌨️ **How to use:**\n"
            "- `/fish bait_or_topic:Shiny Flashy Thing`"
        ),
        inline=False,
    )
    embed_roles.add_field(
        name="1️⃣1️⃣ 🚀 Star Captain & Bridge Station Guide — `/startrek`",
        value=(
            "📍 **Channel:** <#1567240655774941264>\n"
            "📖 **What it does:** Explains all **6 Starship Bridge Stations** (*Helm, Tactical, Science, Engineering, Medical, Communications*) and Sector Encounter rewards.\n"
            "⌨️ **How to use:**\n"
            "- `/startrek station_or_sector:Tactical`"
        ),
        inline=False,
    )
    embed_roles.add_field(
        name="💼 Bonus: Marketplace & Community Commands",
        value=(
            "- **`/vouch`** *(in <#1568494512945373307>)* — Post a verified trade vouch for another member.\n"
            "- **`/report_scammer`** *(Anywhere)* — Privately submit a scammer report + screenshot proof for Admin approval.\n"
            "- **`/suggest`** *(in <#1568514201909985421>)* — Submit a server or bot suggestion for community 👍/👎 voting.\n"
            "- **`/feedback`** *(in <#1568505161087975454>)* — Leave a 1–5 Star review for the Growcom server!"
        ),
        inline=False,
    )
    embed_roles.set_footer(text=FOOTER_TEXT)

    return [embed_farming, embed_roles]


class ToolGuidesCog(commands.Cog):
    """Provisions and updates the read-only #📖tool-guides channel at the top of 🛠️ Growcom Tools."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._provisioned_guilds: set[int] = set()

    async def provision_tool_guides_channel(self, guild: discord.Guild) -> discord.TextChannel:
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

        embeds = build_tool_guide_embeds()

        if not guide_ch:
            guide_ch = await guild.create_text_channel(
                name="📖tool-guides",
                category=tools_cat,
                position=0,
                topic="📖 Official Growcom Tools Command Guide — Read-only tutorial for all 11 Growtopia calculator & helper commands.",
                overwrites=overwrites,
                reason="Create read-only #📖tool-guides channel at top of 🛠️ Growcom Tools",
            )
            msg = await guide_ch.send(embeds=embeds)
            state["tool_guides_message_id"] = str(msg.id)
        else:
            await guide_ch.edit(
                category=tools_cat,
                position=0,
                overwrites=overwrites,
                reason="Ensure #📖tool-guides is read-only and at top of 🛠️ Growcom Tools",
            )
            msg_id = state.get("tool_guides_message_id")
            if msg_id:
                try:
                    existing_msg = await guide_ch.fetch_message(int(msg_id))
                    await existing_msg.edit(embeds=embeds)
                except Exception:
                    new_msg = await guide_ch.send(embeds=embeds)
                    state["tool_guides_message_id"] = str(new_msg.id)

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
                    ch = await self.provision_tool_guides_channel(guild)
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
        ch = await self.provision_tool_guides_channel(interaction.guild)
        await interaction.followup.send(
            f"✅ Refreshed read-only {ch.mention} at the top of **🛠️ Growcom Tools**!",
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ToolGuidesCog(bot))
