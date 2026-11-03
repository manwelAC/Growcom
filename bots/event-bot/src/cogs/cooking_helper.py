"""
Category 9: Cooking Oven Timeline & Ingredient Calculator (cogs/cooking_helper.py)
- /cook (Exact second-by-second Home Oven timeline, Heat setting, Buff effect, and Ingredient Shopping List for 1–200 ovens)
- /set_cook_channel (Admin channel lock + instruction card)
"""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import TYPE_CHECKING, Any

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

if TYPE_CHECKING:
    from bot import EventBot


COOKING_RECIPES: dict[str, dict[str, Any]] = {
    "Berry Crepes": {
        "heat": "🔥 Low Heat",
        "total_seconds": 50,
        "effect": "⚡ **Speed Buff:** Increases player movement speed for 30 minutes.",
        "ingredients": {
            "Flour": 1,
            "Milk": 1,
            "Egg": 1,
            "Blueberries": 1,
            "Sugar": 1,
        },
        "timeline": [
            ("00s (Start)", "Add **`Flour`** + **`Milk`** ➔ Set Oven to **`Low`**"),
            ("16s", "Add **`Egg`**"),
            ("30s", "Add **`Blueberries`**"),
            ("35s", "Add **`Sugar`** *(for 100% quality)*"),
            ("50s (Done!)", "🔨 **Punch Oven immediately to take out!**"),
        ],
    },
    "Arroz Con Pollo": {
        "heat": "🔥 Low Heat",
        "total_seconds": 40,
        "effect": "🍀 **Gem Drop Buff (Lucky Clover effect):** Increases chance of extra Gems when breaking blocks for 30 minutes!",
        "ingredients": {
            "Rice": 1,
            "Chicken Meat": 1,
            "Tomato": 1,
            "Onion": 1,
            "Salt": 1,
            "Pepper": 1,
        },
        "timeline": [
            ("00s (Start)", "Add **`Rice`** + **`Chicken Meat`** ➔ Set Oven to **`Low`**"),
            ("13s", "Add **`Tomato`** + **`Onion`**"),
            ("20s", "Add **`Salt`**"),
            ("30s", "Add **`Pepper`**"),
            ("40s (Done!)", "🔨 **Punch Oven immediately to take out!**"),
        ],
    },
    "Eggs Benedict": {
        "heat": "🔥 Low Heat",
        "total_seconds": 60,
        "effect": "✨ **XP Buff:** Grants **+10% Bonus XP** from all sources for 30 minutes!",
        "ingredients": {
            "Flour": 1,
            "Egg": 2,
            "Milk": 1,
            "Bacon": 1,
            "Butter": 1,
            "Salt": 1,
            "Pepper": 1,
        },
        "timeline": [
            ("00s (Start)", "Add **`Flour`** + **`1st Egg`** + **`Milk`** ➔ Set Oven to **`Low`**"),
            ("20s", "Add **`Bacon`**"),
            ("30s", "Add **`Salt`**"),
            ("39s", "Add **`2nd Egg`** + **`Butter`**"),
            ("45s", "Add **`Pepper`**"),
            ("60s (Done!)", "🔨 **Punch Oven immediately to take out!**"),
        ],
    },
    "Gomtang": {
        "heat": "🔥🔥🔥 High Heat",
        "total_seconds": 50,
        "effect": "🩺 **Medical Buff:** Has a chance to cure active Maladies when eaten!",
        "ingredients": {
            "BeefBone": 1,
            "Onion": 1,
            "Garlic": 1,
            "Salt": 1,
            "Pepper": 1,
        },
        "timeline": [
            ("00s (Start)", "Add **`BeefBone`** + **`Onion`** ➔ Set Oven to **`High`**"),
            ("15s", "Add **`Garlic`**"),
            ("25s", "Add **`Salt`**"),
            ("37s", "Add **`Pepper`**"),
            ("50s (Done!)", "🔨 **Punch Oven immediately to take out!**"),
        ],
    },
    "Filet Mignon": {
        "heat": "🔥🔥🔥 High Heat",
        "total_seconds": 30,
        "effect": "👨‍🍳 **Chef Showdown & Role Day Favorite:** Fast 30-second high-point gourmet steak.",
        "ingredients": {
            "Agedrib": 1,
            "Bacon": 1,
            "Butter": 1,
            "Salt": 1,
            "Pepper": 1,
        },
        "timeline": [
            ("00s (Start)", "Add **`Agedrib`** + **`Bacon`** ➔ Set Oven to **`High`**"),
            ("10s", "Add **`Butter`**"),
            ("15s", "Add **`Salt`**"),
            ("22s", "Add **`Pepper`**"),
            ("30s (Done!)", "🔨 **Punch Oven immediately to take out!**"),
        ],
    },
    "Meatza": {
        "heat": "🔥🔥 Medium Heat",
        "total_seconds": 50,
        "effect": "🍕 **Chef Quest & Party Dish:** High-tier pizza made with 3 meats.",
        "ingredients": {
            "Flour": 1,
            "Tomato": 1,
            "Ground Beef": 1,
            "Bacon": 1,
            "Pepperoni": 1,
            "Salt": 1,
        },
        "timeline": [
            ("00s (Start)", "Add **`Flour`** + **`Tomato`** + **`Ground Beef`** ➔ Set Oven to **`Med`**"),
            ("18s", "Add **`Bacon`** + **`Pepperoni`**"),
            ("25s", "Add **`Salt`**"),
            ("50s (Done!)", "🔨 **Punch Oven immediately to take out!**"),
        ],
    },
    "Mac 'n' Cheese": {
        "heat": "🔥 Low Heat",
        "total_seconds": 45,
        "effect": "🛡️ **Defense Buff:** Reduces incoming damage taken for 30 minutes.",
        "ingredients": {
            "Macaroni": 1,
            "Milk": 1,
            "Cheddar": 1,
            "Salt": 1,
            "Pepper": 1,
        },
        "timeline": [
            ("00s (Start)", "Add **`Macaroni`** + **`Milk`** ➔ Set Oven to **`Low`**"),
            ("15s", "Add **`Cheddar`**"),
            ("22s", "Add **`Salt`**"),
            ("34s", "Add **`Pepper`**"),
            ("45s (Done!)", "🔨 **Punch Oven immediately to take out!**"),
        ],
    },
    "Quiche": {
        "heat": "🔥 Low Heat",
        "total_seconds": 45,
        "effect": "👊 **Punch Buff:** Increases block-breaking punch efficiency for 30 minutes.",
        "ingredients": {
            "Flour": 1,
            "Milk": 1,
            "Egg": 1,
            "Bacon": 1,
            "Salt": 1,
            "Pepper": 1,
        },
        "timeline": [
            ("00s (Start)", "Add **`Flour`** + **`Milk`** ➔ Set Oven to **`Low`**"),
            ("15s", "Add **`Egg`** + **`Bacon`**"),
            ("22s", "Add **`Salt`**"),
            ("34s", "Add **`Pepper`**"),
            ("45s (Done!)", "🔨 **Punch Oven immediately to take out!**"),
        ],
    },
    "Pot O'ulle": {
        "heat": "🔥 Low Heat",
        "total_seconds": 60,
        "effect": "🍲 **Chef Role Quest Staple:** Classic stew using basic farm ingredients.",
        "ingredients": {
            "Chicken Meat": 1,
            "Potato": 1,
            "Carrot": 1,
            "Onion": 1,
            "Salt": 1,
            "Pepper": 1,
        },
        "timeline": [
            ("00s (Start)", "Add **`Chicken Meat`** ➔ Set Oven to **`Low`**"),
            ("20s", "Add **`Potato`** + **`Carrot`** + **`Onion`**"),
            ("30s", "Add **`Salt`**"),
            ("45s", "Add **`Pepper`**"),
            ("60s (Done!)", "🔨 **Punch Oven immediately to take out!**"),
        ],
    },
    "Chocolate Cake": {
        "heat": "🔥 Low Heat",
        "total_seconds": 60,
        "effect": "🎂 **Sweet Pastry:** Used for Chef Quests and Valentine/Party events.",
        "ingredients": {
            "Flour": 1,
            "Egg": 1,
            "Milk": 1,
            "Sugar": 1,
            "Cocoa Bean": 1,
            "Butter": 1,
        },
        "timeline": [
            ("00s (Start)", "Add **`Flour`** + **`Egg`** + **`Milk`** ➔ Set Oven to **`Low`**"),
            ("30s", "Add **`Sugar`** + **`Cocoa Bean`**"),
            ("40s", "Add **`Butter`**"),
            ("60s (Done!)", "🔨 **Punch Oven immediately to take out!**"),
        ],
    },
    "Onion Rings": {
        "heat": "🔥🔥🔥 High Heat",
        "total_seconds": 30,
        "effect": "🧅 **Fast 30s Dish:** Great for quick Chef XP and Role Day quests.",
        "ingredients": {
            "Onion": 1,
            "Flour": 1,
            "Egg": 1,
            "Milk": 1,
            "Olive Oil": 1,
            "Salt": 1,
        },
        "timeline": [
            ("00s (Start)", "Add **`Onion`** + **`Flour`** + **`Egg`** + **`Milk`** ➔ Set Oven to **`High`**"),
            ("15s", "Add **`Olive Oil`** + **`Salt`**"),
            ("30s (Done!)", "🔨 **Punch Oven immediately to take out!**"),
        ],
    },
    "Sunny Side Up": {
        "heat": "🔥🔥 Medium Heat",
        "total_seconds": 24,
        "effect": "🍳 **Fastest Beginner Dish (24s):** Easiest recipe to level up early Cooking skill!",
        "ingredients": {
            "Egg": 1,
            "Salt": 1,
            "Pepper": 1,
        },
        "timeline": [
            ("00s (Start)", "Add **`Egg`** ➔ Set Oven to **`Med`**"),
            ("12s", "Add **`Salt`**"),
            ("18s", "Add **`Pepper`**"),
            ("24s (Done!)", "🔨 **Punch Oven immediately to take out!**"),
        ],
    },
}


