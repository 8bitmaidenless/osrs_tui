"""
screens/wealth.py - Wealth & Bank Tracker screen.

Two tabs share the same screen:
    [Wealth Snapshot]   Record bank contents + total wealth at a point in time.
    [GE Transactions]   Log Grand Exchange buy/sell records.
    
All data is persisted to SQLite via utils/db.py. The screen is designed so that
future aggregate analytics screen can simply query the same DB tables.

Layout (Snapshot tab)
  ┌────────────────────────────────────────────────────────┐
  │  Username field   Note field   [Save Snapshot]         │
  ├──────────────────┬─────────────────────────────────────┤
  │  Item entry form │  Item list (editable before save)   │
  │  Name / Qty / GP │  Name | Qty | Price | Total         │
  └──────────────────┴─────────────────────────────────────┘
  ┌────────────────────────────────────────────────────────┐
  │  Snapshot history (previous saves)                     │
  │  Date | Note | Total Value                             │
  └────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

from typing import Optional

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, ScrollableContainer, Vertical
from textual.screen import Screen
from textual.widgets import (
    Button,
    DataTable,
    Input,
    Label,
    Select,
    Static,
    TabbedContent,
    TabPane
)

from osrs_tui.utils import db
from osrs_tui.utils.api import PlayerData
from osrs_tui.utils.calc import CalcSession


class WealthScreen(Screen):
    """Wealth Snapshot and GE transaction logger."""

    BINDINGS = [("escape", "go_back", "Back")]

    DEFAULT_CSS = """
    WealthScreen { layout: vertical; }
    
    #wealth-header {
        height: 3;
        background: $panel;
        border-bottom: tall $panel-darken-2;
        layout: horizontal;
        align: left middle;
        padding: 0 2;
    }
    #header-username { width: 24; margin-right: 2; }
    #header-note    { width: 1fr; margin-right: 2; }
    
    #snap-body { height: 1fr; layout: horizontal; }
    
    #item-form {
        width: 32;
        height: auto;
        border-right: tall $panel-darken-1;
        padding: 1 2;
    }
    .form-label { color: $text-muted; margin-top: 1; }
    #item-form Input { width: 100%; }
    #add-item-btn { width: 100%; margin-top: 1; }
    
    #item-list-col { width: 1fr; }
    #item-list-title {
        background: $panel-darken-1;
        padding: 0 1;
        height: 1;
        text-style: bold;
    }
    #pending-table { height: 14; }
    #history-title {
        background: $panel-darken-1;
        padding: 0 1;
        height: 1;
        text-style: bold;
        margin-top: 1;
    }
    #history-table { height: 1fr; }
    
    #ge-body { height: 1fr; layout: horizontal; }
    #ge-form {
        width: 36;
        height: auto;
        border-right: tall $panel-darken-2;
        padding: 1 2;
    }
    #ge-form Input { width: 100%; }
    #ge-form Select { width: 100%; }
    #add-ge-btn { width: 100%;  margin-top: 1; }
    #ge-history-col { width: 1fr; }
    #ge-history-title {
        background: $panel-darken-1;
        padding: 0 1;
        height: 1;
        text-style: bold;
    }
    #ge-table { height: 1fr; }
    
    #wealth-footer {
        height: 3;
        background: $panel;
        border-top: tall $panel-darken-2;
        layout: horizontal;
        align: left middle;
        padding: 0 2;
    }
    #status-label { color: $text-muted; margin-left: 2; }
    """

    def __init__(
        self,
        player: Optional[PlayerData] = None,
        session: Optional[CalcSession] = None,
        **kwargs
    ) -> None:
        super().__init__(**kwargs)
        self._player = player
        self._session = session
        self._pending_items: list[dict] = []

    def compose(self) -> ComposeResult:
        # Shared username / note header
        with Horizontal(id="wealth-header"):
            yield Input(
                self._player.username if self._player else "",
                placeholder="RSN",
                id="header-username"
            )
            yield Input(placeholder="Optional note / label", id="header-note")
        
        with TabbedContent():
            with TabPane("💰 Wealth Snapshot", id="tab-snap"):
                yield from self._compose_snapshot_tab()
            with TabPane("📈 GE Transactions", id="tab-ge"):
                yield from self._compose_ge_tab()

        with Horizontal(id="wealth-footer"):
            yield Button("← Back", id="back-btn")
            yield Label("", id="status-label")

    def _compose_snapshot_tab(self) -> ComposeResult:
        with Horizontal(id="snap-body"):
            # Left: item entry form
            with Vertical(id="item-form"):
                yield Label("Item Name", classes="form-label")
                yield Input(placeholder="e.g. Dragon bones", id="item-name")
                yield Label("Quantity", classes="form-label")
                yield Input("1", placeholder="Qty", id="item-qty")
                yield Label("Price Each [gp]", classes="form-label")
                yield Input("0", placeholder="gp each", id="item-price")
                yield Button("+ Add Item", variant="success", id="add-item-btn")
                yield Button("💾 Save Snapshot", variant="primary", id="save-snap-btn")

            # Right: pending items + history
            with Vertical(id="item-list-col"):
                yield Static("Pending Items (unsaved)", id="item-list-title")
                yield DataTable(id="pending-table", zebra_stripes=True)
                yield Static("Snapshot History", id="history-title")
                yield DataTable(id="history-table", zebra_stripes=True)

    def _compose_ge_tab(self) -> ComposeResult:
        with Horizontal(id="ge-body"):
            # Left: GE entry form
            with Vertical(id="ge-form"):
                yield Label("Item Name", classes="form-label")
                yield Input(placeholder="e.g. Abyssal whip", id="ge-item-name")
                yield Label("Type", classes="form-label")
                yield Select(
                    [("Buy", "buy"), ("Sell", "sell")],
                    value="buy",
                    id="ge-type"
                )
                yield Label("Quantity", classes="form-label")
                yield Input("1", placeholder="Qty", id="ge-qty")
                yield Label("Price Each [gp]", classes="form-label")
                yield Input("0", placeholder="gp each", id="ge-price")
                yield Label("Note (optional)", classes="form-label")
                yield Input(placeholder="e.g. 'flip run'", id="ge-note-field")
                yield Button("+ Log Transaction", variant="primary", id="add-ge-btn")

            # Right: GE history
            with Vertical(id="ge-history-col"):
                yield Static("GE Transaction History", id="ge-history-title")
                yield DataTable(id="ge-table", zebra_stripes=True)

    def on_mount(self) -> None:
        # Snapshot Tables
        pt: DataTable = self.query_one("#pending-table", DataTable)
        pt.add_columns("Item", "Qty", "Price Each", "Total Value")

        ht: DataTable = self.query_one("#history-table", DataTable)
        ht.add_columns("Date", "Note", "Total Value", "ID")

        # GE Table
        gt: DataTable = self.query_one("#ge-table", DataTable)
        gt.add_columns("Date", "Item", "Type", "Qty", "Price Each", "Total", "Note")

        self._refresh_history()
        self._refresh_ge_history()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "add-item-btn":
            self._add_pending_item()
        elif bid == "save-snap-btn":
            self._save_snapshot()
        elif bid == "add-ge-btn":
            self._add_ge_transaction()
        elif bid == "back-btn":
            self.action_go_back()

    def _add_pending_item(self) -> None:
        name = self.query_one("#item-name", Input).value.strip()
        if not name:
            self._status("⚠ Item name is required.")
            return
        try:
            qty = int(self.query_one("#item-qty", Input).value or 1)
            price = int(self.query_one("#item-price", Input).value or 0)
        except ValueError:
            self._status("⚠ Qty and price must be whole numbers.")
            return
        
        item = {"name": name, "qty": qty, "price": price}
        self._pending_items.append(item)

        table: DataTable = self.query_one("#pending-table", DataTable)
        table.add_row(name, f"{qty:,}", f"{price:,}", f"{qty * price:,}")
        
        # Clear form
        self.query_one("#item-name", Input).value = ""
        self.query_one("#item-qty", Input).value = "1"
        self.query_one("#item-price", Input).value = "0"
        self._status(f"Added '{name}'. {len(self._pending_items)} pending items.")
    
    def _save_snapshot(self) -> None:
        username = self.query_one("#header-username", Input).value.strip()
        if not username:
            self._status("⚠ RSN is required.")
            return
        if not self._pending_items:
            self._status("⚠ Add at least one item before saving.")
            return
        
        note = self.query_one("#header-note", Input).value.strip()
        snapshot_id = db.save_snapshot(username, self._pending_items, note)
        
        total = sum(i["qty"] * i["price"] for i in self._pending_items)
        self._pending_items.clear()
        self.query_one("#pending-table", DataTable).clear()
        self._refresh_history()
        self._status(
            f"✅ Snapshot #{snapshot_id} saved - total value: {total:,} gp."
        )

    def _refresh_history(self) -> None:
        username = self.query_one("#header-username", Input).value.strip()
        table: DataTable = self.query_one("#history-table", DataTable)
        table.clear()
        if not username:
            return
        for row in db.get_snapshots(username):
            date = row["recorded_at"][:16].replace("T", " ")
            table.add_row(
                date,
                row["note"] or "-",
                f"{row['total_value']:,}",
                str(row["id"])
            )

    # ---
    # GE Logic
    # ---

    def _add_ge_transaction(self) -> None:
        username = self.query_one("#header-username", Input).value.strip()
        if not username:
            self._status("⚠ RSN is required.")
            return
        
        item = self.query_one("#ge-item-name", Input).value.strip()
        if not item:
            self._status("⚠ Item name is required.")
            return
        
        try:
            qty = int(self.query_one("#ge-qty", Input).value or 1)
            price = int(self.query_one("#ge-price", Input).value or 0)
        except ValueError:
            self._status("⚠ Qty and price must be whole numbers.")
            return
        
        tx_type = str(self.query_one("#ge-type", Select).value)
        note = self.query_one("#ge-note-field", Input).value.strip()

        tx_id = db.save_ge_transaction(username, item, tx_type, qty, price, note)
        self._refresh_ge_history()

        total = qty * price
        self._status(
            f"✅ GE #{tx_id} logged - {tx_type.upper()} {qty:,}x {item} @ {price:,} gp "
            f"(total: {total:,} gp)."
        )

        self.query_one("#ge-item-name", Input).value = ""
        self.query_one("#ge-qty", Input).value = "1"
        self.query_one("#ge-price", Input).value = "0"
        self.query_one("#ge-note-field", Input).value = ""

    def _refresh_ge_history(self) -> None:
        username = self.query_one("#header-username", Input).value.strip()
        table: DataTable = self.query_one("#ge-table", DataTable)
        table.clear()
        if not username:
            return
        for row in db.get_ge_transactions(username):
            date = row["recorded_at"][:16].replace("T", " ")
            table.add_row(
                date,
                row["item_name"],
                row["transaction_type"].upper(),
                f"{row['quantity']:,}",
                f"{row['price_each']:,}",
                f"{row['total_value']:,}",
                row["note"] or "-"
            )

    def _status(self, msg: str) -> None:
        self.query_one("#status-label", Label).update(msg)

    def action_go_back(self) -> None:
        self.app.pop_screen()