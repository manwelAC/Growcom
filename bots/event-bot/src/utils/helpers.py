"""
Shared state, permission checks, time parsers, and formatting helpers for Growcom Event Bot.
"""

from __future__ import annotations

from datetime import datetime, time as dt_time, timedelta
import json
import logging
import os
from pathlib import Path
import re
from typing import Any
from zoneinfo import ZoneInfo

import discord

PROJECT_ROOT = Path(__file__).resolve().parents[4]
STATE_FILE = PROJECT_ROOT / "bots" / "event-bot" / "data" / "daily_state.json"
REMINDERS_FILE = PROJECT_ROOT / "bots" / "event-bot" / "data" / "harvest_reminders.json"

FOOTER_TEXT = "Growcom Events by Manwel"

EVENT_TIMEZONE_NAME = os.getenv("EVENT_TIMEZONE", "Asia/Manila")
EVENT_TZ = ZoneInfo(EVENT_TIMEZONE_NAME)
RESET_HOUR = int(os.getenv("DAILY_RESET_HOUR", "13"))
RESET_MINUTE = int(os.getenv("DAILY_RESET_MINUTE", "0"))
DAILY_TRIGGER_TIME = dt_time(hour=RESET_HOUR, minute=RESET_MINUTE, tzinfo=EVENT_TZ)

logger = logging.getLogger("growcom.event_bot")


def load_state() -> dict[str, Any]:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_state(state: dict[str, Any]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def load_reminders() -> list[dict[str, Any]]:
    if REMINDERS_FILE.exists():
        try:
            return json.loads(REMINDERS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def save_reminders(reminders: list[dict[str, Any]]) -> None:
    REMINDERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    REMINDERS_FILE.write_text(json.dumps(reminders, indent=2), encoding="utf-8")


def is_server_manager(interaction: discord.Interaction) -> bool:
    """Ensure only Server Owner, Administrators, or Manage Server roles can execute /set_... commands."""
    if not interaction.guild or not isinstance(interaction.user, discord.Member):
        return False
    perms = interaction.user.guild_permissions
    return bool(perms.administrator or perms.manage_guild or interaction.guild.owner_id == interaction.user.id)


def format_duration(seconds: int) -> str:
    if seconds <= 0:
        return "Instant"
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if secs:
        parts.append(f"{secs}s")
    return " ".join(parts)


def parse_planted_datetime(raw: str | None, now_dt: datetime) -> datetime:
    """
    Dynamically parse when the user planted their trees into an exact timezone-aware datetime.
    Supports:
    - Clock times: '10:30 PM', '10:30pm', '9pm', '2:15 AM', '22:30', '14:00'
      (If the clock time is ahead of current time, automatically resolves to yesterday!)
    - Yesterday + time: 'yesterday 8:30 PM', 'yesterday 20:30'
    - Relative durations: '2h 30m ago', '45m', '1d 4h'
    - Current time: 'now', 'just now'
    """
    if not raw or not raw.strip():
        return now_dt

    text = raw.strip().lower()
    if text in {"now", "just now", "0", "0m", "0s"}:
        return now_dt

    is_yesterday = "yesterday" in text
    clean_text = text.replace("yesterday", "").replace("today", "").strip()

    # 1. Check 12-hour or 24-hour clock time (e.g. "10:30 pm", "10:30pm", "9pm", "22:30")
    clock_match = re.match(r"^(\d{1,2})(?::(\d{2}))?\s*(am|pm)?$", clean_text, re.IGNORECASE)
    if clock_match and (clock_match.group(2) is not None or clock_match.group(3) is not None):
        hour = int(clock_match.group(1))
        minute = int(clock_match.group(2) or 0)
        meridiem = (clock_match.group(3) or "").lower()

        if meridiem == "pm" and hour < 12:
            hour += 12
        elif meridiem == "am" and hour == 12:
            hour = 0

        if 0 <= hour <= 23 and 0 <= minute <= 59:
            candidate = now_dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if is_yesterday or candidate > now_dt:
                candidate -= timedelta(days=1)
            return candidate

    # 2. Check ISO / standard date-time (e.g. "2026-11-03 22:30")
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %I:%M %p", "%b %d %I:%M %p", "%b %d %H:%M"):
        try:
            parsed = datetime.strptime(clean_text, fmt)
            if parsed.year == 1900:
                parsed = parsed.replace(year=now_dt.year)
            return parsed.replace(tzinfo=now_dt.tzinfo)
        except ValueError:
            pass

    # 3. Check relative elapsed duration (e.g. "2h 30m ago", "45m")
    total_seconds = 0
    matches = re.findall(r"(\d+)\s*([dhms])", clean_text)
    if matches:
        for amount_str, unit in matches:
            amount = int(amount_str)
            if unit == "d":
                total_seconds += amount * 86400
            elif unit == "h":
                total_seconds += amount * 3600
            elif unit == "m":
                total_seconds += amount * 60
            elif unit == "s":
                total_seconds += amount
        return now_dt - timedelta(seconds=total_seconds)

    if clean_text.isdigit():
        return now_dt - timedelta(minutes=int(clean_text))

    raise ValueError(
        f"Could not understand time `{raw}`. Try formats like `10:30 PM`, `22:30`, `yesterday 8:00 PM`, `2h 30m ago`, or `now`."
    )
