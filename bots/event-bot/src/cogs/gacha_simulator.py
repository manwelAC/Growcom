"""
Category 18: Growtopia Gacha Simulator & Per-Category Live Leaderboards (cogs/gacha_simulator.py)
- /gacha (Roll 1x, 10x, 25x, or 50x on 5 iconic Growtopia Gacha events with a 1-minute per-user cooldown)
- Synced to the official 2024–2026 Growtopia Wiki (growtopiawiki.com) Event Drop Tables (40 items per Gacha = 200+ items total!)
- Balanced 100.00% probability distribution so no single item exceeds 5% weight:
  • 🌟 MYTHIC JACKPOT: 0.25% total (4 Mythics per pool)
  • 🔥 ULTRA RARE:     1.25% total (5 Ultra Rares per pool)
  • ✨ SUPER RARE:     5.50% total (6 Super Rares per pool)
  • 💜 RARE:          16.00% total (8 Rares per pool — 2.00% each)
  • 💙 UNCOMMON:      32.00% total (8 Uncommons per pool — 4.00% each)
  • 🤍 COMMON:        45.00% total (9 Commons per pool — 5.00% each)
- Read-only #🏆gacha-leaderboards with sleek Pill-Row Table leaderboards
"""

from __future__ import annotations

from datetime import datetime
import json
import random
import re
import time
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs, quote, unquote

import discord
from discord import app_commands
from discord.ext import commands, tasks

from utils.helpers import (
    EVENT_TZ,
    FOOTER_TEXT,
    PROJECT_ROOT,
    load_state,
    logger,
    save_state,
)

if TYPE_CHECKING:
    from bot import EventBot

ACTIVITIES_CATEGORY_ID = 1567242649893609512
MEMBER_ROLE_ID = 1568495447067332608
GACHA_COOLDOWN_SECONDS = 60
GACHA_STATS_FILE = PROJECT_ROOT / "bots" / "event-bot" / "data" / "gacha_stats.json"


