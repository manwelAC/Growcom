"""
Category 10: Crimefighter & Supervillain Counter Cheat-Sheet (cogs/crime_helper.py)
- /crime (Recommended 5-Card Deck, Immunities/Weaknesses, and Turn-by-Turn Counter Cycle for every Growtopia Supervillain)
- /set_crime_channel (Admin channel lock + instruction card)
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


CRIME_VILLAINS: dict[str, dict[str, Any]] = {
    "Ms. Terry": {
        "level": "⭐ Crime Level 1 (Starter Villain)",
        "immunities": "None",
        "weakness": "❄️ Ice Breath + 👊 Super Strength / 👀 Heat Vision",
        "deck": "❄️ `Ice Breath` • 👀 `Heat Vision` • 👊 `Super Strength` • ⚡ `Super Speed` • 💚 `Regeneration`",
        "strategy": [
            "1️⃣ **Turn 1:** Open with **`Ice Breath`** to freeze Ms. Terry.",
            "2️⃣ **Turn 2:** Hit her with **`Super Strength`** or **`Heat Vision`** while she is frozen.",
            "3️⃣ **Turn 3:** Use **`Super Speed`** when she winds up her attack to dodge 100% of the damage, then repeat!",
        ],
        "pro_tip": "Ms. Terry has no elemental immunities, making her the easiest villain to farm on Card Clash day.",
        "sprite_item": "Crime Wave",
    },
    "Dragonhand": {
        "level": "⭐⭐⭐ Crime Level 3 (Fire Martial Artist)",
        "immunities": "🔥 **IMMUNE TO FIRE** (`Heat Vision`, `Incinerate`, `Flame`, `Liquefy` deal 0 damage!)",
        "weakness": "❄️ **2x Damage from ICE** (`Ice Breath`, `Frost`, `Puddle`)",
        "deck": "❄️ `Ice Breath` • 🧊 `Frost` • 💧 `Puddle` • 👊 `Super Strength` • ⚡ `Super Speed`",
        "strategy": [
            "1️⃣ **REMOVE ALL FIRE CARDS** (`Heat Vision` / `Incinerate`) from your deck before fighting Dragonhand!",
            "2️⃣ **Turn 1:** Use **`Puddle`** or **`Ice Breath`** (deals **2x Weakness Damage** and freezes him).",
            "3️⃣ **Turn 2:** Use **`Frost`** or **`Super Strength`** while he is frozen.",
            "4️⃣ **Turn 3:** Use **`Super Speed`** to dodge his **Dragon Fist** strike, then freeze him again!",
        ],
        "pro_tip": "Combining `Puddle` + `Ice Breath` + `Frost` melts Dragonhand in just 3–4 turns!",
        "sprite_item": "Super Superhero Mask",
    },
    "Shockinator": {
        "level": "⭐⭐ Crime Level 2–3 (Electric Villain)",
        "immunities": "⚡ **IMMUNE TO ELECTRIC** (`Shock`, `Overcharge`, `Lightning` deal 0 damage!)",
        "weakness": "👊 **Physical / Brawn** (`Super Strength`, `Crush`) & ❄️ **Ice** (`Ice Breath`)",
        "deck": "❄️ `Ice Breath` • 👊 `Super Strength` • 🪨 `Crush` • ⚡ `Super Speed` • 💚 `Regeneration`",
        "strategy": [
            "1️⃣ **Never bring Electric cards** (`Shock` / `Overcharge`).",
            "2️⃣ **Turn 1:** Freeze him with **`Ice Breath`**.",
            "3️⃣ **Turn 2:** Smash him with **`Crush`** or **`Super Strength`** while frozen.",
            "4️⃣ **Turn 3:** Dodge his **Mega-Volt** blast using **`Super Speed`**, then heal with **`Regeneration`** if needed.",
        ],
        "pro_tip": "Always save `Super Speed` or `Ice Breath` for the turn right after he charges up Electricity!",
        "sprite_item": "Crime Wave",
    },
    "The Hulk (Muscleman)": {
        "level": "⭐⭐⭐ Crime Level 3 (Physical Brute)",
        "immunities": "🛡️ **High Physical Resistance** (`Super Strength` / `Crush` deal reduced damage unless weakened)",
        "weakness": "🔥 **Fire** (`Heat Vision`, `Incinerate`) & ⚡ **Electric** (`Shock`, `Overcharge`)",
        "deck": "❄️ `Ice Breath` • 👀 `Heat Vision` • 🔥 `Incinerate` • 😡 `Enrage` • ⚡ `Super Speed`",
        "strategy": [
            "1️⃣ **Turn 1:** Freeze him with **`Ice Breath`** so he can't smash you.",
            "2️⃣ **Turn 2:** Activate **`Enrage`** (boosts your next attack) ➔ **`Incinerate`** or **`Heat Vision`**.",
            "3️⃣ **Turn 3:** Whenever he uses **Enrage / Smash**, immediately counter with **`Super Speed`** to dodge!",
        ],
        "pro_tip": "Never trade raw punches with Muscleman while he is Enraged — always Freeze or Dodge his Enraged turn!",
        "sprite_item": "Super Superhero Jersey",
    },
    "Frozen Fiona": {
        "level": "⭐⭐⭐ Crime Level 3 (Ice Villain)",
        "immunities": "❄️ **IMMUNE TO ICE** (`Ice Breath`, `Frost`, `Freeze` do NOT work on her!)",
        "weakness": "🔥 **2x Damage from FIRE** (`Heat Vision`, `Incinerate`, `Flame`, `Liquefy`)",
        "deck": "👀 `Heat Vision` • 🔥 `Incinerate` • 😡 `Enrage` • ⚡ `Super Speed` • 💚 `Regeneration`",
        "strategy": [
            "1️⃣ **REMOVE `Ice Breath`!** She cannot be frozen by Ice cards!",
            "2️⃣ **Turn 1:** Use **`Enrage`** or **`Liquefy`** to amplify fire damage.",
            "3️⃣ **Turn 2:** Blast her with **`Incinerate`** + **`Heat Vision`** for massive 2x Fire damage!",
            "4️⃣ **Turn 3:** Use **`Super Speed`** to dodge her Freeze Ray so you don't lose a turn.",
        ],
        "pro_tip": "Because you can't freeze her with `Ice Breath`, `Super Speed` and `Regeneration` are your main defensive cards.",
        "sprite_item": "Super Eye Mask",
    },
    "Big Bertha": {
        "level": "⭐⭐⭐⭐ Crime Level 4 (Heavy Tank Boss)",
        "immunities": "🛡️ **High HP & Armor** (Takes several rotations to bring down)",
        "weakness": "❄️ Freeze-Lock Cycle (`Ice Breath` + `Super Speed` + `Heat Vision`)",
        "deck": "❄️ `Ice Breath` • 👀 `Heat Vision` • 👊 `Super Strength` • ⚡ `Super Speed` • 💚 `Regeneration`",
        "strategy": [
            "1️⃣ **Turn 1:** **`Ice Breath`** to freeze Big Bertha.",
            "2️⃣ **Turn 2:** **`Heat Vision`** (or **`Super Strength`**) while she is frozen.",
            "3️⃣ **Turn 3:** **`Super Speed`** to dodge her heavy **Body Slam**.",
            "4️⃣ **Turn 4:** **`Regeneration`** (or **`Super Strength`**), then immediately loop back to **`Ice Breath`**!",
        ],
        "pro_tip": "Don't get greedy on Turn 3 — if you don't dodge her Body Slam with `Super Speed`, it takes a huge chunk of HP!",
        "sprite_item": "Crime Wave",
    },
    "Cursed Spirit": {
        "level": "⭐⭐⭐⭐ Crime Level 4 (Ghost / Ethereal Boss)",
        "immunities": "👻 **100% IMMUNE TO PHYSICAL** (`Super Strength`, `Crush`, `Pummel` deal **0 damage**!)",
        "weakness": "🔥 **Energy / Elemental Only** (`Heat Vision`, `Incinerate`, `Ice Breath`, `Shock`)",
        "deck": "❄️ `Ice Breath` • 👀 `Heat Vision` • 🔥 `Incinerate` • ⚡ `Shock` • ⚡ `Super Speed`",
        "strategy": [
            "1️⃣ **REMOVE ALL PHYSICAL CARDS** (`Super Strength`, `Crush`) — physical punches pass right through ghosts!",
            "2️⃣ **Turn 1:** Freeze with **`Ice Breath`**.",
            "3️⃣ **Turn 2:** Hit with **`Heat Vision`** or **`Incinerate`**.",
            "4️⃣ **Turn 3:** Dodge with **`Super Speed`**, then hit with **`Shock`** and repeat **`Ice Breath`**!",
        ],
        "pro_tip": "Pure elemental decks (`Ice Breath` + `Heat Vision` + `Incinerate` + `Shock` + `Super Speed`) beat Cursed Spirit effortlessly.",
        "sprite_item": "Ghost Jar",
    },
    "Dr. Destructo": {
        "level": "⭐⭐⭐⭐⭐ Crime Level 5 (Final Arch-Villain Boss!)",
        "immunities": "🤖 **Boss Resistance + Deadly Doomsday Ray**",
        "weakness": "🔄 **Strict 4-Turn Freeze & Dodge Lock**",
        "deck": "❄️ `Ice Breath` • ⚡ `Super Speed` • 👀 `Heat Vision` • 👊 `Super Strength` • 💚 `Regeneration`",
        "strategy": [
            "1️⃣ **Turn 1:** Use **`Ice Breath`** to freeze Dr. Destructo.",
            "2️⃣ **Turn 2:** Use **`Heat Vision`** (or **`Super Strength`**) while he is frozen.",
            "3️⃣ **Turn 3:** Use **`Super Speed`** to dodge his **Doomsday Laser** while your `Ice Breath` is on cooldown!",
            "4️⃣ **Turn 4:** Use **`Regeneration`** (if hurt) or **`Super Strength`**, then immediately repeat **`Ice Breath`** on Turn 5!",
        ],
        "pro_tip": "Never use `Ice Breath` and `Super Speed` on the same turn! Stagger them (`Ice Breath` ➔ Attack ➔ `Super Speed`) so Dr. Destructo never lands a clean hit!",
        "sprite_item": "Crime Wave",
    },
}


class CrimeHelperCog(commands.Cog, name="Crime Helper"):
    def __init__(self, bot: EventBot) -> None:
        self.bot = bot

    async def villain_autocomplete(
        self,
        _interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        query = current.strip().lower()
        choices: list[app_commands.Choice[str]] = []
        for name, info in CRIME_VILLAINS.items():
            if not query or query in name.lower() or query in info["level"].lower() or query in info["immunities"].lower():
                label = f"{name} — {info['level']}"
                choices.append(app_commands.Choice(name=label[:100], value=name))
        return choices[:25]

    @app_commands.command(
        name="set_crime_channel",
        description="Restrict the /crime villain counter cheat-sheet exclusively to a dedicated channel",
    )
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(channel="Dedicated channel for /crime lookups (defaults to current channel)")
    async def set_crime_channel_command(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel | None = None,
    ) -> None:
        if not is_server_manager(interaction):
            await interaction.response.send_message(
                "❌ Only server admins can use `/set_crime_channel`.",
                ephemeral=True,
            )
            return
        await interaction.response.defer()
        target_channel = channel or interaction.channel
        if not isinstance(target_channel, discord.TextChannel):
            await interaction.followup.send("❌ Please select a standard text channel.", ephemeral=True)
            return

        state = load_state()
        state["crime_channel_id"] = target_channel.id
        save_state(state)

        guide_embed = discord.Embed(
            title="🦸 Growcom Crimefighter & Supervillain Counter Guide",
            description=(
                "Use **`/crime`** in this channel to see the exact **Recommended 5-Card Deck**, "
                "**Elemental Immunities**, and **Turn-by-Turn Counter Strategy** for any Growtopia Supervillain!\n\n"
                "**Covered Supervillains:**\n"
                "• ⭐ **Ms. Terry** • ⚡ **Shockinator** • 🔥 **Dragonhand**\n"
                "• 💪 **The Hulk (Muscleman)** • ❄️ **Frozen Fiona** • 🛡️ **Big Bertha**\n"
                "• 👻 **Cursed Spirit** • 🤖 **Dr. Destructo**"
            ),
            color=discord.Color.from_rgb(52, 152, 219),
        )
        guide_embed.set_footer(text=FOOTER_TEXT)
        await target_channel.send(embed=guide_embed)

        await interaction.followup.send(
            f"✅ Locked **`/crime`** exclusively to {target_channel.mention}! "
            f"Players trying to run `/crime` anywhere else will be redirected to {target_channel.mention}.",
            ephemeral=True,
        )

    @app_commands.command(
        name="crime",
        description="Instant Crimefighter 5-Card Deck, Immunities, and Turn-by-Turn Counter Guide for any Supervillain!",
    )
    @app_commands.describe(
        villain="Select the Supervillain (e.g. Dr. Destructo, Dragonhand, Ms. Terry, Shockinator, Cursed Spirit)"
    )
    @app_commands.autocomplete(villain=villain_autocomplete)
    async def crime_command(self, interaction: discord.Interaction, villain: str) -> None:
        state = load_state()
        allowed_channel_id = state.get("crime_channel_id")
        if allowed_channel_id and int(interaction.channel_id or 0) != int(allowed_channel_id):
            await interaction.response.send_message(
                f"❌ The **`/crime`** helper can only be used inside <#{allowed_channel_id}>!",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        matched_name: str | None = None
        for name in CRIME_VILLAINS:
            if name.lower() == villain.strip().lower():
                matched_name = name
                break
        if not matched_name:
            for name in CRIME_VILLAINS:
                if villain.strip().lower() in name.lower():
                    matched_name = name
                    break

        if not matched_name:
            await interaction.followup.send(
                f"❌ Could not find a villain matching **`{villain}`**. Please select a villain from the `/crime` autocomplete list!",
                ephemeral=True,
            )
            return

        info = CRIME_VILLAINS[matched_name]
        embed = discord.Embed(
            title=f"🦸 Crimefighter Guide — {matched_name}",
            description=f"**{info['level']}**\n\n🃏 **Recommended 5-Card Deck:**\n{info['deck']}",
            color=discord.Color.from_rgb(52, 152, 219),
        )
        embed.add_field(
            name="🚫 Villain Immunities",
            value=info["immunities"],
            inline=True,
        )
        embed.add_field(
            name="🎯 Best Weakness / Counter",
            value=info["weakness"],
            inline=True,
        )
        embed.add_field(
            name="📋 Turn-by-Turn Counter Strategy",
            value="\n".join(info["strategy"]),
            inline=False,
        )
        embed.add_field(
            name="💡 Pro Crimefighter Tip",
            value=info["pro_tip"],
            inline=False,
        )

        files: list[discord.File] = []
        sprite_bytes = await self.bot.api.get_item_sprite(info.get("sprite_item", "Crime Wave"))
        if sprite_bytes:
            files.append(discord.File(BytesIO(sprite_bytes), filename="sprite.png"))
            embed.set_thumbnail(url="attachment://sprite.png")

        embed.set_footer(text=FOOTER_TEXT)
        await interaction.followup.send(embed=embed, files=files)


async def setup(bot: EventBot) -> None:
    await bot.add_cog(CrimeHelperCog(bot))
