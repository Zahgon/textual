from __future__ import annotations

import inspect

from rich.syntax import Syntax

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import ScrollableContainer
from textual.screen import ModalScreen, Screen
from textual.widgets import Static


class CodeScreen(ModalScreen):
    DEFAULT_CSS = """
    CodeScreen {
        #code {
            border: heavy $accent;
            margin: 2 4;
            scrollbar-gutter: stable;
            Static {
                width: auto;
            }
        }
    }
    """
    BINDINGS = [("escape", "dismiss", "Dismiss code")]

    def __init__(self, title: str, code: str) -> None:
        super().__init__()
        self.code = code
        self.title = title

    def compose(self) -> ComposeResult:
        with ScrollableContainer(id="code"):
            yield Static(
                Syntax(
                    self.code, lexer="python", indent_guides=True, line_numbers=True
                ),
                expand=True,
            )



class PageScreen(Screen):
    DEFAULT_CSS = """
    PageScreen {
        width: 100%;
        height: 1fr;
        overflow-y: auto;        
    }
    """
    BINDINGS = [
        Binding(
            "c",
            "show_code",
            "Code",
            tooltip="Show the code used to generate this screen",
        )
    ]

    @work(thread=True)
    def get_code(self, source_file: str) -> str | None:
        """Read code from disk, or return `None` on error."""
        pass

