from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from rich.console import RenderableType

if TYPE_CHECKING:
    from textual.app import RenderResult
    from typing_extensions import Self

from textual.binding import Binding, BindingType
from textual.events import Click
from textual.geometry import Size
from textual.message import Message
from textual.reactive import reactive
from textual.scrollbar import ScrollBarRender
from textual.widget import Widget


class Switch(Widget, can_focus=True):
    """A switch widget that represents a boolean value.

    Can be toggled by clicking on it or through its [bindings][textual.widgets.Switch.BINDINGS].

    The switch widget also contains [component classes][textual.widgets.Switch.COMPONENT_CLASSES]
    that enable more customization.
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("enter,space", "toggle_switch", "Toggle", show=False),
    ]
    """
    | Key(s) | Description |
    | :- | :- |
    | enter,space | Toggle the switch state. |
    """

    COMPONENT_CLASSES: ClassVar[set[str]] = {
        "switch--slider",
    }
    """
    | Class | Description |
    | :- | :- |
    | `switch--slider` | Targets the slider of the switch. |
    """

    ALLOW_SELECT = False

    DEFAULT_CSS = """
    Switch {
        border: tall $border-blurred;
        background: $surface;
        height: auto;
        width: auto;
        pointer: pointer;
        
        &:ansi {
            & .switch--slider {
                color: ansi_red;
            }
            &:hover {
                & > .switch--slider {
                    color: ansi_bright_red;
                }
                &.-on > .switch--slider {
                    color: ansi_bright_green;
                }
            }
        }

        padding: 0 2;
        &.-on .switch--slider {
            color: $success;
        }
        & .switch--slider {
            color: $panel;
            background: $panel-darken-2;
        }
        &:hover {
            & > .switch--slider {
                color: $panel-lighten-1
            }
            &.-on > .switch--slider {
                color: $success-lighten-1;
            }
        }
        &:focus {
            border: tall $border;
            background-tint: $foreground 5%;
        }

        &:light {
            &.-on .switch--slider {
                color: $success;
            }
            & .switch--slider {
                color: $primary 15%;
                background: $panel-darken-2;
            }
            &:hover {
                & > .switch--slider {
                    color: $primary 25%;
                }
                &.-on > .switch--slider {
                    color: $success-lighten-1;
                }
            }
        }
    }

    """

    value: reactive[bool] = reactive(False, init=False)
    """The value of the switch; `True` for on and `False` for off."""

    _slider_position = reactive(0.0)
    """The position of the slider."""

    class Changed(Message):
        """Posted when the status of the switch changes.

        Can be handled using `on_switch_changed` in a subclass of `Switch`
        or in a parent widget in the DOM.

        Attributes:
            value: The value that the switch was changed to.
            switch: The `Switch` widget that was changed.
        """

        def __init__(self, switch: Switch, value: bool) -> None:
            super().__init__()
            self.value: bool = value
            self.switch: Switch = switch

        @property
        def control(self) -> Switch:
            """Alias for self.switch."""
            pass

    def __init__(
        self,
        value: bool = False,
        *,
        animate: bool = True,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
        tooltip: RenderableType | None = None,
    ):
        """Initialise the switch.

        Args:
            value: The initial value of the switch.
            animate: True if the switch should animate when toggled.
            name: The name of the switch.
            id: The ID of the switch in the DOM.
            classes: The CSS classes of the switch.
            disabled: Whether the switch is disabled or not.
            tooltip: Optional tooltip.
        """
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        if value:
            self._slider_position = 1.0
            self.set_reactive(Switch.value, value)
        self._should_animate = animate
        if tooltip is not None:
            self.tooltip = tooltip



    def render(self) -> RenderResult:
        style = self.get_component_rich_style("switch--slider")
        return ScrollBarRender(
            virtual_size=100,
            window_size=50,
            position=self._slider_position * 50,
            style=style,
            vertical=False,
        )

    def get_content_width(self, container: Size, viewport: Size) -> int:
        return 4

    def get_content_height(self, container: Size, viewport: Size, width: int) -> int:
        return 1

    async def _on_click(self, event: Click) -> None:
        """Toggle the state of the switch."""
        pass

    def action_toggle_switch(self) -> None:
        """Toggle the state of the switch."""
        pass

    def toggle(self) -> Self:
        """Toggle the switch value.

        As a result of the value changing, a `Switch.Changed` message will
        be posted.

        Returns:
            The `Switch` instance.
        """
        pass
