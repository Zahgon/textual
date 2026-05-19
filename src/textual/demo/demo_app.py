from __future__ import annotations

from textual.app import App
from textual.binding import Binding
from textual.demo.game import GameScreen
from textual.demo.home import HomeScreen
from textual.demo.projects import ProjectsScreen
from textual.demo.widgets import WidgetsScreen


class DemoApp(App):
    """The demo app defines the modes and sets a few bindings."""

    CSS = """
    .column {          
        align: center top;
        &>*{ max-width: 100; }        
    }
    Screen .-maximized {
        margin: 1 2;        
        max-width: 100%;
        &.column { margin: 1 2; padding: 1 2; }
        &.column > * {        
            max-width: 100%;           
        }        
    }
    """

    MODES = {
        "game": GameScreen,
        "home": HomeScreen,
        "projects": ProjectsScreen,
        "widgets": WidgetsScreen,
    }
    DEFAULT_MODE = "home"
    BINDINGS = [
        Binding(
            "h",
            "app.switch_mode('home')",
            "Home",
            tooltip="Show the home screen",
        ),
        Binding(
            "g",
            "app.switch_mode('game')",
            "Game",
            tooltip="Unwind with a Textual game",
        ),
        Binding(
            "p",
            "app.switch_mode('projects')",
            "Projects",
            tooltip="A selection of Textual projects",
        ),
        Binding(
            "w",
            "app.switch_mode('widgets')",
            "Widgets",
            tooltip="Test the builtin widgets",
        ),
        Binding(
            "ctrl+s",
            "app.screenshot",
            "Screenshot",
            tooltip="Save an SVG 'screenshot' of the current screen",
        ),
        Binding(
            "ctrl+a",
            "app.maximize",
            "Maximize",
            tooltip="Maximize the focused widget (if possible)",
        ),
    ]


    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """Disable switching to a mode we are already on."""
        if (
            action == "switch_mode"
            and parameters
            and self.current_mode == parameters[0]
        ):
            return None
        return True
