"""
Category 6: Surgery Cheat-Sheet Assistant (cogs/surgery_helper.py)
- /surgery (Step-by-step Growtopia Surgery guide for all 27 Diseases & Vile Vial Maladies + Interactive Emergency Buttons)
- /set_surgery_channel (Admin channel lock + instruction card)
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


# Complete Official Growtopia Surgery Database (Standard Ultrasound Illnesses + Vile Vial Maladies)
SURGERY_DATABASE: dict[str, dict[str, Any]] = {
    "Bird Flu": {
        "category": "🦠 Flu / Fever Illness",
        "difficulty": "⭐ Easy (No Cutting!)",
        "ultrasound": "He has symptoms of Bird Flu.",
        "incisions": 0,
        "bones": "None",
        "tool_order": "🔬 **Lab Kit** ➔ 💊 **Antibiotics** *(repeat until Temp < 98.6°)*",
        "steps": [
            "1️⃣ **Do NOT use Anesthetic or Scalpel!** Flu surgeries require **0 incisions**.",
            "2️⃣ Use **Ultrasound** to diagnose, then use **Lab Kit** once to unlock **Antibiotics**.",
            "3️⃣ Keep using **Antibiotics** (and **Sponge** if you can't see) until temperature drops below `98.6°` and the surgery completes automatically!",
        ],
        "watch_out": "Never cut the patient on Flu cases! If Temp spikes above `106°`, only spam **Antibiotics**.",
        "sprite_item": "Surgical Antibiotics",
    },
    "Turtle Flu": {
        "category": "🦠 Flu / Fever Illness",
        "difficulty": "⭐ Easy (No Cutting!)",
        "ultrasound": "He is showing signs of Turtle Flu.",
        "incisions": 0,
        "bones": "None",
        "tool_order": "🔬 **Lab Kit** ➔ 💊 **Antibiotics** *(repeat until Temp < 98.6°)*",
        "steps": [
            "1️⃣ **Do NOT use Anesthetic or Scalpel!** Turtle Flu requires **0 incisions**.",
            "2️⃣ Use **Ultrasound** to diagnose, then use **Lab Kit** once.",
            "3️⃣ Spam **Antibiotics** until the fever drops below `98.6°` to finish the surgery!",
        ],
        "watch_out": "Keep a **Sponge** ready if vision gets blocked, and never use Scalpel.",
        "sprite_item": "Surgical Lab Kit",
    },
    "Monkey Flu": {
        "category": "🦠 Flu / Fever Illness",
        "difficulty": "⭐ Easy (No Cutting!)",
        "ultrasound": "He has contracted Monkey Flu.",
        "incisions": 0,
        "bones": "None",
        "tool_order": "🔬 **Lab Kit** ➔ 💊 **Antibiotics** *(repeat until Temp < 98.6°)*",
        "steps": [
            "1️⃣ **Do NOT cut the patient!** Monkey Flu is cured purely by lowering fever (`0` incisions).",
            "2️⃣ Use **Ultrasound** ➔ **Lab Kit**.",
            "3️⃣ Use **Antibiotics** repeatedly until temperature drops below `98.6°`.",
        ],
        "watch_out": "If the fever climbs fast, ignore Antiseptic and strictly use **Antibiotics**.",
        "sprite_item": "Surgical Antibiotics",
    },
    "Nose Job": {
        "category": "👃 Cosmetic / Minor Surgery",
        "difficulty": "⭐ Easy",
        "ultrasound": "The patient wants a Nose Job.",
        "incisions": 1,
        "bones": "Occasionally 1 Shattered",
        "tool_order": "💤 **Anesthetic** ➔ 🔪 **Scalpel (x1)** ➔ 🔨 **Pins** *(if shattered)* ➔ ✅ **Fix it!** ➔ 🧵 **Stitches** ➔ 🦴 **Splint** *(if broken)*",
        "steps": [
            "1️⃣ Use **Ultrasound** to confirm, then use **Anesthetic** to put the patient to sleep.",
            "2️⃣ Use **Scalpel (1x)** (`Incisions: 1`).",
            "3️⃣ If there is a **Shattered Bone**, use **Pins** now while the incision is open!",
            "4️⃣ Click **Fix it!**, then use **Stitches (1x)** to close the incision (and **Splint** if a bone is Broken).",
        ],
        "watch_out": "Always use **Pins** *before* closing your incisions with Stitches!",
        "sprite_item": "Surgical Scalpel",
    },
    "Broken Arm": {
        "category": "🦴 Bone Trauma",
        "difficulty": "⭐⭐ Medium",
        "ultrasound": "The patient has a Broken Arm.",
        "incisions": 1,
        "bones": "1 Broken (or 1 Shattered)",
        "tool_order": "🦴 **Splint** *(if only Broken)* — OR — 💤 **Anesthetic** ➔ 🔪 **Scalpel (x1)** ➔ 🔨 **Pins** ➔ 🧵 **Stitches** ➔ 🦴 **Splint** *(if Shattered)*",
        "steps": [
            "1️⃣ Use **Ultrasound** and check the **Bones** line.",
            "2️⃣ **If only `1 Broken` (0 Shattered):** Simply use **Splint** (and **Stitches** if bleeding) — no Scalpel needed!",
            "3️⃣ **If `1 Shattered`:** Use **Anesthetic** ➔ **Scalpel (1x)** ➔ **Pins** (converts Shattered to Broken) ➔ **Stitches (1x)** ➔ **Splint**!",
        ],
        "watch_out": "**Pins** can only be used when `Incisions >= 1` AND the patient is `Unconscious`!",
        "sprite_item": "Surgical Splint",
    },
    "Broken Leg": {
        "category": "🦴 Bone Trauma",
        "difficulty": "⭐⭐ Medium",
        "ultrasound": "The patient has a Broken Leg.",
        "incisions": 1,
        "bones": "1 Shattered, 1 Broken",
        "tool_order": "💤 **Anesthetic** ➔ 🔪 **Scalpel (x1)** ➔ 🔨 **Pins** ➔ 🧵 **Stitches** ➔ 🦴 **Splint (x2)**",
        "steps": [
            "1️⃣ If the patient is bleeding heavily at start, use **Stitches** once to slow bleeding, then **Ultrasound**.",
            "2️⃣ Use **Anesthetic** to put the patient to sleep.",
            "3️⃣ Use **Scalpel (1x)** to open `1` incision, then use **Pins** to turn the Shattered bone into a Broken bone.",
            "4️⃣ Use **Stitches** until `Incisions: 0` and bleeding stops, then use **Splint (x2)** to fix all Broken bones!",
        ],
        "watch_out": "Never use **Pins** while the patient is Awake — they will bleed heavily and faint!",
        "sprite_item": "Surgical Pins",
    },
    "Heart Attack": {
        "category": "❤️ Organ Emergency",
        "difficulty": "⭐⭐⭐ Hard",
        "ultrasound": "The patient is having a Heart Attack!",
        "incisions": 2,
        "bones": "None",
        "tool_order": "💤 **Anesthetic** ➔ 🔪 **Scalpel (x2)** ➔ ✅ **Fix it!** ➔ 🧵 **Stitches (x2)** *(+ ⚡ **Defibrillator** when heart stops!)*",
        "steps": [
            "1️⃣ Use **Ultrasound** to diagnose. If temperature is already rising (`100°+`), use **Lab Kit** ➔ **Antibiotics**.",
            "2️⃣ Use **Anesthetic**, then use **Scalpel (2x)** (`Incisions: 2`).",
            "3️⃣ Click **Fix it!** as soon as it lights up.",
            "4️⃣ Use **Stitches (2x)** to close all incisions and lower fever with **Antibiotics** if needed.",
        ],
        "watch_out": "⚡ Heart stops very frequently during Heart Attack! Always prioritize **Defibrillator** immediately if `Heart Stopped!` appears.",
        "sprite_item": "Surgical Defibrillator",
    },
    "Appendicitis": {
        "category": "🏥 Organ Surgery",
        "difficulty": "⭐⭐ Medium",
        "ultrasound": "The patient has Appendicitis.",
        "incisions": 2,
        "bones": "None",
        "tool_order": "🔬 **Lab Kit** ➔ 💊 **Antibiotics** ➔ 💤 **Anesthetic** ➔ 🔪 **Scalpel (x2)** ➔ ✅ **Fix it!** ➔ 🧵 **Stitches (x2)**",
        "steps": [
            "1️⃣ Use **Ultrasound**. If fever is rising, use **Lab Kit** and **Antibiotics** first.",
            "2️⃣ Use **Anesthetic** to put the patient to sleep.",
            "3️⃣ Use **Scalpel (2x)** (`Incisions: 2`), then click **Fix it!**.",
            "4️⃣ Use **Stitches (2x)** to close both incisions (and **Antibiotics** if Temp > `98.6°`).",
        ],
        "watch_out": "Appendicitis often starts with a rising fever — don't let Temp reach `110°`!",
        "sprite_item": "Surgical Scalpel",
    },
    "Swallowed a World Lock": {
        "category": "🔒 Foreign Object Surgery",
        "difficulty": "⭐⭐ Medium",
        "ultrasound": "The patient swallowed a World Lock!",
        "incisions": 2,
        "bones": "None",
        "tool_order": "💤 **Anesthetic** ➔ 🔪 **Scalpel (x2)** ➔ ✅ **Fix it!** ➔ 🧵 **Stitches (x2)**",
        "steps": [
            "1️⃣ Use **Ultrasound**, then put the patient to sleep with **Anesthetic**.",
            "2️⃣ Use **Scalpel (2x)** until `Incisions: 2`.",
            "3️⃣ Click **Fix it!** to retrieve the swallowed lock.",
            "4️⃣ Use **Stitches (2x)** until `Incisions: 0` and bleeding stops.",
        ],
        "watch_out": "Check if the patient is `Coming to` before your second stitch — if they wake up mid-stitch, it causes extra bleeding.",
        "sprite_item": "World Lock",
    },
    "Herniated Disc": {
        "category": "🦴 Spine / Deep Surgery",
        "difficulty": "⭐⭐⭐ Hard",
        "ultrasound": "The patient has a Herniated Disc.",
        "incisions": 3,
        "bones": "Often 1 Broken / Shattered",
        "tool_order": "💤 **Anesthetic** ➔ 🔪 **Scalpel (x3)** ➔ 🔨 **Pins** *(if shattered)* ➔ ✅ **Fix it!** ➔ 🧵 **Stitches (x3)** ➔ 🦴 **Splint**",
        "steps": [
            "1️⃣ Use **Ultrasound**, then **Anesthetic**.",
            "2️⃣ Cut **3 times** with **Scalpel** (use **Clamp** or **Stitches** if bleeding becomes heavy).",
            "3️⃣ If any bone is **Shattered**, use **Pins** while open, then click **Fix it!**.",
            "4️⃣ Watch for **`Status: Coming to`**! Re-apply **Anesthetic** before stitching all `3` incisions closed, then use **Splint**.",
        ],
        "watch_out": "Because this takes 3 incisions, the patient almost always starts waking up (`Coming to`) right before you stitch — put them back to sleep first!",
        "sprite_item": "Surgical Clamp",
    },
    "Kidney Failure": {
        "category": "🏥 Organ Surgery",
        "difficulty": "⭐⭐⭐ Hard",
        "ultrasound": "The patient is suffering from Kidney Failure.",
        "incisions": 3,
        "bones": "None",
        "tool_order": "💤 **Anesthetic** ➔ 🔪 **Scalpel (x3)** ➔ ✅ **Fix it!** ➔ 💤 **Anesthetic** *(if Coming to)* ➔ 🧵 **Stitches (x3)**",
        "steps": [
            "1️⃣ Use **Ultrasound** (and **Lab Kit** + **Antibiotics** if fever is rising).",
            "2️⃣ Use **Anesthetic**, then cut **3 times** with **Scalpel**.",
            "3️⃣ Click **Fix it!**.",
            "4️⃣ If status says **`Coming to`**, use **Anesthetic** again, then use **Stitches (3x)** to close!",
        ],
        "watch_out": "Never use **Anesthetic** while the patient is still `Unconscious` — wait until status explicitly changes to `Coming to` or `Awake`!",
        "sprite_item": "Surgical Antiseptic",
    },
    "Liver Infection": {
        "category": "🦠 Organ + Fever Surgery",
        "difficulty": "⭐⭐⭐ Hard",
        "ultrasound": "The patient has a Liver Infection.",
        "incisions": 3,
        "bones": "None",
        "tool_order": "🔬 **Lab Kit** ➔ 💊 **Antibiotics** ➔ 💤 **Anesthetic** ➔ 🔪 **Scalpel (x3)** ➔ ✅ **Fix it!** ➔ 🧵 **Stitches (x3)**",
        "steps": [
            "1️⃣ Use **Ultrasound**, then immediately use **Lab Kit** and **Antibiotics** to control the infection fever.",
            "2️⃣ Use **Anesthetic**, then use **Scalpel (3x)**.",
            "3️⃣ Click **Fix it!**.",
            "4️⃣ Re-apply **Anesthetic** if `Coming to`, close all 3 incisions with **Stitches (3x)**, and finish lowering fever with **Antibiotics**.",
        ],
        "watch_out": "Keep an eye on temperature between cuts — if Temp hits `105°+`, pause cutting and use **Antibiotics**.",
        "sprite_item": "Surgical Antibiotics",
    },
    "Serious Head Injury": {
        "category": "🩸 Severe Trauma Surgery",
        "difficulty": "⭐⭐⭐⭐ Very Hard",
        "ultrasound": "The patient has a Serious Head Injury!",
        "incisions": 3,
        "bones": "Shattered & Broken Bones",
        "tool_order": "🧵 **Stitches** *(stop initial bleeding)* ➔ 💤 **Anesthetic** ➔ 🔪 **Scalpel (x3)** ➔ 🔨 **Pins** ➔ ✅ **Fix it!** ➔ 🧵 **Stitches (x3)** ➔ 🦴 **Splint**",
        "steps": [
            "1️⃣ Patient starts with **heavy bleeding**! Use **Stitches (1–2x)** first so they don't bleed out, then **Ultrasound**.",
            "2️⃣ Use **Anesthetic**, then cut with **Scalpel (3x)**.",
            "3️⃣ Use **Pins** for any Shattered bones while open, then click **Fix it!**.",
            "4️⃣ Re-apply **Anesthetic** if `Coming to`, use **Stitches** until `Incisions: 0` and bleeding stops, then use **Splint** for Broken bones.",
        ],
        "watch_out": "Always stabilize heavy bleeding at the very start before cutting 3 times!",
        "sprite_item": "Surgical Stitches",
    },
    "Lung Tumor": {
        "category": "🫁 Deep Tumor Surgery",
        "difficulty": "⭐⭐⭐⭐ Very Hard",
        "ultrasound": "The patient has a Lung Tumor.",
        "incisions": 4,
        "bones": "Often 1 Broken / Shattered",
        "tool_order": "💤 **Anesthetic** ➔ 🔪 **Scalpel (x4)** ➔ 🔨 **Pins** *(if shattered)* ➔ ✅ **Fix it!** ➔ 💤 **Anesthetic** ➔ 🧵 **Stitches (x4)**",
        "steps": [
            "1️⃣ Use **Ultrasound**, then **Anesthetic**.",
            "2️⃣ Cut **4 times** with **Scalpel** (use **Clamp** or **Stitches** if bleeding gets too fast).",
            "3️⃣ Click **Fix it!** (and use **Pins** if any bone is Shattered).",
            "4️⃣ Wait for `Coming to`, re-apply **Anesthetic**, and close all 4 incisions with **Stitches (4x)**!",
        ],
        "watch_out": "With 4 incisions, bleeding stacks fast — use **Stitches** once mid-way if `Losing blood very quickly!` appears.",
        "sprite_item": "Surgical Clamp",
    },
    "Massive Trauma": {
        "category": "🚨 Critical Emergency Trauma",
        "difficulty": "⭐⭐⭐⭐⭐ Extreme",
        "ultrasound": "The patient has suffered Massive Trauma!",
        "incisions": 4,
        "bones": "Multiple Shattered & Broken Bones",
        "tool_order": "🧵 **Stitches** *(stabilize bleeding)* ➔ 💤 **Anesthetic** ➔ 🔪 **Scalpel (x4)** ➔ 🔨 **Pins (all shattered)** ➔ ✅ **Fix it!** ➔ 💤 **Anesthetic** ➔ 🧵 **Stitches (all)** ➔ 🦴 **Splint (all)**",
        "steps": [
            "1️⃣ **Stabilize first:** Use **Stitches (1–2x)** if bleeding heavily, then **Ultrasound**.",
            "2️⃣ Use **Anesthetic**, then cut **4 times** with **Scalpel** (using **Sponge** whenever vision is blocked).",
            "3️⃣ While cut open, use **Pins** until `Shattered: 0`, then click **Fix it!**.",
            "4️⃣ When status says `Coming to`, use **Anesthetic** again, then **Stitches** until `Incisions: 0` and bleeding stops.",
            "5️⃣ Finally, use **Splint** repeatedly until `Broken: 0`!",
        ],
        "watch_out": "Do NOT close all incisions before using **Pins** on Shattered bones, or you will have to cut the patient open again!",
        "sprite_item": "Surgical Transfusion",
    },
    "Brain Tumor": {
        "category": "🧠 Deepest Surgery (5 Incisions)",
        "difficulty": "⭐⭐⭐⭐⭐ Extreme",
        "ultrasound": "The patient has a Brain Tumor!",
        "incisions": 5,
        "bones": "Often 1 Shattered skull bone",
        "tool_order": "💤 **Anesthetic** ➔ 🔪 **Scalpel (x5)** ➔ 🔨 **Pins** *(if shattered)* ➔ ✅ **Fix it!** ➔ 💤 **Anesthetic** ➔ 🧵 **Stitches (x5)**",
        "steps": [
            "1️⃣ Use **Ultrasound**, then **Anesthetic**.",
            "2️⃣ Cut **5 times** with **Scalpel** (`Incisions: 5`). If bleeding becomes critical, use **Stitches** or **Clamp**.",
            "3️⃣ **Crucial:** By the 4th or 5th cut, status will change to **`Coming to`** — immediately re-apply **Anesthetic** before cutting/stitching further!",
            "4️⃣ Use **Pins** (if Shattered bone), click **Fix it!**, then use **Stitches (5x)** (and **Splint** if Broken).",
        ],
        "watch_out": "Brain Tumor is the only standard surgery requiring **5 Scalpel incisions**. Watch the `Coming to` status like a hawk!",
        "sprite_item": "Surgical Scalpel",
    },
    "Torn Punching Muscle": {
        "category": "🧪 Malady (Breaking Blocks)",
        "difficulty": "⭐⭐⭐ Hard (Malady)",
        "ultrasound": "The patient has a Torn Punching Muscle.",
        "incisions": 3,
        "bones": "Sometimes 1 Broken",
        "tool_order": "💤 **Anesthetic** ➔ 🔪 **Scalpel (x2–3)** ➔ ✅ **Fix it!** ➔ 🧵 **Stitches** ➔ 🦴 **Splint** *(if broken)*",
        "steps": [
            "1️⃣ Use **Ultrasound** to inspect, then **Anesthetic**.",
            "2️⃣ Cut with **Scalpel (2–3x)** until **Fix it!** lights up.",
            "3️⃣ Click **Fix it!**, then close all incisions with **Stitches** (and **Splint** if any bone is Broken).",
        ],
        "watch_out": "Common Malady from farming/breaking blocks! Easy to cure as long as you keep the patient asleep.",
        "sprite_item": "Surgical Stitches",
    },
    "Gem Cuts": {
        "category": "🧪 Malady (Picking Up Gems)",
        "difficulty": "⭐⭐⭐ Hard (Malady)",
        "ultrasound": "The patient is covered in Gem Cuts!",
        "incisions": 2,
        "bones": "None (Heavy Initial Bleeding)",
        "tool_order": "🧵 **Stitches** *(stabilize bleeding)* ➔ 💤 **Anesthetic** ➔ 🔪 **Scalpel (x2)** ➔ ✅ **Fix it!** ➔ 🧵 **Stitches (until 0 bleeding)**",
        "steps": [
            "1️⃣ Patient starts with multiple cuts/bleeding! Use **Stitches** first to bring bleeding under control, then **Ultrasound**.",
            "2️⃣ Use **Anesthetic**, then **Scalpel** until **Fix it!** appears.",
            "3️⃣ Click **Fix it!**, then use **Stitches** until `Incisions: 0` and all bleeding is gone.",
        ],
        "watch_out": "If pulse drops too low from gem bleeding, use **Transfusion** once to restore pulse!",
        "sprite_item": "Surgical Transfusion",
    },
    "Grumbleteeth": {
        "category": "🧪 Malady (Dental / Jaw)",
        "difficulty": "⭐⭐⭐ Hard (Malady)",
        "ultrasound": "The patient has Grumbleteeth.",
        "incisions": 2,
        "bones": "Often 1 Shattered / Broken",
        "tool_order": "💤 **Anesthetic** ➔ 🔪 **Scalpel (x2)** ➔ 🔨 **Pins** *(if shattered)* ➔ ✅ **Fix it!** ➔ 🧵 **Stitches (x2)** ➔ 🦴 **Splint**",
        "steps": [
            "1️⃣ Use **Ultrasound**, then **Anesthetic**.",
            "2️⃣ Cut with **Scalpel (2x)**, use **Pins** if jaw bone is Shattered, and click **Fix it!**.",
            "3️⃣ Stitch closed with **Stitches (2x)** and apply **Splint** if Broken.",
        ],
        "watch_out": "Check for fever at the start — if rising, use **Lab Kit** ➔ **Antibiotics**.",
        "sprite_item": "Surgical Pins",
    },
    "Chicken Feet": {
        "category": "🧪 Malady (Movement / Feet)",
        "difficulty": "⭐⭐⭐ Hard (Malady)",
        "ultrasound": "The patient has Chicken Feet!",
        "incisions": 2,
        "bones": "Shattered & Broken Foot Bones",
        "tool_order": "💤 **Anesthetic** ➔ 🔪 **Scalpel (x2)** ➔ 🔨 **Pins** ➔ ✅ **Fix it!** ➔ 🧵 **Stitches (x2)** ➔ 🦴 **Splint**",
        "steps": [
            "1️⃣ Use **Ultrasound**, then **Anesthetic**.",
            "2️⃣ Use **Scalpel (2x)**, then use **Pins** on any Shattered bones while open.",
            "3️⃣ Click **Fix it!**, close incisions with **Stitches**, and fix Broken bones with **Splint**.",
        ],
        "watch_out": "Remember: **Pins** first while open, **Splint** at the end after stitching!",
        "sprite_item": "Surgical Splint",
    },
    "Lockjaw": {
        "category": "🧪 Malady (Jaw Infection)",
        "difficulty": "⭐⭐⭐ Hard (Malady)",
        "ultrasound": "The patient has Lockjaw.",
        "incisions": 2,
        "bones": "1 Shattered / Broken",
        "tool_order": "🔬 **Lab Kit** ➔ 💊 **Antibiotics** ➔ 💤 **Anesthetic** ➔ 🔪 **Scalpel (x2)** ➔ 🔨 **Pins** ➔ ✅ **Fix it!** ➔ 🧵 **Stitches** ➔ 🦴 **Splint**",
        "steps": [
            "1️⃣ Use **Ultrasound**. If Temp > `98.6°`, use **Lab Kit** ➔ **Antibiotics**.",
            "2️⃣ Use **Anesthetic** ➔ **Scalpel (2x)**.",
            "3️⃣ Use **Pins** (if Shattered) ➔ **Fix it!** ➔ **Stitches (2x)** ➔ **Splint**.",
        ],
        "watch_out": "Watch both fever and shattered jaw bones during Lockjaw.",
        "sprite_item": "Surgical Lab Kit",
    },
    "Ecto-Bones": {
        "category": "🧪 Malady (Vile Vial / Bone Decay)",
        "difficulty": "⭐⭐⭐⭐ Very Hard (Malady)",
        "ultrasound": "The patient is suffering from Ecto-Bones!",
        "incisions": 2,
        "bones": "Multiple Shattered & Broken Bones",
        "tool_order": "💤 **Anesthetic** ➔ 🔪 **Scalpel (x1–2)** ➔ 🔨 **Pins (all shattered)** ➔ ✅ **Fix it!** ➔ 🧵 **Stitches** ➔ 🦴 **Splint (all broken)**",
        "steps": [
            "1️⃣ Use **Ultrasound**, then **Anesthetic**.",
            "2️⃣ Use **Scalpel** to open the patient, then spam **Pins** until `Shattered: 0`.",
            "3️⃣ Click **Fix it!** (if required), close all incisions with **Stitches**, then spam **Splint** until `Broken: 0`!",
        ],
        "watch_out": "Ecto-Bones has tons of broken/shattered bones — make sure you convert EVERY Shattered bone with **Pins** before stitching closed!",
        "sprite_item": "Surgical Pins",
    },
    "Fatty Liver": {
        "category": "🧪 Malady (Vile Vial / Organ)",
        "difficulty": "⭐⭐⭐⭐ Very Hard (Malady)",
        "ultrasound": "The patient has Fatty Liver.",
        "incisions": 3,
        "bones": "None",
        "tool_order": "💤 **Anesthetic** ➔ 🔪 **Scalpel (x3)** ➔ ✅ **Fix it!** ➔ 💤 **Anesthetic** *(if Coming to)* ➔ 🧵 **Stitches (x3)**",
        "steps": [
            "1️⃣ Use **Ultrasound** (stabilize bleeding or fever first if needed).",
            "2️⃣ Use **Anesthetic** ➔ **Scalpel (3x)** ➔ **Fix it!**.",
            "3️⃣ Re-apply **Anesthetic** if `Coming to`, then close with **Stitches (3x)**.",
        ],
        "watch_out": "Watch for heavy bleeding during the 3 incisions.",
        "sprite_item": "Surgical Clamp",
    },
    "Moldy Guts": {
        "category": "🧪 Malady (Vile Vial / Severe Infection)",
        "difficulty": "⭐⭐⭐⭐ Very Hard (Malady)",
        "ultrasound": "The patient has Moldy Guts!",
        "incisions": 3,
        "bones": "None (High Fever)",
        "tool_order": "🔬 **Lab Kit** ➔ 💊 **Antibiotics** ➔ 💤 **Anesthetic** ➔ 🔪 **Scalpel (x3)** ➔ ✅ **Fix it!** ➔ 🧵 **Stitches (x3)** ➔ 💊 **Antibiotics**",
        "steps": [
            "1️⃣ Use **Ultrasound**, then **Lab Kit** ➔ **Antibiotics** to keep the mold fever from spiking past `108°`.",
            "2️⃣ Use **Anesthetic** ➔ **Scalpel (3x)** ➔ **Fix it!**.",
            "3️⃣ Re-apply **Anesthetic** if `Coming to`, stitch closed with **Stitches (3x)**, and finish lowering fever with **Antibiotics**.",
        ],
        "watch_out": "Moldy Guts causes rapid temperature spikes — alternate **Antibiotics** if fever passes `105°`!",
        "sprite_item": "Surgical Antibiotics",
    },
    "Brainworms": {
        "category": "🧪 Malady (Vile Vial / Deep Brain)",
        "difficulty": "⭐⭐⭐⭐⭐ Extreme (Malady)",
        "ultrasound": "The patient has Brainworms!",
        "incisions": 4,
        "bones": "Often 1 Shattered",
        "tool_order": "💤 **Anesthetic** ➔ 🔪 **Scalpel (x4–5)** ➔ 🔨 **Pins** *(if shattered)* ➔ ✅ **Fix it!** ➔ 💤 **Anesthetic** ➔ 🧵 **Stitches (x4–5)**",
        "steps": [
            "1️⃣ Use **Ultrasound**, then **Anesthetic**.",
            "2️⃣ Cut **4 to 5 times** with **Scalpel** until **Fix it!** appears.",
            "3️⃣ Watch for **`Coming to`** before your final cut or first stitch — re-apply **Anesthetic** immediately!",
            "4️⃣ Click **Fix it!**, use **Pins** if Shattered, and close all incisions with **Stitches**.",
        ],
        "watch_out": "Just like Brain Tumor, the patient WILL start waking up mid-surgery — never cut or stitch while `Coming to`!",
        "sprite_item": "Surgical Scalpel",
    },
    "Lupus": {
        "category": "🧪 Malady (Vile Vial / Autoimmune)",
        "difficulty": "⭐⭐⭐⭐⭐ Extreme (Malady)",
        "ultrasound": "The patient has Lupus!",
        "incisions": 4,
        "bones": "Shattered / Broken + High Fever",
        "tool_order": "🔬 **Lab Kit** ➔ 💊 **Antibiotics** ➔ 💤 **Anesthetic** ➔ 🔪 **Scalpel (x3–4)** ➔ 🔨 **Pins** ➔ ✅ **Fix it!** ➔ 💤 **Anesthetic** ➔ 🧵 **Stitches** ➔ 🦴 **Splint**",
        "steps": [
            "1️⃣ Use **Ultrasound**, then **Lab Kit** ➔ **Antibiotics** to slow the fever.",
            "2️⃣ Use **Anesthetic**, then cut with **Scalpel (3–4x)**.",
            "3️⃣ Use **Pins** on any Shattered bones, then click **Fix it!**.",
            "4️⃣ Re-apply **Anesthetic** when `Coming to`, close all incisions with **Stitches**, fix Broken bones with **Splint**, and lower remaining fever with **Antibiotics**.",
        ],
        "watch_out": "Lupus combines deep incisions, fever, and bone damage — keep **Defibrillator** and **Sponge** ready at all times!",
        "sprite_item": "Surgical Defibrillator",
    },
    "Chaos Infection": {
        "category": "🧪 Malady (Vile Vial / Boss Malady)",
        "difficulty": "⭐⭐⭐⭐⭐ Extreme (Hardest Malady)",
        "ultrasound": "The patient has a Chaos Infection!",
        "incisions": 4,
        "bones": "Multiple Shattered/Broken + Heavy Bleeding + High Fever",
        "tool_order": "🧵 **Stitches** *(slow bleeding)* ➔ 🔬 **Lab Kit** ➔ 💊 **Antibiotics** ➔ 💤 **Anesthetic** ➔ 🔪 **Scalpel (x4)** ➔ 🔨 **Pins** ➔ ✅ **Fix it!** ➔ 💤 **Anesthetic** ➔ 🧵 **Stitches** ➔ 🦴 **Splint**",
        "steps": [
            "1️⃣ **Stabilize first:** Use **Stitches (1–2x)** if bleeding rapidly, then **Ultrasound** ➔ **Lab Kit** ➔ **Antibiotics**.",
            "2️⃣ Use **Anesthetic**, then cut **4 times** with **Scalpel**.",
            "3️⃣ Use **Pins** on all Shattered bones while open, then click **Fix it!**.",
            "4️⃣ Re-apply **Anesthetic** when `Coming to`, close all incisions with **Stitches**, fix Broken bones with **Splint**, and finish lowering Temp below `98.6°` with **Antibiotics**!",
        ],
        "watch_out": "Chaos Infection throws every complication at you — follow the Emergency Priority Order (`Defibrillator` > `Sponge` > `Anesthetic` > `Stitches` > `Antibiotics`)!",
        "sprite_item": "Surgical Transfusion",
    },
}


class SurgeryEmergencyView(discord.ui.View):
    """Interactive buttons attached below every /surgery guide for instant mid-surgery emergency rules."""

    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Emergency Priority Order",
        style=discord.ButtonStyle.danger,
        emoji="🚨",
    )
    async def priority_button(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        embed = discord.Embed(
            title="🚨 Golden Priority Order (When Multiple Things Go Wrong!)",
            description=(
                "Whenever multiple complications happen on the same turn during surgery, **always follow this exact priority from top to bottom**:\n\n"
                "1️⃣ ⚡ **`Heart Stopped!`** ➔ **Defibrillator** *(Highest priority! You only have 2 turns before the patient dies!)*\n"
                "2️⃣ 🧽 **`You can't see what you are doing!`** ➔ **Sponge** *(Using any other tool while blind has a huge fail rate!)*\n"
                "3️⃣ 💤 **`Status: Coming to / Awake`** *(while you still need to cut/pin/stitch)* ➔ **Anesthetic** *(⚠️ NEVER use Anesthetic if they are already `Unconscious` or if `Heart Stopped!`)*\n"
                "4️⃣ 🩸 **`Losing blood very quickly!`** ➔ **Stitches** *(or **Clamp** if you are still cutting open; use **Transfusion** if Pulse is `Extremely Weak`)*\n"
                "5️⃣ 🌡️ **`Temp > 104.0° (Rising Fast)`** ➔ **Lab Kit** *(once)* ➔ **Antibiotics** *(Patient dies if Temp reaches `111°`)*"
            ),
            color=discord.Color.red(),
        )
        embed.set_footer(text=FOOTER_TEXT)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(
        label="All 13 Surgical Tools Cheat-Sheet",
        style=discord.ButtonStyle.secondary,
        emoji="🧰",
    )
    async def tools_button(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        embed = discord.Embed(
            title="🧰 All 13 Growtopia Surgery Tools — Quick Reference",
            description=(
                "• 📡 **Ultrasound:** Diagnoses the unknown disease/malady at the start.\n"
                "• 🧽 **Sponge:** Clears blood when *\"You can't see what you are doing!\"*\n"
                "• 💤 **Anesthetic:** Puts patient to sleep (`Unconscious`). Required before `Scalpel`, `Pins`, or `Stitches`.\n"
                "• 🔪 **Scalpel:** Cuts `1` incision (`1` to `5` needed depending on illness until **Fix it!** appears).\n"
                "• 🧵 **Stitches:** Closes `1` incision AND reduces bleeding by 1 level.\n"
                "• 🔬 **Lab Kit:** Unlocks **Antibiotics** for the rest of the surgery.\n"
                "• 💊 **Antibiotics:** Drops fever (`Temp`) back down toward `98.6°`.\n"
                "• 🧴 **Antiseptic:** Prevents/cleans incision infection when `Sanitation` is low.\n"
                "• ⚡ **Defibrillator:** Restarts the heart when `Heart Stopped!`.\n"
                "• 🔨 **Pins:** Turns `1 Shattered` bone into `1 Broken` bone *(must have `Incisions >= 1` and be `Unconscious`)*.\n"
                "• 🦴 **Splint:** Repairs `1 Broken` bone *(can be used even when `Incisions: 0`)*.\n"
                "• ✂️ **Clamp:** Slows down bleeding while incisions are open without closing the incision.\n"
                "• 🩸 **Transfusion:** Restores `Pulse` when the patient has lost too much blood."
            ),
            color=discord.Color.teal(),
        )
        embed.set_footer(text=FOOTER_TEXT)
        await interaction.response.send_message(embed=embed, ephemeral=True)


class SurgeryHelperCog(commands.Cog, name="Surgery Helper"):
    def __init__(self, bot: EventBot) -> None:
        self.bot = bot

    async def surgery_autocomplete(
        self,
        _interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        query = current.strip().lower()
        choices: list[app_commands.Choice[str]] = []
        for name, info in SURGERY_DATABASE.items():
            if not query or query in name.lower() or query in info["category"].lower() or query in info["ultrasound"].lower():
                label = f"{name} — {info['difficulty']} ({info['incisions']} Scalpel)"
                choices.append(app_commands.Choice(name=label[:100], value=name))
        return choices[:25]

    @app_commands.command(
        name="set_surgery_channel",
        description="Restrict the /surgery cheat-sheet assistant exclusively to a dedicated channel",
    )
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(channel="Dedicated channel for /surgery lookups (defaults to current channel)")
    async def set_surgery_channel_command(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel | None = None,
    ) -> None:
        if not is_server_manager(interaction):
            await interaction.response.send_message(
                "❌ Only server admins can use `/set_surgery_channel`.",
                ephemeral=True,
            )
            return
        await interaction.response.defer()
        target_channel = channel or interaction.channel
        if not isinstance(target_channel, discord.TextChannel):
            await interaction.followup.send("❌ Please select a standard text channel.", ephemeral=True)
            return

        state = load_state()
        state["surgery_channel_id"] = target_channel.id
        save_state(state)

        guide_embed = discord.Embed(
            title="🩺 Growcom Surgery Cheat-Sheet Assistant",
            description=(
                "Use **`/surgery`** in this channel to get the exact **step-by-step tool order**, "
                "**Scalpel incision count**, and **emergency complication guide** for any Growtopia Surgery or Vile Vial Malady!\n\n"
                "**How to Use:**\n"
                "1️⃣ Type **`/surgery`** and pick your patient's **Illness** or **Malady** from the autocomplete list "
                "(e.g. `Massive Trauma`, `Brain Tumor`, `Bird Flu`, `Lupus`, `Chaos Infection`, `Moldy Guts`, `Torn Punching Muscle`).\n"
                "2️⃣ Follow the exact **Tool Order** and **Incision Count** shown.\n"
                "3️⃣ Click **🚨 Emergency Priority Order** or **🧰 All 13 Surgical Tools** below any result if your patient's heart stops or fever spikes!"
            ),
            color=discord.Color.from_rgb(231, 76, 60),
        )
        guide_embed.set_footer(text=FOOTER_TEXT)
        await target_channel.send(embed=guide_embed)

        await interaction.followup.send(
            f"✅ Locked **`/surgery`** exclusively to {target_channel.mention}! "
            f"Players trying to run `/surgery` anywhere else will be redirected to {target_channel.mention}.",
            ephemeral=True,
        )

    @app_commands.command(
        name="surgery",
        description="Instant step-by-step Growtopia Surgery & Malady cheat-sheet (Tool order, Scalpels, Emergency rules)!",
    )
    @app_commands.describe(
        patient="Select the Illness or Malady (e.g. Massive Trauma, Brain Tumor, Bird Flu, Lupus, Chaos Infection)"
    )
    @app_commands.autocomplete(patient=surgery_autocomplete)
    async def surgery_command(self, interaction: discord.Interaction, patient: str) -> None:
        state = load_state()
        allowed_channel_id = state.get("surgery_channel_id")
        if allowed_channel_id and int(interaction.channel_id or 0) != int(allowed_channel_id):
            await interaction.response.send_message(
                f"❌ The **`/surgery`** assistant can only be used inside <#{allowed_channel_id}>!",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        # Match case-insensitively or by substring
        matched_name: str | None = None
        for name in SURGERY_DATABASE:
            if name.lower() == patient.strip().lower():
                matched_name = name
                break
        if not matched_name:
            for name in SURGERY_DATABASE:
                if patient.strip().lower() in name.lower():
                    matched_name = name
                    break

        if not matched_name:
            await interaction.followup.send(
                f"❌ Could not find a surgery/malady matching **`{patient}`**. Pick one from the `/surgery` autocomplete list!",
                ephemeral=True,
            )
            return

        info = SURGERY_DATABASE[matched_name]
        incisions = info["incisions"]

        embed = discord.Embed(
            title=f"🩺 Surgery Guide — {matched_name}",
            description=(
                f"📡 **Ultrasound Diagnosis:** *\"{info['ultrasound']}\"*\n\n"
                f"🧰 **Core Tool Order:**\n{info['tool_order']}"
            ),
            color=discord.Color.from_rgb(231, 76, 60),
        )
        embed.add_field(
            name="🏷️ Category",
            value=info["category"],
            inline=True,
        )
        embed.add_field(
            name="⚡ Difficulty",
            value=info["difficulty"],
            inline=True,
        )
        embed.add_field(
            name="🔪 Scalpel Incisions Needed",
            value=f"**`{incisions}x Scalpel`**" if incisions > 0 else "**`0 (DO NOT CUT!)`**",
            inline=True,
        )
        embed.add_field(
            name="🦴 Expected Bone Damage",
            value=f"`{info['bones']}`",
            inline=True,
        )
        embed.add_field(
            name="📋 Step-by-Step Procedure",
            value="\n".join(info["steps"]),
            inline=False,
        )
        embed.add_field(
            name="⚠️ Pro Surgeon Warning",
            value=f"💡 {info['watch_out']}",
            inline=False,
        )
        embed.add_field(
            name="🚨 Live Mid-Surgery Complications (If Anything Goes Wrong)",
            value=(
                "• 🧽 **Can't see anything?** ➔ **`Sponge`** immediately!\n"
                "• ⚡ **Heart Stopped!** ➔ **`Defibrillator`** immediately!\n"
                "• 💤 **Status: `Coming to` / `Awake`?** ➔ **`Anesthetic`** before cutting/pinning/stitching!\n"
                "• 🌡️ **Temp > `98.6°` rising?** ➔ **`Lab Kit`** *(once)* ➔ **`Antibiotics`**\n"
                "• 🩸 **Heavy Bleeding?** ➔ **`Stitches`** *(or **`Transfusion`** if Pulse is weak)*"
            ),
            inline=False,
        )

        embed.set_footer(text=FOOTER_TEXT)
        files: list[discord.File] = []
        sprite_bytes = await self.bot.api.get_item_sprite(info.get("sprite_item", "Surgical Scalpel"))
        if sprite_bytes:
            files.append(discord.File(BytesIO(sprite_bytes), filename="sprite.png"))
            embed.set_thumbnail(url="attachment://sprite.png")

        view = SurgeryEmergencyView()
        await interaction.followup.send(embed=embed, view=view, files=files)


async def setup(bot: EventBot) -> None:
    await bot.add_cog(SurgeryHelperCog(bot))
