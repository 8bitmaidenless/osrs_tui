"""
screens/calculator.py - Skill Calculator Screen.

Layout
------
  ┌─────────────────────────────────────────────────────────────────┐
  │  Header: skill picker, Start XP/Level fields, Target XP/Level  │
  ├──────────────────────────────┬──────────────────────────────────┤
  │  Action list (checkboxes)    │  Results table                   │
  │  - filtered by level_req     │  action | # actions | total xp   │
  │  - sorted by level_req       │                                  │
  ├──────────────────────────────┴──────────────────────────────────┤
  │  [Calculate]   [Export to Resource Cost →]                      │
  └─────────────────────────────────────────────────────────────────┘

The screen accepts an optional `player` so it can pre-fill start XP 
from the player's current stats when launched from the skills screen.
"""

from __future__ import annotations

import math
from typing import Optional

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, ScrollableContainer, Vertical
from textual.screen import Screen
from textual.widgets import (
    Button,
    Checkbox,
    DataTable,
    Input,
    Label,
    Select,
    Static
)

from osrs_tui.utils.api import PlayerData, SKILLS
from osrs_tui.utils.calc import (
    CalcSession,
    TrainingAction,
    ActionResult,
    calculate,
    load_actions
)
from osrs_tui.widgets.charts import StatCard


SUPPORTED_SKILLS = [s for s in SKILLS if s != "Overall"]
F2P_SKILLS = [
    "Attack",
    "Strength",
    "Defence",
    "Ranged",
    "Magic",
    "Prayer",
    "Hitpoints",
    "Mining",
    "Smithing",
    "Fishing",
    "Cooking",
    "Woodcutting",
    "Firemaking",
    "Crafting",
    "Runecraft",
]
MEMBERS_SKILLS = [
    "Fletching",
    "Herblore",
    "Agility",
    "Thieving",
    "Slayer",
    "Farming",
    "Construction",
    "Hunter",
]


