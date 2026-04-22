# from __future__ import annotations

# from textual.screen import Screen


# class HomeScreen(Screen):
#     pass
from __future__ import annotations

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Button, Input, Label, Rule, Select, Static


ACCOUNT_TYPES = [
    ("Normal", "normal"),
    ("Ironman", "ironman"),
    ("Hardcore Ironman", "hardocre"),
    ("Ultimate Ironman", "ultimate"),
]


class HomeScreen(Screen):

    DEFAULT_CSS = """
    HomeScreen {
        align: center middle;
    }
    #home-box {
        width: 64;
        height: auto;
        border: double $accent;
        padding: 2 4;
        background: $panel;
    }
    #home-title {
        text-align: center;
        text-style: bold;
        color: $accent;
        margin-bottom: 0;
    }
    #home-subtitle {
        text-align: center;
        color: $text-muted;
        margin-bottom: 1;
    }
    #username-input { margin-bottom: 1; }
    #account-select { margin-bottom: 1; }
    #lookup-btn { width: 100%; margin-bottom: 1; }
    .nav-section-label {
        color: $text-muted;
        text-align: center;
        margin-top: 1;
        margin-bottom: 1;
    }
    .nav-btn { width: 100%; margin-bottom: 1; }
    #error-label {
        color: $error;
        text-align: center;
        margin-top: 1;
        display: none;
    }
    """

    def compose(self) -> ComposeResult:
        with Static(id="home-box"):
            yield Label("⚔  OSRS TUI  ⚔", id="home-title")
            yield Label("Old School Runescape - Terminal Interface", id="home-subtitle")
            yield Rule()

            yield Input(placeholder="Enter RSN (e.g. Zezima)", id="username-input")
            yield Select(
                [(label, value) for label, value in ACCOUNT_TYPES],
                value="normal",
                id="account-select"
            )
            yield Button("🔍  Look Up Player Stats", variant="primary", id="lookup-btn")

            yield Rule()
            yield Label("--- Tools ---", classes="nav-section-label")

            yield Button("🧮  Skill Calculator", classes="nav-btn", id="nav-calc")
            yield Button("💰  Wealth & Bank Tracker", classes="nav-btn", id="nav-wealth")
            yield Button("📊  Financial Dashboard", classes="nav-btn", id="nav-dashboard")

            yield Label("", id="error-label")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        err = self.query_one("#error-label", Label)
        err.display = False
        if bid == "lookup-btn":
            self._do_lookup()
        elif bid == "nav-calc":
            try:
                from osrs_tui.screens.calculator import CalculatorScreen
                self.app.push_screen(CalculatorScreen())
            except ImportError:
                err.update("⚠ Calc. screen not yet implemented.")
                err.display = True
                return
        elif bid == "nav-wealth":
            try:
                from osrs_tui.screens.wealth import WealthScreen
                self.app.push_screen(WealthScreen())
            except ImportError:
                err.update("⚠ Wealth screen not yet implemented.")
                err.display = True
                return
        elif bid == "nav-dashboard":
            try:
                from osrs_tui.screens.dashboard import DashboardScreen
                self.app.push_screen(DashboardScreen())
            except ImportError:
                err.update("⚠ Dash. screen not yet implemented.")
                err.display = True
                return
            
    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._do_lookup()

    def _do_lookup(self) -> None:
        username = self.query_one("#username-input", Input).value.strip()
        account_type = str(self.query_one("#account-select", Select).value)
        err = self.query_one("#error-label", Label)

        if not username:
            err.update("⚠ Please enter a username.")
            err.display = True
            return
        
        err.display = False
        try:
            from osrs_tui.screens.skills import SkillsScreen
            self.app.push_screen(SkillsScreen(username=username, account_type=account_type))
        except ImportError:
            err.update("⚠ Skills screen not yet implemented.")
            err.display = True
            return
        