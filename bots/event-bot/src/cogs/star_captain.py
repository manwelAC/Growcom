"""
Category 12: Startopia 2.0 Voyage & Ship Mission Solver (cogs/star_captain.py)
- /startrek, /set_startrek_channel
- Based on the official Growtopia Wiki Startopia 2.0 Guide (https://growtopiawiki.com/wiki/Guide:Startopia).
- Covers all 46+ Star Voyage Missions (plus all variant names) with exact step-by-step Star Tool sequences,
  interactive Mid-Voyage Random Encounter solver buttons, and Starship Setup / Sector Progression guides!
"""

from __future__ import annotations

from collections import Counter
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
    save_state,
)

TOOL_ICONS: dict[str, str] = {
    "Tactical Drone": "🛰️",
    "Teleporter Charge": "⚡",
    "Quadriscanner": "📡",
    "Gigablaster": "🔫",
    "HyperShields": "🛡️",
    "Growton Torpedo": "🚀",
    "Cyborg Diplomat": "🤖",
    "Stellar Documents": "📜",
    "AI Brain": "🧠",
    "Galactibolt": "🔧",
    "Space Meds": "💊",
    "Star Supplies": "📦",
}

# Complete official Growtopia Wiki Startopia 2.0 Mission Database
STARTOPIA_MISSIONS: dict[str, dict[str, Any]] = {
    "Ship Setup & Sector Guide (Startopia 2.0)": {
        "aliases": ["setup", "ship", "build", "sector", "startopia 2.0", "ascended", "descended", "rating"],
        "variants": "How to Build a Starship, Upgrade Rating, & Unlock Startopia 2.0 Sectors",
        "steps": [],
        "is_setup_guide": True,
    },
    "Set a Course": {
        "aliases": ["course"],
        "variants": "Standard Introductory Voyage",
        "steps": ["Tactical Drone", "Stellar Documents"],
    },
    "Parasite Hunt": {
        "aliases": ["rebel hunt", "bug hunt", "spider hunt", "smuggler hunt", "xenoid hunt", "hive hunt", "pirate hunt", "greezak hunt", "robot hunt"],
        "variants": "Also covers: Rebel, Bug, Spider, Smuggler, Xenoid, Hive, Pirate, Greezak, & Robot Hunt",
        "steps": ["Tactical Drone", "Teleporter Charge", "Quadriscanner", "Gigablaster", "Teleporter Charge"],
    },
    "Warp Data": {
        "aliases": ["pilot data", "warfare data", "storm data", "collision data", "asteroid data", "skeleton data", "moon data", "cargo data", "energy data", "devastation data", "radiation data", "weapons data", "debris data", "literary data"],
        "variants": "Also covers: Pilot, Warfare, Storm, Collision, Asteroid, Skeleton, Moon, Cargo, Energy, Devastation, Radiation, Weapons, Debris, & Literary Data",
        "steps": ["Tactical Drone", "Teleporter Charge", "Quadriscanner", "Teleporter Charge", "Stellar Documents"],
    },
    "Rebel Attack": {
        "aliases": ["alien attack", "mafia attack", "greezak attack", "robot attack", "pirate attack", "junker attack", "smuggler attack", "volcanix attack", "xenoid attack"],
        "variants": "Also covers: Alien, Mafia, Greezak, Robot, Pirate, Junker, Smuggler, Volcanix, & Xenoid Attack",
        "steps": ["Tactical Drone", "HyperShields", "Growton Torpedo", "Growton Torpedo"],
    },
    "A Challenge?!": {
        "aliases": ["challenge"],
        "variants": "Shield Endurance Voyage",
        "steps": ["Tactical Drone", "HyperShields", "HyperShields", "HyperShields", "HyperShields"],
    },
    "Outpost Attack / One Angry Ship": {
        "aliases": ["outpost attack", "one angry ship"],
        "variants": "Covers both Outpost Attack and One Angry Ship",
        "steps": ["Tactical Drone", "Growton Torpedo", "Cyborg Diplomat", "Teleporter Charge", "Stellar Documents", "Teleporter Charge"],
    },
    "Solar Impact!": {
        "aliases": ["solar impact"],
        "variants": "Solar Flare Emergency Voyage",
        "steps": ["HyperShields", "Galactibolt", "Space Meds", "AI Brain", "Tactical Drone"],
    },
    "Salvage Run / Windy Days": {
        "aliases": ["salvage run", "windy days"],
        "variants": "Covers both Salvage Run and Windy Days",
        "steps": ["Tactical Drone", "Teleporter Charge", "Quadriscanner", "Teleporter Charge"],
    },
    "Starachnid Attack": {
        "aliases": ["starachnid", "spider"],
        "variants": "Giant Space Arachnid Encounter",
        "steps": ["Tactical Drone", "Growton Torpedo", "Star Supplies", "Growton Torpedo", "Gigablaster"],
    },
    "Miner Rescue": {
        "aliases": ["miner"],
        "variants": "Stranded Asteroid Miner Rescue",
        "steps": ["Galactibolt", "Tactical Drone", "Teleporter Charge", "Quadriscanner", "Teleporter Charge", "Teleporter Charge"],
    },
    "Hunter and Prey": {
        "aliases": ["hunter", "prey"],
        "variants": "Bounty Hunter Encounter",
        "steps": ["Tactical Drone", "AI Brain", "Teleporter Charge", "Gigablaster", "Teleporter Charge"],
    },
    "Life Pod": {
        "aliases": ["lifepod"],
        "variants": "Drifting Life Pod Recovery",
        "steps": ["Teleporter Charge", "Quadriscanner", "Space Meds", "Star Supplies"],
    },
    "Ancient Temple": {
        "aliases": ["temple"],
        "variants": "Alien Ruin Diplomacy Voyage",
        "steps": ["Tactical Drone", "Cyborg Diplomat", "Star Supplies", "Stellar Documents"],
    },
    "Dark Ship": {
        "aliases": ["dark"],
        "variants": "Unpowered Mystery Vessel",
        "steps": ["Tactical Drone", "Teleporter Charge", "AI Brain", "Growton Torpedo", "Growton Torpedo"],
    },
    "Experimental Salvage": {
        "aliases": ["experimental"],
        "variants": "Multi-Teleport Salvage Mission",
        "steps": ["Tactical Drone", "Teleporter Charge", "Teleporter Charge", "Teleporter Charge"],
    },
    "Ship Rescue": {
        "aliases": ["ship rescue"],
        "variants": "Damaged Cruiser Medical Rescue",
        "steps": ["Tactical Drone", "Teleporter Charge", "Quadriscanner", "Space Meds", "Teleporter Charge"],
    },
    "Bad Taste": {
        "aliases": ["bad taste"],
        "variants": "Hostile Diplomatic Banquet",
        "steps": ["Teleporter Charge", "Cyborg Diplomat", "Stellar Documents", "Gigablaster"],
    },
    "A Strange One": {
        "aliases": ["strange one", "strange"],
        "variants": "Anomalous Alien Encounter",
        "steps": ["Tactical Drone", "Cyborg Diplomat", "Galactibolt", "AI Brain", "Stellar Documents"],
    },
    "Skeleton Crew": {
        "aliases": ["skeleton crew"],
        "variants": "Abandoned Ghost Crew Investigation",
        "steps": ["Teleporter Charge", "Quadriscanner", "AI Brain", "Stellar Documents"],
    },
    "Tasty Cakes": {
        "aliases": ["tasty cakes", "cakes"],
        "variants": "Alien Bakery Ambush",
        "steps": ["Tactical Drone", "Teleporter Charge", "Quadriscanner", "AI Brain", "Quadriscanner", "Gigablaster", "Teleporter Charge"],
    },
    "Ghost Ship": {
        "aliases": ["ghost ship", "ghost"],
        "variants": "Phantom Vessel Investigation",
        "steps": ["Tactical Drone", "Teleporter Charge", "Quadriscanner", "Cyborg Diplomat", "Stellar Documents", "Teleporter Charge"],
    },
    "Giant Skeleton": {
        "aliases": ["giant skeleton"],
        "variants": "Colossal Space Leviathan Remains",
        "steps": ["Tactical Drone", "AI Brain", "HyperShields", "Star Supplies"],
    },
    "Cryonite Crisis": {
        "aliases": ["cryonite"],
        "variants": "9-Step High-Difficulty Cryonite Voyage",
        "steps": ["Teleporter Charge", "Quadriscanner", "Gigablaster", "Quadriscanner", "AI Brain", "AI Brain", "HyperShields", "Stellar Documents", "Teleporter Charge"],
    },
    "Pit O' Trouble": {
        "aliases": ["pit o trouble", "pit of trouble"],
        "variants": "Alien Pit Ambush",
        "steps": ["Tactical Drone", "Teleporter Charge", "Quadriscanner", "Gigablaster", "Teleporter Charge", "Growton Torpedo"],
    },
    "Close Encounter": {
        "aliases": ["close encounter"],
        "variants": "First Contact Negotiation",
        "steps": ["Tactical Drone", "AI Brain", "Cyborg Diplomat", "Cyborg Diplomat", "Quadriscanner", "AI Brain"],
    },
    "Boarding Party": {
        "aliases": ["boarding party", "boarding"],
        "variants": "Enemy Hull Breachers",
        "steps": ["Quadriscanner", "Gigablaster", "Gigablaster"],
    },
    "Taking Aim": {
        "aliases": ["taking aim"],
        "variants": "Target Elimination Voyage",
        "steps": ["Tactical Drone", "Teleporter Charge", "Gigablaster", "Teleporter Charge"],
    },
    "Junk Punks": {
        "aliases": ["junk punks"],
        "variants": "Scavenger Raiders",
        "steps": ["AI Brain", "Tactical Drone", "Growton Torpedo", "AI Brain"],
    },
    "Escape Pod": {
        "aliases": ["escape pod"],
        "variants": "9-Step Combat & Medical Pod Extraction",
        "steps": ["Tactical Drone", "HyperShields", "Teleporter Charge", "Quadriscanner", "Gigablaster", "Space Meds", "Quadriscanner", "Teleporter Charge", "Growton Torpedo"],
    },
    "Growlactus (Boss Voyage)": {
        "aliases": ["growlactus", "boss", "heart of the galaxy", "desolated waste"],
        "variants": "Final Sector Boss! Winning unlocks Heart of the Galaxy (Ascended); Losing unlocks Desolated Waste (Descended)",
        "steps": ["Tactical Drone", "HyperShields", "Growton Torpedo", "Cyborg Diplomat", "Gigablaster", "AI Brain", "Teleporter Charge", "Quadriscanner", "Gigablaster", "Teleporter Charge"],
    },
    "Xenoid / Junker / Rebel / Raider / Pirate Duel": {
        "aliases": ["xenoid duel", "junker duel", "rebel duel", "raider duel", "pirate duel", "duel"],
        "variants": "Covers Xenoid Duel, Junker Duel, Rebel Duel, Raider Duel, & Pirate Duel",
        "steps": ["Tactical Drone", "HyperShields", "Growton Torpedo", "AI Brain", "Growton Torpedo"],
    },
    "Extermination (Space Station / Moon / Cargo / Mining)": {
        "aliases": ["space station extermination", "moon extermination", "cargo ship extermination", "mining colony extermination", "extermination"],
        "variants": "Covers Space Station, Moon, Cargo Ship, & Mining Colony Extermination",
        "steps": ["Tactical Drone", "Teleporter Charge", "Quadriscanner", "Star Supplies", "Gigablaster", "Stellar Documents"],
    },
    "Shadow Stalkers": {
        "aliases": ["shadow stalkers", "shadow"],
        "variants": "9-Step Stealth Predator Hunt",
        "steps": ["Tactical Drone", "Teleporter Charge", "Quadriscanner", "AI Brain", "Gigablaster", "Teleporter Charge", "Quadriscanner", "Teleporter Charge", "Growton Torpedo"],
    },
    "Planet Calamity": {
        "aliases": ["planet calamity", "calamity"],
        "variants": "Planetary Catastrophe Evacuation",
        "steps": ["Tactical Drone", "Teleporter Charge", "AI Brain", "Teleporter Charge", "HyperShields", "Growton Torpedo", "Teleporter Charge"],
    },
    "Delivery (Scientific / Missile Base / Mining / Moon Base)": {
        "aliases": ["scientific outpost delivery", "missile base delivery", "mining colony delivery", "moon base delivery", "delivery"],
        "variants": "Covers Scientific Outpost, Missile Base, Mining Colony, & Moon Base Delivery",
        "steps": ["Tactical Drone", "Teleporter Charge", "Quadriscanner", "Gigablaster", "Star Supplies", "Teleporter Charge"],
    },
    "Who's There? / She's Gonna Blow!": {
        "aliases": ["whos there", "who's there", "shes gonna blow", "she's gonna blow"],
        "variants": "Covers both Who's There? and She's Gonna Blow!",
        "steps": ["Tactical Drone", "Teleporter Charge", "Quadriscanner", "AI Brain", "Quadriscanner", "Gigablaster", "Teleporter Charge"],
    },
    "Doing The Right Thing! / Secret Stash": {
        "aliases": ["doing the right thing", "secret stash"],
        "variants": "Covers both Doing The Right Thing! and Secret Stash",
        "steps": ["Tactical Drone", "HyperShields", "Teleporter Charge", "Gigablaster", "Quadriscanner", "Teleporter Charge"],
    },
    "Putting Down Roots": {
        "aliases": ["putting down roots", "roots"],
        "variants": "Colony Settlement Voyage",
        "steps": ["Tactical Drone", "Teleporter Charge", "Quadriscanner", "Cyborg Diplomat", "Stellar Documents", "Star Supplies"],
    },
    "Daydreamer": {
        "aliases": ["daydreamer"],
        "variants": "Hypnotic Anomaly Encounter",
        "steps": ["Tactical Drone", "Teleporter Charge", "Cyborg Diplomat", "Gigablaster"],
    },
    "A Tasty Bite": {
        "aliases": ["a tasty bite", "tasty bite"],
        "variants": "Hull-Eating Beast Encounter",
        "steps": ["Tactical Drone", "Cyborg Diplomat", "Galactibolt", "Quadriscanner", "AI Brain", "Galactibolt", "Growton Torpedo"],
    },
    "Rescue (Asteroid / Cargo Ship / Mining / Space Station / Moon)": {
        "aliases": ["asteroid rescue", "cargo ship rescue", "mining colony rescue", "space station rescue", "moon rescue", "rescue"],
        "variants": "Covers Asteroid, Cargo Ship, Mining Colony, Space Station, & Moon Rescue",
        "steps": ["Tactical Drone", "Teleporter Charge", "Cyborg Diplomat", "Space Meds", "Stellar Documents"],
    },
    "Planet Of Echoes": {
        "aliases": ["planet of echoes", "echoes"],
        "variants": "Sonic Planet Expedition",
        "steps": ["Tactical Drone", "Cyborg Diplomat", "Teleporter Charge", "Quadriscanner", "Gigablaster", "Teleporter Charge"],
    },
    "Prevent War": {
        "aliases": ["prevent war", "war"],
        "variants": "Interstellar Peacekeeping Mission",
        "steps": ["HyperShields", "Tactical Drone", "Cyborg Diplomat", "Teleporter Charge", "Stellar Documents", "Galactibolt", "Star Supplies"],
    },
    "Stuck In The Middle": {
        "aliases": ["stuck in the middle"],
        "variants": "Crossfire Mediation Voyage",
        "steps": ["Tactical Drone", "HyperShields", "AI Brain", "Cyborg Diplomat", "AI Brain"],
    },
    "Space Detective": {
        "aliases": ["space detective", "detective"],
        "variants": "Criminal Investigation Voyage",
        "steps": ["Tactical Drone", "Teleporter Charge", "Stellar Documents", "Growton Torpedo"],
    },
    "Doctor In The House!": {
        "aliases": ["doctor in the house", "doctor"],
        "variants": "Alien Medical Emergency",
        "steps": ["Tactical Drone", "Teleporter Charge", "Cyborg Diplomat", "Space Meds", "Gigablaster", "Cyborg Diplomat"],
    },
    "Cleanup (Space Junk / Asteroid / Radiation / Rocket Parts)": {
        "aliases": ["space junk cleanup", "asteroid cleanup", "radiation cleanup", "rocket parts cleanup", "cleanup"],
        "variants": "Covers Space Junk, Asteroid, Radiation, & Rocket Parts Cleanup",
        "steps": ["Tactical Drone", "HyperShields", "Growton Torpedo", "HyperShields", "Stellar Documents"],
    },
    "Gross Mistake": {
        "aliases": ["gross mistake"],
        "variants": "Bio-Hazard Containment Voyage",
        "steps": ["Tactical Drone", "Teleporter Charge", "Quadriscanner", "Gigablaster", "Star Supplies", "Teleporter Charge"],
    },
    "Relic Data / Mineral Data / Weird Contraption": {
        "aliases": ["relic data", "mineral data", "weird contraption"],
        "variants": "Covers Relic Data, Mineral Data, & Weird Contraption",
        "steps": ["Tactical Drone", "Teleporter Charge", "Quadriscanner", "Teleporter Charge", "Stellar Documents"],
    },
    "Blackout": {
        "aliases": ["blackout"],
        "variants": "Power Grid Failure Ambush",
        "steps": ["Galactibolt", "Tactical Drone", "HyperShields", "Growton Torpedo", "Growton Torpedo", "Galactibolt"],
    },
    "Lonely Little Droid": {
        "aliases": ["lonely little droid", "droid"],
        "variants": "Stranded Droid Encounter",
        "steps": ["Cyborg Diplomat", "Teleporter Charge", "Star Supplies", "Quadriscanner", "Gigablaster"],
    },
    "Doing The Job!": {
        "aliases": ["doing the job"],
        "variants": "Mercenary Contract Voyage",
        "steps": ["Tactical Drone", "Cyborg Diplomat", "Teleporter Charge", "Star Supplies", "Stellar Documents", "Teleporter Charge"],
    },
    "Space Opera": {
        "aliases": ["space opera", "opera"],
        "variants": "Galactic Theater Crisis",
        "steps": ["Tactical Drone", "Teleporter Charge", "Cyborg Diplomat", "Cyborg Diplomat", "Gigablaster", "Stellar Documents"],
    },
    "A New Home": {
        "aliases": ["a new home", "new home"],
        "variants": "9-Step Colonization Escort Voyage",
        "steps": ["Tactical Drone", "Cyborg Diplomat", "Growton Torpedo", "Cyborg Diplomat", "Star Supplies", "Space Meds", "HyperShields", "Growton Torpedo", "Cyborg Diplomat"],
    },
}


