"""
This module contains classes for working with Textual's command palette.

See the guide on the [Command Palette](../guide/command_palette.md) for full details.

"""

from __future__ import annotations

from abc import ABC, abstractmethod
from asyncio import (
    CancelledError,
    Queue,
    Task,
    TimeoutError,
    create_task,
    wait,
    wait_for,
)
from dataclasses import dataclass
from functools import total_ordering
from inspect import isclass
from operator import attrgetter
from time import monotonic
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncGenerator,
    AsyncIterator,
    Callable,
    ClassVar,
    Iterable,
    NamedTuple,
)

import rich.repr
from rich.align import Align
from rich.text import Text
from typing_extensions import Final, TypeAlias

from textual import on, work
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical
from textual.content import Content
from textual.events import Click, Mount
from textual.fuzzy import Matcher
from textual.message import Message
from textual.reactive import var
from textual.screen import Screen, SystemModalScreen
from textual.style import Style
from textual.timer import Timer
from textual.types import IgnoreReturnCallbackType
from textual.visual import VisualType
from textual.widget import Widget
from textual.widgets import Button, Input, LoadingIndicator, OptionList, Static
from textual.widgets.option_list import Option
from textual.worker import get_current_worker

if TYPE_CHECKING:
    from textual.app import App, ComposeResult

__all__ = [
    "CommandPalette",
    "DiscoveryHit",
    "Hit",
    "Hits",
    "Matcher",
    "Provider",
]


@dataclass
class Hit:
    """Holds the details of a single command search hit."""

    score: float
    """The score of the command hit.

    The value should be between 0 (no match) and 1 (complete match).
    """

    match_display: VisualType
    """A string or Rich renderable representation of the hit."""

    command: IgnoreReturnCallbackType
    """The function to call when the command is chosen."""

    text: str | None = None
    """The command text associated with the hit, as plain text.

    If `match_display` is not simple text, this attribute should be provided by the
    [Provider][textual.command.Provider] object.
    """

    help: str | None = None
    """Optional help text for the command."""

    @property
    def prompt(self) -> VisualType:
        """The prompt to use when displaying the hit in the command palette."""
        pass

    def __lt__(self, other: object) -> bool:
        if isinstance(other, Hit):
            return self.score < other.score
        return NotImplemented

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Hit):
            return self.score == other.score
        return NotImplemented

    def __post_init__(self) -> None:
        """Ensure 'text' is populated."""
        if self.text is None:
            self.text = str(self.match_display)


@dataclass
class DiscoveryHit:
    """Holds the details of a single command search hit."""

    display: VisualType
    """A string or Rich renderable representation of the hit."""

    command: IgnoreReturnCallbackType
    """The function to call when the command is chosen."""

    text: str | None = None
    """The command text associated with the hit, as plain text.

    If `display` is not simple text, this attribute should be provided by
    the [Provider][textual.command.Provider] object.
    """

    help: str | None = None
    """Optional help text for the command."""

    @property
    def prompt(self) -> VisualType:
        """The prompt to use when displaying the discovery hit in the command palette."""
        pass

    @property
    def score(self) -> float:
        """A discovery hit always has a score of 0.

        The order in which discovery hits are displayed is determined by the order
        in which they are yielded by the Provider. It's up to the developer to yield
        DiscoveryHits in the .
        """
        return 0.0

    def __lt__(self, other: object) -> bool:
        if isinstance(other, DiscoveryHit):
            assert self.text is not None
            assert other.text is not None
            return other.text < self.text
        return NotImplemented

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Hit):
            return self.text == other.text
        return NotImplemented

    def __post_init__(self) -> None:
        """Ensure 'text' is populated."""
        if self.text is None:
            self.text = str(self.display)


Hits: TypeAlias = AsyncIterator["DiscoveryHit | Hit"]
"""Return type for the command provider's `search` method."""

ProviderSource: TypeAlias = "Iterable[type[Provider] | Callable[[], type[Provider]]]"
"""The type used to declare the providers for a CommandPalette."""


