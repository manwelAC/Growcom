"""
Category 11: Fishing Lure & Fish Training Guide (cogs/fishing_guide.py)
- /fish (Shows catchable fish, weight ranges, rod recommendations, and Fish Port training guide for every Growtopia Lure/Bait)
- /set_fish_channel (Admin channel lock + instruction card)
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


FISHING_DATABASE: dict[str, dict[str, Any]] = {
    "Shrimp Lure": {
        "tier": "⭐⭐⭐⭐ High-Tier Standard Lure",
        "water_type": "🌊 Standard Water / Deep Ocean",
        "best_rods": "Licorice Rod • Poseidon's Trident • Bamboo Rod",
        "catchable_fish": [
            "🐟 **Mahi Mahi** (`25 – 120 lbs`)",
            "🐋 **Whale** (`80 – 200 lbs` — Can also be used as Giant Bait!)",
            "🦈 **Orca / Swordfish** (`60 – 195 lbs`)",
            "🦴 **Coelacanth** (`50 – 180 lbs` — Rare Ancient Fish)",
            "🦞 **Lobster / Crab** (`10 – 65 lbs`)",
        ],
        "rewards": "• Slice with **Fillet Knife** for **Fish Chunks** & **Sushi Knife** drops.\n• **Fishing Role Day:** High chance for **Crustacean Blocks**, **Tackle Box** items, & **Fishing XP**.",
        "pro_tip": "Shrimp Lure is the most consistent all-around lure for both **Fish Frenzy** points (1 pt per lb) and **Fishing Role Quests**!",
        "sprite_item": "Shrimp Lure",
    },
    "Uranium Glowing Lure": {
        "tier": "☢️⭐⭐⭐⭐⭐ Special Radioactive Lure",
        "water_type": "☢️ Irradiated / Glowing Water (Geiger Water)",
        "best_rods": "Geiger Rod • Licorice Rod",
        "catchable_fish": [
            "☢️ **Mutant Fish / Three-Eyed Fish** (`15 – 150 lbs`)",
            "🐟 **Glowing Guardfish** (`30 – 160 lbs`)",
            "🦈 **Radioactive Piranha** (`20 – 110 lbs`)",
        ],
        "rewards": "• Slicing Mutant Fish yields **Green / Red / Blue / Yellow / Purple Chemicals**!\n• Rare chance for **Uranium**, **Geiger Charger** parts, and **Mutant Kitchen** ingredients.",
        "pro_tip": "You MUST fish inside water that has been irradiated (glowing green water) for Uranium Glowing Lure to catch Mutant Fish!",
        "sprite_item": "Uranium Glowing Lure",
    },
    "Wiggly Worm": {
        "tier": "⭐ Starter Bait (Tackle Box Staple)",
        "water_type": "🌊 Any Water Block",
        "best_rods": "Bamboo Rod • Hickory Rod • Licorice Rod",
        "catchable_fish": [
            "🐟 **Bass & Sunfish** (`1 – 35 lbs`)",
            "🐠 **Goldfish & Guppy** (`1 – 15 lbs`)",
            "🐟 **Catfish** (`10 – 55 lbs`)",
            "🐟 **Salmon** (`15 – 70 lbs` — Save these to use as Giant Bait!)",
        ],
        "rewards": "• Cheap, fast catches for early **Fishing Role Level 1–3** quests.\n• Slicing small fish yields **Fish Flakes** (used to feed & train fish in Fish Tanks!).",
        "pro_tip": "Slice small `<20 lb` fish with a **Fillet Knife** to stock up on **Fish Flakes** for Fish Port training!",
        "sprite_item": "Wiggly Worm",
    },
    "Fishing Fly": {
        "tier": "⭐⭐ Fast-Bite Surface Lure",
        "water_type": "🌊 Standard Water",
        "best_rods": "Hickory Rod • Licorice Rod",
        "catchable_fish": [
            "🐟 **Salmon** (`20 – 85 lbs`)",
            "🐟 **Catfish & Bass** (`10 – 65 lbs`)",
            "🐟 **Gar** (`25 – 95 lbs`)",
            "🐟 **Mahi Mahi** (`30 – 110 lbs`)",
        ],
        "rewards": "• Faster bite speed than Wiggly Worm.\n• Great source of **Salmon** (which can be used as bait itself for 150+ lb catches!).",
        "pro_tip": "Pair `Fishing Fly` with a **Reel** buff (`Fast Reel`) during **Fish Frenzy** for rapid medium-weight catches.",
        "sprite_item": "Fishing Fly",
    },
    "Shiny Flashy Thing": {
        "tier": "⭐⭐⭐ Medium-Heavy Metal Lure",
        "water_type": "🌊 Standard Water",
        "best_rods": "Licorice Rod • Hickory Rod",
        "catchable_fish": [
            "🐟 **Mahi Mahi & Gar** (`35 – 125 lbs`)",
            "🦈 **Dogfish & Pike** (`40 – 140 lbs`)",
            "🐋 **Orca** (`70 – 175 lbs`)",
        ],
        "rewards": "• Higher average weight (`lbs`) per catch than Worms or Flies.\n• Occasional bonus treasure/junk pulls when used with Magnet rods.",
        "pro_tip": "Great mid-budget lure when you run out of Shrimp Lures from your Tackle Boxes.",
        "sprite_item": "Shiny Flashy Thing",
    },
    "Salmon (Used as Bait)": {
        "tier": "⭐⭐⭐⭐⭐ Giant Trophy Bait",
        "water_type": "🌊 Deep Water",
        "best_rods": "Licorice Rod • Poseidon's Trident",
        "catchable_fish": [
            "🐋 **Whale** (`100 – 200 lbs`)",
            "🦈 **Orca & Giant Swordfish** (`90 – 195 lbs`)",
            "🦴 **Coelacanth** (`80 – 190 lbs`)",
            "🦞 **Giant Lobster** (`50 – 120 lbs`)",
        ],
        "rewards": "• Massive `100–200 lb` catches for **Fish Frenzy** Daily Challenge (`+100 to +200 pts` in a single catch!).\n• Best way to catch **Whales** or **Perfect 200 lb Trophy Fish**.",
        "pro_tip": "Yes, you can equip a caught **Salmon** directly as bait on your Fishing Rod! It filters out tiny fish so only giants bite.",
        "sprite_item": "Salmon",
    },
    "Mega-Pellet (Fish Training Guide)": {
        "tier": "🏆 Fish Port / Fish Tank Training System",
        "water_type": "🏺 Placed inside a **Fish Port** block",
        "best_rods": "N/A — Used by feeding fish inside a Fish Port",
        "catchable_fish": [
            "🐠 **Trained Fish:** Any fish placed inside a **Fish Port** can be fed **Fish Flakes** & **Mega-Pellets** to grow heavier and learn tricks!",
            "🏆 **Perfect Fish:** Raising a fish smoothly without starving or overfeeding turns it into a glowing **Perfect Fish**!",
        ],
        "rewards": "• **Trained / Perfect Fish** can be mounted on **Fish Wall Mounts** or used for high-tier **Fishing Role Quests**.\n• **Mega-Pellet** instantly boosts growth & training progress without waiting full hunger cycles.",
        "pro_tip": "Check your Fish Port status before feeding: only feed **Fish Flakes** when the fish is **Hungry**, and keep water clean so it doesn't get sick!",
        "sprite_item": "Mega-Pellet",
    },
}


class FishingGuideCog(commands.Cog, name="Fishing Guide"):
    def __init__(self, bot: EventBot) -> None:
        self.bot = bot

    async def lure_autocomplete(
        self,
        _interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        query = current.strip().lower()
        choices: list[app_commands.Choice[str]] = []
        for name, info in FISHING_DATABASE.items():
            if not query or query in name.lower() or query in info["tier"].lower() or query in info["water_type"].lower():
                label = f"{name} — {info['tier']}"
                choices.append(app_commands.Choice(name=label[:100], value=name))
        return choices[:25]

    @app_commands.command(
        name="set_fish_channel",
        description="Restrict the /fish lure & training guide exclusively to a dedicated channel",
    )
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(channel="Dedicated channel for /fish lookups (defaults to current channel)")
    async def set_fish_channel_command(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel | None = None,
    ) -> None:
        if not is_server_manager(interaction):
            await interaction.response.send_message(
                "❌ Only server admins can use `/set_fish_channel`.",
                ephemeral=True,
            )
            return
        await interaction.response.defer()
        target_channel = channel or interaction.channel
        if not isinstance(target_channel, discord.TextChannel):
            await interaction.followup.send("❌ Please select a standard text channel.", ephemeral=True)
            return

        state = load_state()
        state["fish_channel_id"] = target_channel.id
        save_state(state)

        guide_embed = discord.Embed(
            title="🎣 Growcom Fishing Lure & Fish Training Guide",
            description=(
                "Use **`/fish`** in this channel to check which **Lure / Bait** catches which fish, "
                "expected **pound (`lb`) ranges**, **Fillet Knife rewards**, and how **Fish Port training** works!\n\n"
                "**Covered Lures & Guides:**\n"
                "• 🦐 **Shrimp Lure** • ☢️ **Uranium Glowing Lure** • 🪱 **Wiggly Worm**\n"
                "• 🪰 **Fishing Fly** • ✨ **Shiny Flashy Thing** • 🐟 **Salmon (Giant Bait)**\n"
                "• 🏆 **Mega-Pellet (Fish Tank Training Guide)**"
            ),
            color=discord.Color.from_rgb(26, 188, 156),
        )
        guide_embed.set_footer(text=FOOTER_TEXT)
        await target_channel.send(embed=guide_embed)

        await interaction.followup.send(
            f"✅ Locked **`/fish`** exclusively to {target_channel.mention}! "
            f"Players trying to run `/fish` anywhere else will be redirected to {target_channel.mention}.",
            ephemeral=True,
        )

    @app_commands.command(
        name="fish",
        description="Look up any Growtopia Fishing Lure's catchable fish, lb weights, rod pairings, & training tips!",
    )
    @app_commands.describe(
        lure="Select a Lure, Bait, or Training Guide (e.g. Shrimp Lure, Uranium Glowing Lure, Wiggly Worm, Mega-Pellet)"
    )
    @app_commands.autocomplete(lure=lure_autocomplete)
    async def fish_command(self, interaction: discord.Interaction, lure: str) -> None:
        state = load_state()
        allowed_channel_id = state.get("fish_channel_id")
        if allowed_channel_id and int(interaction.channel_id or 0) != int(allowed_channel_id):
            await interaction.response.send_message(
                f"❌ The **`/fish`** guide can only be used inside <#{allowed_channel_id}>!",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        matched_name: str | None = None
        for name in FISHING_DATABASE:
            if name.lower() == lure.strip().lower():
                matched_name = name
                break
        if not matched_name:
            for name in FISHING_DATABASE:
                if lure.strip().lower() in name.lower():
                    matched_name = name
                    break

        if not matched_name:
            await interaction.followup.send(
                f"❌ Could not find a fishing lure matching **`{lure}`**. Please pick one from the `/fish` autocomplete list!",
                ephemeral=True,
            )
            return

        info = FISHING_DATABASE[matched_name]
        embed = discord.Embed(
            title=f"🎣 Fishing Guide — {matched_name}",
            description=f"**{info['tier']}**",
            color=discord.Color.from_rgb(26, 188, 156),
        )
        embed.add_field(
            name="🌊 Water Required",
            value=info["water_type"],
            inline=True,
        )
        embed.add_field(
            name="🎣 Best Rod Pairing",
            value=f"`{info['best_rods']}`",
            inline=True,
        )
        embed.add_field(
            name="🐟 Catchable Fish & Weight Range (lbs)",
            value="\n".join(f"• {f}" for f in info["catchable_fish"]),
            inline=False,
        )
        embed.add_field(
            name="🎁 Slicing & Role Day Rewards",
            value=info["rewards"],
            inline=False,
        )
        embed.add_field(
            name="💡 Pro Angler Tip",
            value=info["pro_tip"],
            inline=False,
        )

        files: list[discord.File] = []
        sprite_bytes = await self.bot.api.get_item_sprite(info.get("sprite_item", "Shrimp Lure"))
        if sprite_bytes:
            files.append(discord.File(BytesIO(sprite_bytes), filename="sprite.png"))
            embed.set_thumbnail(url="attachment://sprite.png")

        embed.set_footer(text=FOOTER_TEXT)
        await interaction.followup.send(embed=embed, files=files)


async def setup(bot: EventBot) -> None:
    await bot.add_cog(FishingGuideCog(bot))
