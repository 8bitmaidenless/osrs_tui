"""
widgets/charts.py - Lightweight TUI chart widgets built with Textual's Canvas.

No external plotting library needed. These widgets use block-drawing
characters to render sparklines and bar charts that look good even in small
terminal windows.

Widgets
-------
    Sparkline       - single-row wealth-over-time trend line
    BarChart        - vertical bar chart for monthly GE flow (buy vs. sell)
    StatCard        - compact metric card
"""

from __future__ import annotations

import math
from typing import Optional

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Label, Static


_SPARK_CHARS = " ▁▂▃▄▅▆▇█"

_BAR_FULL = "█"
_BAR_EMPTY = " "


# ----------
# Sparkline
# ----------

class Sparkline(Static):
    """
    Renders a single-row text sparkline from a list of numeric values.
    
    Usage:
        spark = Sparkline(values=[100, 200, 150, 400], label="Wealth trend")
        spark.update_values([100, 200, 300])
        
    """
    
    DEFAULT_CSS = """
    Sparkline = {
        height: 3;
        padding: 0 1;
        color: $accent;
    }
    """

    def __init__(self, values: list[float], label: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self._values = values
        self._label = label
        self._render()

    def _render(self) -> None:
        vals = self._values
        if not vals:
            self.update(f"{self.label}\n{'-' * 20}  (no data)")
            return
        
        lo, hi = min(vals), max(vals)
        span = hi - lo or 1

        chars = []
        for v in vals:
            idx = int((v - lo) / span * (len(_SPARK_CHARS) - 1))
            chars.append(_SPARK_CHARS[idx])

        spark_str = "".join(chars)
        pct_change = ""
        if len(vals) >= 2:
            delta = vals[-1] - vals[0]
            pct = delta / abs(vals[0]) * 100 if vals[0] else 0
            arrow = "▲" if delta >= 0 else "▼"
            sign = "+" if delta >= 0 else ""
            pct_change = f"  {arrow} {sign}{pct:.1f}%"

        self.update(
            f"{self._label}\n"
            f"{spark_str}{pct_change}\n"
            f"{'-' * len(spark_str)}"
        )

    def update_values(self, values: list[float]) -> None:
        self._values = values
        self._render()


# ----------------
# Bar chart
# --------------

class BarChart(Widget):
    """
    Renders a two-series (buy / sell) vertical bar chart using block chars.
    
    Each month is a column; height is proportional to the max value across
    all series. Drawn top-to-bottom so it fits in a fixed widget height.
    
    """

    DEFAULT_CSS = """
    BarChart {
        height: auto;
        padding: 0 1;
    }
    """

    def __init__(
        self,
        data: list[dict],
        bar_height: int = 8,
        **kwargs
    ) -> None:
        super().__init__(**kwargs)
        self._data = data
        self._bar_height = bar_height

    def compose(self) -> ComposeResult:
        lines = self._render_lines()
        for line in lines:
            yield Label(line)

    def _render_lines(self) -> list[str]:
        if not self._data:
            return ["No transaction data yet."]
        
        max_val = max(
            max(d.get("spent", 0), d.get("earned", 0)) for d in self._data
        ) or 1

        height = self._bar_height
        cols = 5

        grid: list[list[str]] = [
            [" " * cols for _ in self._data]
            for _ in range(height)
        ]

        for col_idx, d in enumerate(self._data):
            buy_h = int(d.get("spent", 0) / max_val * height)
            sell_h = int(d.get("earned", 0) / max_val * height)

            for row in range(height):
                depth = height - 1 - row
                buy_char = "🟥" if depth < buy_h else "  "
                sell_char = "🟩" if depth < sell_h else "  "
                grid[row][col_idx] = buy_char + sell_char + " "
            
        lines = []
        for row in grid:
            lines.append("".join(row))

        labels = "".join(
            d.get("month", "??")[-2:].center(cols) for d in self._data
        )
        lines.append("-" * (cols * len(self._data)))
        lines.append(labels)
        lines.append("🟥 Spent   🟩 Earned")
        return lines


class StatCard(Static):
    """
    A compact metric card:
      ┌────────────────────┐
      │ Total Wealth       │
      │ 142,000,000 gp     │
      │ ▲+12,500 since last│
      └────────────────────┘
    """

    DEFAULT_CSS = """
    StatCard {
        border: round $panel-darken-2;
        padding: 0 2;
        height: 5;
        width: 1fr;
        margin: 0 1;
        background: $panel;
    }
    .card-title { color: $text-muted; }
    .card-value { text-style: bold; color: $accent; }
    .card-delta-pos { color: ansi_green; }
    .card-delta-neg { color: ansi_red; }
    .card-delta-neu { color: $text-muted; }
    """

    def __init__(
        self,
        title: str,
        value: str,
        delta: Optional[str] = None,
        delta_positive: Optional[bool] = None,
        **kwargs
    ) -> None:
        super().__init__(**kwargs)
        self._title = title
        self._value = value
        self._delta = delta
        self._delta_positive = delta_positive

    def compose(self) -> ComposeResult:
        yield Label(self._title, classes="card-title")
        yield Label(self._value, classes="card-value")
        if self._delta is not None:
            cls = (
                "card-delta-pos" if self._delta_positive
                else "card-delta-neg" if self._delta_positive is False
                else "card-delta-neu"
            )
            yield Label(self._delta, classes=cls)