class Provider(ABC):
    """Base class for command palette command providers.

    To create new command provider, inherit from this class and implement
    [`search`][textual.command.Provider.search].
    """

    def __init__(self, screen: Screen[Any], match_style: Style | None = None) -> None:
        """Initialise the command provider.

        Args:
            screen: A reference to the active screen.
        """
        if match_style is not None:
            assert isinstance(
                match_style, Style
            ), "match_style must be a Visual style (from textual.style import Style)"
        self.__screen = screen
        self.__match_style = match_style
        self._init_task: Task | None = None
        self._init_success = False

    @property
    def focused(self) -> Widget | None:
        """The currently-focused widget in the currently-active screen in the application.

        If no widget has focus this will be `None`.
        """
        pass

    @property
    def screen(self) -> Screen[object]:
        """The currently-active screen in the application."""
        pass

    @property
    def app(self) -> App[object]:
        """A reference to the application."""
        return self.__screen.app

    @property
    def match_style(self) -> Style | None:
        """The preferred style to use when highlighting matching portions of the [`match_display`][textual.command.Hit.match_display]."""
        pass

    def matcher(self, user_input: str, case_sensitive: bool = False) -> Matcher:
        """Create a [fuzzy matcher][textual.fuzzy.Matcher] for the given user input.

        Args:
            user_input: The text that the user has input.
            case_sensitive: Should matching be case sensitive?

        Returns:
            A [fuzzy matcher][textual.fuzzy.Matcher] object for matching against candidate hits.
        """
        return Matcher(
            user_input,
            match_style=self.match_style,
            case_sensitive=case_sensitive,
        )

    def _post_init(self) -> None:
        """Internal method to run post init task."""
        pass

    async def _wait_init(self) -> None:
        """Wait for initialization."""
        pass

    async def startup(self) -> None:
        """Called after the Provider is initialized, but before any calls to `search`."""

    async def _search(self, query: str) -> Hits:
        """Internal method to perform search.

        Args:
            query: The user input to be matched.

        Yields:
            Instances of [`Hit`][textual.command.Hit].
        """
        pass

    @abstractmethod
    async def search(self, query: str) -> Hits:
        """A request to search for commands relevant to the given query.

        Args:
            query: The user input to be matched.

        Yields:
            Instances of [`Hit`][textual.command.Hit].
        """
        yield NotImplemented

    async def discover(self) -> Hits:
        """A default collection of hits for the provider.

        Yields:
            Instances of [`DiscoveryHit`][textual.command.DiscoveryHit].

        Note:
            This is different from
            [`search`][textual.command.Provider.search] in that it should
            yield [`DiscoveryHit`s][textual.command.DiscoveryHit] that
            should be shown by default (before user input).

            It is permitted to *not* implement this method.
        """
        pass

    async def _shutdown(self) -> None:
        """Internal method to call shutdown and log errors."""
        try:
            await self.shutdown()
        except Exception:
            from rich.traceback import Traceback

            self.app.log.error(Traceback())

    async def shutdown(self) -> None:
        """Called when the Provider is shutdown.

        Use this method to perform an cleanup, if required.

        """


class SimpleCommand(NamedTuple):
    """A simple command."""

    name: str
    """The name of the command."""
    callback: IgnoreReturnCallbackType
    """The callback to invoke when the command is selected."""
    help_text: str | None = None
    """The description of the command."""


CommandListItem: TypeAlias = (
    "SimpleCommand | tuple[str, IgnoreReturnCallbackType, str | None] | tuple[str, IgnoreReturnCallbackType]"
)


class SimpleProvider(Provider):
    """A simple provider which the caller can pass commands to."""

    def __init__(
        self,
        screen: Screen[Any],
        commands: list[CommandListItem],
    ) -> None:
        # Convert all commands to SimpleCommand instances
        super().__init__(screen, None)
        self._commands: list[SimpleCommand] = []
        for command in commands:
            if isinstance(command, SimpleCommand):
                self._commands.append(command)
            elif len(command) == 2:
                self._commands.append(SimpleCommand(*command, None))
            elif len(command) == 3:
                self._commands.append(SimpleCommand(*command))
            else:
                raise ValueError(f"Invalid command: {command}")

    def __call__(
        self, screen: Screen[Any], match_style: Style | None = None
    ) -> SimpleProvider:
        self.__match_style = match_style
        return self


    async def search(self, query: str) -> Hits:
        matcher = self.matcher(query)
        for name, callback, help_text in self._commands:
            if (match := matcher.match(name)) > 0:
                yield Hit(
                    match,
                    matcher.highlight(name),
                    callback,
                    help=help_text,
                )

    async def discover(self) -> Hits:
        """Handle a request for the discovery commands for this provider.

        Yields:
            Commands that can be discovered.
        """
        pass