def build_ship_setup_embed() -> discord.Embed:
    """Builds the Startopia 2.0 Starship Construction, Equipment Rating, & Sector Guide."""
    embed = discord.Embed(
        title="🚀 Startopia 2.0 — How to Build Ships, Upgrade Rating, & Unlock Sectors",
        description=(
            "To start Star Voyages, create a **Starship World** using an **Imperial, Stellarix, Greezak, or HyperTech Starship Blast**. "
            "Every ship comes with 3 core blocks: **Helm** (starts voyages), **Reactor** (holds Star Fuel), and **Viewscreen** (checks ship stats).\n\n"
            "### 🏗️ 1. Upgrading Ship Rating (Helm + Reactor + Viewscreen)\n"
            "To unlock higher sectors, place higher-tier **Helms, Reactors, and Viewscreens** inside your ship:\n"
            "- **Imperial Mk.I / Mk.II / Mk.III:** `30` / `200` / `280` Rating each\n"
            "- **Stellarix Union Mk.I / Mk.II / Mk.III:** `720` / `900` / `1,080` Rating each\n"
            "- **Greezak Horde Mk.I / Mk.II / Mk.III:** `2,000` / `2,310` / `2,640` Rating each\n"
            "- **HyperTech Mk.I / Mk.II / Mk.III:** `4,200` / `4,690` / `5,200` Rating each\n\n"
            "### 🛡️ 2. Reducing Skill Fails (Support Consoles & Gear)\n"
            "- **Oracle Science Station (Mk.I–III):** Reduces **Ship Hull** skill fails (+ wear *Engineer Class Uniform*)\n"
            "- **Vitahope Life Support (Mk.I–III):** Reduces **Crew Health** skill fails (+ wear *Medic Class Uniform*)\n"
            "- **Bastion Tactical Console (Mk.I–III):** Reduces **Reputation** skill fails (+ wear *Command Class Uniform*)\n"
            "- **Skill Spice (Consumable):** Cuts skill fail chance by **50%**! **Captain's Log:** Chance to save Star Tools.\n\n"
            "### 🌌 3. Startopia 2.0 Sectors & Growlactus\n"
            "Progress through **Alpha → Beta → Delta → Epsilon → The Galactic Nexus → Growlactus**:\n"
            "- 🏆 **Beat Growlactus:** Unlocks **The Heart of the Galaxy (Ascended Sector)** — drops *Arm Blaster, Crystal Aura, Exo Suit Body/Helmet, Moon Lamp*!\n"
            "- 💀 **Lose to Growlactus:** Unlocks **The Desolated Waste (Descended Sector)** — drops *My Pet Sputnik, Space Tattoo, Escapee's Collar, Space Junk*!\n"
            "- ⚔️ Land 500 ships in both sectors to earn the **Interstellar Tycoon** achievement & **Crystal Infused Sword**!"
        ),
        color=0x8E44AD,
        timestamp=datetime.now(EVENT_TZ),
    )
    embed.set_footer(text=FOOTER_TEXT)
    return embed


