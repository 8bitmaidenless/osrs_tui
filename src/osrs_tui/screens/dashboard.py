"""
screens/dashboard.py - Financial Dashboard screen.

Aggregates all stored wealth snapshots and GE transaction data for a player
into a single overview with:

  ┌─ Stat cards ──────────────────────────────────────────────────────┐
  │  Current Wealth │ Change vs Last │ Total GE Earned │ Net GE Profit│
  └───────────────────────────────────────────────────────────────────┘
  ┌─ Wealth trend (sparkline) ──────┐  ┌─ Top GE items ──────────────┐
  │  ▁▂▃▄▆▇█  ▲ +12.4%             │  │  Item       Net Profit/Loss  │
  └─────────────────────────────────┘  └─────────────────────────────┘
  ┌─ Monthly GE flow (bar chart) ───────────────────────────────────  ┐
  │  🟥buy / 🟩sell per month                                         │
  └───────────────────────────────────────────────────────────────────┘

The screen loads data in a worker thread so the UI never stalls.
Pressing R refreshes all data from the DB.
"""

from __future__ import annotations

from typing import Optional

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, ScrollableContainer, Vertical
from textual.screen import Screen
from textual.widgets import (
    DataTable,
    Input,
    Button,
    Label,
    LoadingIndicator,
    Static
)

from osrs_tui.utils import db
from osrs_tui.widgets.charts import BarChart, Sparkline, StatCard


def _fmt_gp(n: int) -> str:
    """Format a coin value: show M/K suffix for readability."""
    if abs(n) >= 1_000_000:
        return f"{n / 1_000_000:.2f}M gp"
    if abs(n) >= 1_000:
        return f"{n / 1_000:.1f}K gp"
    return f"{n:,} gp"


def _delta_str(delta: int) -> tuple[str, Optional[bool]]:
    """Return (formatted_string, is_positive) for a StatCard delta."""
    if delta == 0:
        return "↔ No change", None
    sign = "▲ +" if delta > 0 else "▼ "
    return f"{sign}{_fmt_gp(delta)} vs. last snapshot", delta > 0