@rich.repr.auto
@total_ordering
class Command(Option):
    """Class that holds a hit in the [`CommandList`][textual.command.CommandList]."""

    def __init__(
        self,
        prompt: VisualType,
        hit: DiscoveryHit | Hit,
        id: str | None = None,
        disabled: bool = False,
    ) -> None:
        """Initialise the option.

        Args:
            prompt: The prompt for the option.
            hit: The details of the hit associated with the option.
            id: The optional ID for the option.
            disabled: The initial enabled/disabled state. Enabled by default.
        """
        super().__init__(prompt, id, disabled)
        self.hit = hit
        """The details of the hit associated with the option."""

    def __hash__(self) -> int:
        return id(self)

    def __lt__(self, other: object) -> bool:
        if isinstance(other, Command):
            return self.hit < other.hit
        return NotImplemented

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Command):
            return self.hit == other.hit
        return NotImplemented


class CommandList(OptionList, can_focus=False):
    """The command palette command list."""

    DEFAULT_CSS = """
    
    CommandList:ansi {
        & > .option-list--option-highlighted {             
            color: $block-cursor-foreground;
            background: $block-cursor-background;
            text-style: $block-cursor-text-style;    
        }               
    }       
    
    CommandList {
        visibility: hidden;
        border-top: blank;
        border-bottom: hkey black;
        border-left: none;
        border-right: none;
        height: auto;
        max-height: 70vh;
        background: transparent;
        padding: 0;
    }

    CommandList:focus {
        border: blank;
    }

    CommandList.--visible {
        visibility: visible;
    }

    CommandList.--populating {
        border-bottom: none;
    }

    CommandList > .option-list--option-highlighted {
        color: $block-cursor-blurred-foreground;
        background: $block-cursor-blurred-background;
        text-style: $block-cursor-blurred-text-style;        
    }
    

    CommandList:nocolor > .option-list--option-highlighted {       
        text-style: reverse;
    }

    CommandList > .option-list--option {
        padding: 0 2;
        color: $foreground;
        text-style: bold;
    }
    """


class SearchIcon(Static, inherit_css=False):
    """Widget for displaying a search icon before the command input."""

    DEFAULT_CSS = """
    SearchIcon {
        color: #000;  /* required for snapshot tests */
        margin-left: 1;
        margin-top: 1;
        width: 2;
    }
    """

    icon: var[str] = var("🔎")
    """The icon to display."""

    def render(self) -> VisualType:
        """Render the icon.

        Returns:
            The icon renderable.
        """
        return self.icon


class CommandInput(Input):
    """The command palette input control."""

    DEFAULT_CSS = """
    CommandInput, CommandInput:focus {
        border: blank;
        width: 1fr;
        padding-left: 0;
        background: transparent;
        background-tint: 0%;
    }
    """