class StartopiaHelperView(discord.ui.View):
    """Interactive buttons for Random Mid-Voyage Encounters, Emergency Healing, and Ship Setup."""

    def __init__(self) -> None:
        super().__init__(timeout=600)

    @discord.ui.button(label="Mid-Voyage Encounters", emoji="🛸", style=discord.ButtonStyle.primary)
    async def encounters_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        embed = discord.Embed(
            title="🛸 Startopia — Random Mid-Voyage Encounters & Popups",
            description=(
                "During any Star Voyage, a random emergency popup can interrupt your sequence! "
                "Use the matching tool below to clear the interruption, then continue your normal mission steps:\n\n"
                "- 🤖 **Cyborg Diplomat:**\n"
                "  *\"Grumpy Ambassador\"* OR *\"Your communicators burst into life! It's your mother!\"*\n"
                "- 🧠 **AI Brain:**\n"
                "  *\"Pirates are hacking our computer systems!\"* OR *\"Star Command popups when they hail you!\"*\n"
                "- 💊 **Space Meds:**\n"
                "  *\"The reactor's leaking radiation!\"*\n"
                "- 📜 **Stellar Documents:**\n"
                "  *\"Misfiled documents\"* OR *\"Contacted by a bureaucrat from Laymtak II\"*\n"
                "- 🚀 **Growton Torpedo:**\n"
                "  *\"A wing of pirate ships swoops in!\"* / *\"Grinding sound outside\"* / *\"Test fire of the Torpedoes\"*\n"
                "- 🛡️ **HyperShields:**\n"
                "  *\"Silicoid Worms attached to shields!\"* / *\"Shield Generator fluctuating\"* / *\"Space Debris\"*\n"
                "- 🔫 **Gigablaster:**\n"
                "  *\"Rabid space dogs\"* / *\"Disloyal crew\"* / *\"Space snakes attack\"*\n"
                "- 🔧 **Galactibolt:**\n"
                "  *\"Main cargo door isn't opening\"* / *\"Left engine hanging off\"* / *\"Lights failing\"* / *\"Plumbing isn't working\"* / *\"Oxygen leak!\"*\n"
                "- 📦 **Star Supplies:**\n"
                "  *\"Refugees of the local starvation crisis are blaming us for it!\"*"
            ),
            color=0x3498DB,
            timestamp=datetime.now(EVENT_TZ),
        )
        embed.set_footer(text=FOOTER_TEXT)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Low Hull / Crew / Rep Fix", emoji="❤️", style=discord.ButtonStyle.danger)
    async def emergency_stats_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        embed = discord.Embed(
            title="❤️ Emergency Ship Hull, Crew Health, & Reputation Recovery",
            description=(
                "If **Ship Hull**, **Crew Health**, or **Reputation** drops to `0%–1%`, your voyage fails and consumes Star Fuel!\n\n"
                "- 🔧 **Ship Hull Low?** → Use **`Galactibolt`** immediately to repair the ship.\n"
                "- 💊 **Crew Health Low?** → Use **`Space Meds`** immediately to heal the crew.\n"
                "- 📦 **Reputation Low?** → Use **`Star Supplies`** immediately to restore reputation.\n"
                "- 🔁 **Got a Skill Fail?** → Do **NOT** skip to the next step! Click the **exact same tool again** until it succeeds, then continue the sequence."
            ),
            color=0xE74C3C,
            timestamp=datetime.now(EVENT_TZ),
        )
        embed.set_footer(text=FOOTER_TEXT)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Ship Setup & Startopia 2.0 Sectors", emoji="🚀", style=discord.ButtonStyle.secondary)
    async def ship_setup_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.send_message(embed=build_ship_setup_embed(), ephemeral=True)


