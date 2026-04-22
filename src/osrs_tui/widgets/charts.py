from __future__ import annotations

import math
from typing import Optional

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Label, Static


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
            yield Label(self._data, classes=cls)