class DashboardScreen(Screen):
    """Aggregate financial dashboard for one plyer."""

    BINDINGS = [
        ("escape", "go_back", "Back"),
        ("r", "refresh", "Refresh"),
    ]

    DEFAULT_CSS = """
    DashboardScreen { layout: vertical; }
    
    #dash-toolbar {
        height: 3;
        background: $panel;
        border-bottom: tall $panel-darken-2;
        layout: horizontal;
        align: left middle;
        padding: 0 2;
    }
    #dash-username { width: 26; margin-right: 2; }
    #dash-load-btn { margin-right: 2; }
    #dash-title-label { color: $accent; text-style: bold; margin-right: 2; }
    
    #dash-loading { align: center middle; height: 1fr; }
    #dash-empty { align: center middle; height: 1fr; color: $text-muted; }
    
    #dash-content { height: 1fr; layout: vertical; display: none; }
    
    #stat-row {
        height: 7;
        layout: horizontal;
        margin-bottom: 1;
    }
    
    #mid-row {
        height: 10;
        layout: horizontal;
        margin-bottom: 1;
    }
    #sparkline-box {
        width: 2fr; 
        border: round $panel-darken-2;
        padding: 0 1;
        background: $panel;
        margin-right: 1;
    }
    #sparkline-title {
        text-style: bold;
        color: $text-muted;
        height: 1;
    }
    #top-items-box {
        width: 1fr;
        border: round $panel-darken-2;
        background: $panel;
    }
    #top-items-title {
        background: $panel-darken-1;
        padding: 0 1;
        text-style: bold;
        height: 1;
    }
    #top-items-table { height: 1fr; }
    
    #barchart-box {
        height: auto;
        border: round $panel-darken-2;
        padding: 0 1;
        background: $panel;
        margin-bottom: 1;
    }
    #barchart-title {
        text-style: bold;
        color: $text-muted;
        height: 1;
    }
    
    #dash-footer {
        height: 3;
        background: $panel;
        border-top: tall $panel-darken-2;
        layout: horizontal;
        align: left middle;
        padding: 0 2;
    }
    #dash-status { color: $text-muted; margin-left: 2; }
    """

    def __init__(self, username: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self._username = username

    def compose(self) -> ComposeResult:
        with Horizontal(id="dash-toolbar"):
            yield Label("📊 Financial Dashboard", id="dash-title-label")
            yield Input(
                self._username,
                placeholder="RSN",
                id="dash-username"
            )
            yield Button("Load", variant="primary", id="dash-load-btn")
        
        with Container(id="dash-loading"):
            yield LoadingIndicator()
            yield Label("Loading financial data...")

        with Container(id="dash-empty"):
            yield Label(
                "Enter an RSN above and press Load.\n"
                "Data comes from your saved wealth snapshots and GE transactions."
            )
        
        with ScrollableContainer(id="dash-content"):
            with Horizontal(id="stat-row"):
                pass

            with Horizontal(id="mid-row"):
                with Vertical(id="sparkline-box"):
                    yield Static("Wealth Over Time", id="sparkline-title")

                with Vertical(id="top-items-box"):
                    yield Static("Top GE Items by Net P/L", id="top-items-title")
                    yield DataTable(
                        id="top-items-table",
                        zebra_stripes=True,
                        show_cursor=False
                    )
            
            with Vertical(id="barchart-box"):
                yield Static("Monthly GE Flow (last 12 months)", id="barchart-title")

        with Horizontal(id="dash-footer"):
            yield Button("← Back", id="back-btn")
            yield Label("", id="dash-status")

    def on_mount(self) -> None:
        self.query_one("#dash-loading").display = False
        self.query_one("#dash-content").display = False

        tbl: DataTable = self.query_one("#top-items-table", DataTable)
        tbl.add_columns("Item", "Net P/L")

        if self._username:
            self._load_data(self._username)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "dash-load-btn":
            username = self.query_one("#dash-username", Input).value.strip()
            if username:
                self._load_data(username)
        elif event.button.id == "back-btn":
            self.action_go_back()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "dash-username":
            username = event.value.strip()
            if username:
                self._load_data(username)

    def _load_data(self, username: str) -> None:
        self._username = username
        self.query_one("#dash-loading").display = True
        self.query_one("#dash-empty").display = False
        self.query_one("#dash-content").display = False
        self._status("")
        self.run_worker(self._fetch_and_render(username), exclusive=True)

    async def _fetch_and_render(self, username: str) -> None:
        import asyncio

        wealth_history, ge_summary, wealth_delta, monthly_flow = \
            await asyncio.get_event_loop().run_in_executor(
                None, 
                self._blocking_fetch,
                username
            )
        self.query_one("#dash-loading").display = False

        if wealth_delta["snapshot_count"] == 0 and ge_summary["tx_count"] == 0:
            self.query_one("#dash-empty").display = True
            self._status(f"No data found for '{username}'.")
            return
        
        self._populate(username, wealth_history, ge_summary, wealth_delta, monthly_flow)
        self.query_one("#dash-content").display = True
        self._status(
            f"Loaded {wealth_delta['snapshot_count']} snapshots, "
            f"{ge_summary['tx_count']} GE transactions."
        )
    
    @staticmethod
    def _blocking_fetch(username: str) -> tuple:
        return (
            db.get_wealth_history(username),
            db.get_ge_summary(username),
            db.get_wealth_delta(username),
            db.get_ge_monthly_flow(username)
        )
    
    def _populate(
        self,
        username: str,
        wealth_history,
        ge_summary: dict,
        wealth_delta: dict,
        monthly_flow: list[dict]
    ) -> None:
        self._populate_stat_cards(wealth_delta, ge_summary)
        self._populate_sparkline(wealth_history)
        self._populate_top_items(ge_summary["top_items"])
        self._populate_barchart(monthly_flow)

    def _populate_stat_cards(self, wd: dict, ge: dict) -> None:
        row = self.query_one("#stat-row", Horizontal)
        row.remove_children()

        delta_str, delta_pos = _delta_str(wd["delta"])

        cards = [
            StatCard(
                title="Current Wealth",
                value=_fmt_gp(wd["latest"]),
                delta=f"{wd['snapshot_count']} snapshots recorded",
                delta_positive=None
            ),
            StatCard(
                title="Wealth Change",
                value=_fmt_gp(wd["delta"]) if wd["delta"] != 0 else "-",
                delta=delta_str,
                delta_positive=delta_pos
            ),
            StatCard(
                title="Total GE Earned",
                value=_fmt_gp(ge["total_earned"]),
                delta=f"{ge['tx_count']} transactions logged",
                delta_positive=None
            ),
            StatCard(
                title="Net GE Profit",
                value=_fmt_gp(ge["net_profit"]),
                delta=(
                    "▲ Profitable" if ge["net_profit"] > 0
                    else "▼ Net loss" if ge["net_profit"] < 0
                    else "↔ Break even"
                ),
                delta_positive=(
                    True if ge["net_profit"] > 0 else
                    False if ge["net_profit"] < 0 else None
                ),
            ),
        ]

        for card in cards:
            row.mount(card)

    def _populate_sparkline(self, wealth_history) -> None:
        box = self.query_one("#sparkline-box", Vertical)

        for old in box.query(Sparkline):
            old.remove()

        values = [float(r["total_value"]) for r in wealth_history]
        spark = Sparkline(values=values, label="")
        box.mount(spark)

    def _populate_top_items(self, top_items: list[dict]) -> None:
        tbl: DataTable = self.query_one("#top-items-table", DataTable)
        tbl.clear()
        if not top_items:
            tbl.add_row("-", "-")
            return
        for item in top_items:
            net = item["net"]
            sign = "▲ +" if net > 0 else ("▼ " if net < 0 else "")
            tbl.add_row(item["item_name"], f"{sign}{_fmt_gp(net)}")

    def _populate_barchart(self, monthly_flow: list[dict]) -> None:
        box = self.query_one("#barchart-box", Vertical)
        for old in box.query(BarChart):
            old.remove()
        
        data = [
            {
                "month": row["month"],
                "spent": row["spent"],
                "earned": row["earned"],
            }
            for row in monthly_flow
        ]
        chart = BarChart(data=data, bar_height=6)
        box.mount(chart)

    def action_go_back(self) -> None:
        self.app.pop_screen()
    
    def action_refresh(self) -> None:
        username = self.query_one("#dash-username", Input).value.strip()
        if username:
            self._load_data(username)

    def _status(self, msg: str) -> None:
        self.query_one("#dash-status", Label).update(msg)