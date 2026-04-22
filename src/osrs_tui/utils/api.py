"""
utils/api.py - Thin async wrapper around the runescape-hiscore package.

All network I/O is kept here so screens never import the library directly.
This makes it trivial to swap the underlying package later.

"""
from __future__ import annotations
import requests
import math

import asyncio
from dataclasses import dataclass, field
from typing import Dict, Optional


# -------------------------------------------
# Domain models
# -------------------------------------------

BASE_URL = "https://services.runescape.com/m=hiscore_oldschool/"
SPARK_CHARS = "▁▂▃▄▅▆▇█"

SKILL_ORDER = [
    "Overall",
    "Attack", "Hitpoints", "Mining",
    "Strength", "Agility", "Smithing",
    "Defence", "Herblore", "Fishing",
    "Ranged", "Thieving", "Cooking",
    "Prayer", "Crafting", "Firemaking",
    "Magic", "Fletching", "Woodcutting",
    "Runecraft", "Slayer", "Farming",
    "Construction", "Hunter", "Sailing",
]

SKILLS = [
    "Overall",
    "Attack",
    "Defence",
    "Strength",
    "Hitpoints",
    "Ranged",
    "Prayer",
    "Magic",
    "Cooking",
    "Woodcutting",
    "Fletching",
    "Fishing",
    "Firemaking",
    "Crafting",
    "Smithing",
    "Mining",
    "Herblore",
    "Agility",
    "Thieving",
    "Slayer",
    "Farming",
    "Runecraft",
    "Sailing",
    "Construction",
    "Hunter",
]

MODES = {
    "ultimate": "index_lite_ultimate.ws",
    "hardcore": "index_lite_hardcore_ironman.ws",
    "ironman": "index_lite_ironman.ws",
    "normal": "index_lite.ws",
}

SKILL_ICONS = {
    "Overall":       "⚔",
    "Attack":        "⚔",
    "Hitpoints":     "❤",
    "Mining":        "⛏",
    "Strength":      "💪",
    "Agility":       "🏃",
    "Smithing":      "🔨",
    "Defence":       "🛡",
    "Herblore":      "🌿",
    "Fishing":       "🎣",
    "Ranged":        "🏹",
    "Thieving":      "🗝",
    "Cooking":       "🍳",
    "Prayer":        "✝",
    "Crafting":      "💎",
    "Firemaking":    "🔥",
    "Magic":         "🔮",
    "Fletching":     "🪃",
    "Woodcutting":   "🪓",
    "Runecraft":  "🌀",
    "Slayer":        "💀",
    "Farming":       "🌱",
    "Construction":  "🏠",
    "Sailing": "⛵️",
    "Hunter": "🦅",
}


@dataclass
class SkillData:
    name: str
    level: int
    rank: int
    xp: int
    xp_to_next: int = 0

    @property
    def icon(self) -> str:
        return SKILL_ICONS.get(self.name, "•")
    
    @property
    def xp_formatted(self) -> str:
        return f"{self.xp:,}"
    
    @property
    def rank_formatted(self) -> str:
        return f"{self.rank:,}" if self.rank > 0 else "-"
    

@dataclass
class PlayerData:
    username: str
    account_type: str = "normal"
    skills: Dict[str, SkillData] = field(default_factory=dict)
    total_level: int = 0
    total_xp: int = 0

    @property
    def combat_level(self) -> int:
        """Approximate combat level from skill data."""
        s = self.skills
        if not s:
            return 0
        base = 0.25 * (
            s.get("Defence", SkillData("", 1, 0, 0)).level
            + s.get("Hitpoints", SkillData("", 10, 0, 0)).level
            + s.get("Prayer", SkillData("", 1, 0, 0)).level // 2
        )
        melee = 0.325 * (
            s.get("Attack", SkillData("", 1, 0, 0)).level
            + s.get("Strength", SkillData("", 1, 0, 0)).level
        )
        ranged = s.get("Ranged", SkillData("", 1, 0, 0)).level
        magic = s.get("Magic", SkillData("", 1, 0, 0)).level
        best = max(0.325 * ranged * 1.5, 0.325 * magic * 1.5, melee)
        return int(base + best)
    

# ----------------------------------------------------------------------------
# Async fetch
# -----------------------------------------------------------------------------


class APIError(Exception):
    """Raised when hiscore lookup fails."""


async def fetch_player(username: str, account_type: str = "normal") -> PlayerData:
    """
    Fetch hiscore data for `username` in a thread pool so we don't block 
    the Textual event loop.
    
    """
    return await asyncio.get_event_loop().run_in_executor(
        None,
        _blocking_fetch,
        username,
        account_type
    )


# ----------------------------------------------------------------------------
# Helper functions
# ----------------------------------------------------------------------------


def _xp_for_level(level: int) -> int:
    """Calculate the total XP required to reach a given level in OSRS."""
    return math.floor(
        (1 / 4) * sum(
            math.floor(x + 300 * (2 ** (x / 7)))
            for x in range(1, level)
        )
    )


def _xp_difference(level_a: int, level_b: int) -> int:
    """Calculate the XP difference between two levels."""
    low, high = sorted(level_a, level_b)
    return _xp_for_level(high) - _xp_for_level(low)


def _make_sparkline(data: list[int]) -> str:
    mn, mx = min(data), max(data)
    span = mx - mn or 1
    return "".join(
        SPARK_CHARS[int((v - mn) / span * (len(SPARK_CHARS)-1))]
        for v in data
    )


def _blocking_fetch(username: str, account_type: str) -> PlayerData:
    """Synchronous fetch - runs in a thread."""
    try:
        data = _fetch_hiscore(username, account_type)
    except Exception as err:
        raise APIError(f"Could not load '{username}': {err}")
    
    skills: Dict[str, SkillData] = {}

    account_type = data[0]
    _skill_list = data[1]

    for entry in _skill_list:
        name = entry.get("skill", None)
        if name not in SKILL_ORDER:
            continue
        try:
            xp = int(entry.get("xp", 0))
            level = int(entry.get("level", 0))
            rank = int(entry.get("rank", -1))
        except (TypeError, ValueError):
            continue

        xp_next = 0
        if 1 <= level < 99:
            xp_next = _xp_for_level(level + 1) - xp
            xp_next = max(0, xp_next)
        
        skills[name] = SkillData(
            name=name,
            level=level,
            rank=rank,
            xp=xp,
            xp_to_next=xp_next
        )
    overall = skills.get("Overall")
    return PlayerData(
        username=username,
        account_type=account_type,
        skills=skills,
        total_level=overall.level if overall else 0,
        total_xp=overall.xp if overall else 0
    )


def _fetch_hiscore(username: str, account_type) -> tuple[str, list[dict]]:
    err = None
    if account_type not in MODES:
        raise ValueError(f'Invalid value for `account_type` received: "{account_type}"')
    ep = MODES[account_type]
    url = f"{BASE_URL}{ep}?player={username}"
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            lines = r.text.strip().splitlines()
            stats = []
            for skill, line in zip(SKILLS, lines):
                rank, lvl, xp = map(int, line.split(","))
                stats.append({
                    "skill": skill,
                    "rank": rank,
                    "level": lvl,
                    "xp": xp,
                })
            return account_type, stats
        if r.status_code not in (404,):
            r.raise_for_status()
    except Exception as e:
        err = e
    raise err or requests.HTTPError(f"<_fetch_hiscore error> User '{username}' ['{account_type}'] not found.")


_XP_TABLE = [_xp_for_level(i) for i in range(1, 100)]