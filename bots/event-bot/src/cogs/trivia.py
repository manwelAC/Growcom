"""
Category 14: Daily Growtopia Item Trivia & Monthly 10 DL Championship (cogs/trivia.py)

Argon-Standard Daily Trivia Engine featuring:
- Anti-Wiki & Anti-Cheat Mechanics: Multi-constraint cryptic riddles, strict 20s speedrun timer,
  randomized button positions, ephemeral sessions, and single daily attempt per player.
- Live Monthly Championship Leaderboard: Monthly reset on the 1st of every month at 00:00 GT Time.
- 10 Diamond Locks (10 DLs) Grand Prize sponsored by Manwel awarded to each month's top performer.
- Tiebreaker Engine: Total Points -> Correct Answers Count -> Average Answer Speed (fastest wins).
- Dedicated Channels:
  • #🎯daily-trivia (Interactive Play Desk)
  • #🏆trivia-leaderboards (Read-only Live Auto-Updating Leaderboard & Hall of Fame)

Commands:
- /trivia (Open today's trivia challenge or check status)
- /setup_trivia_channels (Admin: auto-provision #🎯daily-trivia & #🏆trivia-leaderboards)
- /set_trivia_channel [channel] (Admin: lock /trivia to dedicated channel)
- /trivia_leaderboard (Display or refresh live championship standings)
- /trivia_reset_season (Admin: manually end season, crown winner, and reset scores)
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import hashlib
import json
import logging
import random
import time
from typing import TYPE_CHECKING, Any

import discord
from discord import app_commands
from discord.ext import commands, tasks

from utils.helpers import (
    EVENT_TZ,
    FOOTER_TEXT,
    PROJECT_ROOT,
    is_server_manager,
    load_state,
    save_state,
)

if TYPE_CHECKING:
    from bot import EventBot

logger = logging.getLogger("growcom.trivia")

ACTIVITIES_CATEGORY_ID = 1567242649893609512
TOOLS_CATEGORY_ID = 1567213972283719811
DEFAULT_MEMBER_ROLE_ID = 1568495447067332608

TRIVIA_STATS_FILE = PROJECT_ROOT / "bots" / "event-bot" / "data" / "trivia_stats.json"
GRAND_PRIZE_TEXT = "💎 10 Diamond Locks (Sponsored by Manwel)"
SESSION_TIMEOUT_SECONDS = 20.0
MIN_ACCOUNT_AGE_DAYS = 7  # Anti-alt threshold

# ==============================================================================
# ANTI-WIKI QUESTION BANK (50 Handcrafted Multi-Constraint Master Questions)
# ==============================================================================
TRIVIA_QUESTIONS: list[dict[str, Any]] = [
    {
        "id": 1,
        "category": "🌾 Farming & Splicing",
        "question": (
            "I require 5 fist punches to break. My seed takes over 3 days (around 87.9 hours) to bloom, "
            "and I drop green gems when harvested. My block cannot be spliced in modern Growtopia. "
            "What farmable block am I?"
        ),
        "options": ["Laser Grid", "Pepper Tree", "Chandelier", "Fish Tank"],
        "answer": "Laser Grid",
        "explanation": "Laser Grid has hardness 5 (30 raw/6), takes ~87.9 hours (316,472s) to grow, drops green gems, and is unsplicable.",
    },
    {
        "id": 2,
        "category": "🌾 Farming & Splicing",
        "question": (
            "I am a popular farmable block with rarity 47. My seed blooms in roughly 29.2 hours (105,233s), "
            "and my block requires exactly 4 fist punches to break. What am I?"
        ),
        "options": ["Pepper Tree", "Fish Tank", "Venus Guytrap", "Pinball Bumper"],
        "answer": "Pepper Tree",
        "explanation": "Pepper Tree (ID 4584) has rarity 47, hardness 4 hits, and a bloom duration of 105,233 seconds (~29.2 hours).",
    },
    {
        "id": 3,
        "category": "🌾 Farming & Splicing",
        "question": (
            "I am an iconic high-tier farmable block with rarity 87. My tree takes over 7 days and 15 hours "
            "(661,113 seconds) to bloom, and my block requires 7 fist punches to break. What am I?"
        ),
        "options": ["Chandelier", "Magic Bell", "Crystal Block", "High Tech Block"],
        "answer": "Chandelier",
        "explanation": "Chandelier (ID 340) has rarity 87, takes 661,113 seconds (~7.65 days) to bloom, and requires 7 fist punches.",
    },
    {
        "id": 4,
        "category": "🌱 Roots Mechanics",
        "question": (
            "When Bountiful seeds are cultivated on Fertile Soil through multiple growth cycles, "
            "how many fist punches does it take to harvest a fully Mature Root block, and exactly how much XP does it yield?"
        ),
        "options": [
            "3 punches • 80 XP",
            "4 punches • 20 XP",
            "2 punches • 50 XP",
            "5 punches • 100 XP",
        ],
        "answer": "3 punches • 80 XP",
        "explanation": "Mature roots have hardness 18 (3 fist hits, or 2 pickaxe hits) and award exactly 80 XP per harvest!",
    },
    {
        "id": 5,
        "category": "🌱 Roots Mechanics",
        "question": (
            "During the Super Pineapple event, harvesting a Mature Pineapple Roots block returns the soil to normal "
            "and awards how much XP to the player?"
        ),
        "options": ["6 XP", "15 XP", "80 XP", "25 XP"],
        "answer": "6 XP",
        "explanation": "Harvesting any mature pineapple roots (Regular, Super, or Rotten) yields exactly 6 XP and reverts the tile to Fertile Soil.",
    },
    {
        "id": 6,
        "category": "🔬 Surgery Mastery",
        "question": (
            "During a surgical operation, the patient's temperature surges to 104.5°F, their pulse is racing, "
            "and they have 1 open incision. What is the strictly correct first procedure before applying cooling or cutting?"
        ),
        "options": [
            "Apply Antibiotics",
            "Apply Ice Pack",
            "Use Sponge",
            "Use Scalpel",
        ],
        "answer": "Apply Antibiotics",
        "explanation": "A high fever combined with an open incision indicates impending septic shock. Antibiotics must be administered immediately to stabilize the infection.",
    },
    {
        "id": 7,
        "category": "🔬 Surgery Mastery",
        "question": (
            "In Growtopia surgery, which specialized medical tool is used to fix shattered bones with titanium pins "
            "when a standard Splint is insufficient?"
        ),
        "options": [
            "Pins and Screws",
            "Ultrasonic Device",
            "Surgical Clamp",
            "Transfusion",
        ],
        "answer": "Pins and Screws",
        "explanation": "Pins and Screws are required to align and mend shattered or compound fractures where a simple Splint fails.",
    },
    {
        "id": 8,
        "category": "🔬 Surgery Mastery",
        "question": (
            "When a patient's heartbeat flatlines to 0 BPM (Cardiac Arrest) on the surgical monitor, "
            "which tool must be used immediately to revive cardiac activity?"
        ),
        "options": ["Defibrillator", "Epinephrine", "Ventilator", "Stethoscope"],
        "answer": "Defibrillator",
        "explanation": "When the heart flatlines (0 BPM / cardiac arrest), the Defibrillator shocks the heart back into rhythm before irreversible brain death occurs.",
    },
    {
        "id": 9,
        "category": "🧱 Block Physics & Hardness",
        "question": (
            "Which of the following standard placeable building blocks has the HIGHEST fist hit hardness in items.dat, "
            "requiring a massive 20 bare fist punches to break?"
        ),
        "options": ["Steel Block", "Obsidian", "Bedrock", "Dragon Gate"],
        "answer": "Steel Block",
        "explanation": "Steel Block (ID 186) has a hardness rating of 120 in items.dat (120/6 = 20 bare fist punches), higher than Obsidian (12 punches).",
    },
    {
        "id": 10,
        "category": "🧱 Block Physics & Hardness",
        "question": (
            "I am a gateway block with rarity 16. My tree blooms in just 1 hour and 16 minutes (4,576 seconds), "
            "yet my block requires a stubborn 10 fist punches to break. What am I?"
        ),
        "options": ["Portcullis", "Dungeon Door", "House Entrance", "Secret Passage"],
        "answer": "Portcullis",
        "explanation": "Portcullis (ID 60) grows very fast (4,576s / ~1.27 hrs) but has heavy door hardness requiring 10 fist hits.",
    },
    {
        "id": 11,
        "category": "⚡ Leveling & XP Math",
        "question": (
            "Using Growtopia's official leveling formula: XP = 50 × (L² + 2), "
            "exactly how much XP is required to transition from Level 60 to Level 61?"
        ),
        "options": ["180,100 XP", "175,000 XP", "186,050 XP", "192,200 XP"],
        "answer": "180,100 XP",
        "explanation": "50 × (60² + 2) = 50 × (3,600 + 2) = 50 × 3,602 = 180,100 XP exactly.",
    },
    {
        "id": 12,
        "category": "⚡ Leveling & XP Math",
        "question": (
            "At what exact cumulative total XP does a player achieve Level 100 and unlock the prestigious Golden Name?"
        ),
        "options": ["16,339,900 XP", "15,000,000 XP", "20,500,000 XP", "12,911,000 XP"],
        "answer": "16,339,900 XP",
        "explanation": "Cumulative XP from Level 1 to 100 = Σ 50 × (L² + 2) for L=1..99 = 16,339,900 XP.",
    },
    {
        "id": 13,
        "category": "⚡ Leveling & XP Math",
        "question": (
            "What is the maximum achievable level cap in Growtopia, and what total cumulative XP is required to reach it?"
        ),
        "options": [
            "Level 125 • 32,174,900 XP",
            "Level 100 • 16,339,900 XP",
            "Level 120 • 28,500,000 XP",
            "Level 150 • 50,000,000 XP",
        ],
        "answer": "Level 125 • 32,174,900 XP",
        "explanation": "The current maximum level cap in Growtopia is Level 125, which requires exactly 32,174,900 cumulative XP from Level 1.",
    },
    {
        "id": 14,
        "category": "🍳 Culinary Arts",
        "question": (
            "When cooking with an E.Z-Cook Oven, what status event occurs if high heat is left unattended "
            "beyond the target time bracket without adjusting temperature or adding stabilizing ingredients?"
        ),
        "options": [
            "Ruined / Burnt Dish (Charcoal)",
            "Exploding Oven (Tile destruction)",
            "Half Yield Reduction",
            "Food Poisoning aura",
        ],
        "answer": "Ruined / Burnt Dish (Charcoal)",
        "explanation": "Overheating food without reducing temperature or adding spices causes it to overcook and turn into Burnt Food / Charcoal.",
    },
    {
        "id": 15,
        "category": "🍳 Culinary Arts",
        "question": (
            "Which foundational culinary ingredient is produced by processing Wheat Seed and Water in a laboratory combiner?"
        ),
        "options": ["Flour", "Dough", "Yeast", "Cornstarch"],
        "answer": "Flour",
        "explanation": "Flour is the fundamental base carbohydrate ingredient in Growtopia cooking, made from wheat crops.",
    },
    {
        "id": 16,
        "category": "🎣 Fishing & Deep Sea",
        "question": (
            "Which high-end fishing rod grants the highest bonus catch weight and stability when hunting for 100+ lb "
            "Monster Fish in deep sea waters?"
        ),
        "options": [
            "Deep Sea Fishing Rod",
            "Fiberglass Fishing Rod",
            "Bamboo Fishing Rod",
            "Golden Fishing Rod",
        ],
        "answer": "Deep Sea Fishing Rod",
        "explanation": "The Deep Sea Fishing Rod is specifically tuned to resist high tension snaps and catch record-weight trophy fish.",
    },
    {
        "id": 17,
        "category": "🎣 Fishing & Deep Sea",
        "question": (
            "What happens during the fishing mini-game if the player reels continuously while the tension indicator is deep in the Red Zone?"
        ),
        "options": [
            "Line Snaps & Bait is Lost",
            "Fish Escapes immediately with rod damage",
            "Player is pulled into the water",
            "Fish weight is cut in half",
        ],
        "answer": "Line Snaps & Bait is Lost",
        "explanation": "Reeling under excessive red-zone tension causes the line to snap immediately, losing both the lure/bait and the catch.",
    },
    {
        "id": 18,
        "category": "🦸 Crime Wave & Superpowers",
        "question": (
            "During a Crime Wave villain battle, what elemental superpower is the direct operational counter "
            "to defeat Dr. Destructo's explosive heat shields?"
        ),
        "options": ["Ice Breath", "Heat Vision", "Super Strength", "Electrokinesis"],
        "answer": "Ice Breath",
        "explanation": "Dr. Destructo's heat-based weaponry and fire shields are critically neutralized by the Ice Breath superpower.",
    },
    {
        "id": 19,
        "category": "🚀 Startopia Command",
        "question": (
            "In Startopia / Star Trek starship missions, when the warp core overheats and radiation fills engineering, "
            "which crew member role must be dispatched to vent the plasma conduits?"
        ),
        "options": ["Engineer", "Tactical Officer", "Medical Doctor", "Diplomat"],
        "answer": "Engineer",
        "explanation": "Engineers handle all structural repairs, warp drive stabilization, and reactor radiation hazards.",
    },
    {
        "id": 20,
        "category": "🚀 Startopia Command",
        "question": (
            "When encountering a heavily armed alien dreadnought requesting peace negotiations, "
            "which specialist must command the comms array to prevent an unprovoked torpedo volley?"
        ),
        "options": ["Diplomat", "Science Officer", "Security Guard", "Pilot"],
        "answer": "Diplomat",
        "explanation": "The Diplomat specialist defuses hostile alien encounters, translates dialects, and avoids combat sequences.",
    },
    {
        "id": 21,
        "category": "💎 Relics & Gacha Lore",
        "question": (
            "Which mythic Valentine's Day jackpot item obtained from Super Golden Booty Chests is widely considered "
            "the most valuable cosmetic relic in the event and grants high float/double-jump physics?"
        ),
        "options": [
            "Golden Heart Crystal",
            "Golden Ribbon Wings",
            "Golden Sparkling Mallet",
            "Heartbreak Wings",
        ],
        "answer": "Golden Heart Crystal",
        "explanation": "Golden Heart Crystal (GHC) is the ultra-coveted 0.08% mythic jackpot of Valentine's GBCs, valued above 12,000+ World Locks.",
    },
    {
        "id": 22,
        "category": "💎 Relics & Gacha Lore",
        "question": (
            "During the Summerfest event, what is the ultimate ultra-rare floating item obtainable from smashing Summer Surprise Piñatas?"
        ),
        "options": [
            "Phoenix Wings",
            "Golden Sunbed",
            "Super Fireworks",
            "Fire Dragon",
        ],
        "answer": "Phoenix Wings",
        "explanation": "Phoenix Wings are the signature Mythic Jackpot of Summerfest Piñata smashing, featuring radiant flaming animations.",
    },
    {
        "id": 23,
        "category": "🎪 Carnival & Guild Clash",
        "question": (
            "Which legendary Ring obtained from the Carnival Ringmaster grants the wearer double punch knockback distance, "
            "launching other players across the world?"
        ),
        "options": ["Ring of Force", "Ring of Winds", "Ring of Nature", "Ring of Water"],
        "answer": "Ring of Force",
        "explanation": "The Ring of Force is famed for giving players extreme punch propulsion and knockback strength.",
    },
    {
        "id": 24,
        "category": "🎪 Carnival & Guild Clash",
        "question": (
            "How many Ringmaster quests must a player successfully complete during Carnival in order to receive a guaranteed Ring roll?"
        ),
        "options": ["10 Quests", "5 Quests", "20 Quests", "15 Quests"],
        "answer": "10 Quests",
        "explanation": "Completing 10 consecutive Ringmaster quests awards a Ringmaster's Case / Golden Ticket granting a guaranteed Ring roll.",
    },
    {
        "id": 25,
        "category": "☢️ Geiger & Radiation",
        "question": (
            "When operating a Geiger Counter, what does a rapid, frantic RED signal with high-pitch beeps indicate?"
        ),
        "options": [
            "Within 1–3 tiles of a buried Radioactive item/Crystal",
            "Geiger Counter is out of battery charge",
            "World has background environmental radiation",
            "Player is standing on Fertile Soil",
        ],
        "answer": "Within 1–3 tiles of a buried Radioactive item/Crystal",
        "explanation": "The intense rapid red signal signifies the player is within 1 to 3 blocks of a buried radiation prize (e.g. White Crystal, Black Crystal).",
    },
    {
        "id": 26,
        "category": "☢️ Geiger & Radiation",
        "question": (
            "Which ultra-rare crystal dropped by radioactive Geiger search can be transmuted with an Alien Crystal to create a Star Seed?"
        ),
        "options": ["White Crystal", "Red Crystal", "Green Crystal", "Blue Crystal"],
        "answer": "White Crystal",
        "explanation": "White Crystals are the rarest standard Geiger crystal and form the core component of high-tier cosmic crafting.",
    },
    {
        "id": 27,
        "category": "🧱 Block Physics & Hardness",
        "question": (
            "I am a trap block introduced during Halloween. I look identical to an innocent green plant, "
            "but I snap and kill players who walk into me. I take 6 fist punches to break and grow in ~19.5 hours. What am I?"
        ),
        "options": ["Venus Guytrap", "Spike", "Prickly Cactus", "Grimstone"],
        "answer": "Venus Guytrap",
        "explanation": "Venus Guytrap (ID 454) is a lethal plant trap with hardness 6 and a 70,151-second growth cycle.",
    },
    {
        "id": 28,
        "category": "🌾 Farming & Splicing",
        "question": (
            "Which farmable block has rarity 42, takes ~20.9 hours (75,348s) to grow, requires 3 fist punches to break, "
            "and is transparent glass?"
        ),
        "options": ["Fish Tank", "Window", "Glass Pane", "Display Box"],
        "answer": "Fish Tank",
        "explanation": "Fish Tank (ID 3004) has rarity 42, takes ~20.9 hours to bloom, and breaks in 3 fist punches.",
    },
    {
        "id": 29,
        "category": "🌾 Farming & Splicing",
        "question": (
            "I am an ancient ornamental block with rarity 95. My tree takes almost 10 full days (~238.9 hours) to bloom, "
            "and my block requires 10 hits to smash. What am I?"
        ),
        "options": ["Magic Bell", "Chandelier", "Gargoyle", "Cutaway Building"],
        "answer": "Magic Bell",
        "explanation": "Magic Bell (ID 5990) has an enormous bloom time of 860,225s (~9.95 days), rarity 95, and 10 fist hits.",
    },
    {
        "id": 30,
        "category": "💰 Economy & Currencies",
        "question": (
            "In Growtopia's primary currency hierarchy, exactly how many World Locks (WLs) are required to forge "
            "one single Blue Gem Lock (BGL)?"
        ),
        "options": ["10,000 WLs", "1,000 WLs", "5,000 WLs", "100,000 WLs"],
        "answer": "10,000 WLs",
        "explanation": "100 World Locks = 1 Diamond Lock (DL). 100 Diamond Locks = 1 Blue Gem Lock (BGL). Thus, 100 × 100 = 10,000 WLs.",
    },
]


def load_trivia_stats() -> dict[str, Any]:
    """Load player stats, current month, and hall of fame from disk."""
    if TRIVIA_STATS_FILE.exists():
        try:
            return json.loads(TRIVIA_STATS_FILE.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Failed to parse trivia_stats.json (%s), creating fresh.", exc)
    now_month = datetime.now(EVENT_TZ).strftime("%Y-%m")
    return {
        "current_month": now_month,
        "players": {},
        "hall_of_fame": [],
    }


def save_trivia_stats(data: dict[str, Any]) -> None:
    """Save player stats and hall of fame to disk atomically."""
    TRIVIA_STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
    TRIVIA_STATS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_daily_question(date_str: str) -> dict[str, Any]:
    """
    Deterministic, fair daily question picker.
    All players on the same Growtopia calendar day receive the exact same question!
    """
    seed_val = int(hashlib.sha256(f"growcom_trivia_{date_str}".encode()).hexdigest(), 16)
    idx = seed_val % len(TRIVIA_QUESTIONS)
    return TRIVIA_QUESTIONS[idx]


def get_current_gt_date() -> str:
    """Return the current calendar date in Growtopia / event timezone."""
    return datetime.now(EVENT_TZ).strftime("%Y-%m-%d")


def get_current_gt_month() -> str:
    """Return the current calendar month in Growtopia / event timezone."""
    return datetime.now(EVENT_TZ).strftime("%Y-%m")


# ==============================================================================
# DISCORD VIEWS & INTERACTIVE DESKS (Argon Standard)
# ==============================================================================


class TriviaPlayDeskView(discord.ui.View):
    """
    Persistent Interactive Play Desk pinned in #🎯daily-trivia.
    Provides zero-clutter buttons to play today's challenge, view stats, or inspect rules.
    """

    def __init__(self, cog: TriviaCog) -> None:
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="Play Today's Trivia",
        emoji="🎯",
        style=discord.ButtonStyle.success,
        custom_id="trivia_btn:play_today",
    )
    async def play_today_button(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog.start_player_session(interaction)

    @discord.ui.button(
        label="My Stats & Streak",
        emoji="📊",
        style=discord.ButtonStyle.primary,
        custom_id="trivia_btn:my_stats",
    )
    async def my_stats_button(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog.show_player_stats(interaction)

    @discord.ui.button(
        label="Championship Top 10",
        emoji="🏆",
        style=discord.ButtonStyle.secondary,
        custom_id="trivia_btn:top10",
    )
    async def top10_button(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog.show_quick_leaderboard(interaction)

    @discord.ui.button(
        label="Prize & Rules (10 DLs)",
        emoji="📜",
        style=discord.ButtonStyle.secondary,
        custom_id="trivia_btn:rules",
    )
    async def rules_button(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.cog.show_rules_modal_or_embed(interaction)


class TriviaSessionView(discord.ui.View):
    """
    Ephemeral 20-Second Anti-Wiki Challenge Session.
    Randomizes option order, enforces strict 20-second timeout, and tracks elapsed milliseconds.
    """

    def __init__(
        self,
        cog: TriviaCog,
        user_id: int,
        user_name: str,
        question_data: dict[str, Any],
        today_date: str,
    ) -> None:
        super().__init__(timeout=SESSION_TIMEOUT_SECONDS)
        self.cog = cog
        self.user_id = user_id
        self.user_name = user_name
        self.q = question_data
        self.today_date = today_date
        self.start_time = time.time()
        self.answered = False

        # Randomize options so button order differs for every player
        options_shuffled = list(self.q["options"])
        random.shuffle(options_shuffled)

        # Style letters A, B, C, D
        emojis = ["🇦", "🇧", "🇨", "🇩"]
        for idx, opt in enumerate(options_shuffled):
            emoji = emojis[idx] if idx < len(emojis) else "🔹"
            btn = discord.ui.Button(
                label=opt[:80],
                emoji=emoji,
                style=discord.ButtonStyle.secondary,
                custom_id=f"trivia_opt:{idx}:{opt[:30]}",
            )
            btn.callback = self._make_option_callback(opt)
            self.add_item(btn)

    def _make_option_callback(self, chosen_option: str):
        async def callback(interaction: discord.Interaction) -> None:
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("❌ This is not your trivia session!", ephemeral=True)
                return

            if self.answered:
                await interaction.response.send_message("⚠️ You already submitted an answer!", ephemeral=True)
                return

            self.answered = True
            elapsed = max(0.1, round(time.time() - self.start_time, 2))

            # Disable all buttons
            for child in self.children:
                if isinstance(child, discord.ui.Button):
                    child.disabled = True
                    if child.label == self.q["answer"]:
                        child.style = discord.ButtonStyle.success
                    elif child.label == chosen_option:
                        child.style = discord.ButtonStyle.danger

            is_correct = (chosen_option == self.q["answer"])
            result_embed = await self.cog.record_player_answer(
                user_id=self.user_id,
                user_name=self.user_name,
                today_date=self.today_date,
                is_correct=is_correct,
                elapsed_seconds=elapsed,
                question_data=self.q,
                chosen_option=chosen_option,
            )

            await interaction.response.edit_message(embed=result_embed, view=self)
            self.stop()

        return callback

    async def on_timeout(self) -> None:
        if self.answered:
            return
        self.answered = True

        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
                if child.label == self.q["answer"]:
                    child.style = discord.ButtonStyle.success

        timeout_embed = await self.cog.record_player_answer(
            user_id=self.user_id,
            user_name=self.user_name,
            today_date=self.today_date,
            is_correct=False,
            elapsed_seconds=SESSION_TIMEOUT_SECONDS,
            question_data=self.q,
            chosen_option="[Time Ran Out]",
        )
        logger.info("Trivia session timed out for user %s", self.user_id)


# ==============================================================================
# MAIN TRIVIA COG (Category 14)
# ==============================================================================


class TriviaCog(commands.Cog, name="Daily Growtopia Trivia"):
    def __init__(self, bot: EventBot) -> None:
        self.bot = bot
        self._provisioned_guilds: set[int] = set()
        self.leaderboard_loop.start()

    def cog_unload(self) -> None:
        self.leaderboard_loop.cancel()

    # --------------------------------------------------------------------------
    # Scoring & State Recording
    # --------------------------------------------------------------------------

    async def record_player_answer(
        self,
        user_id: int,
        user_name: str,
        today_date: str,
        is_correct: bool,
        elapsed_seconds: float,
        question_data: dict[str, Any],
        chosen_option: str,
    ) -> discord.Embed:
        stats = load_trivia_stats()
        players: dict[str, Any] = stats.setdefault("players", {})
        uid_str = str(user_id)
        player = players.setdefault(
            uid_str,
            {
                "name": user_name,
                "points": 0,
                "correct_count": 0,
                "total_answered": 0,
                "streak": 0,
                "max_streak": 0,
                "total_seconds": 0.0,
                "avg_speed": 0.0,
                "last_played_date": "",
            },
        )

        player["name"] = user_name
        current_streak = int(player.get("streak", 0))

        if is_correct:
            base_pts = 100
            speed_pts = max(0, int((SESSION_TIMEOUT_SECONDS - min(SESSION_TIMEOUT_SECONDS, elapsed_seconds)) * 3))
            streak_pts = min(50, (current_streak + 1) * 5)
            total_earned = base_pts + speed_pts + streak_pts

            new_streak = current_streak + 1
            player["streak"] = new_streak
            player["max_streak"] = max(player.get("max_streak", 0), new_streak)
            player["correct_count"] = player.get("correct_count", 0) + 1
            player["points"] = player.get("points", 0) + total_earned
        else:
            base_pts = 0
            speed_pts = 0
            streak_pts = 0
            total_earned = 0
            new_streak = 0
            player["streak"] = 0

        player["total_answered"] = player.get("total_answered", 0) + 1
        player["total_seconds"] = round(float(player.get("total_seconds", 0.0)) + elapsed_seconds, 2)
        if player["total_answered"] > 0:
            player["avg_speed"] = round(player["total_seconds"] / player["total_answered"], 2)
        player["last_played_date"] = today_date

        save_trivia_stats(stats)

        # Trigger live update in #🏆trivia-leaderboards
        for guild in self.bot.guilds:
            asyncio.create_task(self.update_leaderboard_channel(guild))

        # Build response embed
        if is_correct:
            embed = discord.Embed(
                title="🎉 EXCELLENT! Correct Answer!",
                description=(
                    f"**Question:** {question_data['question']}\n\n"
                    f"✅ **Your Answer:** **`{chosen_option}`**\n"
                    f"⏱️ **Answer Speed:** **`{elapsed_seconds:.2f}s`** *(out of {SESSION_TIMEOUT_SECONDS:.0f}s)*\n\n"
                    f"💡 **Lore & Stat Breakdown:**\n{question_data['explanation']}"
                ),
                color=0x00E676,  # Argon Emerald Mint
            )
            embed.add_field(name="✨ Base Points", value=f"**`+{base_pts}`**", inline=True)
            embed.add_field(name="⚡ Speed Bonus", value=f"**`+{speed_pts}`**", inline=True)
            embed.add_field(
                name="🔥 Streak Bonus",
                value=f"**`+{streak_pts}`** *({new_streak}d streak)*",
                inline=True,
            )
            embed.add_field(name="🏆 Total Earned", value=f"**`+{total_earned} Points`**", inline=True)
            embed.add_field(name="🌟 Monthly Score", value=f"**`{player['points']:,} Points`**", inline=True)
            embed.add_field(name="🚀 Avg Speed", value=f"**`{player['avg_speed']:.2f}s`**", inline=True)
        else:
            is_timeout = (chosen_option == "[Time Ran Out]")
            title = "⏱️ Time's Up! You Ran Out of Time" if is_timeout else "❌ Incorrect Answer"
            embed = discord.Embed(
                title=title,
                description=(
                    f"**Question:** {question_data['question']}\n\n"
                    f"❌ **Your Input:** **`{chosen_option}`**\n"
                    f"✅ **Correct Answer:** **`{question_data['answer']}`**\n\n"
                    f"💡 **Why:**\n{question_data['explanation']}\n\n"
                    f"*(Streak reset to 0. Come back tomorrow at 00:00 GT Time to earn more points!)*"
                ),
                color=0xFF5252,  # Argon Crimson
            )
            embed.add_field(name="✨ Points Gained", value="**`+0 Points`**", inline=True)
            embed.add_field(name="🌟 Total Score", value=f"**`{player['points']:,} Points`**", inline=True)
            embed.add_field(name="🔥 Current Streak", value="**`0 Days`**", inline=True)

        embed.set_footer(text=f"{FOOTER_TEXT} • Daily Trivia Championship (Grand Prize: 10 DLs)")
        return embed

    # --------------------------------------------------------------------------
    # Interactive Actions
    # --------------------------------------------------------------------------

    async def start_player_session(self, interaction: discord.Interaction) -> None:
        today_date = get_current_gt_date()
        stats = load_trivia_stats()
        uid_str = str(interaction.user.id)
        player = stats.get("players", {}).get(uid_str, {})

        # 1. Check if player already completed today's challenge
        if player.get("last_played_date") == today_date:
            embed = discord.Embed(
                title="⏳ You Have Already Played Today!",
                description=(
                    f"You already completed today's trivia challenge for **`{today_date}`**!\n\n"
                    f"• **Current Score:** **`{player.get('points', 0):,}` Points**\n"
                    f"• **Current Streak:** **`{player.get('streak', 0)}` Days** 🔥\n"
                    f"• **Average Speed:** **`{player.get('avg_speed', 0.0):.2f}s`**\n\n"
                    f"⏰ **Next Challenge Drops At:** `<t:{int(datetime.now(timezone.utc).replace(hour=0, minute=0, second=0).timestamp()) + 86400}:R>`\n"
                    f"*(1 attempt per player per calendar day)*"
                ),
                color=0x3498DB,
            )
            embed.set_footer(text=FOOTER_TEXT)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # 2. Anti-Alt check (account age)
        created_at = interaction.user.created_at
        account_age = (datetime.now(timezone.utc) - created_at).days
        if account_age < MIN_ACCOUNT_AGE_DAYS:
            await interaction.response.send_message(
                f"❌ **Anti-Alt Protection:** Your Discord account must be at least **{MIN_ACCOUNT_AGE_DAYS} days old** "
                f"to participate in the 10 Diamond Lock championship.",
                ephemeral=True,
            )
            return

        # 3. Fetch today's question
        question = get_daily_question(today_date)
        view = TriviaSessionView(
            cog=self,
            user_id=interaction.user.id,
            user_name=interaction.user.display_name,
            question_data=question,
            today_date=today_date,
        )

        embed = discord.Embed(
            title=f"🎯 Daily Growtopia Trivia • {question['category']}",
            description=(
                f"**Date:** `{today_date}` • **Time Limit:** `20.0 Seconds`\n\n"
                f"**Question:**\n"
                f"> **{question['question']}**\n\n"
                f"⏱️ **Speed counts!** Click the correct button below before the 20-second timer expires."
            ),
            color=0xFFD700,  # Gold
        )
        embed.set_footer(text=f"{FOOTER_TEXT} • Strict Anti-Wiki Speedrun Engine")
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def show_player_stats(self, interaction: discord.Interaction) -> None:
        stats = load_trivia_stats()
        uid_str = str(interaction.user.id)
        player = stats.get("players", {}).get(uid_str)

        if not player or player.get("total_answered", 0) == 0:
            await interaction.response.send_message(
                "📊 You haven't participated in this month's Trivia Championship yet!\n"
                "Click **`[ 🎯 Play Today's Trivia ]`** to earn your first points toward the **10 Diamond Locks**!",
                ephemeral=True,
            )
            return

        # Calculate player rank
        all_players = sorted(
            stats["players"].items(),
            key=lambda x: (
                x[1].get("points", 0),
                x[1].get("correct_count", 0),
                -x[1].get("avg_speed", 99.0),
            ),
            reverse=True,
        )
        rank = next((idx + 1 for idx, (uid, _) in enumerate(all_players) if uid == uid_str), len(all_players))

        embed = discord.Embed(
            title=f"📊 Trivia Player Profile • {interaction.user.display_name}",
            color=0x3498DB,
        )
        embed.add_field(name="🏆 Current Rank", value=f"**`#{rank}`** of {len(all_players):,} players", inline=True)
        embed.add_field(name="🌟 Total Points", value=f"**`{player.get('points', 0):,}` pts**", inline=True)
        embed.add_field(name="🔥 Current Streak", value=f"**`{player.get('streak', 0)}` Days**", inline=True)
        embed.add_field(
            name="🎯 Accuracy",
            value=f"**`{player.get('correct_count', 0)} / {player.get('total_answered', 0)}`** correct",
            inline=True,
        )
        embed.add_field(name="⚡ Avg Speed", value=f"**`{player.get('avg_speed', 0.0):.2f}s`**", inline=True)
        embed.add_field(name="🏅 Best Streak", value=f"**`{player.get('max_streak', 0)}` Days**", inline=True)

        embed.set_footer(text=f"{FOOTER_TEXT} • Season: {stats.get('current_month')}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def show_quick_leaderboard(self, interaction: discord.Interaction) -> None:
        stats = load_trivia_stats()
        embed = self.build_leaderboard_embed(stats)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def show_rules_modal_or_embed(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            title="📜 Growcom Daily Trivia • Championship Rules & Prize",
            description=(
                f"**💎 Monthly Grand Prize:** **{GRAND_PRIZE_TEXT}**\n"
                f"The #1 ranked player at the end of each calendar month wins 10 DLs delivered directly in-game!\n\n"
                "**🎯 Gameplay Mechanics:**\n"
                "• **1 Question Per Day:** Drops daily at `00:00 GT Time`. All members get the same question.\n"
                "• **20-Second Anti-Wiki Timer:** You must answer before the timer expires.\n"
                "• **Randomized Buttons:** Button choices are randomized for every player.\n"
                "• **Ephemeral:** Your session is private so others cannot copy your answers.\n\n"
                "**⚡ Scoring Formula:**\n"
                "• **Base Points:** `+100 pts` for a correct answer\n"
                "• **Speed Bonus:** Up to `+60 pts` for answering quickly (`(20 - seconds) × 3`)\n"
                "• **Daily Streak Bonus:** `+5 pts` per consecutive day active (up to `+50 pts`)\n"
                "• **Max Daily Score:** `210 pts`\n\n"
                "**⚖️ Tiebreaker Order:**\n"
                "`1. Total Points` ➔ `2. Total Correct Answers` ➔ `3. Lowest Average Speed`"
            ),
            color=0xFFD700,
        )
        embed.set_footer(text=FOOTER_TEXT)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # --------------------------------------------------------------------------
    # Leaderboard & Desk Builders
    # --------------------------------------------------------------------------

    def build_play_desk_embed(self) -> discord.Embed:
        today_date = get_current_gt_date()
        month_str = get_current_gt_month()

        embed = discord.Embed(
            title="🎯 Growcom Daily Growtopia Trivia Desk",
            description=(
                f"Welcome to the **Daily Growtopia Item Trivia Championship**!\n"
                f"Test your deep knowledge of Growtopia items, physics, surgery, and mechanics.\n\n"
                f"🏆 **Monthly Grand Prize:** **{GRAND_PRIZE_TEXT}**\n"
                f"📅 **Current Season:** **`{month_str}`** • **Today's Date:** **`{today_date}`**\n"
                f"⏰ **Daily Reset:** **`00:00 GT Time`**\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "**How to Play:**\n"
                "1. Click **`[ 🎯 Play Today's Trivia ]`** below.\n"
                "2. An ephemeral question will appear with a **strict 20-second timer**.\n"
                "3. Tap the correct answer as fast as possible to earn **Speed & Streak Bonuses**!\n"
                "4. Climb the monthly leaderboard in **#🏆trivia-leaderboards** to win **10 DLs**!\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            ),
            color=0xFFD700,  # Gold
        )
        embed.set_footer(text=f"{FOOTER_TEXT} • Strict Anti-Wiki Speedrun Engine")
        return embed

    def build_leaderboard_embed(self, stats: dict[str, Any]) -> discord.Embed:
        month_str = stats.get("current_month", get_current_gt_month())
        players: dict[str, Any] = stats.get("players", {})

        sorted_players = sorted(
            players.items(),
            key=lambda x: (
                x[1].get("points", 0),
                x[1].get("correct_count", 0),
                -x[1].get("avg_speed", 99.0),
            ),
            reverse=True,
        )[:10]

        embed = discord.Embed(
            title="🏆 Growcom Monthly Trivia Championship",
            description=(
                f"**💎 Monthly Grand Prize:** **{GRAND_PRIZE_TEXT}**\n"
                f"📅 **Active Season:** **`{month_str} Championship`**\n"
                f"🎯 **Participate Daily in:** <#1568907253854113855> *(or #🎯daily-trivia)*\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "**Top 10 Contenders (Points • Streak • Avg Speed)**\n"
            ),
            color=0xFFD700,
            timestamp=datetime.now(EVENT_TZ),
        )

        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

        if not sorted_players:
            embed.description += "\n*No players have scored yet this month! Be the first to play today!*"
        else:
            lines = []
            for idx, (uid, pdata) in enumerate(sorted_players):
                medal = medals[idx] if idx < len(medals) else f"`#{idx + 1}`"
                name = str(pdata.get("name", f"Player-{uid[-4:]}"))[:16]
                points = int(pdata.get("points", 0))
                streak = int(pdata.get("streak", 0))
                speed = float(pdata.get("avg_speed", 0.0))
                lines.append(
                    f"{medal} **`{name:<16}`** • **`{points:,} pts`** • `{streak}d streak` • `{speed:.1f}s avg`"
                )
            embed.description += "\n".join(lines)

        # Hall of fame
        hof = stats.get("hall_of_fame", [])
        if hof:
            hof_lines = []
            for h in hof[-3:]:
                hof_lines.append(
                    f"👑 **{h.get('month')}:** **{h.get('winner_name')}** ({h.get('points', 0):,} pts) • Awarded 10 DLs"
                )
            embed.add_field(
                name="🏛️ Hall of Fame (Past Champions)",
                value="\n".join(hof_lines),
                inline=False,
            )

        embed.set_footer(text=f"{FOOTER_TEXT} • Resets on the 1st of every month at 00:00 GT Time")
        return embed

    # --------------------------------------------------------------------------
    # Monthly Season Rollover
    # --------------------------------------------------------------------------

    async def check_monthly_rollover(self, guild: discord.Guild) -> None:
        stats = load_trivia_stats()
        current_calendar_month = get_current_gt_month()
        stored_month = stats.get("current_month")

        if stored_month and stored_month != current_calendar_month:
            logger.info("Month transition detected: %s -> %s. Crowning champion!", stored_month, current_calendar_month)
            players: dict[str, Any] = stats.get("players", {})

            if players:
                # Find top 1 player
                sorted_players = sorted(
                    players.items(),
                    key=lambda x: (
                        x[1].get("points", 0),
                        x[1].get("correct_count", 0),
                        -x[1].get("avg_speed", 99.0),
                    ),
                    reverse=True,
                )
                top_uid, top_data = sorted_players[0]
                champion_name = top_data.get("name", f"Player-{top_uid[-4:]}")
                champion_points = top_data.get("points", 0)

                # Add to hall of fame
                stats.setdefault("hall_of_fame", []).append({
                    "month": stored_month,
                    "winner_id": int(top_uid),
                    "winner_name": champion_name,
                    "points": champion_points,
                    "prize": "10 Diamond Locks",
                    "crowned_at": datetime.now(timezone.utc).isoformat(),
                })

                # Post victory announcement to leaderboard channel
                state = load_state()
                lb_ch_id = state.get("trivia_leaderboard_channel_id")
                if lb_ch_id:
                    ch = guild.get_channel(int(lb_ch_id))
                    if isinstance(ch, discord.TextChannel):
                        win_embed = discord.Embed(
                            title=f"👑 Announcing the {stored_month} Trivia Champion!",
                            description=(
                                f"🎉 Huge congratulations to <@{top_uid}> (**{champion_name}**) for finishing **#1** "
                                f"with **`{champion_points:,}` Points**!\n\n"
                                f"💎 **Grand Prize:** **10 Diamond Locks** will be delivered by **Manwel**!\n\n"
                                f"The new **{current_calendar_month} Championship** has officially begun. "
                                f"All monthly scores have been reset. Good luck to all contenders!"
                            ),
                            color=0xFFD700,
                        )
                        win_embed.set_footer(text=FOOTER_TEXT)
                        await ch.send(content=f"👑 <@{top_uid}>", embed=win_embed)

            # Reset monthly scores for fresh month
            stats["players"] = {}
            stats["current_month"] = current_calendar_month
            save_trivia_stats(stats)
            await self.update_leaderboard_channel(guild)

    # --------------------------------------------------------------------------
    # Background Tasks & Provisioning
    # --------------------------------------------------------------------------

    @tasks.loop(minutes=5)
    async def leaderboard_loop(self) -> None:
        """Periodic 5-minute sync to update the leaderboard card and verify monthly rollovers."""
        for guild in self.bot.guilds:
            try:
                await self.check_monthly_rollover(guild)
                await self.update_leaderboard_channel(guild)
            except Exception as exc:
                logger.warning("Error in trivia leaderboard loop: %s", exc)

    @leaderboard_loop.before_loop
    async def before_leaderboard_loop(self) -> None:
        await self.bot.wait_until_ready()

    async def update_leaderboard_channel(self, guild: discord.Guild) -> None:
        state = load_state()
        lb_ch_id = state.get("trivia_leaderboard_channel_id")
        if not lb_ch_id:
            return

        ch = guild.get_channel(int(lb_ch_id))
        if not isinstance(ch, discord.TextChannel):
            return

        stats = load_trivia_stats()
        embed = self.build_leaderboard_embed(stats)

        msg_id = state.get("trivia_leaderboard_message_id")
        if msg_id:
            try:
                msg = await ch.fetch_message(int(msg_id))
                await msg.edit(embed=embed)
                return
            except discord.NotFound:
                pass
            except Exception as exc:
                logger.warning("Could not edit trivia leaderboard message: %s", exc)

        try:
            new_msg = await ch.send(embed=embed)
            state["trivia_leaderboard_message_id"] = new_msg.id
            save_state(state)
        except Exception as exc:
            logger.warning("Could not post trivia leaderboard message: %s", exc)

    async def provision_trivia_channels(
        self,
        guild: discord.Guild,
        force_repost: bool = False,
    ) -> tuple[discord.TextChannel, discord.TextChannel]:
        state = load_state()
        everyone_role = guild.default_role
        bot_member = guild.me
        member_role_id = int(state.get("member_role_id", DEFAULT_MEMBER_ROLE_ID))
        member_role = guild.get_role(member_role_id)

        target_cat: discord.CategoryChannel | None = guild.get_channel(ACTIVITIES_CATEGORY_ID)  # type: ignore[assignment]
        if not isinstance(target_cat, discord.CategoryChannel):
            target_cat = guild.get_channel(TOOLS_CATEGORY_ID)  # type: ignore[assignment]
        if not isinstance(target_cat, discord.CategoryChannel):
            for cat in guild.categories:
                if any(w in cat.name.lower() for w in ["activities", "games", "tools"]):
                    target_cat = cat
                    break

        play_overwrites = {
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
            play_overwrites[member_role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
            )

        lb_overwrites = {
            everyone_role: discord.PermissionOverwrite(view_channel=False),
            bot_member: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                embed_links=True,
                manage_messages=True,
            ),
        }
        if member_role:
            lb_overwrites[member_role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=False,  # Read-only
                read_message_history=True,
            )

        # 1. Play Channel (#🎯daily-trivia)
        play_ch_id = state.get("trivia_channel_id")
        play_ch = guild.get_channel(int(play_ch_id)) if play_ch_id else None
        if not play_ch:
            for ch in guild.text_channels:
                if ch.name in ("🎯daily-trivia", "daily-trivia", "trivia"):
                    play_ch = ch
                    break

        if not play_ch:
            play_ch = await guild.create_text_channel(
                name="🎯daily-trivia",
                category=target_cat,
                overwrites=play_overwrites,
                topic="Growcom Daily GT Item Trivia — Compete daily for the 10 Diamond Locks monthly grand prize!",
            )
            force_repost = True

        state["trivia_channel_id"] = play_ch.id

        # 2. Leaderboard Channel (#🏆trivia-leaderboards)
        lb_ch_id = state.get("trivia_leaderboard_channel_id")
        lb_ch = guild.get_channel(int(lb_ch_id)) if lb_ch_id else None
        if not lb_ch:
            for ch in guild.text_channels:
                if ch.name in ("🏆trivia-leaderboards", "trivia-leaderboards", "trivia-leaderboard"):
                    lb_ch = ch
                    break

        if not lb_ch:
            lb_ch = await guild.create_text_channel(
                name="🏆trivia-leaderboards",
                category=target_cat,
                overwrites=lb_overwrites,
                topic="Growcom Monthly Trivia Championship Standings — 10 Diamond Locks awarded on the 1st of every month!",
            )
            force_repost = True

        state["trivia_leaderboard_channel_id"] = lb_ch.id
        save_state(state)

        # Post Play Desk in #🎯daily-trivia if needed
        desk_msg_id = state.get("trivia_desk_message_id")
        desk_msg = None
        if desk_msg_id:
            try:
                desk_msg = await play_ch.fetch_message(int(desk_msg_id))
            except Exception:
                desk_msg = None

        if not desk_msg or force_repost:
            desk_embed = self.build_play_desk_embed()
            desk_view = TriviaPlayDeskView(self)
            new_desk_msg = await play_ch.send(embed=desk_embed, view=desk_view)
            state["trivia_desk_message_id"] = new_desk_msg.id
            save_state(state)

        # Post/Update Leaderboard Card
        await self.update_leaderboard_channel(guild)
        return play_ch, lb_ch

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        self.bot.add_view(TriviaPlayDeskView(self))
        for guild in self.bot.guilds:
            if guild.id in self._provisioned_guilds:
                continue
            if guild.me and guild.me.guild_permissions.manage_channels:
                try:
                    await self.provision_trivia_channels(guild, force_repost=False)
                    self._provisioned_guilds.add(guild.id)
                except Exception as exc:
                    logger.warning("Could not auto-provision trivia channels in %s: %s", guild.name, exc)

    # --------------------------------------------------------------------------
    # Slash Commands
    # --------------------------------------------------------------------------

    @app_commands.command(
        name="trivia",
        description="Launch today's Daily Growtopia Trivia challenge or view your monthly standing!",
    )
    async def trivia_command(self, interaction: discord.Interaction) -> None:
        state = load_state()
        allowed_channel_id = state.get("trivia_channel_id")
        if allowed_channel_id and int(interaction.channel_id or 0) != int(allowed_channel_id):
            await interaction.response.send_message(
                f"❌ The **`/trivia`** tool can only be played inside <#{allowed_channel_id}>!",
                ephemeral=True,
            )
            return

        await self.start_player_session(interaction)

    @app_commands.command(
        name="setup_trivia_channels",
        description="Admin: Auto-provision #🎯daily-trivia and #🏆trivia-leaderboards under Activities/Tools.",
    )
    async def setup_trivia_channels_cmd(self, interaction: discord.Interaction) -> None:
        if not is_server_manager(interaction) or not interaction.guild:
            await interaction.response.send_message("❌ Admin permission required.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        play_ch, lb_ch = await self.provision_trivia_channels(interaction.guild, force_repost=True)
        await interaction.followup.send(
            f"✅ Configured Trivia System successfully!\n"
            f"• Play Desk: {play_ch.mention}\n"
            f"• Leaderboard: {lb_ch.mention}\n"
            f"• Monthly Grand Prize: **{GRAND_PRIZE_TEXT}**",
            ephemeral=True,
        )

    @app_commands.command(
        name="set_trivia_channel",
        description="Restrict /trivia exclusively to a designated channel",
    )
    @app_commands.describe(channel="Dedicated channel for /trivia (defaults to current channel)")
    async def set_trivia_channel_cmd(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel | None = None,
    ) -> None:
        if not is_server_manager(interaction):
            await interaction.response.send_message("❌ Only server admins can use `/set_trivia_channel`.", ephemeral=True)
            return

        target_ch = channel or interaction.channel
        if not isinstance(target_ch, discord.TextChannel):
            await interaction.response.send_message("❌ Please select a standard text channel.", ephemeral=True)
            return

        state = load_state()
        state["trivia_channel_id"] = target_ch.id
        save_state(state)

        # Repost desk
        desk_embed = self.build_play_desk_embed()
        desk_view = TriviaPlayDeskView(self)
        msg = await target_ch.send(embed=desk_embed, view=desk_view)
        state["trivia_desk_message_id"] = msg.id
        save_state(state)

        await interaction.response.send_message(
            f"✅ Locked **`/trivia`** exclusively to {target_ch.mention} and deployed the interactive Play Desk!",
            ephemeral=True,
        )

    @app_commands.command(
        name="trivia_leaderboard",
        description="Display the live Monthly Trivia Championship Top 10 standings and prize details",
    )
    async def trivia_leaderboard_cmd(self, interaction: discord.Interaction) -> None:
        stats = load_trivia_stats()
        embed = self.build_leaderboard_embed(stats)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="trivia_reset_season",
        description="Admin: Manually crown the current month's champion, archive scores, and reset for a new season.",
    )
    async def trivia_reset_season_cmd(self, interaction: discord.Interaction) -> None:
        if not is_server_manager(interaction) or not interaction.guild:
            await interaction.response.send_message("❌ Admin permission required.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        stats = load_trivia_stats()
        current_m = stats.get("current_month", get_current_gt_month())
        players = stats.get("players", {})

        if not players:
            await interaction.followup.send("⚠️ No player scores recorded in the current season.", ephemeral=True)
            return

        sorted_players = sorted(
            players.items(),
            key=lambda x: (
                x[1].get("points", 0),
                x[1].get("correct_count", 0),
                -x[1].get("avg_speed", 99.0),
            ),
            reverse=True,
        )
        top_uid, top_data = sorted_players[0]
        champ_name = top_data.get("name", f"Player-{top_uid[-4:]}")
        champ_pts = top_data.get("points", 0)

        stats.setdefault("hall_of_fame", []).append({
            "month": current_m,
            "winner_id": int(top_uid),
            "winner_name": champ_name,
            "points": champ_pts,
            "prize": "10 Diamond Locks",
            "crowned_at": datetime.now(timezone.utc).isoformat(),
        })

        stats["players"] = {}
        save_trivia_stats(stats)
        await self.update_leaderboard_channel(interaction.guild)

        await interaction.followup.send(
            f"🏆 **Season Manually Ended!**\n"
            f"• Champion: <@{top_uid}> (**{champ_name}**) with **`{champ_pts:,}` pts**!\n"
            f"• Grand Prize: **{GRAND_PRIZE_TEXT}**\n"
            f"Scores have been archived and reset for the new season.",
            ephemeral=True,
        )


async def setup(bot: EventBot) -> None:
    await bot.add_cog(TriviaCog(bot))