# Official 2024–2026 Growtopia Wiki (growtopiawiki.com) Gacha Pools (40 items per pool, summing to 100.00% weight)
GACHA_POOLS: dict[str, dict[str, Any]] = {
    "valentine_gbc": {
        "name": "Valentine's Super GBC",
        "short_name": "Valentine's GBC",
        "emoji": "💘",
        "cost_wl": 5,
        "color": (233, 30, 99),
        "banner_desc": "Smash **Super Golden Booty Chests** & **Well of Love** (2024–2026 Pool) for **GHC**, **Golden Ribbon Wings**, & **Golden Sparkling Mallet**!",
        "jackpot_item": "Golden Heart Crystal / Golden Ribbon Wings",
        "drops": [
            # 🌟 MYTHIC JACKPOT (0.25% total)
            {"name": "Golden Heart Crystal", "rarity_tier": "🌟 MYTHIC JACKPOT", "short_tier": "MYTHIC", "weight": 0.08, "wl_value": 12500, "emoji": "💎"},
            {"name": "Golden Ribbon Wings", "rarity_tier": "🌟 MYTHIC JACKPOT", "short_tier": "MYTHIC", "weight": 0.06, "wl_value": 9500, "emoji": "🎀"},
            {"name": "Golden Angel Wings", "rarity_tier": "🌟 MYTHIC JACKPOT", "short_tier": "MYTHIC", "weight": 0.06, "wl_value": 8500, "emoji": "👼"},
            {"name": "Golden Sparkling Mallet", "rarity_tier": "🌟 MYTHIC JACKPOT", "short_tier": "MYTHIC", "weight": 0.05, "wl_value": 8000, "emoji": "🔨"},
            # 🔥 ULTRA RARE (1.25% total — 0.25% each)
            {"name": "Ribbon Wings", "rarity_tier": "🔥 ULTRA RARE", "short_tier": "ULTRA RARE", "weight": 0.25, "wl_value": 1800, "emoji": "🎀"},
            {"name": "Heartbreak Wings", "rarity_tier": "🔥 ULTRA RARE", "short_tier": "ULTRA RARE", "weight": 0.25, "wl_value": 1600, "emoji": "💔"},
            {"name": "Mobile Suit Wings", "rarity_tier": "🔥 ULTRA RARE", "short_tier": "ULTRA RARE", "weight": 0.25, "wl_value": 1500, "emoji": "🤖"},
            {"name": "Lovey Dovey Mantle", "rarity_tier": "🔥 ULTRA RARE", "short_tier": "ULTRA RARE", "weight": 0.25, "wl_value": 1400, "emoji": "🧣"},
            {"name": "Stained Glass Crown", "rarity_tier": "🔥 ULTRA RARE", "short_tier": "ULTRA RARE", "weight": 0.25, "wl_value": 1250, "emoji": "👑"},
            # ✨ SUPER RARE (5.50% total)
            {"name": "Angelic Circlet", "rarity_tier": "✨ SUPER RARE", "short_tier": "SUPER RARE", "weight": 0.85, "wl_value": 220, "emoji": "😇"},
            {"name": "Sparkling Mallet", "rarity_tier": "✨ SUPER RARE", "short_tier": "SUPER RARE", "weight": 0.90, "wl_value": 180, "emoji": "🔨"},
            {"name": "Quiver of Hearts", "rarity_tier": "✨ SUPER RARE", "short_tier": "SUPER RARE", "weight": 0.90, "wl_value": 160, "emoji": "🏹"},
            {"name": "Stained Glass Scepter", "rarity_tier": "✨ SUPER RARE", "short_tier": "SUPER RARE", "weight": 0.95, "wl_value": 140, "emoji": "🪄"},
            {"name": "Cotton Candy Cape", "rarity_tier": "✨ SUPER RARE", "short_tier": "SUPER RARE", "weight": 0.95, "wl_value": 120, "emoji": "☁️"},
            {"name": "Heartbow", "rarity_tier": "✨ SUPER RARE", "short_tier": "SUPER RARE", "weight": 0.95, "wl_value": 85, "emoji": "🏹"},
            # 💜 RARE (16.00% total — 2.00% each)
            {"name": "Angel Wings", "rarity_tier": "💜 RARE", "short_tier": "RARE", "weight": 2.00, "wl_value": 65, "emoji": "🪽"},
            {"name": "Hair Longbow", "rarity_tier": "💜 RARE", "short_tier": "RARE", "weight": 2.00, "wl_value": 35, "emoji": "🎀"},
            {"name": "Cupcake Pet", "rarity_tier": "💜 RARE", "short_tier": "RARE", "weight": 2.00, "wl_value": 30, "emoji": "🧁"},
            {"name": "Rose Cape", "rarity_tier": "💜 RARE", "short_tier": "RARE", "weight": 2.00, "wl_value": 25, "emoji": "🌹"},
            {"name": "Crimson Thief Coat", "rarity_tier": "💜 RARE", "short_tier": "RARE", "weight": 2.00, "wl_value": 22, "emoji": "🧥"},
            {"name": "Crimson Thief Mask", "rarity_tier": "💜 RARE", "short_tier": "RARE", "weight": 2.00, "wl_value": 20, "emoji": "🎭"},
            {"name": "Lace Parasol", "rarity_tier": "💜 RARE", "short_tier": "RARE", "weight": 2.00, "wl_value": 18, "emoji": "☂️"},
            {"name": "Good Witch's Wand", "rarity_tier": "💜 RARE", "short_tier": "RARE", "weight": 2.00, "wl_value": 15, "emoji": "🪄"},
            # 💙 UNCOMMON (32.00% total — 4.00% each)
            {"name": "Heart Portrait", "rarity_tier": "💙 UNCOMMON", "short_tier": "UNCOMMON", "weight": 4.00, "wl_value": 6, "emoji": "🖼️"},
            {"name": "Knee High Stockings", "rarity_tier": "💙 UNCOMMON", "short_tier": "UNCOMMON", "weight": 4.00, "wl_value": 6, "emoji": "🧦"},
            {"name": "Rainbow Platform", "rarity_tier": "💙 UNCOMMON", "short_tier": "UNCOMMON", "weight": 4.00, "wl_value": 5, "emoji": "🌈"},
            {"name": "Ladybug Trampoline", "rarity_tier": "💙 UNCOMMON", "short_tier": "UNCOMMON", "weight": 4.00, "wl_value": 5, "emoji": "🐞"},
            {"name": "Ceremonial Altar", "rarity_tier": "💙 UNCOMMON", "short_tier": "UNCOMMON", "weight": 4.00, "wl_value": 5, "emoji": "⛩️"},
            {"name": "Formal Rose Necktie", "rarity_tier": "💙 UNCOMMON", "short_tier": "UNCOMMON", "weight": 4.00, "wl_value": 4, "emoji": "👔"},
            {"name": "Teeny Angel Wings", "rarity_tier": "💙 UNCOMMON", "short_tier": "UNCOMMON", "weight": 4.00, "wl_value": 4, "emoji": "🪽"},
            {"name": "Pegasus", "rarity_tier": "💙 UNCOMMON", "short_tier": "UNCOMMON", "weight": 4.00, "wl_value": 4, "emoji": "🦄"},
            # 🤍 COMMON (45.00% total — 5.00% each)
            {"name": "Flower Vase", "rarity_tier": "🤍 COMMON", "short_tier": "COMMON", "weight": 5.00, "wl_value": 2, "emoji": "🏺"},
            {"name": "Fluttering Bunting", "rarity_tier": "🤍 COMMON", "short_tier": "COMMON", "weight": 5.00, "wl_value": 2, "emoji": "🎏"},
            {"name": "Potpourri Dispenser", "rarity_tier": "🤍 COMMON", "short_tier": "COMMON", "weight": 5.00, "wl_value": 2, "emoji": "🌸"},
            {"name": "Lovely Lollipop", "rarity_tier": "🤍 COMMON", "short_tier": "COMMON", "weight": 5.00, "wl_value": 1, "emoji": "🍭"},
            {"name": "Bear That Cares", "rarity_tier": "🤍 COMMON", "short_tier": "COMMON", "weight": 5.00, "wl_value": 1, "emoji": "🧸"},
            {"name": "Love Birds", "rarity_tier": "🤍 COMMON", "short_tier": "COMMON", "weight": 5.00, "wl_value": 1, "emoji": "🐦"},
            {"name": "Heartstone Block (x10)", "rarity_tier": "🤍 COMMON", "short_tier": "COMMON", "weight": 5.00, "wl_value": 1, "emoji": "🧱"},
            {"name": "Cotton Candy Swirl (x10)", "rarity_tier": "🤍 COMMON", "short_tier": "COMMON", "weight": 5.00, "wl_value": 1, "emoji": "🍥"},
            {"name": "Candy Heart (x5)", "rarity_tier": "🤍 COMMON", "short_tier": "COMMON", "weight": 5.00, "wl_value": 1, "emoji": "🍬"},
        ],
    },
    "summer_fireworks": {
        "name": "SummerFest Super Fireworks",
        "short_name": "SummerFest Fireworks",
        "emoji": "🎆",
        "cost_wl": 8,
        "color": (255, 152, 0),
        "banner_desc": "Launch **Super Fireworks** & **Artifact Chests** (2024–2026 Pool) for **Noble Phoenix**, **Neptune's Gauntlet**, & **Phoenix Wings**!",
        "jackpot_item": "Noble Phoenix / Phoenix Wings",
        "drops": [
            # 🌟 MYTHIC JACKPOT (0.25% total)
            {"name": "Noble Phoenix", "rarity_tier": "🌟 MYTHIC JACKPOT", "short_tier": "MYTHIC", "weight": 0.06, "wl_value": 25000, "emoji": "🔥"},
            {"name": "Phoenix Wings", "rarity_tier": "🌟 MYTHIC JACKPOT", "short_tier": "MYTHIC", "weight": 0.06, "wl_value": 22000, "emoji": "🦅"},
            {"name": "Neptune's Gauntlet", "rarity_tier": "🌟 MYTHIC JACKPOT", "short_tier": "MYTHIC", "weight": 0.07, "wl_value": 19500, "emoji": "🔱"},
            {"name": "Phoenix Paraglider", "rarity_tier": "🌟 MYTHIC JACKPOT", "short_tier": "MYTHIC", "weight": 0.06, "wl_value": 16500, "emoji": "🪂"},
            # 🔥 ULTRA RARE (1.25% total — 0.25% each)
            {"name": "Neptune's Pendant", "rarity_tier": "🔥 ULTRA RARE", "short_tier": "ULTRA RARE", "weight": 0.25, "wl_value": 6500, "emoji": "📿"},
            {"name": "Phoenix Mantle", "rarity_tier": "🔥 ULTRA RARE", "short_tier": "ULTRA RARE", "weight": 0.25, "wl_value": 4200, "emoji": "🧣"},
            {"name": "Phoenix Pacifier", "rarity_tier": "🔥 ULTRA RARE", "short_tier": "ULTRA RARE", "weight": 0.25, "wl_value": 3200, "emoji": "🔥"},
            {"name": "Ultraviolet Crown", "rarity_tier": "🔥 ULTRA RARE", "short_tier": "ULTRA RARE", "weight": 0.25, "wl_value": 2800, "emoji": "👑"},
            {"name": "Lantern's ChronoReaper", "rarity_tier": "🔥 ULTRA RARE", "short_tier": "ULTRA RARE", "weight": 0.25, "wl_value": 2200, "emoji": "⚔️"},
            # ✨ SUPER RARE (5.50% total)
            {"name": "Occean's Eternal Wake", "rarity_tier": "✨ SUPER RARE", "short_tier": "SUPER RARE", "weight": 0.85, "wl_value": 280, "emoji": "🌊"},
            {"name": "Ultra Red Phoenix Frag", "rarity_tier": "✨ SUPER RARE", "short_tier": "SUPER RARE", "weight": 0.90, "wl_value": 240, "emoji": "🟥"},
            {"name": "Ultra Blue Neptune Frag", "rarity_tier": "✨ SUPER RARE", "short_tier": "SUPER RARE", "weight": 0.90, "wl_value": 210, "emoji": "🟦"},
            {"name": "Phoenix Sword", "rarity_tier": "✨ SUPER RARE", "short_tier": "SUPER RARE", "weight": 0.95, "wl_value": 160, "emoji": "🗡️"},
            {"name": "Poseidon's Trident", "rarity_tier": "✨ SUPER RARE", "short_tier": "SUPER RARE", "weight": 0.95, "wl_value": 130, "emoji": "🔱"},
            {"name": "Sharkzooka", "rarity_tier": "✨ SUPER RARE", "short_tier": "SUPER RARE", "weight": 0.95, "wl_value": 110, "emoji": "🦈"},
            # 💜 RARE (16.00% total — 2.00% each)
            {"name": "Cool Capybara", "rarity_tier": "💜 RARE", "short_tier": "RARE", "weight": 2.00, "wl_value": 38, "emoji": "🦫"},
            {"name": "Ice Cream Truck", "rarity_tier": "💜 RARE", "short_tier": "RARE", "weight": 2.00, "wl_value": 32, "emoji": "🍦"},
            {"name": "Slipper Floatie", "rarity_tier": "💜 RARE", "short_tier": "RARE", "weight": 2.00, "wl_value": 28, "emoji": "🩴"},
            {"name": "Super Summer Surprise", "rarity_tier": "💜 RARE", "short_tier": "RARE", "weight": 2.00, "wl_value": 25, "emoji": "🎁"},
            {"name": "Oceanic Crown", "rarity_tier": "💜 RARE", "short_tier": "RARE", "weight": 2.00, "wl_value": 22, "emoji": "👑"},
            {"name": "Leaf Wings", "rarity_tier": "💜 RARE", "short_tier": "RARE", "weight": 2.00, "wl_value": 20, "emoji": "🍃"},
            {"name": "Riding Flamingo", "rarity_tier": "💜 RARE", "short_tier": "RARE", "weight": 2.00, "wl_value": 18, "emoji": "🦩"},
            {"name": "Summer Surprise", "rarity_tier": "💜 RARE", "short_tier": "RARE", "weight": 2.00, "wl_value": 16, "emoji": "📦"},
            # 💙 UNCOMMON (32.00% total — 4.00% each)
            {"name": "Resting Goggles", "rarity_tier": "💙 UNCOMMON", "short_tier": "UNCOMMON", "weight": 4.00, "wl_value": 7, "emoji": "🥽"},
            {"name": "Whirlpool", "rarity_tier": "💙 UNCOMMON", "short_tier": "UNCOMMON", "weight": 4.00, "wl_value": 6, "emoji": "🌀"},
            {"name": "Drowned Dreads", "rarity_tier": "💙 UNCOMMON", "short_tier": "UNCOMMON", "weight": 4.00, "wl_value": 6, "emoji": "💇"},
            {"name": "Bek and Cal", "rarity_tier": "💙 UNCOMMON", "short_tier": "UNCOMMON", "weight": 4.00, "wl_value": 5, "emoji": "🐦"},
            {"name": "Lifeguard Jacket", "rarity_tier": "💙 UNCOMMON", "short_tier": "UNCOMMON", "weight": 4.00, "wl_value": 5, "emoji": "🦺"},
            {"name": "Hydro Cannon", "rarity_tier": "💙 UNCOMMON", "short_tier": "UNCOMMON", "weight": 4.00, "wl_value": 5, "emoji": "🔫"},
            {"name": "Greg, The Octopus", "rarity_tier": "💙 UNCOMMON", "short_tier": "UNCOMMON", "weight": 4.00, "wl_value": 4, "emoji": "🐙"},
            {"name": "Pet Toucan", "rarity_tier": "💙 UNCOMMON", "short_tier": "UNCOMMON", "weight": 4.00, "wl_value": 4, "emoji": "🦜"},
            # 🤍 COMMON (45.00% total — 5.00% each)
            {"name": "Palm Tree with Lights", "rarity_tier": "🤍 COMMON", "short_tier": "COMMON", "weight": 5.00, "wl_value": 2, "emoji": "🌴"},
            {"name": "Sand Palace (x3)", "rarity_tier": "🤍 COMMON", "short_tier": "COMMON", "weight": 5.00, "wl_value": 2, "emoji": "🏰"},
            {"name": "Floral Hair Pin", "rarity_tier": "🤍 COMMON", "short_tier": "COMMON", "weight": 5.00, "wl_value": 2, "emoji": "🌺"},
            {"name": "Tied-Up Towel", "rarity_tier": "🤍 COMMON", "short_tier": "COMMON", "weight": 5.00, "wl_value": 2, "emoji": "🏖️"},
            {"name": "Beach Blast", "rarity_tier": "🤍 COMMON", "short_tier": "COMMON", "weight": 5.00, "wl_value": 2, "emoji": "🏝️"},
            {"name": "Bubble Machine", "rarity_tier": "🤍 COMMON", "short_tier": "COMMON", "weight": 5.00, "wl_value": 1, "emoji": "🫧"},
            {"name": "Inflatable Dolphin", "rarity_tier": "🤍 COMMON", "short_tier": "COMMON", "weight": 5.00, "wl_value": 1, "emoji": "🐬"},
            {"name": "Surfboard", "rarity_tier": "🤍 COMMON", "short_tier": "COMMON", "weight": 5.00, "wl_value": 1, "emoji": "🏄"},
            {"name": "Fireworks (x20)", "rarity_tier": "🤍 COMMON", "short_tier": "COMMON", "weight": 5.00, "wl_value": 1, "emoji": "🧨"},
        ],
    },
    "halloween_growganoth": {
        "name": "Halloween Growganoth Sacrifice",
        "short_name": "Halloween Growganoth",
        "emoji": "🎃",
        "cost_wl": 10,
        "color": (156, 39, 176),
        "banner_desc": "Sacrifice **Dark King's Offerings** & **Dark Tickets** (2024–2025 Pool) for **Nightmare Devil Wings**, **Blades of Athena**, & **Unhelpful Hand**!",
        "jackpot_item": "Nightmare Devil Wings / Blades of Athena",
        "drops": [
            # 🌟 MYTHIC JACKPOT (0.25% total)
            {"name": "Nightmare Devil Wings", "rarity_tier": "🌟 MYTHIC JACKPOT", "short_tier": "MYTHIC", "weight": 0.07, "wl_value": 11500, "emoji": "🦇"},
            {"name": "Blades of Athena", "rarity_tier": "🌟 MYTHIC JACKPOT", "short_tier": "MYTHIC", "weight": 0.06, "wl_value": 9800, "emoji": "⚔️"},
            {"name": "Unhelpful Hand", "rarity_tier": "🌟 MYTHIC JACKPOT", "short_tier": "MYTHIC", "weight": 0.06, "wl_value": 8500, "emoji": "🖐️"},
            {"name": "Pumpkin Carriage", "rarity_tier": "🌟 MYTHIC JACKPOT", "short_tier": "MYTHIC", "weight": 0.06, "wl_value": 7800, "emoji": "🎃"},
            # 🔥 ULTRA RARE (1.25% total — 0.25% each)
            {"name": "Dark King's Crown", "rarity_tier": "🔥 ULTRA RARE", "short_tier": "ULTRA RARE", "weight": 0.25, "wl_value": 3400, "emoji": "👑"},
            {"name": "Devil Wings", "rarity_tier": "🔥 ULTRA RARE", "short_tier": "ULTRA RARE", "weight": 0.25, "wl_value": 2600, "emoji": "😈"},
            {"name": "Pop Demon's Riding Tiger", "rarity_tier": "🔥 ULTRA RARE", "short_tier": "ULTRA RARE", "weight": 0.25, "wl_value": 2100, "emoji": "🐯"},
            {"name": "Maniacal Mobile Wings", "rarity_tier": "🔥 ULTRA RARE", "short_tier": "ULTRA RARE", "weight": 0.25, "wl_value": 1850, "emoji": "🦇"},
            {"name": "Ring Lord's Mace", "rarity_tier": "🔥 ULTRA RARE", "short_tier": "ULTRA RARE", "weight": 0.25, "wl_value": 1500, "emoji": "🔨"},
            # ✨ SUPER RARE (5.50% total)
            {"name": "Astral Aura - Black Cat", "rarity_tier": "✨ SUPER RARE", "short_tier": "SUPER RARE", "weight": 0.85, "wl_value": 260, "emoji": "🐈‍⬛"},
            {"name": "Cinder Sprites", "rarity_tier": "✨ SUPER RARE", "short_tier": "SUPER RARE", "weight": 0.90, "wl_value": 210, "emoji": "🔥"},
            {"name": "Dark King's Offering", "rarity_tier": "✨ SUPER RARE", "short_tier": "SUPER RARE", "weight": 0.90, "wl_value": 190, "emoji": "💀"},
            {"name": "Cursed Spirit Pendant", "rarity_tier": "✨ SUPER RARE", "short_tier": "SUPER RARE", "weight": 0.95, "wl_value": 175, "emoji": "📿"},
            {"name": "Apocalypse Scythe", "rarity_tier": "✨ SUPER RARE", "short_tier": "SUPER RARE", "weight": 0.95, "wl_value": 150, "emoji": "镰"},
            {"name": "Chaos Cursed Wand", "rarity_tier": "✨ SUPER RARE", "short_tier": "SUPER RARE", "weight": 0.95, "wl_value": 125, "emoji": "🪄"},
            # 💜 RARE (16.00% total — 2.00% each)
            {"name": "Pop Demon's Jacket", "rarity_tier": "💜 RARE", "short_tier": "RARE", "weight": 2.00, "wl_value": 35, "emoji": "🧥"},
            {"name": "Pop Demon's Hair", "rarity_tier": "💜 RARE", "short_tier": "RARE", "weight": 2.00, "wl_value": 30, "emoji": "💇"},
            {"name": "Bad Witch's Hat", "rarity_tier": "💜 RARE", "short_tier": "RARE", "weight": 2.00, "wl_value": 28, "emoji": "🧙‍♀️"},
            {"name": "Count Duckula", "rarity_tier": "💜 RARE", "short_tier": "RARE", "weight": 2.00, "wl_value": 26, "emoji": "🦆"},
            {"name": "Zombie Horse", "rarity_tier": "💜 RARE", "short_tier": "RARE", "weight": 2.00, "wl_value": 24, "emoji": "🐎"},
            {"name": "Abominable Claws", "rarity_tier": "💜 RARE", "short_tier": "RARE", "weight": 2.00, "wl_value": 22, "emoji": "🐾"},
            {"name": "Cliff, The Cerberus", "rarity_tier": "💜 RARE", "short_tier": "RARE", "weight": 2.00, "wl_value": 20, "emoji": "🐕"},
            {"name": "Chainsaw Hand", "rarity_tier": "💜 RARE", "short_tier": "RARE", "weight": 2.00, "wl_value": 18, "emoji": "🪚"},
            # 💙 UNCOMMON (32.00% total — 4.00% each)
            {"name": "Bad Witch's Dress", "rarity_tier": "💙 UNCOMMON", "short_tier": "UNCOMMON", "weight": 4.00, "wl_value": 7, "emoji": "👗"},
            {"name": "Circus Eyes", "rarity_tier": "💙 UNCOMMON", "short_tier": "UNCOMMON", "weight": 4.00, "wl_value": 6, "emoji": "👀"},
            {"name": "Circus Teeth", "rarity_tier": "💙 UNCOMMON", "short_tier": "UNCOMMON", "weight": 4.00, "wl_value": 6, "emoji": "🦷"},
            {"name": "Candlewick's Mask", "rarity_tier": "💙 UNCOMMON", "short_tier": "UNCOMMON", "weight": 4.00, "wl_value": 6, "emoji": "🕯️"},
            {"name": "Scarabslushie Suit", "rarity_tier": "💙 UNCOMMON", "short_tier": "UNCOMMON", "weight": 4.00, "wl_value": 5, "emoji": "🪲"},
            {"name": "Black Cat Leash", "rarity_tier": "💙 UNCOMMON", "short_tier": "UNCOMMON", "weight": 4.00, "wl_value": 5, "emoji": "🐈‍⬛"},
            {"name": "Mimic Chest", "rarity_tier": "💙 UNCOMMON", "short_tier": "UNCOMMON", "weight": 4.00, "wl_value": 5, "emoji": "🧰"},
            {"name": "Vampire Bed", "rarity_tier": "💙 UNCOMMON", "short_tier": "UNCOMMON", "weight": 4.00, "wl_value": 4, "emoji": "⚰️"},
            # 🤍 COMMON (45.00% total — 5.00% each)
            {"name": "Pop Demon's Shorts", "rarity_tier": "🤍 COMMON", "short_tier": "COMMON", "weight": 5.00, "wl_value": 2, "emoji": "🩳"},
            {"name": "Buttoned Eyes", "rarity_tier": "🤍 COMMON", "short_tier": "COMMON", "weight": 5.00, "wl_value": 2, "emoji": "🔘"},
            {"name": "Bloated Bullfrog Balloon", "rarity_tier": "🤍 COMMON", "short_tier": "COMMON", "weight": 5.00, "wl_value": 2, "emoji": "🐸"},
            {"name": "Spooky Gift", "rarity_tier": "🤍 COMMON", "short_tier": "COMMON", "weight": 5.00, "wl_value": 2, "emoji": "🎁"},
            {"name": "Spooky Box", "rarity_tier": "🤍 COMMON", "short_tier": "COMMON", "weight": 5.00, "wl_value": 2, "emoji": "📦"},
            {"name": "Spooky Rags", "rarity_tier": "🤍 COMMON", "short_tier": "COMMON", "weight": 5.00, "wl_value": 1, "emoji": " rags"},
            {"name": "Carved Pumpkin Hat", "rarity_tier": "🤍 COMMON", "short_tier": "COMMON", "weight": 5.00, "wl_value": 1, "emoji": "🎃"},
            {"name": "Cobweb (x15)", "rarity_tier": "🤍 COMMON", "short_tier": "COMMON", "weight": 5.00, "wl_value": 1, "emoji": "🕸️"},
            {"name": "Candy Corn (x20)", "rarity_tier": "🤍 COMMON", "short_tier": "COMMON", "weight": 5.00, "wl_value": 1, "emoji": "🌽"},
        ],
    },
    "winter_wish": {
        "name": "WinterFest Royal Winter Chest",
        "short_name": "WinterFest Royal Chest",
        "emoji": "❄️",
        "cost_wl": 6,
        "color": (3, 169, 244),
        "banner_desc": "Open **Royal Winter Chests** & **Winter Wishes** (2024–2025 Pool) for **Royal Winter Title**, **Me11e's Snowshine**, & **Ice Dragon Hand**!",
        "jackpot_item": "Royal Winter Title / Me11e's Snowshine",
        "drops": [
            # 🌟 MYTHIC JACKPOT (0.25% total)
            {"name": "Royal Winter Title", "rarity_tier": "🌟 MYTHIC JACKPOT", "short_tier": "MYTHIC", "weight": 0.06, "wl_value": 10500, "emoji": "👑"},
            {"name": "Me11e's Snowshine", "rarity_tier": "🌟 MYTHIC JACKPOT", "short_tier": "MYTHIC", "weight": 0.06, "wl_value": 8800, "emoji": "❄️"},
            {"name": "Ice Dragon Hand", "rarity_tier": "🌟 MYTHIC JACKPOT", "short_tier": "MYTHIC", "weight": 0.07, "wl_value": 8200, "emoji": "🐉"},
            {"name": "Icy Daggers of Winter", "rarity_tier": "🌟 MYTHIC JACKPOT", "short_tier": "MYTHIC", "weight": 0.06, "wl_value": 7400, "emoji": "🗡️"},
            # 🔥 ULTRA RARE (1.25% total — 0.25% each)
            {"name": "Staff of the North Star", "rarity_tier": "🔥 ULTRA RARE", "short_tier": "ULTRA RARE", "weight": 0.25, "wl_value": 2400, "emoji": "🌟"},
            {"name": "WM - South Pole Winter", "rarity_tier": "🔥 ULTRA RARE", "short_tier": "ULTRA RARE", "weight": 0.25, "wl_value": 1950, "emoji": "🌨️"},
            {"name": "Winter Frost Bow", "rarity_tier": "🔥 ULTRA RARE", "short_tier": "ULTRA RARE", "weight": 0.25, "wl_value": 1650, "emoji": "🏹"},
            {"name": "Aurora Robe", "rarity_tier": "🔥 ULTRA RARE", "short_tier": "ULTRA RARE", "weight": 0.25, "wl_value": 1450, "emoji": "🧥"},
            {"name": "Royal Wishing Star", "rarity_tier": "🔥 ULTRA RARE", "short_tier": "ULTRA RARE", "weight": 0.25, "wl_value": 1250, "emoji": "⭐"},
            # ✨ SUPER RARE (5.50% total)
            {"name": "Giant Snowball Suit", "rarity_tier": "✨ SUPER RARE", "short_tier": "SUPER RARE", "weight": 0.85, "wl_value": 220, "emoji": "⛄"},
            {"name": "Pet Present Goblin", "rarity_tier": "✨ SUPER RARE", "short_tier": "SUPER RARE", "weight": 0.90, "wl_value": 185, "emoji": "👺"},
            {"name": "Winter Wishing Star", "rarity_tier": "✨ SUPER RARE", "short_tier": "SUPER RARE", "weight": 0.90, "wl_value": 155, "emoji": "🌠"},
            {"name": "Missile Toad Pet", "rarity_tier": "✨ SUPER RARE", "short_tier": "SUPER RARE", "weight": 0.95, "wl_value": 130, "emoji": "🐸"},
            {"name": "Snowy Night Cloak", "rarity_tier": "✨ SUPER RARE", "short_tier": "SUPER RARE", "weight": 0.95, "wl_value": 115, "emoji": "🧥"},
            {"name": "Ghost of WinterFest Robe", "rarity_tier": "✨ SUPER RARE", "short_tier": "SUPER RARE", "weight": 0.95, "wl_value": 95, "emoji": "👻"},
            # 💜 RARE (16.00% total — 2.00% each)
            {"name": "Aurora Lantern", "rarity_tier": "💜 RARE", "short_tier": "RARE", "weight": 2.00, "wl_value": 30, "emoji": "🏮"},
            {"name": "Growch Biceps", "rarity_tier": "💜 RARE", "short_tier": "RARE", "weight": 2.00, "wl_value": 26, "emoji": "💪"},
            {"name": "Growch Bod", "rarity_tier": "💜 RARE", "short_tier": "RARE", "weight": 2.00, "wl_value": 24, "emoji": "👹"},
            {"name": "Polar Bear Suit", "rarity_tier": "💜 RARE", "short_tier": "RARE", "weight": 2.00, "wl_value": 22, "emoji": "🐻‍❄️"},
            {"name": "Polar Bear Hood", "rarity_tier": "💜 RARE", "short_tier": "RARE", "weight": 2.00, "wl_value": 20, "emoji": "🐻‍❄️"},
            {"name": "Snowfrost Top Hat", "rarity_tier": "💜 RARE", "short_tier": "RARE", "weight": 2.00, "wl_value": 18, "emoji": "🎩"},
            {"name": "Light Up Pants", "rarity_tier": "💜 RARE", "short_tier": "RARE", "weight": 2.00, "wl_value": 16, "emoji": "👖"},
            {"name": "Elf on a Shelf", "rarity_tier": "💜 RARE", "short_tier": "RARE", "weight": 2.00, "wl_value": 15, "emoji": "🧝"},
            # 💙 UNCOMMON (32.00% total — 4.00% each)
            {"name": "WinterFest Box Mask", "rarity_tier": "💙 UNCOMMON", "short_tier": "UNCOMMON", "weight": 4.00, "wl_value": 6, "emoji": "📦"},
            {"name": "WinterFest Wreath", "rarity_tier": "💙 UNCOMMON", "short_tier": "UNCOMMON", "weight": 4.00, "wl_value": 6, "emoji": "🎄"},
            {"name": "Winterfest Earmuffs", "rarity_tier": "💙 UNCOMMON", "short_tier": "UNCOMMON", "weight": 4.00, "wl_value": 5, "emoji": "🎧"},
            {"name": "Penguin Beanie", "rarity_tier": "💙 UNCOMMON", "short_tier": "UNCOMMON", "weight": 4.00, "wl_value": 5, "emoji": "🐧"},
            {"name": "Winterfest Carolers", "rarity_tier": "💙 UNCOMMON", "short_tier": "UNCOMMON", "weight": 4.00, "wl_value": 5, "emoji": "🎶"},
            {"name": "WinterFest Royal Pants", "rarity_tier": "💙 UNCOMMON", "short_tier": "UNCOMMON", "weight": 4.00, "wl_value": 4, "emoji": "👖"},
            {"name": "Winter Bush Onesie", "rarity_tier": "💙 UNCOMMON", "short_tier": "UNCOMMON", "weight": 4.00, "wl_value": 4, "emoji": "🌳"},
            {"name": "Gavle Goat", "rarity_tier": "💙 UNCOMMON", "short_tier": "UNCOMMON", "weight": 4.00, "wl_value": 4, "emoji": "🐐"},
            # 🤍 COMMON (45.00% total — 5.00% each)
            {"name": "Nutcracker Toy Block", "rarity_tier": "🤍 COMMON", "short_tier": "COMMON", "weight": 5.00, "wl_value": 2, "emoji": "💂"},
            {"name": "Long Yule Log", "rarity_tier": "🤍 COMMON", "short_tier": "COMMON", "weight": 5.00, "wl_value": 2, "emoji": "🪵"},
            {"name": "Gift Wrapped Wallpaper", "rarity_tier": "🤍 COMMON", "short_tier": "COMMON", "weight": 5.00, "wl_value": 2, "emoji": "🎁"},
            {"name": "Gingerbread House", "rarity_tier": "🤍 COMMON", "short_tier": "COMMON", "weight": 5.00, "wl_value": 1, "emoji": "🏠"},
            {"name": "Icy Igloo", "rarity_tier": "🤍 COMMON", "short_tier": "COMMON", "weight": 5.00, "wl_value": 1, "emoji": "🧊"},
            {"name": "Winter Solstice Lights", "rarity_tier": "🤍 COMMON", "short_tier": "COMMON", "weight": 5.00, "wl_value": 1, "emoji": "💡"},
            {"name": "Mistletoe", "rarity_tier": "🤍 COMMON", "short_tier": "COMMON", "weight": 5.00, "wl_value": 1, "emoji": "🌿"},
            {"name": "Cherry Jelly Block (x20)", "rarity_tier": "🤍 COMMON", "short_tier": "COMMON", "weight": 5.00, "wl_value": 1, "emoji": "🍒"},
            {"name": "Lime Jelly Block (x20)", "rarity_tier": "🤍 COMMON", "short_tier": "COMMON", "weight": 5.00, "wl_value": 1, "emoji": "🟢"},
        ],
    },
    "lunar_well": {
        "name": "Lunar Well of Fortune",
        "short_name": "Lunar Well of Fortune",
        "emoji": "🧧",
        "cost_wl": 6,
        "color": (244, 67, 54),
        "banner_desc": "Open **Lunar Chests** & **Fortune Cookies** (2025–2026 Pool) for **Draconic Guardian**, **Nezha's Wheels**, & **Golden Dragon Statue**!",
        "jackpot_item": "Draconic Guardian / Nezha's Wheels",
        "drops": [
            # 🌟 MYTHIC JACKPOT (0.25% total)
            {"name": "Draconic Guardian", "rarity_tier": "🌟 MYTHIC JACKPOT", "short_tier": "MYTHIC", "weight": 0.06, "wl_value": 13500, "emoji": "🐉"},
            {"name": "Nezha's Wheels", "rarity_tier": "🌟 MYTHIC JACKPOT", "short_tier": "MYTHIC", "weight": 0.06, "wl_value": 11000, "emoji": "☸️"},
            {"name": "Golden Dragon Statue", "rarity_tier": "🌟 MYTHIC JACKPOT", "short_tier": "MYTHIC", "weight": 0.07, "wl_value": 9000, "emoji": "🐲"},
            {"name": "Leaping Carp Dragon", "rarity_tier": "🌟 MYTHIC JACKPOT", "short_tier": "MYTHIC", "weight": 0.06, "wl_value": 7800, "emoji": "🐟"},
            # 🔥 ULTRA RARE (1.25% total — 0.25% each)
            {"name": "Horse Zodiac Medallion", "rarity_tier": "🔥 ULTRA RARE", "short_tier": "ULTRA RARE", "weight": 0.25, "wl_value": 2600, "emoji": "🐎"},
            {"name": "Draconic WM Dragon Keep", "rarity_tier": "🔥 ULTRA RARE", "short_tier": "ULTRA RARE", "weight": 0.25, "wl_value": 2200, "emoji": "🏯"},
            {"name": "Jade Dragon Spear", "rarity_tier": "🔥 ULTRA RARE", "short_tier": "ULTRA RARE", "weight": 0.25, "wl_value": 1750, "emoji": "🔱"},
            {"name": "Zodiac Year of Snake", "rarity_tier": "🔥 ULTRA RARE", "short_tier": "ULTRA RARE", "weight": 0.25, "wl_value": 1550, "emoji": "🐍"},
            {"name": "Mythic Tortoise Charm", "rarity_tier": "🔥 ULTRA RARE", "short_tier": "ULTRA RARE", "weight": 0.25, "wl_value": 1350, "emoji": "🐢"},
            # ✨ SUPER RARE (5.50% total)
            {"name": "Nezha's Pauldrons", "rarity_tier": "✨ SUPER RARE", "short_tier": "SUPER RARE", "weight": 0.85, "wl_value": 240, "emoji": "🛡️"},
            {"name": "Nezha's Vest", "rarity_tier": "✨ SUPER RARE", "short_tier": "SUPER RARE", "weight": 0.90, "wl_value": 195, "emoji": "🦺"},
            {"name": "Pipa Jing's Instrument", "rarity_tier": "✨ SUPER RARE", "short_tier": "SUPER RARE", "weight": 0.90, "wl_value": 165, "emoji": "琵"},
            {"name": "Dragon Warrior Cape", "rarity_tier": "✨ SUPER RARE", "short_tier": "SUPER RARE", "weight": 0.95, "wl_value": 135, "emoji": "🧣"},
            {"name": "Lunar Silk Robe", "rarity_tier": "✨ SUPER RARE", "short_tier": "SUPER RARE", "weight": 0.95, "wl_value": 115, "emoji": "👘"},
            {"name": "Year of Horse Statue", "rarity_tier": "✨ SUPER RARE", "short_tier": "SUPER RARE", "weight": 0.95, "wl_value": 95, "emoji": "🗿"},
            # 💜 RARE (16.00% total — 2.00% each)
            {"name": "Fists of Iron", "rarity_tier": "💜 RARE", "short_tier": "RARE", "weight": 2.00, "wl_value": 32, "emoji": "🥊"},
            {"name": "Horse Lucky Token", "rarity_tier": "💜 RARE", "short_tier": "RARE", "weight": 2.00, "wl_value": 28, "emoji": "🪙"},
            {"name": "Year of Snake Statue", "rarity_tier": "💜 RARE", "short_tier": "RARE", "weight": 2.00, "wl_value": 25, "emoji": "🐍"},
            {"name": "Year of Dragon Statue", "rarity_tier": "💜 RARE", "short_tier": "RARE", "weight": 2.00, "wl_value": 24, "emoji": "🐉"},
            {"name": "Rebel Jacket", "rarity_tier": "💜 RARE", "short_tier": "RARE", "weight": 2.00, "wl_value": 20, "emoji": "🧥"},
            {"name": "Lunar Snake Scarf", "rarity_tier": "💜 RARE", "short_tier": "RARE", "weight": 2.00, "wl_value": 18, "emoji": "🧣"},
            {"name": "Guardian Lion Statue", "rarity_tier": "💜 RARE", "short_tier": "RARE", "weight": 2.00, "wl_value": 16, "emoji": "🦁"},
            {"name": "Maneki-neko", "rarity_tier": "💜 RARE", "short_tier": "RARE", "weight": 2.00, "wl_value": 15, "emoji": "🐱"},
            # 💙 UNCOMMON (32.00% total — 4.00% each)
            {"name": "Year of the Horse Mask", "rarity_tier": "💙 UNCOMMON", "short_tier": "UNCOMMON", "weight": 4.00, "wl_value": 6, "emoji": "🐴"},
            {"name": "Red Envelope Mask", "rarity_tier": "💙 UNCOMMON", "short_tier": "UNCOMMON", "weight": 4.00, "wl_value": 6, "emoji": "🧧"},
            {"name": "Red Tang Suit", "rarity_tier": "💙 UNCOMMON", "short_tier": "UNCOMMON", "weight": 4.00, "wl_value": 5, "emoji": "👘"},
            {"name": "Fireworks Cart", "rarity_tier": "💙 UNCOMMON", "short_tier": "UNCOMMON", "weight": 4.00, "wl_value": 5, "emoji": "🛒"},
            {"name": "Hanfu", "rarity_tier": "💙 UNCOMMON", "short_tier": "UNCOMMON", "weight": 4.00, "wl_value": 5, "emoji": "👗"},
            {"name": "Red Dragon Head", "rarity_tier": "💙 UNCOMMON", "short_tier": "UNCOMMON", "weight": 4.00, "wl_value": 4, "emoji": "🐲"},
            {"name": "Lucky Fortune Cookie", "rarity_tier": "💙 UNCOMMON", "short_tier": "UNCOMMON", "weight": 4.00, "wl_value": 4, "emoji": "🥠"},
            {"name": "Chinese Prayer Wheel", "rarity_tier": "💙 UNCOMMON", "short_tier": "UNCOMMON", "weight": 4.00, "wl_value": 4, "emoji": "☸️"},
            # 🤍 COMMON (45.00% total — 5.00% each)
            {"name": "Red Lucky Knot", "rarity_tier": "🤍 COMMON", "short_tier": "COMMON", "weight": 5.00, "wl_value": 2, "emoji": "🪢"},
            {"name": "Antique Tea Caddy", "rarity_tier": "🤍 COMMON", "short_tier": "COMMON", "weight": 5.00, "wl_value": 2, "emoji": "🍵"},
            {"name": "Monkey Face Mask", "rarity_tier": "🤍 COMMON", "short_tier": "COMMON", "weight": 5.00, "wl_value": 2, "emoji": "🐵"},
            {"name": "Bamboo Hat", "rarity_tier": "🤍 COMMON", "short_tier": "COMMON", "weight": 5.00, "wl_value": 1, "emoji": "👒"},
            {"name": "Stack of Lanterns", "rarity_tier": "🤍 COMMON", "short_tier": "COMMON", "weight": 5.00, "wl_value": 1, "emoji": "🏮"},
            {"name": "Pagoda Tower Block", "rarity_tier": "🤍 COMMON", "short_tier": "COMMON", "weight": 5.00, "wl_value": 1, "emoji": "🏯"},
            {"name": "Incense Urn", "rarity_tier": "🤍 COMMON", "short_tier": "COMMON", "weight": 5.00, "wl_value": 1, "emoji": "⚱️"},
            {"name": "Chinese Fireworks (x10)", "rarity_tier": "🤍 COMMON", "short_tier": "COMMON", "weight": 5.00, "wl_value": 1, "emoji": "🎆"},
            {"name": "Chinese Crackers (x10)", "rarity_tier": "🤍 COMMON", "short_tier": "COMMON", "weight": 5.00, "wl_value": 1, "emoji": "🧨"},
        ],
    },
}