class StarCaptainCog(commands.Cog, name="Star Captain"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def startrek_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        q = current.strip().lower()
        matches: list[app_commands.Choice[str]] = []
        for name, info in STARTOPIA_MISSIONS.items():
            aliases = info.get("aliases", [])
            variants = info.get("variants", "").lower()
            if not q or q in name.lower() or q in variants or any(q in a for a in aliases):
                matches.append(app_commands.Choice(name=name[:100], value=name))
        return matches[:25]

    @app_commands.command(
        name="startrek",
        description="Startopia 2.0 Voyage & Ship Mission Guide: exact tool order for all 46+ missions & sectors!",
    )
    @app_commands.describe(
        station_or_sector="Type the Startopia Mission name shown on your Helm (e.g. Parasite Hunt, Rebel Attack, Growlactus)"
    )
    @app_commands.autocomplete(station_or_sector=startrek_autocomplete)
    async def startrek_command(self, interaction: discord.Interaction, station_or_sector: str) -> None:
        query = station_or_sector.strip().lower()
        matched_key = None
        for name, info in STARTOPIA_MISSIONS.items():
            aliases = info.get("aliases", [])
            variants = info.get("variants", "").lower()
            if query == name.lower() or query in name.lower() or query in variants or any(query in a for a in aliases):
                matched_key = name
                break

        if not matched_key:
            await interaction.response.send_message(
                f"❌ Could not find a Startopia mission matching **`{station_or_sector}`**. "
                "Try typing the mission title shown on your Starship Helm (e.g. `Parasite Hunt`, `Warp Data`, `Rebel Attack`, `Growlactus`, or `Ship Setup`)!",
                ephemeral=True,
            )
            return

        info = STARTOPIA_MISSIONS[matched_key]
        if info.get("is_setup_guide"):
            await interaction.response.send_message(
                embed=build_ship_setup_embed(),
                view=StartopiaHelperView(),
            )
            return

        steps: list[str] = info["steps"]
        step_lines = []
        for idx, tool_name in enumerate(steps, start=1):
            icon = TOOL_ICONS.get(tool_name, "🔹")
            step_lines.append(f"**Step {idx}.** {icon} **{tool_name}**")

        counts = Counter(steps)
        summary_badges = "  •  ".join(
            f"{TOOL_ICONS.get(t, '🔹')} `{qty}x` {t}" for t, qty in counts.items()
        )

        embed = discord.Embed(
            title=f"🚀 Startopia 2.0 Voyage Guide: {matched_key}",
            description=f"📌 *{info['variants']}*\n\nClick the Star Tools below **in exact order** from Step 1 to Step {len(steps)}:",
            color=0x3498DB,
            timestamp=datetime.now(EVENT_TZ),
        )
        embed.add_field(
            name=f"🔢 Tool Order ({len(steps)} Steps)",
            value="\n".join(step_lines),
            inline=False,
        )
        embed.add_field(
            name="🎒 Minimum Tools Required (Before Skill Fails)",
            value=summary_badges,
            inline=False,
        )
        embed.add_field(
            name="💡 Pro Tips During Voyage",
            value=(
                "- **Skill Fail?** Repeat the **exact same tool** again before moving to the next step!\n"
                "- **Random Popup Encounter?** Click **`🛸 Mid-Voyage Encounters`** below to see which tool clears it."
            ),
            inline=False,
        )
        embed.set_footer(text=FOOTER_TEXT)
        await interaction.response.send_message(embed=embed, view=StartopiaHelperView())

    @app_commands.command(
        name="set_startrek_channel",
        description="Lock the /startrek command to a specific channel (e.g. #🚀star-captain)",
    )
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(channel="The channel where /startrek is allowed (defaults to current channel)")
    async def set_startrek_channel_command(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel | None = None,
    ) -> None:
        if not is_server_manager(interaction):
            await interaction.response.send_message("❌ Only server admins can use `/set_startrek_channel`.", ephemeral=True)
            return
        target_channel = channel or interaction.channel
        if not isinstance(target_channel, discord.TextChannel):
            await interaction.response.send_message("❌ Please select a standard text channel.", ephemeral=True)
            return
        state = load_state()
        state["startrek_channel_id"] = target_channel.id
        save_state(state)
        await interaction.response.send_message(
            f"✅ Locked **`/startrek`** to {target_channel.mention}! Players can now only use `/startrek` inside {target_channel.mention}."
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(StarCaptainCog(bot))
