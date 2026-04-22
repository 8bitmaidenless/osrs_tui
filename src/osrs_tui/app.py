from __future__ import annotations

from textual.app import App, ComposeResult
from textual.widgets import Footer, Header

from osrs_tui.screens.home import HomeScreen


class OSRSApp(App):
    TITLE = "OSRS TUI"
    SUB_TITLE = "Old School Runescape - Terminal Interface"

    CSS = """
    $accent: #e8c253;
    $accent-darken-1: #b8972f;
    
    Screen {
        background: $surface;
    }
    Header {
        background: #1a1209;
        color: $accent;
    }
    Footer {
        background: #1a1209;
    }
    """

    BINDINGS = [
        ("ctrl+q", "quit", "Quit"),
    ]

    def on_mount(self) -> None:
        self.push_screen(HomeScreen())

    
def main() -> None:
    OSRSApp().run()


if __name__ == "__main__":
    main()