def load_gacha_stats() -> dict[str, dict[str, dict[str, Any]]]:
    if GACHA_STATS_FILE.exists():
        try:
            data = json.loads(GACHA_STATS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {k: {} for k in GACHA_POOLS}


def save_gacha_stats(stats: dict[str, dict[str, dict[str, Any]]]) -> None:
    GACHA_STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
    GACHA_STATS_FILE.write_text(json.dumps(stats, indent=2), encoding="utf-8")


def _clean_ascii_name(raw_name: str, max_len: int = 14) -> str:
    cleaned = "".join(ch for ch in raw_name if 32 <= ord(ch) <= 126 and ch != "`").strip()
    if not cleaned:
        cleaned = "Player"
    return cleaned[:max_len]


def build_category_leaderboard_embed(pool_key: str, cat_stats: dict[str, dict[str, Any]]) -> discord.Embed:
    """
    Build the sleek Pill-Row Table Leaderboard (matching the Mr. Pulsar reference):
    - Bold inline-code header pill: **`Rank  User            Mythic   Won (WL)    Rolls`**
    - Cyan linked inline-code row pills: [`#1    Manwel          0 (0U)   436 WL      50   `](https://...)
    """
    pool = GACHA_POOLS[pool_key]
    r, g, b = pool["color"]

    total_cat_rolls = sum(int(v.get("rolls", 0)) for v in cat_stats.values())
    total_cat_mythics = sum(int(v.get("mythics", 0)) for v in cat_stats.values())
    total_cat_won = sum(int(v.get("won_wl", 0)) for v in cat_stats.values())

    embed = discord.Embed(
        title=f"{pool['emoji']} {pool['name']}",
        description=(
            f"{pool['banner_desc']}\n"
            f"🎯 **Jackpots:** `{pool['jackpot_item']}`  •  💰 **Cost:** `{pool['cost_wl']} WL/roll`  •  "
            f"🎲 **Total Rolls:** `{total_cat_rolls:,}`"
        ),
        color=discord.Color.from_rgb(r, g, b),
        timestamp=datetime.now(EVENT_TZ),
    )

    header_pill = "**`Rank  User            Mythic   Won (WL)    Rolls`**"
    rows: list[str] = [header_pill]

    if not cat_stats:
        empty_pill = "[`#--   No pulls yet    0 (0U)   0 WL        0    `](https://discord.com/channels/1567168949584658534/1568907253854113855)"
        rows.append(empty_pill)
    else:
        sorted_players = sorted(
            cat_stats.items(),
            key=lambda kv: (
                int(kv[1].get("mythics", 0)),
                int(kv[1].get("won_wl", 0)),
                int(kv[1].get("won_wl", 0)) - int(kv[1].get("spent_wl", 0)),
            ),
            reverse=True,
        )[:10]

        for idx, (uid, pdata) in enumerate(sorted_players):
            rank_col = f"#{idx + 1}"
            raw_name = str(pdata.get("name") or f"User-{str(uid)[-4:]}")
            user_col = _clean_ascii_name(raw_name, 14)
            rolls = int(pdata.get("rolls", 0))
            spent = int(pdata.get("spent_wl", 0))
            won = int(pdata.get("won_wl", 0))
            mythics = int(pdata.get("mythics", 0))
            ultras = int(pdata.get("ultra_rares", 0))
            best_drop = str(pdata.get("best_drop", "None"))
            best_wl = int(pdata.get("best_wl", 0))

            mythic_col = f"{mythics} ({ultras}U)"
            won_col = f"{won:,} WL"
            rolls_col = f"{rolls:,}"

            row_text = (
                f"{rank_col:<6}"
                f"{user_col:<16}"
                f"{mythic_col:<9}"
                f"{won_col:<12}"
                f"{rolls_col:<5}"
            )
            frag = (
                f"uid={uid}&name={quote(user_col)}&m={mythics}&u={ultras}"
                f"&won={won}&spent={spent}&rolls={rolls}&best={quote(best_drop)}&bwl={best_wl}"
            )
            url = f"https://discord.com/channels/1567168949584658534/1568907253854113855#{frag}"
            rows.append(f"[`{row_text}`]({url})")

    embed.add_field(
        name=f"🏆 {pool['short_name']} Leaderboard ({total_cat_mythics} Jackpots • {total_cat_won:,} WL Won)",
        value="\n".join(rows),
        inline=False,
    )

    embed.set_footer(text=f"{FOOTER_TEXT} • 40-Item 2026 Pool • Auto-Synced Live from #🎰gacha-simulator")
    return embed


class GachaQuickRollView(discord.ui.View):
    """Persistent quick-roll buttons pinned in #🎰gacha-simulator and attached to every roll result."""

    def __init__(self, cog: GachaSimulatorCog) -> None:
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="Valentine GBC (10x)",
        style=discord.ButtonStyle.danger,
        emoji="💘",
        custom_id="gacha_roll:valentine_gbc:10",
        row=0,
    )
    async def roll_valentine(self, interaction: discord.Interaction, _btn: discord.ui.Button) -> None:
        await self.cog.handle_gacha_roll(interaction, "valentine_gbc", 10)

    @discord.ui.button(
        label="Summer Fireworks (10x)",
        style=discord.ButtonStyle.primary,
        emoji="🎆",
        custom_id="gacha_roll:summer_fireworks:10",
        row=0,
    )
    async def roll_summer(self, interaction: discord.Interaction, _btn: discord.ui.Button) -> None:
        await self.cog.handle_gacha_roll(interaction, "summer_fireworks", 10)

    @discord.ui.button(
        label="Halloween Dark Ticket (10x)",
        style=discord.ButtonStyle.secondary,
        emoji="🎃",
        custom_id="gacha_roll:halloween_growganoth:10",
        row=0,
    )
    async def roll_halloween(self, interaction: discord.Interaction, _btn: discord.ui.Button) -> None:
        await self.cog.handle_gacha_roll(interaction, "halloween_growganoth", 10)

    @discord.ui.button(
        label="WinterFest Chest (10x)",
        style=discord.ButtonStyle.primary,
        emoji="❄️",
        custom_id="gacha_roll:winter_wish:10",
        row=1,
    )
    async def roll_winter(self, interaction: discord.Interaction, _btn: discord.ui.Button) -> None:
        await self.cog.handle_gacha_roll(interaction, "winter_wish", 10)

    @discord.ui.button(
        label="Lunar Well (10x)",
        style=discord.ButtonStyle.success,
        emoji="🧧",
        custom_id="gacha_roll:lunar_well:10",
        row=1,
    )
    async def roll_lunar(self, interaction: discord.Interaction, _btn: discord.ui.Button) -> None:
        await self.cog.handle_gacha_roll(interaction, "lunar_well", 10)