class CommandPalette(SystemModalScreen[None]):
    """The Textual command palette."""

    AUTO_FOCUS = "CommandInput"

    COMPONENT_CLASSES: ClassVar[set[str]] = Screen.COMPONENT_CLASSES | {
        "command-palette--help-text",
        "command-palette--highlight",
    }
    """
    | Class | Description |
    | :- | :- |
    | `command-palette--help-text` | Targets the help text of a matched command. |
    | `command-palette--highlight` | Targets the highlights of a matched command. |
    """

    DEFAULT_CSS = """
   
    CommandPalette:inline {
        /* If the command palette is invoked in inline mode, we may need additional lines. */
        min-height: 20;
    }
    CommandPalette {
        color: $foreground;
        background: $background 60%;
        align-horizontal: center;        

        #--container {
            display: none;
        }

        &:ansi {
            background: transparent;
        }
    }

    CommandPalette.-ready {
        #--container {
            display: block;
        }
    }


    CommandPalette > .command-palette--help-text  {
        color: transparent;
        text-style: dim not bold;
    }
    
    CommandPalette > .command-palette--highlight {
        text-style: bold underline;
    }   

    CommandPalette:nocolor > .command-palette--highlight {
        text-style: underline;
    }

    CommandPalette > Vertical {
        margin-top: 3; 
        height: 100%;
        visibility: hidden;
        background: $surface;
        &:dark { background: $panel-darken-1; }
    }

    CommandPalette #--input {
        height: auto;
        visibility: visible;
        border: hkey black 50%;
    }

    CommandPalette #--input.--list-visible {
        border-bottom: none;
    }

    CommandPalette #--input Label {
        margin-top: 1;
        margin-left: 1;
    }

    CommandPalette #--input Button {
        min-width: 7;
        margin-right: 1;
    }

    CommandPalette #--results {
        overlay: screen;
        height: auto;
    }

    CommandPalette LoadingIndicator {
        height: auto;
        visibility: hidden;
        border-bottom: hkey $border;
    }

    CommandPalette LoadingIndicator.--visible {
        visibility: visible;
    }
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding(
            "ctrl+end, shift+end",
            "command_list('last')",
            "Go to bottom",
            show=False,
        ),
        Binding(
            "ctrl+home, shift+home",
            "command_list('first')",
            "Go to top",
            show=False,
        ),
        Binding("down", "cursor_down", "Next command", show=False),
        Binding("escape", "escape", "Exit the command palette"),
        Binding("pagedown", "command_list('page_down')", "Next page", show=False),
        Binding("pageup", "command_list('page_up')", "Previous page", show=False),
        Binding("up", "command_list('cursor_up')", "Previous command", show=False),
    ]
    """
    | Key(s) | Description |
    | :- | :- |
    | ctrl+end, shift+end | Jump to the last available commands. |
    | ctrl+home, shift+home | Jump to the first available commands. |
    | down | Navigate down through the available commands. |
    | escape | Exit the command palette. |
    | pagedown | Navigate down a page through the available commands. |
    | pageup | Navigate up a page through the available commands. |
    | up | Navigate up through the available commands. |
    """

    run_on_select: ClassVar[bool] = True
    """A flag to say if a command should be run when selected by the user.

    If `True` then when a user hits `Enter` on a command match in the result
    list, or if they click on one with the mouse, the command will be
    selected and run. If set to `False` the input will be filled with the
    command and then `Enter` should be pressed on the keyboard or the 'go'
    button should be pressed.
    """

    _list_visible: var[bool] = var(False, init=False)
    """Internal reactive to toggle the visibility of the command list."""

    _show_busy: var[bool] = var(False, init=False)
    """Internal reactive to toggle the visibility of the busy indicator."""

    _calling_screen: var[Screen[Any] | None] = var(None)
    """A record of the screen that was active when we were called."""

    @dataclass
    class OptionHighlighted(Message):
        """Posted to App when an option is highlighted in the command palette."""

        highlighted_event: OptionList.OptionHighlighted
        """The option highlighted event from the OptionList within the command palette."""

    @dataclass
    class Opened(Message):
        """Posted to App when the command palette is opened."""

    @dataclass
    class Closed(Message):
        """Posted to App when the command palette is closed."""

        option_selected: bool
        """True if an option was selected, False if the palette was closed without selecting an option."""

    def __init__(
        self,
        providers: ProviderSource | None = None,
        *,
        placeholder: str = "Search for commands…",
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialise the command palette.

        Args:
            providers: An optional list of providers to use. If None, the providers supplied
                in the App or Screen will be used.
            placeholder: The placeholder text for the command palette.
        """
        super().__init__(
            id=id,
            classes=classes,
            name=name,
        )
        self.add_class("--textual-command-palette")

        self._selected_command: DiscoveryHit | Hit | None = None
        """The command that was selected by the user."""
        self._busy_timer: Timer | None = None
        """Keeps track of if there's a busy indication timer in effect."""
        self._no_matches_timer: Timer | None = None
        """Keeps track of if there are 'No matches found' message waiting to be displayed."""
        self._supplied_providers: ProviderSource | None = providers
        self._providers: list[Provider] = []
        """List of Provider instances involved in searches."""
        self._hit_count: int = 0
        """Number of hits displayed."""
        self._placeholder = placeholder

    @staticmethod
    def is_open(app: App[object]) -> bool:
        """Is a command palette current open?

        Args:
            app: The app to test.

        Returns:
            `True` if a command palette is currently open, `False` if not.
        """
        pass

    @property
    def _provider_classes(self) -> set[type[Provider]]:
        """The currently available command providers.

        This is a combination of the command providers defined [in the
        application][textual.app.App.COMMANDS] and those [defined in
        the current screen][textual.screen.Screen.COMMANDS].
        """
        pass

    def compose(self) -> ComposeResult:
        """Compose the command palette.

        Returns:
            The content of the screen.
        """
        with Vertical(id="--container"):
            with Horizontal(id="--input"):
                yield SearchIcon()
                yield CommandInput(placeholder=self._placeholder, select_on_focus=False)
                if not self.run_on_select:
                    yield Button("\u25b6")
            with Vertical(id="--results"):
                yield CommandList()
                yield LoadingIndicator()

    def _on_click(self, event: Click) -> None:  # type: ignore[override]
        """Handle the click event.

        Args:
            event: The click event.

        This method is used to allow clicking on the 'background' as a
        method of dismissing the palette.
        """
        pass

    def _on_mount(self, _: Mount) -> None:
        """Configure the command palette once the DOM is ready."""
        pass

    async def _on_unmount(self) -> None:  # type: ignore[override]
        """Shutdown providers when command palette is closed."""
        pass

    def _stop_busy_countdown(self) -> None:
        """Stop any busy countdown that's in effect."""
        pass

    _BUSY_COUNTDOWN: Final[float] = 0.5
    """How many seconds to wait for commands to come in before showing we're busy."""

    def _start_busy_countdown(self) -> None:
        """Start a countdown to showing that we're busy searching."""
        pass

    def _stop_no_matches_countdown(self) -> None:
        """Stop any 'No matches' countdown that's in effect."""
        pass

    _NO_MATCHES_COUNTDOWN: Final[float] = 0.5
    """How many seconds to wait before showing 'No matches found'."""

    def _start_no_matches_countdown(self, search_value: str) -> None:
        """Start a countdown to showing that there are no matches for the query.

        Args:
            search_value: The value being searched for.

        Adds a 'No matches found' option to the command list after
        `_NO_MATCHES_COUNTDOWN` seconds.
        """
        pass

    def _watch__list_visible(self) -> None:
        """React to the list visible flag being toggled."""
        pass

    async def _watch__show_busy(self) -> None:
        """React to the show busy flag being toggled.

        This watcher adds or removes a busy indication depending on the
        flag's state.
        """
        pass

    @staticmethod
    async def _consume(hits: Hits, commands: Queue[DiscoveryHit | Hit]) -> None:
        """Consume a source of matching commands, feeding the given command queue.

        Args:
            hits: The hits to consume.
            commands: The command queue to feed.
        """
        pass

    async def _search_for(
        self, search_value: str
    ) -> AsyncGenerator[DiscoveryHit | Hit, bool]:
        """Search for a given search value amongst all of the command providers.

        Args:
            search_value: The value to search for.

        Yields:
            The hits made amongst the registered command providers.
        """
        pass

    def _refresh_command_list(
        self, command_list: CommandList, commands: list[Command], clear_current: bool
    ) -> None:
        """Refresh the command list.

        Args:
            command_list: The widget that shows the list of commands.
            commands: The commands to show in the widget.
            clear_current: Should the current content of the list be cleared first?
        """
        pass

    _RESULT_BATCH_TIME: Final[float] = 0.25
    """How long to wait before adding commands to the command list."""

    _NO_MATCHES: Final[str] = "--no-matches"
    """The ID to give the disabled option that shows there were no matches."""

    _GATHER_COMMANDS_GROUP: Final[str] = "--textual-command-palette-gather-commands"
    """The group name of the command gathering worker."""

    @work(exclusive=True, group=_GATHER_COMMANDS_GROUP)
    async def _gather_commands(self, search_value: str) -> None:
        """Gather up all of the commands that match the search value.

        Args:
            search_value: The value to search for.
        """
        pass

    def _cancel_gather_commands(self) -> None:
        """Cancel any operation that is gather commands."""
        pass

    @on(Input.Changed)
    def _input(self, event: Input.Changed) -> None:
        """React to input in the command palette.

        Args:
            event: The input event.
        """
        pass

    @on(OptionList.OptionSelected)
    def _select_command(self, event: OptionList.OptionSelected) -> None:
        """React to a command being selected from the dropdown.

        Args:
            event: The option selection event.
        """
        pass

    @on(Input.Submitted)
    @on(Button.Pressed)
    def _select_or_command(
        self, event: Input.Submitted | Button.Pressed | None = None
    ) -> None:
        """Depending on context, select or execute a command."""
        pass

    @on(OptionList.OptionHighlighted)
    def _stop_event_leak(self, event: OptionList.OptionHighlighted) -> None:
        """Stop any unused events so they don't leak to the application."""
        pass

    def _action_escape(self) -> None:
        """Handle a request to escape out of the command palette."""
        pass

    def _action_command_list(self, action: str) -> None:
        """Pass an action on to the [`CommandList`][textual.command.CommandList].

        Args:
            action: The action to pass on to the [`CommandList`][textual.command.CommandList].
        """
        pass

    def _action_cursor_down(self) -> None:
        """Handle the cursor down action.

        This allows the cursor down key to either open the command list, if
        it's closed but has options, or if it's open with options just
        cursor through them.
        """
        pass
