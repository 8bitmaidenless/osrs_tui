"""
screens/resource.py - Grand Exchange Resource & Price Analysis screen.

Entry points
------------
    1. From the Skill Calculator's export button:
        ResourceScreen(session=calc_session)
    The session's InputMaterials
    
    
"""

from __future__ import annotations

import asyncio
import math
from typing import Optional

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, ScrollableContainer, Vertical
from textual.screen import Screen
from textual.widgets import (
    Button,
    DataTable,
    Input,
    Label,
    LoadingIndicator,
    Static,
    TabbedContent,
    TabPane
)

from osrs_tui.utils import db
from osrs_tui.utils.ge_api import (
    GEAPIError,
    GEItem,
    GEPrice,
    fetch_prices_bulk,
    search_items,
)

try:
    from osrs_tui.utils.calc import CalcSession
except ImportError:
    CalcSession = None


# Helpers

def _gp(n: Optional[int], fallback: str = "-") -> str:
    if n is None:
        return fallback
    if abs(n) >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    if abs(n) >= 1_000:
        return f"{n / 1_000:.1f}K"
    return f"{n:,}"


def _signed_gp(n: int) -> str:
    sign = "▲ +" if n > 0 else ("▼ " if n < 0 else "↔ ")
    return f"{sign}{_gp(abs(n))}"


# screen

