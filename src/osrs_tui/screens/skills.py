from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, ScrollableContainer, Vertical
from textual.screen import Screen
from textual.widgets import Label, LoadingIndicator, Static

from osrs_tui.utils.api import APIError, PlayerData, fetch_player
from osrs_tui.widgets.stats import PlayerHeader, SkillBars, SkillsTable


class SkillsScreen(Screen):
    """Displays full hiscore stats for one player."""

    # DEFAULT_CSS = """
    # SkillsScreen {
    #     layout: vertical;
    # }
    # #loading-container {
    #     align: center middle;
    #     height: 1fr;
    # }
    # #error-container {
    #     align: center middle;
    #     height: 1fr;
    # }
    # #error-msg {
    #     color: $error;
    #     text-align: center;
    # }
    # #stats-body {
    #     height: 1fr;
    #     display: none;
    # }
    # #skills-col {
    #     width: 2fr;
    # }
    # #bars-col {
    #     width: 1fr;
    #     border-left: tall $panel-darken-2;
    #     overflow-y: auto;
    # }
    # #footer-bar {
    #     height: 1;
    #     background: $panel-darken-1;
    #     padding: 0 2;
    #     color: $text-muted;
    # }
    # """
    DEFAULT_CSS = """
    StatsScreen {
        layout: vertical;
    }
    #loading-container {
        align: center middle;
        height: 1fr;
    }
    #error-container {
        align: center middle;
        height: 1fr;
    }
    #error-msg {
        color: $error;
        text-align: center;
    }
    #stats-body {
        height: 1fr;
        display: none;
    }
    #skills-col {
        width: 2fr;
    }
    #bars-col {
        width: 1fr;
        border-left: tall $panel-darken-2;
        overflow-y: auto;
    }
    #footer-bar {
        height: 1;
        background: $panel-darken-1;
        padding: 0 2;
        color: $text-muted;
    }
    """

    BINDINGS = [
        ("escape", "go_back", "Back"),
        ("q", "go_back", "Back"),
        ("r", "reload", "Reload"),
        ("c", "open_calculator", "Calculator"),
        ("w", "open_wealth", "Wealth"),
        ("d", "open_dashboard", "Dashboard"),
    ]

    def __init__(self, username: str, account_type: str = "normal", **kwargs) -> None:
        super().__init__(**kwargs)
        self._username = username
        self._account_type = account_type
        self._player: PlayerData | None = None

    # Layout

    def compose(self) -> ComposeResult:
        # Loading state
        with Container(id="loading-container"):
            yield LoadingIndicator()
            yield Label(f"Fetching data for '{self._username}'...")

        # Error state (hidden until needed)
        with Container(id="error-container"):
            yield Label("", id="error-msg")
            yield Label("Press [b]Esc[/b] to go back.", markup=True)

        # Main stats body (hidden until data loads)
        with Horizontal(id="stats-body"):
            with Vertical(id="skills-col"):
                yield Static(id="player-header-slot")
                yield Static(id="skills-table-slot")
            with ScrollableContainer(id="bars-col"):
                yield Static(id="bars-slot")

        # Footer hint bar
        yield Static(
            "[b]Esc[/b] Back"
            "  "
            "[b]R[/b] Reload"
            "  "
            "[b]C[/b] Calculator"
            "   "
            "[b]W[/b] Wealth",
            markup=True,
            id="footer-bar"
        )
    
    def on_mount(self) -> None:
        self.query_one("#error-container").display = False
        self.query_one("#stats-body").display = False
        # Async load
        self.run_worker(self._load_player(), exclusive=True)

    # ------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------

    async def _load_player(self) -> None:
        try:
            player = await fetch_player(self._username)
        except APIError as err:
            self._show_error(str(err))
            return
        except Exception as err:
            self._show_error(f"Unexpected error: {err}")
            return
        
        self._player = player
        self._populate(player)

    def _show_error(self, message: str) -> None:
        self.query_one("#loading-container").display = False
        self.query_one("#error-container").display = True
        self.query_one("#error-msg", Label).update(f"⚠ {message}")

    def _populate(self, player: PlayerData) -> None:
        """Mount child widgets into the placeholder slots."""
        # Swap loading -> body
        self.query_one("#loading-container").display = False
        self.query_one("#stats-body").display = True

        # Header
        header_slot = self.query_one("#player-header-slot", Static)
        header_slot.remove_children()
        header = PlayerHeader(player)
        header_slot.mount(header)

        # Skills table
        table_slot = self.query_one("#skills-table-slot", Static)
        table_slot.remove_children()
        table_slot.mount(SkillsTable(player))

        # XP bars
        bars_slot = self.query_one("#bars-slot", Static)
        bars_slot.remove_children()
        bars_slot.mount(SkillBars(player))

    # --------------------------------------------------
    # Actions
    # --------------------------------------------------

    def action_go_back(self) -> None:
        self.app.pop_screen()
    
    def action_reload(self) -> None:
        """Re-fetch the same player."""
        self.query_one("#loading-container").display = True
        self.query_one("#error-container").display = False
        self.query_one("#stats-body").display = False
        self.run_worker(self._load_player(), exclusive=True)

    def action_open_calculator(self) -> None:
        try:
            from osrs_tui.screens.calculator import CalculatorScreen
            self.app.push_screen(CalculatorScreen(player=self._player))
        except ImportError:
            self._show_error("CalculatorScreen not implemented.")
            return
    
    def action_open_wealth(self) -> None:
        try:
            from osrs_tui.screens.wealth import WealthScreen
            self.app.push_screen(WealthScreen(player=self._player))
        except ImportError:
            self._show_error("WealthScreen not implemented.")
            return
        
    def action_open_dashboard(self) -> None:
        try:
            from osrs_tui.screens.dashboard import DashboardScreen
            self.app.push_screen(DashboardScreen(username=self._username))
        except ImportError:
            self._show_error("DashboardScreen not implemented.")
            return
        
