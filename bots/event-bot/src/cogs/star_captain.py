"""
Category 12: Star Captain Starship & Sector Guide (cogs/star_captain.py)
- /startrek (Complete cheat-sheet for all 6 Starship Bridge Stations, Sector Encounters, and Star Supplies rewards)
- /set_startrek_channel (Admin channel lock + instruction card)
"""

from __future__ import annotations

from io import BytesIO
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


STARSHIP_DATABASE: dict[str, dict[str, Any]] = {
    "Weapons (Tactical Station)": {
        "role": "⚔️ Primary Damage Dealer (Phasers & Torpedoes)",
        "priority": "⭐⭐⭐⭐⭐ Essential in Every Combat Encounter",
        "controls": [
            "🔫 **Fire Phasers:** Fast, reliable laser damage that strips **Enemy Shields** first.",
            "🚀 **Photon Torpedo:** Heavy hull damage — **save Torpedoes until Enemy Shields are DOWN (0%)** for maximum damage!",
            "🎯 **Target Lock / Calibrate:** Increases weapon accuracy so your Torpedoes don't miss evasive ships.",
        ],
        "rotation": "1️⃣ Strip enemy shields to `0%` using **Phasers**.\n2️⃣ Lock on with **Target Lock** ➔ Fire **Photon Torpedoes** directly into their exposed Hull!",
        "rewards": "Drops **Star Supplies**, **Tactical Skill XP**, **Cadet Badges**, and **Galactic** ship components.",
        "sprite_item": "Starship Weapons",
    },
    "Shields (Defense Station)": {
        "role": "🛡️ Ship Survival & Shield Modulation",
        "priority": "⭐⭐⭐⭐⭐ Essential (Prevents Ship Destruction!)",
        "controls": [
            "🛡️ **Raise / Modulate Shields:** Absorbs incoming enemy Phaser & Torpedo fire.",
            "🔄 **Rebalance Shields:** Shifts shield energy to the quadrant taking heavy fire.",
            "⚡ **Overcharge Shields:** Temporarily boosts shield capacity right before an enemy Boss volley.",
        ],
        "rotation": "1️⃣ Always **Raise Shields** on Turn 1 of any combat encounter!\n2️⃣ Whenever shields drop below `40%`, immediately **Modulate / Recharge Shields** so hull takes 0 damage.",
        "rewards": "Prevents mission failure & grants **Star Captain XP** + **Defense Star Supplies**.",
        "sprite_item": "Starship Shields",
    },
    "Helm (Navigation Station)": {
        "role": "🕹️ Evasion, Sector Jumping, & Positioning",
        "priority": "⭐⭐⭐⭐ High (Dodges Torpedoes & Moves Sectors)",
        "controls": [
            "💨 **Evasive Maneuvers:** Dramatically increases ship dodge chance against incoming Torpedoes.",
            "🌌 **Warp / Jump Sector:** Moves the Starship to the next sector once the current anomaly/enemy is cleared.",
            "🧭 **Approach / Keep Distance:** Adjusts range for Weapons and Teleporter teams.",
        ],
        "rotation": "1️⃣ Activate **Evasive Maneuvers** whenever the enemy ship charges a heavy weapon.\n2️⃣ Coordinate with **Weapons** & **Teleporter** before warping to the next sector.",
        "rewards": "Unlocks deep-space sectors with higher **Star Supplies** & **Star Strife** mission points (`+20 to +200 pts`).",
        "sprite_item": "Starship Helm",
    },
    "Engineering (Power & Repairs)": {
        "role": "🔧 Hull Repair & Reactor Power Routing",
        "priority": "⭐⭐⭐⭐ High (Keeps Weapons & Shields Powered)",
        "controls": [
            "⚡ **Route Power (Weapons / Shields / Engines):** Boosts the effectiveness of whichever station needs energy most.",
            "🔧 **Emergency Hull Repair:** Restores ship Hull HP if enemy fire penetrated the shields.",
            "❄️ **Vent Plasma / Cool Core:** Prevents reactor overload during long boss fights.",
        ],
        "rotation": "1️⃣ Route power to **Shields + Weapons** at the start of combat.\n2️⃣ If Hull HP drops below `60%`, prioritize **Emergency Hull Repair** immediately!",
        "rewards": "Essential for surviving **Pirate / Imperial Boss Sectors** and earning **Star Captain Role Quests**.",
        "sprite_item": "Starship Engineering",
    },
    "Medical (Sickbay Station)": {
        "role": "🩺 Crew Healing & Life Support",
        "priority": "⭐⭐⭐ Medium-High (Saves Injured Crew & Away Teams)",
        "controls": [
            "💉 **Heal Crew / Bio-Scan:** Heals crew members injured by boarding parties or bridge explosions.",
            "🌬️ **Restore Life Support:** Fixes oxygen/radiation leaks caused by hull breaches.",
            "🧬 **Synthesize Vaccine:** Cures space anomalies & alien infections during sector events.",
        ],
        "rotation": "1️⃣ Monitor crew HP after heavy enemy hits.\n2️⃣ Heal injured bridge officers immediately so their station cooldowns don't slow down!",
        "rewards": "Required to complete **Diplomatic / Anomaly Sectors** and keep 100% crew survival bonus.",
        "sprite_item": "Starship Medical",
    },
    "Teleporter (Away Team & Boarding)": {
        "role": "✨ Boarding Enemy Ships & Rescuing Survivors",
        "priority": "⭐⭐⭐ Medium-High (Required for Rescue & Capture Missions)",
        "controls": [
            "📡 **Scan Target:** Locates survivors, loot caches, or enemy shield generators.",
            "✨ **Beam Away Team (Board):** Sends boarding party to sabotage enemy systems *(Enemy Shields must be DOWN!)*. ",
            "📥 **Beam Aboard (Extract):** Rescues stranded colonists or retrieves **Star Supplies** crates.",
        ],
        "rotation": "1️⃣ **Wait until Enemy Shields are `0%`** (you cannot beam through active shields!).\n2️⃣ **Scan** ➔ **Beam Away Team / Extract** before Weapons destroys the target ship!",
        "rewards": "Grants bonus **Star Supplies**, **Alien Artifacts**, and **Rescue Mission** points!",
        "sprite_item": "Starship Teleporter",
    },
    "Sectors & Star Supplies Guide": {
        "role": "🌌 Complete Star Captain Role Day & Loot Guide",
        "priority": "🏆 Best Strategy for Star Captain Role Day & Star Strife",
        "controls": [
            "🟢 **Patrol / Easy Sectors:** Fast 1–2 ship encounters (`+20–50 pts` in Star Strife, quick **Role Quest** completion).",
            "🟡 **Anomaly / Rescue Sectors:** Require **Medical** + **Teleporter** stations rather than pure combat.",
            "🔴 **Deep Space / Boss Sectors (Greezak & Imperial Dreadnoughts):** Require a coordinated crew on **Shields + Weapons + Engineering + Helm** (`+100–200 pts` & max **Star Supplies**!).",
        ],
        "rotation": "1️⃣ On **Star Captain Role Day**, complete your daily **Star Captain Quest** first for `+1 Growtoken` & bonus Role XP.\n2️⃣ Trade **Star Supplies** & **Cadet Badges** for exclusive Star Captain items (`Starboard`, `Cyborg` gear, `Galactic` blocks).",
        "rewards": "• **Star Supplies** • **Cadet Badges** • **Growtoken** (on Role Day) • **Star Captain Role Skins & Titles**",
        "sprite_item": "Star Supplies",
    },
}


