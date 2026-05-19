"""Provides a RadioSet widget, which groups radio buttons."""

from __future__ import annotations

from typing import ClassVar, Optional

import rich.repr
from rich.console import RenderableType

from textual import _widget_navigation
from textual.binding import Binding, BindingType
from textual.containers import VerticalScroll
from textual.events import Click, Mount
from textual.message import Message
from textual.reactive import reactive, var
from textual.widgets._radio_button import RadioButton


class RadioSet(VerticalScroll, can_focus=True, can_focus_children=False):
    """Widget for grouping a collection of radio buttons into a set.

    When a collection of [`RadioButton`][textual.widgets.RadioButton]s are
    grouped with this widget, they will be treated as a mutually-exclusive
    grouping. If one button is turned on, the previously-on button will be
    turned off.
    """

    ALLOW_SELECT = False
    ALLOW_MAXIMIZE = True

    DEFAULT_CSS = """
    RadioSet {
        border: tall $border-blurred;
        background: $surface;
        padding: 0 1;        
        height: auto;
        width: 1fr;
        pointer: pointer;

        &.-textual-compact {
            border: none !important;
            padding: 0;
        }

        & > RadioButton {
            background: transparent;
            border: none;
            padding: 0;
            width: 1fr;

            & > .toggle--button {
                color: $panel-darken-2;
                background: $panel;
            }            
        }

        & > RadioButton.-on .toggle--button {
            color: $text-success;
        }

        &:blur {
            & > RadioButton.-selected {
                & > .toggle--label {
                    background: $block-cursor-blurred-background;
                }
            }
        }

        &:focus {
            /* The following rules/styles mimic similar ToggleButton:focus rules in
            * ToggleButton. If those styles ever get updated, these should be too.
            */
            border: tall $border;
            background-tint: $foreground 5%;
            & > RadioButton.-selected {
            
                & > .toggle--label {
                    background: $block-cursor-background;                
                    color: $block-cursor-foreground;                
                    text-style: $block-cursor-text-style;
                }                         
            }

        }
    }
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("down,right", "next_button", "Next option", show=False),
        Binding("enter,space", "toggle_button", "Toggle", show=False),
        Binding("up,left", "previous_button", "Previous option", show=False),
    ]
    """
    | Key(s) | Description |
    | :- | :- |
    | enter, space | Toggle the currently-selected button. |
    | left, up | Select the previous radio button in the set. |
    | right, down | Select the next radio button in the set. |
    """

    _selected: var[int | None] = var[Optional[int]](None)
    """The index of the currently-selected radio button."""

    compact: reactive[bool] = reactive(False, toggle_class="-textual-compact")
    """Enable compact display?"""

    @rich.repr.auto
    class Changed(Message):
        """Posted when the pressed button in the set changes.

        This message can be handled using an `on_radio_set_changed` method.
        """

        ALLOW_SELECTOR_MATCH = {"pressed"}
        """Additional message attributes that can be used with the [`on` decorator][textual.on]."""

        def __init__(self, radio_set: RadioSet, pressed: RadioButton) -> None:
            """Initialise the message.

            Args:
                pressed: The radio button that was pressed.
            """
            super().__init__()
            self.radio_set = radio_set
            """A reference to the [`RadioSet`][textual.widgets.RadioSet] that was changed."""
            self.pressed = pressed
            """The [`RadioButton`][textual.widgets.RadioButton] that was pressed to make the change."""
            self.index = radio_set.pressed_index
            """The index of the [`RadioButton`][textual.widgets.RadioButton] that was pressed to make the change."""

        @property
        def control(self) -> RadioSet:
            """A reference to the [`RadioSet`][textual.widgets.RadioSet] that was changed.

            This is an alias for [`Changed.radio_set`][textual.widgets.RadioSet.Changed.radio_set]
            and is used by the [`on`][textual.on] decorator.
            """
            pass

        def __rich_repr__(self) -> rich.repr.Result:
            yield "radio_set", self.radio_set
            yield "pressed", self.pressed
            yield "index", self.index

    def __init__(
        self,
        *buttons: str | RadioButton,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
        tooltip: RenderableType | None = None,
        compact: bool = False,
    ) -> None:
        """Initialise the radio set.

        Args:
            buttons: The labels or [`RadioButton`][textual.widgets.RadioButton]s to group together.
            name: The name of the radio set.
            id: The ID of the radio set in the DOM.
            classes: The CSS classes of the radio set.
            disabled: Whether the radio set is disabled or not.
            tooltip: Optional tooltip.
            compact: Enable compact radio set style

        Note:
            When a `str` label is provided, a
            [RadioButton][textual.widgets.RadioButton] will be created from
            it.
        """
        self._pressed_button: RadioButton | None = None
        """Holds the radio buttons we're responsible for."""
        super().__init__(
            *[
                (button if isinstance(button, RadioButton) else RadioButton(button))
                for button in buttons
            ],
            name=name,
            id=id,
            classes=classes,
            disabled=disabled,
        )
        if tooltip is not None:
            self.tooltip = tooltip
        self.compact = compact

    def _on_mount(self, _: Mount) -> None:
        """Perform some processing once mounted in the DOM."""
        pass


    def _on_radio_button_changed(self, event: RadioButton.Changed) -> None:
        """Respond to the value of a button in the set being changed.

        Args:
            event: The event.
        """
        pass

    def _on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        """Handle a change to which button in the set is pressed.

        This handler ensures that, when a button is pressed, it's also the
        selected button.
        """
        pass

    async def _on_click(self, _: Click) -> None:
        """Handle a click on or within the radio set.

        This handler ensures that focus moves to the clicked radio set, even
        if there's a click on one of the radio buttons it contains.
        """
        pass

    @property
    def pressed_button(self) -> RadioButton | None:
        """The currently-pressed [`RadioButton`][textual.widgets.RadioButton], or `None` if none are pressed."""
        pass

    @property
    def pressed_index(self) -> int:
        """The index of the currently-pressed [`RadioButton`][textual.widgets.RadioButton], or -1 if none are pressed."""
        pass

    def action_previous_button(self) -> None:
        """Navigate to the previous button in the set.

        Note that this will wrap around to the end if at the start.
        """
        pass

    def action_next_button(self) -> None:
        """Navigate to the next button in the set.

        Note that this will wrap around to the start if at the end.
        """
        pass

    def action_toggle_button(self) -> None:
        """Toggle the state of the currently-selected button."""
        pass

    def _scroll_to_selected(self) -> None:
        """Ensure that the selected button is in view."""
        pass
