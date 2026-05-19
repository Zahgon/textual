"""Provides a selection list widget, allowing one or more items to be selected."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, ClassVar, Generic, Iterable, TypeVar, cast

from rich.repr import Result
from rich.segment import Segment
from rich.style import Style
from typing_extensions import Self

from textual import events
from textual.binding import Binding
from textual.content import Content, ContentText
from textual.messages import Message
from textual.strip import Strip
from textual.widgets._option_list import (
    Option,
    OptionDoesNotExist,
    OptionList,
    OptionListContent,
)
from textual.widgets._toggle_button import ToggleButton

SelectionType = TypeVar("SelectionType")
"""The type for the value of a [`Selection`][textual.widgets.selection_list.Selection] in a [`SelectionList`][textual.widgets.SelectionList]"""

MessageSelectionType = TypeVar("MessageSelectionType")
"""The type for the value of a [`Selection`][textual.widgets.selection_list.Selection] in a [`SelectionList`][textual.widgets.SelectionList] message."""


class SelectionError(TypeError):
    """Type of an error raised if a selection is badly-formed."""


class Selection(Generic[SelectionType], Option):
    """A selection for a [`SelectionList`][textual.widgets.SelectionList]."""

    def __init__(
        self,
        prompt: ContentText,
        value: SelectionType,
        initial_state: bool = False,
        id: str | None = None,
        disabled: bool = False,
    ):
        """Initialise the selection.

        Args:
            prompt: The prompt for the selection.
            value: The value for the selection.
            initial_state: The initial selected state of the selection.
            id: The optional ID for the selection.
            disabled: The initial enabled/disabled state. Enabled by default.
        """

        selection_prompt = Content.from_text(prompt)
        super().__init__(selection_prompt.split()[0], id, disabled)
        self._value: SelectionType = value
        """The value associated with the selection."""
        self._initial_state: bool = initial_state
        """The initial selected state for the selection."""

    @property
    def value(self) -> SelectionType:
        """The value for this selection."""
        pass

    @property
    def initial_state(self) -> bool:
        """The initial selected state for the selection."""
        pass


class SelectionList(Generic[SelectionType], OptionList):
    """A vertical selection list that allows making multiple selections."""

    BINDINGS = [Binding("space", "select", "Toggle option", show=False)]
    """
    | Key(s) | Description |
    | :- | :- |
    | space | Toggle the state of the highlighted selection. |
    """

    COMPONENT_CLASSES: ClassVar[set[str]] = {
        "selection-list--button",
        "selection-list--button-selected",
        "selection-list--button-highlighted",
        "selection-list--button-selected-highlighted",
    }
    """
    | Class | Description |
    | :- | :- |
    | `selection-list--button` | Target the default button style. |
    | `selection-list--button-selected` | Target a selected button style. |
    | `selection-list--button-highlighted` | Target a highlighted button style. |
    | `selection-list--button-selected-highlighted` | Target a highlighted selected button style. |
    """

    DEFAULT_CSS = """
    SelectionList {
        height: auto;
        text-wrap: nowrap;
        text-overflow: ellipsis;
        
        & > .selection-list--button {
            color: $panel-darken-2;
            background: $panel;
        }

        & > .selection-list--button-highlighted {
            color: $panel-darken-2;
            background: $panel;
        }

        & > .selection-list--button-selected {
            color: $text-success;
            background: $panel;
        }

        & > .selection-list--button-selected-highlighted {
            color: $text-success;
            background: $panel;
        }

    }
    """

    class SelectionMessage(Generic[MessageSelectionType], Message):
        """Base class for all selection messages."""

        def __init__(
            self, selection_list: SelectionList[MessageSelectionType], index: int
        ) -> None:
            """Initialise the selection message.

            Args:
                selection_list: The selection list that owns the selection.
                index: The index of the selection that the message relates to.
            """
            super().__init__()
            self.selection_list: SelectionList[MessageSelectionType] = selection_list
            """The selection list that sent the message."""
            self.selection: Selection[MessageSelectionType] = (
                selection_list.get_option_at_index(index)
            )
            """The highlighted selection."""
            self.selection_index: int = index
            """The index of the selection that the message relates to."""

        @property
        def control(self) -> OptionList:
            """The selection list that sent the message.

            This is an alias for
            [`SelectionMessage.selection_list`][textual.widgets.SelectionList.SelectionMessage.selection_list]
            and is used by the [`on`][textual.on] decorator.
            """
            pass

        def __rich_repr__(self) -> Result:
            yield "selection_list", self.selection_list
            yield "selection", self.selection
            yield "selection_index", self.selection_index

    class SelectionHighlighted(SelectionMessage[MessageSelectionType]):
        """Message sent when a selection is highlighted.

        Can be handled using `on_selection_list_selection_highlighted` in a subclass of
        [`SelectionList`][textual.widgets.SelectionList] or in a parent node in the DOM.
        """

    class SelectionToggled(SelectionMessage[MessageSelectionType]):
        """Message sent when a selection is toggled.

        This is only sent when the value is *explicitly* toggled e.g.
        via `toggle` or `toggle_all`, or via user interaction.
        If you programmatically set a value to be selected, this message will
        not be sent, even if it happens to be the opposite of what was
        originally selected (i.e. setting a True to a False or vice-versa).

        Since this message indicates a toggle occurring at a per-option level,
        a message will be sent for each option that is toggled, even when a
        bulk action is performed (e.g. via `toggle_all`).

        Can be handled using `on_selection_list_selection_toggled` in a subclass of
        [`SelectionList`][textual.widgets.SelectionList] or in a parent node in the DOM.
        """

    @dataclass
    class SelectedChanged(Generic[MessageSelectionType], Message):
        """Message sent when the collection of selected values changes.

        This is sent regardless of whether the change occurred via user interaction
        or programmatically via the `SelectionList` API.

        When a bulk change occurs, such as through `select_all` or `deselect_all`,
        only a single `SelectedChanged` message will be sent (rather than one per
        option).

        Can be handled using `on_selection_list_selected_changed` in a subclass of
        [`SelectionList`][textual.widgets.SelectionList] or in a parent node in the DOM.
        """

        selection_list: SelectionList[MessageSelectionType]
        """The `SelectionList` that sent the message."""

        @property
        def control(self) -> SelectionList[MessageSelectionType]:
            """An alias for `selection_list`."""
            pass

    def __init__(
        self,
        *selections: Selection[SelectionType]
        | tuple[ContentText, SelectionType]
        | tuple[ContentText, SelectionType, bool],
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
        compact: bool = False,
    ):
        """Initialise the selection list.

        Args:
            *selections: The content for the selection list.
            name: The name of the selection list.
            id: The ID of the selection list in the DOM.
            classes: The CSS classes of the selection list.
            disabled: Whether the selection list is disabled or not.
            compact: Enable a compact style?
        """

        self._selected: dict[SelectionType, None] = {}
        """Tracking of which values are selected."""
        self._send_messages = False
        """Keep track of when we're ready to start sending messages."""
        options = [self._make_selection(selection) for selection in selections]
        self._values: dict[SelectionType, int] = {
            option.value: index for index, option in enumerate(options)
        }
        """Keeps track of which value relates to which option."""
        super().__init__(*options, name=name, id=id, classes=classes, disabled=disabled)
        self.compact = compact

    @property
    def selected(self) -> list[SelectionType]:
        """The selected values.

        This is a list of all of the
        [values][textual.widgets.selection_list.Selection.value] associated
        with selections in the list that are currently in the selected
        state.
        """
        pass

    def _on_mount(self, _event: events.Mount) -> None:
        """Configure the list once the DOM is ready."""
        pass

    def _message_changed(self) -> None:
        """Post a message that the selected collection has changed, where appropriate.

        Note:
            A message will only be sent if `_send_messages` is `True`. This
            makes this safe to call before the widget is ready for posting
            messages.
        """
        pass

    def _message_toggled(self, option_index: int) -> None:
        """Post a message that an option was toggled, where appropriate.

        Note:
            A message will only be sent if `_send_messages` is `True`. This
            makes this safe to call before the widget is ready for posting
            messages.
        """
        pass

    def _apply_to_all(self, state_change: Callable[[SelectionType], bool]) -> Self:
        """Apply a selection state change to all selection options in the list.

        Args:
            state_change: The state change function to apply.

        Returns:
            The [`SelectionList`][textual.widgets.SelectionList] instance.

        Note:
            This method will post a single
            [`SelectedChanged`][textual.widgets.OptionList.SelectedChanged]
            message if a change is made in a call to this method.
        """
        pass

    def _select(self, value: SelectionType) -> bool:
        """Mark the given value as selected.

        Args:
            value: The value to mark as selected.

        Returns:
            `True` if the value was selected, `False` if not.
        """
        pass

    def select(self, selection: Selection[SelectionType] | SelectionType) -> Self:
        """Mark the given selection as selected.

        Args:
            selection: The selection to mark as selected.

        Returns:
            The [`SelectionList`][textual.widgets.SelectionList] instance.
        """
        pass

    def select_all(self) -> Self:
        """Select all items.

        Returns:
            The [`SelectionList`][textual.widgets.SelectionList] instance.
        """
        pass

    def _deselect(self, value: SelectionType) -> bool:
        """Mark the given selection as not selected.

        Args:
            value: The value to mark as not selected.

        Returns:
            `True` if the value was deselected, `False` if not.
        """
        pass

    def deselect(self, selection: Selection[SelectionType] | SelectionType) -> Self:
        """Mark the given selection as not selected.

        Args:
            selection: The selection to mark as not selected.

        Returns:
            The [`SelectionList`][textual.widgets.SelectionList] instance.
        """
        pass

    def deselect_all(self) -> Self:
        """Deselect all items.

        Returns:
            The [`SelectionList`][textual.widgets.SelectionList] instance.
        """
        pass

    def _toggle(self, value: SelectionType) -> bool:
        """Toggle the selection state of the given value.

        Args:
            value: The value to toggle.

        Returns:
            `True`.
        """
        pass

    def toggle(self, selection: Selection[SelectionType] | SelectionType) -> Self:
        """Toggle the selected state of the given selection.

        Args:
            selection: The selection to toggle.

        Returns:
            The [`SelectionList`][textual.widgets.SelectionList] instance.
        """
        pass

    def toggle_all(self) -> Self:
        """Toggle all items.

        Returns:
            The [`SelectionList`][textual.widgets.SelectionList] instance.
        """
        pass

    def _make_selection(
        self,
        selection: (
            Selection[SelectionType]
            | tuple[ContentText, SelectionType]
            | tuple[ContentText, SelectionType, bool]
        ),
    ) -> Selection[SelectionType]:
        """Turn incoming selection data into a `Selection` instance.

        Args:
            selection: The selection data.

        Returns:
            An instance of a `Selection`.

        Raises:
            SelectionError: If the selection was badly-formed.
        """
        pass

    def _toggle_highlighted_selection(self) -> None:
        """Toggle the state of the highlighted selection.

        If nothing is selected in the list this is a non-operation.
        """
        pass

    def _get_left_gutter_width(self) -> int:
        """Returns the size of any left gutter that should be taken into account.

        Returns:
            The width of the left gutter.
        """
        return len(
            ToggleButton.BUTTON_LEFT
            + ToggleButton.BUTTON_INNER
            + ToggleButton.BUTTON_RIGHT
            + " "
        )

    def render_line(self, y: int) -> Strip:
        """Render a line in the display.

        Args:
            y: The line to render.

        Returns:
            A [`Strip`][textual.strip.Strip] that is the line to render.
        """

        # TODO: This is rather crufty and hard to fathom. Candidate for a rewrite.

        # First off, get the underlying prompt from OptionList.
        line = super().render_line(y)

        # We know the prompt we're going to display, what we're going to do
        # is place a CheckBox-a-like button next to it. So to start with
        # let's pull out the actual Selection we're looking at right now.
        _, scroll_y = self.scroll_offset
        selection_index = scroll_y + y
        try:
            selection = self.get_option_at_index(selection_index)
        except OptionDoesNotExist:
            return line

        # Figure out which component style is relevant for a checkbox on
        # this particular line.
        component_style = "selection-list--button"
        if selection.value in self._selected:
            component_style += "-selected"
        if self.highlighted == selection_index:
            component_style += "-highlighted"

        # # # Get the underlying style used for the prompt.
        # TODO: This is not a reliable way of getting the base style
        underlying_style = next(iter(line)).style or self.rich_style
        assert underlying_style is not None

        # Get the style for the button.
        button_style = self.get_component_rich_style(component_style)

        # Build the style for the side characters. Note that this is
        # sensitive to the type of character used, so pay attention to
        # BUTTON_LEFT and BUTTON_RIGHT.
        side_style = Style.from_color(button_style.bgcolor, underlying_style.bgcolor)

        # Add the option index to the style. This is used to determine which
        # option to select when the button is clicked or hovered.
        side_style += Style(meta={"option": selection_index})
        button_style += Style(meta={"option": selection_index})

        # At this point we should have everything we need to place a
        # "button" before the option.
        return Strip(
            [
                Segment(ToggleButton.BUTTON_LEFT, style=side_style),
                Segment(ToggleButton.BUTTON_INNER, style=button_style),
                Segment(ToggleButton.BUTTON_RIGHT, style=side_style),
                Segment(" ", style=underlying_style),
                *line,
            ]
        )

    def _on_option_list_option_highlighted(
        self, event: OptionList.OptionHighlighted
    ) -> None:
        """Capture the `OptionList` highlight event and turn it into a [`SelectionList`][textual.widgets.SelectionList] event.

        Args:
            event: The event to capture and recreate.
        """
        pass

    def _on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Capture the `OptionList` selected event and turn it into a [`SelectionList`][textual.widgets.SelectionList] event.

        Args:
            event: The event to capture and recreate.
        """
        pass

    def get_option_at_index(self, index: int) -> Selection[SelectionType]:
        """Get the selection option at the given index.

        Args:
            index: The index of the selection option to get.

        Returns:
            The selection option at that index.

        Raises:
            OptionDoesNotExist: If there is no selection option with the index.
        """
        return cast("Selection[SelectionType]", super().get_option_at_index(index))

    def get_option(self, option_id: str) -> Selection[SelectionType]:
        """Get the selection option with the given ID.

        Args:
            option_id: The ID of the selection option to get.

        Returns:
            The selection option with the ID.

        Raises:
            OptionDoesNotExist: If no selection option has the given ID.
        """
        pass

    def _pre_remove_option(self, option: Option, index: int) -> None:
        """Hook called prior to removing an option."""
        pass

    def add_options(
        self,
        items: Iterable[
            OptionListContent
            | Selection[SelectionType]
            | tuple[ContentText, SelectionType]
            | tuple[ContentText, SelectionType, bool]
        ],
    ) -> Self:
        """Add new selection options to the end of the list.

        Args:
            items: The new items to add.

        Returns:
            The [`SelectionList`][textual.widgets.SelectionList] instance.

        Raises:
            DuplicateID: If there is an attempt to use a duplicate ID.
            SelectionError: If one of the selection options is of the wrong form.
        """
        pass

    def add_option(
        self,
        item: (
            OptionListContent
            | Selection
            | tuple[ContentText, SelectionType]
            | tuple[ContentText, SelectionType, bool]
        ) = None,
    ) -> Self:
        """Add a new selection option to the end of the list.

        Args:
            item: The new item to add.

        Returns:
            The [`SelectionList`][textual.widgets.SelectionList] instance.

        Raises:
            DuplicateID: If there is an attempt to use a duplicate ID.
            SelectionError: If the selection option is of the wrong form.
        """
        pass

    def clear_options(self) -> Self:
        """Clear the content of the selection list.

        Returns:
            The `SelectionList` instance.
        """
        pass