class StarCaptainCog(commands.Cog, name="Star Captain Guide"):
    def __init__(self, bot: EventBot) -> None:
        self.bot = bot

    async def station_autocomplete(
        self,
        _interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        query = current.strip().lower()
        choices: list[app_commands.Choice[str]] = []
        for name, info in STARSHIP_DATABASE.items():
            if not query or query in name.lower() or query in info["role"].lower():
                label = f"{name} — {info['role']}"
                choices.append(app_commands.Choice(name=label[:100], value=name))
        return choices[:25]

    @app_commands.command(
        name="set_startrek_channel",
        description="Restrict the /startrek starship & sector guide exclusively to a dedicated channel",
    )
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(channel="Dedicated channel for /startrek lookups (defaults to current channel)")
    async def set_startrek_channel_command(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel | None = None,
    ) -> None:
        if not is_server_manager(interaction):
            await interaction.response.send_message(
                "❌ Only server admins can use `/set_startrek_channel`.",
                ephemeral=True,
            )
            return
        await interaction.response.defer()
        target_channel = channel or interaction.channel
        if not isinstance(target_channel, discord.TextChannel):
            await interaction.followup.send("❌ Please select a standard text channel.", ephemeral=True)
            return

        state = load_state()
        state["startrek_channel_id"] = target_channel.id
        save_state(state)

        guide_embed = discord.Embed(
            title="🚀 Growcom Star Captain Starship & Sector Guide",
            description=(
                "Use **`/startrek`** in this channel for instant cheat-sheets on every **Starship Bridge Station** "
                "and **Sector Encounter**!\n\n"
                "**Covered Stations & Guides:**\n"
                "• ⚔️ **Weapons (Tactical)** • 🛡️ **Shields (Defense)** • 🕹️ **Helm (Navigation)**\n"
                "• 🔧 **Engineering (Power & Repairs)** • 🩺 **Medical (Sickbay)** • ✨ **Teleporter (Away Team)**\n"
                "• 🌌 **Sectors & Star Supplies Guide**"
            ),
            color=discord.Color.from_rgb(155, 89, 182),
        )
        guide_embed.set_footer(text=FOOTER_TEXT)
        await target_channel.send(embed=guide_embed)

        await interaction.followup.send(
            f"✅ Locked **`/startrek`** exclusively to {target_channel.mention}! "
            f"Players trying to run `/startrek` anywhere else will be redirected to {target_channel.mention}.",
            ephemeral=True,
        )

    @app_commands.command(
        name="startrek",
        description="Star Captain cheat-sheet for Starship Bridge Stations (Helm, Weapons, Shields, etc.) & Sectors!",
    )
    @app_commands.describe(
        station="Select a Starship Station or Sector Guide (e.g. Weapons, Shields, Helm, Engineering, Teleporter)"
    )
    @app_commands.autocomplete(station=station_autocomplete)
    async def startrek_command(self, interaction: discord.Interaction, station: str) -> None:
        state = load_state()
        allowed_channel_id = state.get("startrek_channel_id")
        if allowed_channel_id and int(interaction.channel_id or 0) != int(allowed_channel_id):
            await interaction.response.send_message(
                f"❌ The **`/startrek`** guide can only be used inside <#{allowed_channel_id}>!",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        matched_name: str | None = None
        for name in STARSHIP_DATABASE:
            if name.lower() == station.strip().lower():
                matched_name = name
                break
        if not matched_name:
            for name in STARSHIP_DATABASE:
                if station.strip().lower() in name.lower():
                    matched_name = name
                    break

        if not matched_name:
            await interaction.followup.send(
                f"❌ Could not find a Starship station matching **`{station}`**. Please select one from the `/startrek` autocomplete list!",
                ephemeral=True,
            )
            return

        info = STARSHIP_DATABASE[matched_name]
        embed = discord.Embed(
            title=f"🚀 Star Captain Guide — {matched_name}",
            description=f"**{info['role']}**\nPriority: {info['priority']}",
            color=discord.Color.from_rgb(155, 89, 182),
        )
        embed.add_field(
            name="🎛️ Station Controls & Abilities",
            value="\n".join(f"• {c}" for c in info["controls"]),
            inline=False,
        )
        embed.add_field(
            name="🔄 Optimal Turn Rotation",
            value=info["rotation"],
            inline=False,
        )
        embed.add_field(
            name="🎁 Mission Rewards & Role Day Loot",
            value=info["rewards"],
            inline=False,
        )

        files: list[discord.File] = []
        sprite_bytes = await self.bot.api.get_item_sprite(info.get("sprite_item", "Star Supplies"))
        if sprite_bytes:
            files.append(discord.File(BytesIO(sprite_bytes), filename="sprite.png"))
            embed.set_thumbnail(url="attachment://sprite.png")

        embed.set_footer(text=FOOTER_TEXT)
        await interaction.followup.send(embed=embed, files=files)


async def setup(bot: EventBot) -> None:
    await bot.add_cog(StarCaptainCog(bot))
