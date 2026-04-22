"""
widgets/stats.py - Reusable Textual widgets for displaying OSRS stat data.
"""

from __future__ import annotations

from typing import Optional

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import DataTable, Label, ProgressBar, Static

from osrs_tui.utils.api import PlayerData, SKILL_ORDER, SkillData


# -----------------------------------------------------------------
# Player header / summary
# -----------------------------------------------------------------

class PlayerHeader(Static):
    """Displays username, combat level, total level, and total XP."""

    DEFAULT_CSS = """
    PlayerHeader {
        background: $panel;
        border: tall $accent;
        padding: 0 2;
        height: 5;
    }
    PlayerHeader .header-name {
        text-style: bold;
        color: $accent;
        content-align: center middle;
    }
    PlayerHeader .header-stats {
        color: $text-muted;
        content-align: center middle;
    }
    """

    def __init__(self, player: PlayerData, **kwargs) -> None:
        super().__init__(**kwargs)
        self._player = player

    def compose(self) -> ComposeResult:
        p = self._player
        account_badge = {
            "ironman": " [IM]",
            "hardcore": " [HC]",
            "ultimate": " [UIM]",
        }.get(p.account_type, "")

        yield Label(
            f"👤  {p.username}{account_badge}",
            classes="header-name"
        )
        yield Label(
            f"⚔ Combat: {p.combat_level}   "
            f"📊 Total Level: {p.total_level:,}   "
            f"✨ Total XP: {p.total_xp:,}",
            classes="header-stats"
        )


# ------------------------------------------------------------
# Skills table
# ------------------------------------------------------------

class SkillsTable(Widget):
    """
    DataTable showing all OSRS skills: icon, name, level, rank, XP,
    and XP-to-next-level. Sorted by SKILL_ORDER.
    """

    DEFAULT_CSS = """
    SkillsTable {
        height: 1fr;
    }
    SkillsTable DataTable {
        height: 1fr;
    }
    """

    def __init__(self, player: PlayerData, **kwargs) -> None:
        super().__init__(**kwargs)
        self._player = player
    
    def compose(self) -> ComposeResult:
        yield DataTable(id="skills-dt", zebra_stripes=True, cursor_type="row")

    def on_mount(self) -> None:
        table: DataTable = self.query_one("#skills-dt", DataTable)
        table.add_columns("", "Skill", "Level", "Rank", "XP", "XP to next")

        for skill_name in SKILL_ORDER:
            skill = self._player.skills.get(skill_name)
            if skill is None:
                continue

            xp_next = (
                f"{skill.xp_to_next:,}"
                if skill.level < 99 and skill_name != "Overall"
                else ("MAX" if skill_name != "Overall" else "-")
            )

            table.add_row(
                skill.icon,
                skill.name.replace("_", " ").title(),
                str(skill.level),
                skill.rank_formatted,
                skill.xp_formatted,
                xp_next
            )


# ------------------------------------------------------------
# XP progress bars for a quick visual overview
# ------------------------------------------------------------

class SkillBars(Widget):
    """
    Compact vertical list of XP progress bars, one per combat / key skill.
    Shows progress toward level 99 (or 200M for overall).
    """

    COMBAT_SKILLS = [
        "Attack",
        "Strength",
        "Defence",
        "Ranged",
        "Magic",
        "Prayer",
        "Hitpoints",
        "Slayer"
    ]

    GATHERING_SKILLS = [
        "Mining",
        "Fishing",
        "Thieving",
        "Woodcutting",
    ]

    PRODUCTION_SKILLS = [
        "Smithing",
        "Herblore",
        "Cooking",
        "Crafting",
        "Runecraft",
        "Farming",
        "Fletching",
    ]
    OTHER_SKILLS = [
        "Agility",
        "Firemaking",
        "Slayer",
        "Hunter",
        "Construction",
        "Sailing",
    ]
    FEATURED_SKILLS = {
        "combat": COMBAT_SKILLS,
        "gathering": GATHERING_SKILLS,
        "production": PRODUCTION_SKILLS,
        "other": OTHER_SKILLS,
    }

    DEFAULT_CSS = """
    SkillBars {
        height: auto;
        padding: 0 1;
    }
    SkillBars Label {
        margin-top: 1;
    }
    SkillBars ProgressBar {
        width: 1fr;
    }"""

    def __init__(self, player: PlayerData, featured: str = "combat", **kwargs) -> None:
        super().__init__(**kwargs)
        self._player = player
        if featured not in self.FEATURED_SKILLS:
            featured = "combat"
        self._featured = self.FEATURED_SKILLS[featured]

    def compose(self) -> ComposeResult:
        for name in self._featured:
            skill = self._player.skills.get(name)
            if skill is None:
                continue
            pct = min(skill.level / 99, 1.0)
            icon = skill.icon
            yield Label(f"{icon} {name.title()}  lvl {skill.level}/99")
            bar = ProgressBar(total=100, show_eta=False, show_percentage=True)
            yield bar

            bar._osrs_pct = pct  # type: ignore[attr-defined]
    
    def on_mount(self) -> None:
        for bar in self.query(ProgressBar):
            pct = getattr(bar, "_osrs_pct", 0.0)
            bar.advance(pct * 100)