class ResourceScreen(Screen):
    
    BINDINGS = [
        ("escape", "go_back", "Back"),
        ("ctrl+r", "refresh_prices", "Refresh prices"),
        ("ctrl+s", "save_lists", "Save lists"),
    ]

    DEFAULT_CSS = """
    ResourceScreen { layout: vertical; }
    
    #res-toolbar {
        height: 3;
        background: $panel;
        border-bottom: tall $panel-darken-2;
        layout: horizontal;
        align: left middle;
        padding: 0 2;
    }
    #res-title { color: $accent; text-style: bold; width: 22; }
    #res-search { width: 1fr; margin-right: 1; }
    #res-search-btn { margin-right: 1; }
    
    TabbedContent { height: 1fr; }
    
    #lookup-body { height: 1fr; layout: vertical; }
    #search-status { color: $text-muted; height: 1; padding: 0 1; }
    #search-loading { align: center middle; height: 5; display: none; }
    #results-table { height: 1fr; }
    #lookup-actions {
        height: 3;
        layout: horizontal;
        align: left middle;
        padding: 0 1;
        background: $panel;
        border-top: tall $panel-darken-2;
    }
    #lookup-actions Button { margin-right: 1; }
    
    #saved-body { height: 1fr; layout: vertical; }
    #saved-table { height: 1fr; }
    #saved-actions {
        height: 3;
        layout: horizontal;
        align: left middle;
        padding: 0 1;
        background: $panel;
        border-top: tall $panel-darken-2;
    }
    #saved-actions Button { margin-right: 1; }
    
    #lists-body { height: 1fr; layout: vertical; }
    #lists-upper {
        height: 1fr; 
        layout: horizontal;
    }
    
    .list-panel {
        width: 1fr;
        layout: vertical;
        border: round $panel-darken-2;
        margin: 1;
    }
    .list-panel-title {
        height: 1;
        background: $panel-darken-1;
        padding: 0 1;
        text-style: bold;
    }
    .expense-title { color: $error; }
    .sale-title { color: ansi_green; }
    .list-table { height: 1fr; }
    .list-actions {
        height: 3;
        layout: horizontal;
        align: left middle;
        padding: 0 1;
        background: $panel;
        border-top: tall $panel-darken-2;
    }
    .list-actions Button { margin-right: 1; }
    
    #summary-bar {
        height: 4;
        background: $panel;
        border-top: tall $panel-darken-2;
        layout: horizontal;
        align: left middle;
        padding: 0 2;
    }
    .summary-card {
        width: 1fr;
        height: 3;
        border: round $panel-darken-2;
        padding: 0 1;
        margin-right: 1;
    }
    .summary-label { color: $text-muted; }
    .summary-value { text-style: bold; color: $accent; }
    .profit { color: ansi_green; text-style: bold; }
    .loss { color: $error; text-style: bold; }
    .neutral { color: $text-muted; text-style: bold; }
    
    #res-footer {
        height: 3;
        background: $panel;
        border-top: tall $panel-darken-2;
        layout: horizontal;
        align: left middle;
        padding: 0 2;
    }
    #res-status { color: $text-muted; margin-left: 2; }
    """

    def __init__(
        self,
        session: Optional["CalcSession"] = None,
        **kwargs
    ) -> None:
        super().__init__(**kwargs)
        self._session = session

        self._expense_items: list[dict] = []
        self._sale_items: list[dict] = []

        self._search_results: list[GEItem] = []

        self._price_cache: dict[int, GEPrice] = {}

    def compose(self) -> ComposeResult:
        with Horizontal(id="res-toolbar"):
            yield Label("🏦 GE Resource Screen", id="res-title")
            yield Input(placeholder="Search item name...", id="res-search")
            yield Button("Search", variant="primary", id="res-search-btn")

        with TabbedContent(id="res-tabs"):
            with TabPane("🔍 Item Lookup", id="tab-lookup"):
                yield from self._compose_lookup_tab()
            with TabPane("★ Saved Items", id="tab-saved"):
                yield from self._compose_saved_tab()
            with TabPane("📋 Price Lists", id="tab-lists"):
                yield from self._compose_lists_tab()

        with Horizontal(id="res-footer"):
            yield Button("← Back", id="back-btn")
            yield Label(
                "[b]Ctrl+R[/b] Refresh prices   [b]Ctrl+S[/b] Save lists",
                markup=True
            )
            yield Label("", id="res-status")

    def _compose_lookup_tab(self) -> ComposeResult:
        with Vertical(id="lookup-body"):
            with Container(id="search-loading"):
                yield LoadingIndicator()
            yield Label("Enter a search term above.", id="search-status")
            yield DataTable(id="results-table", zebra_stripes=True, cursor_type="row")
            with Horizontal(id="lookup-actions"):
                yield Button("★ Tag Item", id="btn-tag", disabled=True)
                yield Button("+ Expense", id="btn-add-expense", disabled=True, variant="error")
                yield Button("+ Sale", id="btn-add-sale", disabled=True, variant="success")
                yield Button("💰 Fetch Price", id="btn-fetch-price", disabled=True)

    def _compose_saved_tab(self) -> ComposeResult:
        with Vertical(id="saved-body"):
            yield DataTable(id="saved-table", zebra_stripes=True, cursor_type="row")
            with Horizontal(id="saved-actions"):
                yield Button("+ Expense", id="btn-saved-expense", disabled=True, variant="error")
                yield Button("+ Sale", id="btn-saved-sale", disabled=True, variant="success")
                yield Button("✕ Untag", id="btn-untag", disabled=True)

    def _compose_lists_tab(self) -> ComposeResult:
        with Vertical(id="lists-body"):
            with Horizontal(id="lists-upper"):
                with Vertical(classes="list-panel"):
                    yield Static("💸 Expense List", classes="list-panel-title expense-title")
                    yield DataTable(
                        id="expense-table",
                        zebra_stripes=True,
                        cursor_type="row",
                        classes="list-table"
                    )
                    with Horizontal(classes="list-actions"):
                        yield Button("✕ Remove", id="btn-rm-expense", disabled=True)
                        yield Button("↺ Refresh", id="btn-refresh-expense")
                
                with Vertical(classes="list-panel"):
                    yield Static("💰 Sale List", classes="list-panel-title sale-title")
                    yield DataTable(
                        id="sale-table",
                        zebra_stripes=True,
                        cursor_type="row",
                        classes="list-table"
                    )
                    with Horizontal(classes="list-actions"):
                        yield Button("x Remove", id="btn-rm-sale", disabled=True)
                        yield Button("↺ Refresh", id="btn-refresh-sale")

            with Horizontal(id="summary-bar"):
                with Vertical(classes="summary-card"):
                    yield Label("Total Expense", classes="summary-label")
                    yield Label("-", id="lbl-total-expense", classes="summary-value")
                with Vertical(classes="summary-card"):
                    yield Label("Total Income", classes="summary-label")
                    yield Label("-", id="lbl-total-sale", classes="summary-value")
                with Vertical(classes="summary-card"):
                    yield Label("Net P/L  (per action cycle)", classes="summary-label")
                    yield Label("-", id="lbl-net-pl", classes="summary-value")
                with Vertical(classes="summary-card"):
                    yield Label("XP / gp spent", classes="summary-label")
                    yield Label("-", id="lbl-xp-per-gp", classes="summary-value")

    def on_mount(self) -> None:
        self._setup_tables()
        self._load_saved_tab()

        if self._session is not None:
            self._import_from_session(self._session)
            self.query_one("#res-tabs", TabbedContent).active = "tab-lists"
            self._status(
                f"Loaded from Skill Calculator: {self._session.skill.lower().title()}  "
                f"Lvl {self._session.start_level} → {self._session.target_level}  "
                f"({self._session.actions_needed:,} action cycles)"
            )
    
    def _setup_tables(self) -> None:
        rt = self.query_one("#results-table", DataTable)
        rt.add_columns("Item Name", "Members", "GE Limit", "High Alch", "Low Alch")

        st = self.query_one("#saved-table", DataTable)
        