class CalculatorScreen(Screen):
    """Skill XP/level calculator with exportable session state."""

    BINDINGS = [
        ("escape", "go_back", "Back"),
        ("ctrl+r", "calculate", "Calculate"),
    ]

    DEFAULT_CSS = """
    CalculatorScreen {
        layout: vertical;
    }
    #calc-header {
        height: auto;
        background: $panel;
        border-bottom: tall $panel-darken-2;
        padding: 1 2;
        layout: horizontal;
    }
    #calc-header > * {
        margin-right: 2;
    }
    #skill-select { width: 22; }
    .xp-group { width: 30; height: auto; }
    .xp-group Label { margin-bottom: 1; color: $text-muted; }
    .xp-row { layout: horizontal; height: auto; }
    .xp-row Input { width: 13; margin-right: 1; }
    .xp-row Label { width: 3; content-align: center middle; }
    #calc-body {
        height: 1fr;
        layout: horizontal;
    }
    #actions-col {
        width: 36;
        border-right: tall $panel-darken-2;
    }
    #actions-title {
        background: $panel-darken-1;
        padding: 0 1;
        text-style: bold;
        height: 1;
    }
    #actions-scroll {
        height: 1fr;
    }
    .action-check { margin: 0 1; }
    #results-col {
        width: 1fr;
    }
    #results-title {
        background: $panel-darken-1;
        padding: 0 1;
        text-style: bold;
        height: 1;
    }
    #results-table { height: 1fr; }
    #calc-footer {
        height: 3;
        background: $panel;
        border-top: tall $panel-darken-2;
        layout: horizontal;
        align: left middle;
        padding: 0 2;
    }
    #calc-btn { margin-right: 2; }
    #export-btn { }
    #calc-status { color: $text-muted; margin-left: 2; }
    """

    def __init__(
        self,
        player: Optional[PlayerData] = None,
        initial_skill: Optional[str] = None,
        **kwargs
    ) -> None:
        super().__init__(**kwargs)
        self._player = player
        self._initial_skill = initial_skill or "Mining"
        self._all_actions: list[TrainingAction] = []
        self._last_results: list[ActionResult] = []
        self._last_session: Optional[CalcSession] = None

    # -------------------------------------------------------
    # Compose
    # -------------------------------------------------------

    def compose(self) -> ComposeResult:
        # --- Header ---
        with Horizontal(id="calc-header"):
            with Vertical(classes="xp-group"):
                yield Label("Skill")
                yield Select(
                    [(s.upper(), s) for s in SUPPORTED_SKILLS],
                    value=self._initial_skill,
                    id="skill-select"
                )
            with Vertical(classes="xp-group"):
                yield Label("Start    (XP / Level)")
                with Horizontal(classes="xp-row"):
                    yield Input("0", id="start-xp", placeholder="XP")
                    yield Label(" /")
                    yield Input("1", id="start-lvl", placeholder="Lvl")
            with Vertical(classes="xp-group"):
                yield Label("Target    (XP / Level)")
                with Horizontal(classes="xp-row"):
                    yield Input("0", id="target-xp", placeholder="XP")
                    yield Label(" /")
                    yield Input("1", id="target-lvl", placeholder="Lvl")
            
            with Vertical(classes="xp-group"):
                yield Label("0 Actions selected", id="actions-counter")
                yield Static(id="agg-card-slot")
                # yield Label("Aggregate")
                # with Horizontal(classes="xp-row"):
                #     yield Label("Actions:\t", id="agg-actions-label")
                #     yield Label("0", id="actions-counter")
                #     yield Label("selected")
                # yield Static(id="agg-card-slot")

        # --- Body ---
        with Horizontal(id="calc-body"):
            with Vertical(id="actions-col"):
                yield Static("Training Methods", id="actions-title")
                with ScrollableContainer(id="actions-scroll"):
                    pass

            with Vertical(id="results-col"):
                yield Static("Results", id="results-title")
                yield DataTable(id="results-table", zebra_stripes=True)

        # --- Footer ---
        with Horizontal(id="calc-footer"):
            yield Button("Calculate  (Ctrl+R)", variant="primary", id="calc-btn")
            yield Button("Export to Resources →", id="export-btn", disabled=True)
            yield Label("", id="calc-status")

    def on_mount(self) -> None:
        table: DataTable = self.query_one("#results-table", DataTable)
        table.add_columns("Method", "Actions Needed", "Total XP", "Inputs / action", "Tools")

        # self._load_skill(self._initial_skill)

        if self._player:
            skill = self._player.skills.get(self._initial_skill)
            if skill:
                self._set_start_xp(skill.xp)

    # ----------------
    # Skill change
    # ---------------

    def on_select_changed(self, event: Select.Changed) -> None:
        # self._syncing = True
        if event.select.id == "skill-select":
            skill = str(event.value)
            self._load_skill(skill)
            if self._player:
                # self._syncing = True
                s = self._player.skills.get(skill)
                if s:
                    self.query_one("#start-xp", Input).value = "0"
                    self.query_one("#start-lvl",Input).value = "1"
                    # self._syncing = False
                    self._set_start_xp(s.xp)
        
            
    
    def _load_skill(self, skill: str) -> None:
        self._all_actions = load_actions(skill)
        scroll = self.query_one("#actions-scroll", ScrollableContainer)
        scroll.remove_children()
        for action in sorted(self._all_actions, key=lambda a: a.level_req):
            lbl = f"[{action.level_req}] {action.name}"
            scroll.mount(Checkbox(lbl, id=f"action-{action.name.lower().replace(' ', '-')}", classes="action-check"))
            # scroll.mount(cb)

    # ----------------
    # XP <-> Level sync (two way)
    # -----------------

    # def on_input_changed(self, event: Input.Changed) -> None:
    def on_input_submitted(self, event: Input.Sumitted) -> None:
        iid = event.input.id
        try:
            val = int(event.value)
        except ValueError:
            return
        
        # Suppress recursive callbacks with a guard flag
        if getattr(self, "_syncing", False):
            return
        self._syncing = True
        try:
            if iid == "start-xp":
                self.query_one("#start-lvl", Input).value = str(CalcSession._xp_to_level(val))
            elif iid == "start-lvl":
                self.query_one("#start-xp", Input).value = str(CalcSession._level_to_xp(val))
            elif iid == "target-xp":
                self.query_one("#target-lvl", Input).value = str(CalcSession._xp_to_level(val))
            elif iid == "target-lvl":
                self.query_one("#target-xp", Input).value = str(CalcSession._level_to_xp(val))

        finally:
            self._syncing = False
        
    def _set_start_xp(self, xp: int) -> None:
        self.query_one("#start-xp", Input).value = str(xp)
        self.query_one("#start-lvl", Input).value = str(CalcSession._xp_to_level(xp))

    # --------------
    # Calculate
    # --------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "calc-btn":
            self.action_calculate()
        elif event.button.id == "export-btn":
            self._export_to_resource()
        
    def action_calculate(self) -> None:
        # Gather inputs
        try:
            start_xp = int(self.query_one("#start-xp", Input).value or 0)
            target_xp = int(self.query_one("#target-xp", Input).value or 0)
        except ValueError:
            self._set_status("⚠ Invalid XP values.")
            return
        
        skill = str(self.query_one("#skill-select", Select).value)

        if target_xp <= start_xp:
            self._set_status("⚠ Target XP must be greater than start XP.")
            return
        
        # Collect selected actions
        selected = [
            cb.label.plain.split("] ", 1)[-1].replace("-", " ").capitalize()
            for cb in self.query(".action-check")
            if isinstance(cb, Checkbox) and cb.value
        ]

        if not selected:
            self._set_status("⚠ Select at least one training method.")
            return
        
        session = CalcSession(
            skill=skill,
            start_xp=start_xp,
            target_xp=target_xp,
            selected_actions=selected
        )

        # results = calculate(session, self._all_actions)
        results, aggregate = calculate(session, self._all_actions)
        agg_xp, agg_actions = aggregate
        session.results = results
        session.aggregate_xp = agg_xp
        session.aggregate_actions = agg_actions
        self._last_session = session
        self._last_results = results

        self._populate_results(results, session)
        self.query_one("#export-btn", Button).disabled = len(results) == 0

    def _populate_results(self, results: list[ActionResult], session: CalcSession) -> None:
        table: DataTable = self.query_one("#results-table", DataTable)
        table.clear()

        if not results:
            self._set_status("No results.")
            return
        
        for r in results:
            mats = ", ".join(
                f"{int(m.qty)}x {m.name}" for m in r.material_totals()
            ) or "-"
            tools = ", ".join(
                f"{int(t.qty)}x {t.name} [lvl. {t.level_req}]" for t in r.action.skill_tools()
            ) or "-"
            inputs_per = ", ".join(
                f"{m.qty}x {m.name}" for m in r.action.input_materials()
            )
            table.add_row(
                r.action.name,
                f"{r.actions_needed:,}",
                f"{r.total_xp:,.0f}",
                inputs_per,
                tools
            )
        
        aggslot = self.query_one("#agg-card-slot", Static)
        aggslot.mount(
            StatCard(
                title=f"Needed [{session.aggregate_xp:,} XP]",
                value=f"{session.aggregate_actions:,} actions"
            )
        )
        # self.query_one("#actions-counter", Label).update(f"{len(session.results)}")
        self.query_one("#actions-counter", Label).update(f"{len(session.results)} Actions selected")

        xp_gap = session.xp_needed
        self._set_status(
            f"XP needed: {xp_gap:,}  |  "
            f"Lvl {session.start_level} → {session.target_level}"
        )

    def _set_status(self, msg: str) -> None:
        self.query_one("#calc-status", Label).update(msg)

    # ----------------------------
    # Export
    # ----------------------------

    def _export_to_resource(self) -> None:
        if not self._last_session:
            return
        # Future: push ResourceScreen(session=self._last_session)
        # For now, acknowledge the hook is in place:
        try:
            from osrs_tui.screens.resource import ResourceScreen
            self.app.push_screen(ResourceScreen(session=self._last_session))
        except ImportError:
            self._set_status("⚠ Resource screen not implemented.")
            return
        
    # ---------------
    # Actions
    # ---------------

    def action_go_back(self) -> None:
        self.app.pop_screen()