class GachaSimulatorCog(commands.Cog, name="Gacha Simulator"):
    def __init__(self, bot: EventBot) -> None:
        self.bot = bot
        self._cooldowns: dict[int, float] = {}
        self._startup_synced: bool = False

    async def cog_load(self) -> None:
        self.bot.add_view(GachaQuickRollView(self))
        self.leaderboard_sync_loop.start()

    async def cog_unload(self) -> None:
        self.leaderboard_sync_loop.cancel()

    def check_user_cooldown(self, user_id: int) -> int | None:
        """Enforce the 1-minute (60s) rate limit per user across both /gacha and quick-roll buttons."""
        now = time.time()
        expires_at = self._cooldowns.get(user_id, 0.0)
        if now < expires_at:
            return int(expires_at)
        self._cooldowns[user_id] = now + GACHA_COOLDOWN_SECONDS
        return None

    async def recover_stats_from_discord(self, guild: discord.Guild) -> None:
        """
        Discord-as-Database Recovery:
        Parses hidden URL fragments (`#uid=...&won=...&rolls=...`) inside the Pill-Row Table links
        in #🏆gacha-leaderboards so container restarts never wipe player scores!
        """
        state = load_state()
        lb_channel_id = state.get("gacha_leaderboard_channel_id")
        if not lb_channel_id:
            return

        lb_channel = guild.get_channel(int(lb_channel_id))
        if not isinstance(lb_channel, discord.TextChannel):
            try:
                lb_channel = await self.bot.fetch_channel(int(lb_channel_id))  # type: ignore[assignment]
            except Exception:
                return

        if not isinstance(lb_channel, discord.TextChannel):
            return

        stats = load_gacha_stats()
        frag_pattern = re.compile(r"#(uid=\d+&[^\)]+)\)")

        try:
            async for msg in lb_channel.history(limit=20):
                if msg.author.id != (self.bot.user.id if self.bot.user else 0) or not msg.embeds:
                    continue
                emb = msg.embeds[0]
                title = emb.title or ""
                matched_pool_key: str | None = None
                for pk, pinfo in GACHA_POOLS.items():
                    if pinfo["name"] in title:
                        matched_pool_key = pk
                        break
                if not matched_pool_key:
                    continue

                msg_map = state.get("gacha_leaderboard_message_ids", {})
                if msg_map.get(matched_pool_key) != msg.id:
                    msg_map[matched_pool_key] = msg.id
                    state["gacha_leaderboard_message_ids"] = msg_map
                    save_state(state)

                for field in emb.fields:
                    for line in (field.value or "").splitlines():
                        m_frag = frag_pattern.search(line)
                        if not m_frag:
                            continue
                        qs = parse_qs(m_frag.group(1))
                        uid = (qs.get("uid") or [""])[0]
                        if not uid:
                            continue
                        pname = unquote((qs.get("name") or ["Player"])[0])
                        mythics = int((qs.get("m") or ["0"])[0])
                        ultras = int((qs.get("u") or ["0"])[0])
                        won = int((qs.get("won") or ["0"])[0])
                        spent = int((qs.get("spent") or ["0"])[0])
                        rolls = int((qs.get("rolls") or ["0"])[0])
                        best_drop = unquote((qs.get("best") or ["None"])[0])
                        best_wl = int((qs.get("bwl") or ["0"])[0])

                        cat_bucket = stats.setdefault(matched_pool_key, {})
                        existing = cat_bucket.get(uid)
                        if not existing or int(existing.get("rolls", 0)) < rolls:
                            cat_bucket[uid] = {
                                "name": pname,
                                "rolls": rolls,
                                "spent_wl": spent,
                                "won_wl": won,
                                "mythics": mythics,
                                "ultra_rares": ultras,
                                "best_drop": best_drop,
                                "best_wl": best_wl,
                            }
            save_gacha_stats(stats)
        except Exception as exc:
            logger.warning("Failed to recover gacha stats from Discord history: %s", exc)

    async def update_leaderboard_card(self, guild: discord.Guild, pool_key: str) -> None:
        """Immediately push-update the specific Gacha category's leaderboard embed in #🏆gacha-leaderboards."""
        state = load_state()
        lb_channel_id = state.get("gacha_leaderboard_channel_id")
        if not lb_channel_id:
            return

        lb_channel = guild.get_channel(int(lb_channel_id))
        if not isinstance(lb_channel, discord.TextChannel):
            try:
                lb_channel = await self.bot.fetch_channel(int(lb_channel_id))  # type: ignore[assignment]
            except Exception:
                return

        if not isinstance(lb_channel, discord.TextChannel):
            return

        stats = load_gacha_stats()
        cat_stats = stats.get(pool_key, {})
        embed = build_category_leaderboard_embed(pool_key, cat_stats)

        msg_map: dict[str, int] = state.get("gacha_leaderboard_message_ids", {})
        msg_id = msg_map.get(pool_key)

        if msg_id:
            try:
                msg = await lb_channel.fetch_message(int(msg_id))
                await msg.edit(embed=embed)
                return
            except discord.NotFound:
                pass
            except Exception as exc:
                logger.warning("Could not edit gacha leaderboard message %s: %s", msg_id, exc)
                return

        try:
            new_msg = await lb_channel.send(embed=embed)
            msg_map[pool_key] = new_msg.id
            state["gacha_leaderboard_message_ids"] = msg_map
            save_state(state)
        except Exception as exc:
            logger.warning("Could not create gacha leaderboard message for %s: %s", pool_key, exc)

    @tasks.loop(minutes=5)
    async def leaderboard_sync_loop(self) -> None:
        """Self-healing 5-minute background sync to guarantee #🏆gacha-leaderboards stays 100% in sync."""
        for guild in self.bot.guilds:
            if not self._startup_synced:
                await self.recover_stats_from_discord(guild)
                self._startup_synced = True
            for pool_key in GACHA_POOLS:
                await self.update_leaderboard_card(guild, pool_key)

    @leaderboard_sync_loop.before_loop
    async def before_leaderboard_sync_loop(self) -> None:
        await self.bot.wait_until_ready()

    async def handle_gacha_roll(
        self,
        interaction: discord.Interaction,
        pool_key: str,
        count: int,
        from_slash: bool = False,
    ) -> None:
        state = load_state()
        allowed_channel_id = state.get("gacha_channel_id")
        if allowed_channel_id and int(interaction.channel_id or 0) != int(allowed_channel_id):
            await interaction.response.send_message(
                f"❌ The Gacha Simulator can only be used inside <#{allowed_channel_id}>!",
                ephemeral=True,
            )
            return

        exp_ts = self.check_user_cooldown(interaction.user.id)
        if exp_ts is not None:
            await interaction.response.send_message(
                f"⏳ **Gacha Cooldown Active!** You can roll again <t:{exp_ts}:R> (at <t:{exp_ts}:T>).\n"
                f"*(Gacha Simulator has a **1-minute** rate limit per player!)*",
                ephemeral=True,
            )
            return

        if not interaction.response.is_done():
            await interaction.response.defer()

        if interaction.guild and not self._startup_synced:
            await self.recover_stats_from_discord(interaction.guild)
            self._startup_synced = True

        pool = GACHA_POOLS.get(pool_key, GACHA_POOLS["valentine_gbc"])
        count = max(1, min(count, 50))
        drops_list = pool["drops"]
        weights = [float(d["weight"]) for d in drops_list]

        rolled_items = random.choices(drops_list, weights=weights, k=count)

        spent_wl = count * int(pool["cost_wl"])
        won_wl = sum(int(d["wl_value"]) for d in rolled_items)
        net_wl = won_wl - spent_wl

        tally: dict[str, dict[str, Any]] = {}
        mythics_pulled = 0
        ultras_pulled = 0
        best_single_item = rolled_items[0]
        pulled_mythic_names: list[str] = []

        for item in rolled_items:
            if int(item["wl_value"]) > int(best_single_item["wl_value"]):
                best_single_item = item
            if "MYTHIC" in item["rarity_tier"]:
                mythics_pulled += 1
                if item["name"] not in pulled_mythic_names:
                    pulled_mythic_names.append(item["name"])
            elif "ULTRA" in item["rarity_tier"]:
                ultras_pulled += 1

            entry = tally.setdefault(
                item["name"],
                {
                    "count": 0,
                    "wl_value": int(item["wl_value"]),
                    "rarity_tier": item["rarity_tier"],
                    "short_tier": item.get("short_tier", "COMMON"),
                    "emoji": item["emoji"],
                },
            )
            entry["count"] += 1

        # Update persistent player stats for this Gacha category
        stats = load_gacha_stats()
        cat_bucket = stats.setdefault(pool_key, {})
        uid_str = str(interaction.user.id)
        pstats = cat_bucket.setdefault(
            uid_str,
            {
                "name": interaction.user.display_name,
                "rolls": 0,
                "spent_wl": 0,
                "won_wl": 0,
                "mythics": 0,
                "ultra_rares": 0,
                "best_drop": "None",
                "best_wl": 0,
            },
        )
        pstats["name"] = interaction.user.display_name
        pstats["rolls"] = int(pstats.get("rolls", 0)) + count
        pstats["spent_wl"] = int(pstats.get("spent_wl", 0)) + spent_wl
        pstats["won_wl"] = int(pstats.get("won_wl", 0)) + won_wl
        pstats["mythics"] = int(pstats.get("mythics", 0)) + mythics_pulled
        pstats["ultra_rares"] = int(pstats.get("ultra_rares", 0)) + ultras_pulled
        if int(best_single_item["wl_value"]) >= int(pstats.get("best_wl", 0)):
            pstats["best_wl"] = int(best_single_item["wl_value"])
            pstats["best_drop"] = best_single_item["name"]

        save_gacha_stats(stats)

        # Build Roll Result Embed with Pill-Row Unbox Table matching the reference image
        r, g, b = pool["color"]
        if mythics_pulled > 0:
            r, g, b = (255, 215, 0)

        sorted_tally = sorted(tally.items(), key=lambda kv: kv[1]["wl_value"], reverse=True)
        u_rows: list[str] = ["**`Qty    Item Unboxed            Tier         Value   `**"]
        for iname, info in sorted_tally[:15]:
            sub_val = info["count"] * info["wl_value"]
            qty_col = f"{info['count']}x"
            item_col = _clean_ascii_name(iname, 22)
            tier_col = _clean_ascii_name(info.get("short_tier", "COMMON"), 11)
            val_col = f"{sub_val:,} WL"
            row_txt = f"{qty_col:<7}{item_col:<24}{tier_col:<13}{val_col:<8}"
            u_rows.append(
                f"[`{row_txt}`](https://discord.com/channels/1567168949584658534/1568907256467169381)"
            )

        net_emoji = "📈" if net_wl >= 0 else "📉"
        net_str = f"+{net_wl:,} WL" if net_wl >= 0 else f"{net_wl:,} WL"

        jackpot_banner = ""
        if mythics_pulled > 0:
            mythic_names_str = ", ".join(pulled_mythic_names)
            jackpot_banner = (
                f"🚨 **MYTHIC JACKPOT UNBOXED!!** <@{interaction.user.id}> just pulled "
                f"**`{mythics_pulled}x` {mythic_names_str}**!!\n\n"
            )

        embed = discord.Embed(
            title=f"{pool['emoji']} {pool['name']} — {count}x Gacha Roll",
            description=(
                f"{jackpot_banner}"
                f"👤 **Roller:** <@{interaction.user.id}>\n"
                f"💸 **Spent:** `{spent_wl:,} WL`  •  💎 **Value Unboxed:** `{won_wl:,} WL`  •  "
                f"{net_emoji} **Net Profit:** `{net_str}`"
            ),
            color=discord.Color.from_rgb(r, g, b),
            timestamp=datetime.now(EVENT_TZ),
        )
        embed.add_field(
            name=f"🎁 Items Unboxed ({len(sorted_tally)} Unique Drops from 40-Item Pool)",
            value="\n".join(u_rows),
            inline=False,
        )

        lifetime_net = int(pstats["won_wl"]) - int(pstats["spent_wl"])
        lifetime_net_str = f"+{lifetime_net:,} WL" if lifetime_net >= 0 else f"{lifetime_net:,} WL"
        lb_ch_id = state.get("gacha_leaderboard_channel_id")
        lb_mention = f"<#{lb_ch_id}>" if lb_ch_id else "`#🏆gacha-leaderboards`"

        embed.add_field(
            name=f"📊 Your Lifetime {pool['short_name']} Stats (Synced to {lb_mention})",
            value=(
                f"• **Total Rolls:** `{pstats['rolls']:,}`  •  **Mythic Jackpots:** `{pstats['mythics']}` (`{pstats['ultra_rares']}` Ultra)\n"
                f"• **Lifetime Won:** `{pstats['won_wl']:,} WL` (`Net: {lifetime_net_str}`)  •  **Best Pull:** `{pstats['best_drop']}`"
            ),
            inline=False,
        )
        embed.set_footer(text=f"{FOOTER_TEXT} • 2026 Growtopia Wiki Pool (40 Items/Event) • 1-Minute Cooldown")

        await interaction.followup.send(embed=embed, view=GachaQuickRollView(self))

        if interaction.guild:
            await self.update_leaderboard_card(interaction.guild, pool_key)

    @app_commands.command(
        name="gacha",
        description="Roll Growtopia Gacha boxes (2024–2026 Pool: Valentine GBC, SummerFest, Growganoth, WinterFest, Lunar)!",
    )
    @app_commands.describe(
        category="Choose which Growtopia Gacha event to roll (40 official items per pool!)",
        rolls="Number of rolls to open at once (1x, 10x, 25x, or 50x)",
    )
    @app_commands.choices(
        category=[
            app_commands.Choice(name="💘 Valentine's Super GBC (GHC, Golden Ribbon Wings, Golden Mallet)", value="valentine_gbc"),
            app_commands.Choice(name="🎆 SummerFest Super Fireworks (Noble Phoenix, Neptune's Gauntlet, Phoenix Wings)", value="summer_fireworks"),
            app_commands.Choice(name="🎃 Halloween Growganoth (Nightmare Devil Wings, Blades of Athena, Unhelpful Hand)", value="halloween_growganoth"),
            app_commands.Choice(name="❄️ WinterFest Royal Chest (Royal Winter Title, Me11e's Snowshine, Ice Dragon)", value="winter_wish"),
            app_commands.Choice(name="🧧 Lunar Well of Fortune (Draconic Guardian, Nezha's Wheels, Golden Dragon)", value="lunar_well"),
        ],
        rolls=[
            app_commands.Choice(name="1x Single Roll", value=1),
            app_commands.Choice(name="10x Multi-Roll (Recommended)", value=10),
            app_commands.Choice(name="25x Mega Roll", value=25),
            app_commands.Choice(name="50x Whale Roll (Max)", value=50),
        ],
    )
    async def gacha_command(
        self,
        interaction: discord.Interaction,
        category: str = "valentine_gbc",
        rolls: int = 10,
    ) -> None:
        await self.handle_gacha_roll(interaction, category, rolls, from_slash=True)


async def setup(bot: EventBot) -> None:
    await bot.add_cog(GachaSimulatorCog(bot))