class OvenTimerView(discord.ui.View):
    def __init__(self, dish_name: str, recipe: dict[str, Any]) -> None:
        super().__init__(timeout=None)
        self.dish_name = dish_name
        self.recipe = recipe

    @discord.ui.button(
        label="Start Live Oven Countdown",
        style=discord.ButtonStyle.success,
        emoji="⏱️",
    )
    async def start_timer_button(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        now_ts = int(datetime.now(EVENT_TZ).timestamp())
        total_sec = int(self.recipe["total_seconds"])
        done_ts = now_ts + total_sec

        step_timestamps: list[str] = []
        for time_label, action in self.recipe["timeline"]:
            digits = "".join(ch for ch in time_label.split()[0] if ch.isdigit())
            offset_sec = int(digits) if digits else 0
            step_ts = now_ts + offset_sec
            step_timestamps.append(f"• **`+{offset_sec:02d}s`** (<t:{step_ts}:T> • <t:{step_ts}:R>) ➔ {action}")

        embed = discord.Embed(
            title=f"⏱️ Live Oven Timer Started — {self.dish_name}",
            description=(
                f"🔥 **Oven Heat:** {self.recipe['heat']}\n"
                f"⏰ **Take Out Dish:** <t:{done_ts}:T> (**<t:{done_ts}:R>**)\n\n"
                "**Live Step Timestamps:**\n" + "\n".join(step_timestamps)
            ),
            color=discord.Color.orange(),
        )
        embed.set_footer(text=FOOTER_TEXT)
        await interaction.response.send_message(embed=embed, ephemeral=True)


class CookingHelperCog(commands.Cog, name="Cooking Helper"):
    def __init__(self, bot: EventBot) -> None:
        self.bot = bot

    async def dish_autocomplete(
        self,
        _interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        query = current.strip().lower()
        choices: list[app_commands.Choice[str]] = []
        for name, info in COOKING_RECIPES.items():
            if not query or query in name.lower() or query in info["effect"].lower():
                label = f"{name} ({info['heat']} • {info['total_seconds']}s)"
                choices.append(app_commands.Choice(name=label[:100], value=name))
        return choices[:25]

    @app_commands.command(
        name="set_cook_channel",
        description="Restrict the /cook oven timeline & ingredient calculator exclusively to a dedicated channel",
    )
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(channel="Dedicated channel for /cook lookups (defaults to current channel)")
    async def set_cook_channel_command(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel | None = None,
    ) -> None:
        if not is_server_manager(interaction):
            await interaction.response.send_message(
                "❌ Only server admins can use `/set_cook_channel`.",
                ephemeral=True,
            )
            return
        await interaction.response.defer()
        target_channel = channel or interaction.channel
        if not isinstance(target_channel, discord.TextChannel):
            await interaction.followup.send("❌ Please select a standard text channel.", ephemeral=True)
            return

        state = load_state()
        state["cook_channel_id"] = target_channel.id
        save_state(state)

        guide_embed = discord.Embed(
            title="🍳 Growcom Cooking Oven Timeline & Ingredient Calculator",
            description=(
                "Use **`/cook`** in this channel for exact **second-by-second Home Oven timelines** and "
                "**multi-oven ingredient shopping lists**!\n\n"
                "**How to Use:**\n"
                "1️⃣ Type **`/cook`** and select your dish (e.g. `Berry Crepes`, `Arroz Con Pollo`, `Eggs Benedict`, `Gomtang`, `Filet Mignon`, `Meatza`).\n"
                "2️⃣ Optionally enter how many **`ovens`** you are cooking on at once (defaults to `20` ovens).\n"
                "3️⃣ Click **⏱️ Start Live Oven Countdown** right below the guide when you turn on your first oven!"
            ),
            color=discord.Color.orange(),
        )
        guide_embed.set_footer(text=FOOTER_TEXT)
        await target_channel.send(embed=guide_embed)

        await interaction.followup.send(
            f"✅ Locked **`/cook`** exclusively to {target_channel.mention}! "
            f"Players trying to run `/cook` anywhere else will be redirected to {target_channel.mention}.",
            ephemeral=True,
        )

    @app_commands.command(
        name="cook",
        description="Exact second-by-second Growtopia Oven timeline, heat setting, & ingredient calculator!",
    )
    @app_commands.describe(
        dish="Select the dish to cook (e.g. Berry Crepes, Arroz Con Pollo, Eggs Benedict, Gomtang, Filet Mignon)",
        ovens="How many ovens you are cooking on at once (defaults to 20 ovens)",
    )
    @app_commands.autocomplete(dish=dish_autocomplete)
    async def cook_command(
        self,
        interaction: discord.Interaction,
        dish: str,
        ovens: app_commands.Range[int, 1, 500] = 20,
    ) -> None:
        state = load_state()
        allowed_channel_id = state.get("cook_channel_id")
        if allowed_channel_id and int(interaction.channel_id or 0) != int(allowed_channel_id):
            await interaction.response.send_message(
                f"❌ The **`/cook`** helper can only be used inside <#{allowed_channel_id}>!",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        matched_name: str | None = None
        for name in COOKING_RECIPES:
            if name.lower() == dish.strip().lower():
                matched_name = name
                break
        if not matched_name:
            for name in COOKING_RECIPES:
                if dish.strip().lower() in name.lower():
                    matched_name = name
                    break

        if not matched_name:
            await interaction.followup.send(
                f"❌ Could not find a cooking recipe matching **`{dish}`**. Please select a dish from the `/cook` autocomplete list!",
                ephemeral=True,
            )
            return

        recipe = COOKING_RECIPES[matched_name]
        timeline_lines = [
            f"⏱️ **`{sec_label}`** — {instruction}"
            for sec_label, instruction in recipe["timeline"]
        ]

        ingredient_lines: list[str] = []
        for ing_name, qty_per_oven in recipe["ingredients"].items():
            total_qty = qty_per_oven * ovens
            stacks, rem = divmod(total_qty, 200)
            stack_note = f" *(`{stacks}` stack{'s' if stacks != 1 else ''}" + (f" + `{rem}`)*" if rem else ")*") if stacks > 0 else ""
            ingredient_lines.append(
                f"• **`{total_qty:,}x` {ing_name}** (`{qty_per_oven}x` per oven){stack_note}"
            )

        embed = discord.Embed(
            title=f"🍳 Cooking Guide — {matched_name} ({ovens:,} Oven{'s' if ovens != 1 else ''})",
            description=recipe["effect"],
            color=discord.Color.orange(),
        )
        embed.add_field(
            name="🌡️ Oven Temperature",
            value=f"**{recipe['heat']}**",
            inline=True,
        )
        embed.add_field(
            name="⏳ Total Cook Time",
            value=f"**`{recipe['total_seconds']} Seconds`**",
            inline=True,
        )
        embed.add_field(
            name="🍽️ Total Yield",
            value=f"**`{ovens:,}x` {matched_name}**",
            inline=True,
        )
        embed.add_field(
            name="⏱️ Exact Second-by-Second Oven Timeline",
            value="\n".join(timeline_lines),
            inline=False,
        )
        embed.add_field(
            name=f"🛒 Total Ingredients Needed ({ovens:,} Oven{'s' if ovens != 1 else ''})",
            value="\n".join(ingredient_lines),
            inline=False,
        )

        files: list[discord.File] = []
        sprite_bytes = await self.bot.api.get_item_sprite(matched_name)
        if sprite_bytes:
            files.append(discord.File(BytesIO(sprite_bytes), filename="sprite.png"))
            embed.set_thumbnail(url="attachment://sprite.png")

        embed.set_footer(text=FOOTER_TEXT)
        view = OvenTimerView(dish_name=matched_name, recipe=recipe)
        await interaction.followup.send(embed=embed, view=view, files=files)


async def setup(bot: EventBot) -> None:
    await bot.add_cog(CookingHelperCog(bot))
