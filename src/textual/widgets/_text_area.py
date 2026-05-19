from __future__ import annotations

import dataclasses
import re
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Iterable, Optional, Sequence, Tuple

from rich.console import RenderableType
from rich.segment import Segment
from rich.style import Style
from rich.text import Text
from typing_extensions import Literal

from textual._text_area_theme import TextAreaTheme
from textual._tree_sitter import TREE_SITTER, get_language
from textual.actions import SkipAction
from textual.cache import LRUCache
from textual.color import Color
from textual.content import Content
from textual.document._document import (
    Document,
    DocumentBase,
    EditResult,
    Location,
    Selection,
    _utf8_encode,
)
from textual.document._document_navigator import DocumentNavigator
from textual.document._edit import Edit
from textual.document._history import EditHistory
from textual.document._syntax_aware_document import (
    SyntaxAwareDocument,
    SyntaxAwareDocumentError,
)
from textual.document._wrapped_document import WrappedDocument
from textual.expand_tabs import expand_tabs_inline, expand_text_tabs_from_widths
from textual.screen import Screen
from textual.style import Style as ContentStyle

if TYPE_CHECKING:
    from tree_sitter import Language, Query

from textual import events, log
from textual._cells import cell_len, cell_width_to_column_index
from textual.binding import Binding
from textual.events import Message, MouseEvent
from textual.geometry import Offset, Region, Size, Spacing, clamp
from textual.reactive import Reactive, reactive
from textual.scroll_view import ScrollView
from textual.strip import Strip

_OPENING_BRACKETS = {"{": "}", "[": "]", "(": ")"}
_CLOSING_BRACKETS = {v: k for k, v in _OPENING_BRACKETS.items()}
_TREE_SITTER_PATH = Path(__file__).parent / "../tree-sitter/"
_HIGHLIGHTS_PATH = _TREE_SITTER_PATH / "highlights/"

StartColumn = int
EndColumn = Optional[int]
HighlightName = str
Highlight = Tuple[StartColumn, EndColumn, HighlightName]
"""A tuple representing a syntax highlight within one line."""

BUILTIN_LANGUAGES = [
    "python",
    "markdown",
    "json",
    "toml",
    "yaml",
    "html",
    "css",
    "javascript",
    "rust",
    "go",
    "regex",
    "sql",
    "java",
    "bash",
    "xml",
]
"""Languages that are included in the `syntax` extras."""


class ThemeDoesNotExist(Exception):
    """Raised when the user tries to use a theme which does not exist.
    This means a theme which is not builtin, or has not been registered.
    """


class LanguageDoesNotExist(Exception):
    """Raised when the user tries to use a language which does not exist.
    This means a language which is not builtin, or has not been registered.
    """


@dataclass
class TextAreaLanguage:
    """A container for a language which has been registered with the TextArea."""

    name: str
    """The name of the language"""

    language: "Language | None"
    """The tree-sitter language object if that has been overridden, or None if it is a built-in language."""

    highlight_query: str
    """The tree-sitter highlight query to use for syntax highlighting."""


class TextArea(ScrollView):
    DEFAULT_CSS = """\
TextArea {
    width: 1fr;
    height: 1fr;
    border: tall $border-blurred;
    padding: 0 1;
    color: $foreground;
    background: $surface;
    pointer: text;
    &.-textual-compact {
        border: none !important;
    }
    & .text-area--cursor {
        text-style: $input-cursor-text-style;
    }
    & .text-area--gutter {
        color: $foreground 40%;
    }

    & .text-area--cursor-gutter {
        color: $foreground 60%;
        background: $boost;
        text-style: bold;
    }

    & .text-area--cursor-line {
       background: $boost;
    }

    & .text-area--selection {
        background: $input-selection-background;
        color: $input-selection-foreground;
    }

    & .text-area--matching-bracket {
        background: $foreground 30%;
    }

    & .text-area--suggestion {
        color: $text-muted;
    }

    & .text-area--placeholder {
        color: $text 40%;
    }

    &:focus {
        border: tall $border;
    }

    &:ansi {
        .text-area--cursor {
            color: $input-cursor-foreground;
            background: $input-cursor-background;
            text-style: reverse;
        }
        & .text-area--selection {
            background: transparent;
            text-style: reverse;
        }
    }

    &:dark {
        .text-area--cursor {
            color: $input-cursor-foreground;
            background: $input-cursor-background;
        }
        &.-read-only .text-area--cursor {
            background: $warning-darken-1;
        }
    }

    &:light {
        .text-area--cursor {
            color: $text 90%;
            background: $foreground 70%;
        }
        &.-read-only .text-area--cursor {
            background: $warning-darken-1;
        }
    }    
}
"""

    COMPONENT_CLASSES: ClassVar[set[str]] = {
        "text-area--cursor",
        "text-area--gutter",
        "text-area--cursor-gutter",
        "text-area--cursor-line",
        "text-area--selection",
        "text-area--matching-bracket",
        "text-area--suggestion",
        "text-area--placeholder",
    }
    """
    `TextArea` offers some component classes which can be used to style aspects of the widget.

    Note that any attributes provided in the chosen `TextAreaTheme` will take priority here.

    | Class | Description |
    | :- | :- |
    | `text-area--cursor` | Target the cursor. |
    | `text-area--gutter` | Target the gutter (line number column). |
    | `text-area--cursor-gutter` | Target the gutter area of the line the cursor is on. |
    | `text-area--cursor-line` | Target the line the cursor is on. |
    | `text-area--selection` | Target the current selection. |
    | `text-area--matching-bracket` | Target matching brackets. |
    | `text-area--suggestion` | Target the text set in the `suggestion` reactive. |
    | `text-area--placeholder` | Target the placeholder text. |
    """

    BINDINGS = [
        # Cursor movement
        Binding(
            "up",
            "cursor_up",
            "Cursor up",
            show=False,
        ),
        Binding(
            "down",
            "cursor_down",
            "Cursor down",
            show=False,
        ),
        Binding(
            "left",
            "cursor_left",
            "Cursor left",
            show=False,
        ),
        Binding(
            "right",
            "cursor_right",
            "Cursor right",
            show=False,
        ),
        Binding(
            "ctrl+left",
            "cursor_word_left",
            "Cursor word left",
            show=False,
        ),
        Binding(
            "ctrl+right",
            "cursor_word_right",
            "Cursor word right",
            show=False,
        ),
        Binding(
            "home,ctrl+a",
            "cursor_line_start",
            "Cursor line start",
            show=False,
        ),
        Binding(
            "end,ctrl+e",
            "cursor_line_end",
            "Cursor line end",
            show=False,
        ),
        Binding(
            "pageup",
            "cursor_page_up",
            "Cursor page up",
            show=False,
        ),
        Binding(
            "pagedown",
            "cursor_page_down",
            "Cursor page down",
            show=False,
        ),
        # Making selections (generally holding the shift key and moving cursor)
        Binding(
            "ctrl+shift+left",
            "cursor_word_left(True)",
            "Cursor left word select",
            show=False,
        ),
        Binding(
            "ctrl+shift+right",
            "cursor_word_right(True)",
            "Cursor right word select",
            show=False,
        ),
        Binding(
            "shift+home",
            "cursor_line_start(True)",
            "Cursor line start select",
            show=False,
        ),
        Binding(
            "shift+end",
            "cursor_line_end(True)",
            "Cursor line end select",
            show=False,
        ),
        Binding(
            "shift+up",
            "cursor_up(True)",
            "Cursor up select",
            show=False,
        ),
        Binding(
            "shift+down",
            "cursor_down(True)",
            "Cursor down select",
            show=False,
        ),
        Binding(
            "shift+left",
            "cursor_left(True)",
            "Cursor left select",
            show=False,
        ),
        Binding(
            "shift+right",
            "cursor_right(True)",
            "Cursor right select",
            show=False,
        ),
        # Shortcut ways of making selections
        # Binding("f5", "select_word", "select word", show=False),
        Binding(
            "f6",
            "select_line",
            "Select line",
            show=False,
        ),
        Binding(
            "f7",
            "select_all",
            "Select all",
            show=False,
        ),
        # Deletion
        Binding(
            "backspace",
            "delete_left",
            "Delete character left",
            show=False,
        ),
        Binding(
            "ctrl+w,ctrl+backspace",
            "delete_word_left",
            "Delete left to start of word",
            show=False,
        ),
        Binding(
            "delete,ctrl+d",
            "delete_right",
            "Delete character right",
            show=False,
        ),
        Binding(
            "alt+delete",
            "delete_word_right",
            "Delete right to start of word",
            show=False,
        ),
        Binding(
            "ctrl+x,super+x",
            "cut",
            "Cut",
            show=False,
        ),
        Binding(
            "ctrl+c,super+c",
            "copy",
            "Copy",
            show=False,
        ),
        Binding(
            "ctrl+v",
            "paste",
            "Paste",
            show=False,
        ),
        Binding(
            "ctrl+u",
            "delete_to_start_of_line",
            "Delete to line start",
            show=False,
        ),
        Binding(
            "ctrl+k",
            "delete_to_end_of_line_or_delete_line",
            "Delete to line end",
            show=False,
        ),
        Binding(
            "ctrl+shift+k",
            "delete_line",
            "Delete line",
            show=False,
        ),
        Binding(
            "ctrl+z,super+z",
            "undo",
            "Undo",
            show=False,
        ),
        Binding(
            "ctrl+y,super+y",
            "redo",
            "Redo",
            show=False,
        ),
    ]
    """
    | Key(s)                 | Description                                  |
    | :-                     | :-                                           |
    | up                     | Move the cursor up.                          |
    | down                   | Move the cursor down.                        |
    | left                   | Move the cursor left.                        |
    | ctrl+left              | Move the cursor to the start of the word.    |
    | ctrl+shift+left        | Move the cursor to the start of the word and select.    |
    | right                  | Move the cursor right.                       |
    | ctrl+right             | Move the cursor to the end of the word.      |
    | ctrl+shift+right       | Move the cursor to the end of the word and select.      |
    | home,ctrl+a            | Move the cursor to the start of the line.    |
    | end,ctrl+e             | Move the cursor to the end of the line.      |
    | shift+home             | Move the cursor to the start of the line and select.      |
    | shift+end              | Move the cursor to the end of the line and select.      |
    | pageup                 | Move the cursor one page up.                 |
    | pagedown               | Move the cursor one page down.               |
    | shift+up               | Select while moving the cursor up.           |
    | shift+down             | Select while moving the cursor down.         |
    | shift+left             | Select while moving the cursor left.         |
    | shift+right            | Select while moving the cursor right.        |
    | backspace              | Delete character to the left of cursor.      |
    | ctrl+w,ctrl+backspace  | Delete from cursor to start of the word.     |
    | delete,ctrl+d          | Delete character to the right of cursor.     |
    | alt+delete             | Delete from cursor to end of the word.       |
    | ctrl+shift+k           | Delete the current line.                     |
    | ctrl+u                 | Delete from cursor to the start of the line. |
    | ctrl+k                 | Delete from cursor to the end of the line.   |
    | f6                     | Select the current line.                     |
    | f7                     | Select all text in the document.             |
    | ctrl+z,super+z         | Undo.                                        |
    | ctrl+y,super+y         | Redo.                                        |
    | ctrl+x,super+x         | Cut selection or line if no selection.       |
    | ctrl+c,super+c         | Copy selection to clipboard.                 |
    | ctrl+v,super+v         | Paste from clipboard.                        |
    """

    language: Reactive[str | None] = reactive(None, always_update=True, init=False)
    """The language to use.

    This must be set to a valid, non-None value for syntax highlighting to work.

    If the value is a string, a built-in language parser will be used if available.

    If you wish to use an unsupported language, you'll have to register
    it first using  [`TextArea.register_language`][textual.widgets._text_area.TextArea.register_language].
    """

    theme: Reactive[str] = reactive("css", always_update=True, init=False)
    """The name of the theme to use.

    Themes must be registered using  [`TextArea.register_theme`][textual.widgets._text_area.TextArea.register_theme] before they can be used.

    Syntax highlighting is only possible when the `language` attribute is set.
    """

    selection: Reactive[Selection] = reactive(
        Selection(), init=False, always_update=True
    )
    """The selection start and end locations (zero-based line_index, offset).

    This represents the cursor location and the current selection.

    The `Selection.end` always refers to the cursor location.

    If no text is selected, then `Selection.end == Selection.start` is True.

    The text selected in the document is available via the `TextArea.selected_text` property.
    """

    show_line_numbers: Reactive[bool] = reactive(False, init=False)
    """True to show the line number column on the left edge, otherwise False.

    Changing this value will immediately re-render the `TextArea`."""

    line_number_start: Reactive[int] = reactive(1, init=False)
    """The line number the first line should be."""

    indent_width: Reactive[int] = reactive(4, init=False)
    """The width of tabs or the multiple of spaces to align to on pressing the `tab` key.

    If the document currently open contains tabs that are currently visible on screen,
    altering this value will immediately change the display width of the visible tabs.
    """

    match_cursor_bracket: Reactive[bool] = reactive(True, init=False)
    """If the cursor is at a bracket, highlight the matching bracket (if found)."""

    cursor_blink: Reactive[bool] = reactive(True, init=False)
    """True if the cursor should blink."""

    soft_wrap: Reactive[bool] = reactive(True, init=False)
    """True if text should soft wrap."""

    read_only: Reactive[bool] = reactive(False)
    """True if the content is read-only.

    Read-only means end users cannot insert, delete or replace content.

    The document can still be edited programmatically via the API.
    """

    show_cursor: Reactive[bool] = reactive(True)
    """Show the cursor in read only mode?

    If `True`, the cursor will be visible when `read_only==True`.
    If `False`, the cursor will be hidden when `read_only==True`, and the TextArea will
    scroll like other containers.

    """

    compact: reactive[bool] = reactive(False, toggle_class="-textual-compact")
    """Enable compact display?"""

    highlight_cursor_line: reactive[bool] = reactive(True)
    """Highlight the line under the cursor?"""

    _cursor_visible: Reactive[bool] = reactive(False, repaint=False, init=False)
    """Indicates where the cursor is in the blink cycle. If it's currently
    not visible due to blinking, this is False."""

    suggestion: Reactive[str] = reactive("")
    """A suggestion for auto-complete (pressing right will insert it)."""

    hide_suggestion_on_blur: Reactive[bool] = reactive(True)
    """Hide suggestion when the TextArea does not have focus."""

    placeholder: Reactive[str | Content] = reactive("")
    """Text to show when the text area has no content."""

    @dataclass
    class Changed(Message):
        """Posted when the content inside the TextArea changes.

        Handle this message using the `on` decorator - `@on(TextArea.Changed)`
        or a method named `on_text_area_changed`.
        """

        text_area: TextArea
        """The `text_area` that sent this message."""

        @property
        def control(self) -> TextArea:
            """The `TextArea` that sent this message."""
            pass

    @dataclass
    class SelectionChanged(Message):
        """Posted when the selection changes.

        This includes when the cursor moves or when text is selected."""

        selection: Selection
        """The new selection."""
        text_area: TextArea
        """The `text_area` that sent this message."""


    def __init__(
        self,
        text: str = "",
        *,
        language: str | None = None,
        theme: str = "css",
        soft_wrap: bool = True,
        tab_behavior: Literal["focus", "indent"] = "focus",
        read_only: bool = False,
        show_cursor: bool = True,
        show_line_numbers: bool = False,
        line_number_start: int = 1,
        max_checkpoints: int = 50,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
        tooltip: RenderableType | None = None,
        compact: bool = False,
        highlight_cursor_line: bool = True,
        placeholder: str | Content = "",
    ) -> None:
        """Construct a new `TextArea`.

        Args:
            text: The initial text to load into the TextArea.
            language: The language to use.
            theme: The theme to use.
            soft_wrap: Enable soft wrapping.
            tab_behavior: If 'focus', pressing tab will switch focus. If 'indent', pressing tab will insert a tab.
            read_only: Enable read-only mode. This prevents edits using the keyboard.
            show_cursor: Show the cursor in read only mode (no effect otherwise).
            show_line_numbers: Show line numbers on the left edge.
            line_number_start: What line number to start on.
            max_checkpoints: The maximum number of undo history checkpoints to retain.
            name: The name of the `TextArea` widget.
            id: The ID of the widget, used to refer to it from Textual CSS.
            classes: One or more Textual CSS compatible class names separated by spaces.
            disabled: True if the widget is disabled.
            tooltip: Optional tooltip.
            compact: Enable compact style (without borders).
            highlight_cursor_line: Highlight the line under the cursor.
            placeholder: Text to display when there is not content.
        """
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)

        self._languages: dict[str, TextAreaLanguage] = {}
        """Maps language names to TextAreaLanguage. This is only used for languages
        registered by end-users using `TextArea.register_language`. If a user attempts
        to set `TextArea.language` to a language that is not registered here, we'll
        attempt to get it from the environment. If that fails, we'll fall back to
        plain text.
        """

        self._themes: dict[str, TextAreaTheme] = {}
        """Maps theme names to TextAreaTheme."""

        self.indent_type: Literal["tabs", "spaces"] = "spaces"
        """Whether to indent using tabs or spaces."""

        self._word_pattern = re.compile(r"(?<=\W)(?=\w)|(?<=\w)(?=\W)")
        """Compiled regular expression for what we consider to be a 'word'."""

        self.history: EditHistory = EditHistory(
            max_checkpoints=max_checkpoints,
            checkpoint_timer=2.0,
            checkpoint_max_characters=100,
        )
        """A stack (the end of the list is the top of the stack) for tracking edits."""

        self._selecting = False
        """True if we're currently selecting text using the mouse, otherwise False."""

        self._matching_bracket_location: Location | None = None
        """The location (row, column) of the bracket which matches the bracket the
        cursor is currently at. If the cursor is at a bracket, or there's no matching
        bracket, this will be `None`."""

        self._highlights: dict[int, list[Highlight]] = defaultdict(list)
        """Mapping line numbers to the set of highlights for that line."""

        self._highlight_query: "Query | None" = None
        """The query that's currently being used for highlighting."""

        self.document: DocumentBase = Document(text)
        """The document this widget is currently editing."""

        self.wrapped_document: WrappedDocument = WrappedDocument(self.document)
        """The wrapped view of the document."""

        self.navigator: DocumentNavigator = DocumentNavigator(self.wrapped_document)
        """Queried to determine where the cursor should move given a navigation
        action, accounting for wrapping etc."""

        self._cursor_offset = (0, 0)
        """The virtual offset of the cursor (not screen-space offset)."""

        self.set_reactive(TextArea.soft_wrap, soft_wrap)
        self.set_reactive(TextArea.read_only, read_only)
        self.set_reactive(TextArea.show_cursor, show_cursor)
        self.set_reactive(TextArea.show_line_numbers, show_line_numbers)
        self.set_reactive(TextArea.line_number_start, line_number_start)
        self.set_reactive(TextArea.highlight_cursor_line, highlight_cursor_line)
        self.set_reactive(TextArea.placeholder, placeholder)

        self._line_cache: LRUCache[tuple, Strip] = LRUCache(1024)

        self._set_document(text, language)

        self.language = language
        self.theme = theme

        self._theme: TextAreaTheme
        """The `TextAreaTheme` corresponding to the set theme name. When the `theme`
        reactive is set as a string, the watcher will update this attribute to the
        corresponding `TextAreaTheme` object."""

        self.tab_behavior = tab_behavior

        if tooltip is not None:
            self.tooltip = tooltip

        self.compact = compact

    @classmethod
    def code_editor(
        cls,
        text: str = "",
        *,
        language: str | None = None,
        theme: str = "monokai",
        soft_wrap: bool = False,
        tab_behavior: Literal["focus", "indent"] = "indent",
        read_only: bool = False,
        show_cursor: bool = True,
        show_line_numbers: bool = True,
        line_number_start: int = 1,
        max_checkpoints: int = 50,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
        tooltip: RenderableType | None = None,
        compact: bool = False,
        highlight_cursor_line: bool = True,
        placeholder: str | Content = "",
    ) -> TextArea:
        """Construct a new `TextArea` with sensible defaults for editing code.

        This instantiates a `TextArea` with line numbers enabled, soft wrapping
        disabled, "indent" tab behavior, and the "monokai" theme.

        Args:
            text: The initial text to load into the TextArea.
            language: The language to use.
            theme: The theme to use.
            soft_wrap: Enable soft wrapping.
            tab_behavior: If 'focus', pressing tab will switch focus. If 'indent', pressing tab will insert a tab.
            read_only: Enable read-only mode. This prevents edits using the keyboard.
            show_cursor: Show the cursor in read only mode (no effect otherwise).
            show_line_numbers: Show line numbers on the left edge.
            line_number_start: What line number to start on.
            name: The name of the `TextArea` widget.
            id: The ID of the widget, used to refer to it from Textual CSS.
            classes: One or more Textual CSS compatible class names separated by spaces.
            disabled: True if the widget is disabled.
            tooltip: Optional tooltip
            compact: Enable compact style (without borders).
            highlight_cursor_line: Highlight the line under the cursor.
        """
        return cls(
            text,
            language=language,
            theme=theme,
            soft_wrap=soft_wrap,
            tab_behavior=tab_behavior,
            read_only=read_only,
            show_cursor=show_cursor,
            show_line_numbers=show_line_numbers,
            line_number_start=line_number_start,
            max_checkpoints=max_checkpoints,
            name=name,
            id=id,
            classes=classes,
            disabled=disabled,
            tooltip=tooltip,
            compact=compact,
            highlight_cursor_line=highlight_cursor_line,
            placeholder=placeholder,
        )

    @staticmethod
    def _get_builtin_highlight_query(language_name: str) -> str:
        """Get the highlight query for a builtin language.

        Args:
            language_name: The name of the builtin language.

        Returns:
            The highlight query.
        """
        try:
            highlight_query_path = (
                Path(_HIGHLIGHTS_PATH.resolve()) / f"{language_name}.scm"
            )
            highlight_query = highlight_query_path.read_text()
        except OSError as error:
            log.warning(f"Unable to load highlight query. {error}")
            highlight_query = ""

        return highlight_query

    def notify_style_update(self) -> None:
        self._line_cache.clear()
        super().notify_style_update()

    def update_suggestion(self) -> None:
        """A hook to update the [`suggestion`][textual.widgets.TextArea.suggestion] attribute."""

    def check_consume_key(self, key: str, character: str | None = None) -> bool:
        """Check if the widget may consume the given key.

        As a textarea we are expecting to capture printable keys.

        Args:
            key: A key identifier.
            character: A character associated with the key, or `None` if there isn't one.

        Returns:
            `True` if the widget may capture the key in its `Key` message, or `False` if it won't.
        """
        pass

    def _build_highlight_map(self) -> None:
        """Query the tree for ranges to highlights, and update the internal highlights mapping."""
        self._line_cache.clear()
        highlights = self._highlights
        highlights.clear()
        if not self._highlight_query:
            return

        captures = self.document.query_syntax_tree(self._highlight_query)
        for highlight_name, nodes in captures.items():
            for node in nodes:
                node_start_row, node_start_column = node.start_point
                node_end_row, node_end_column = node.end_point

                if node_start_row == node_end_row:
                    highlight = (node_start_column, node_end_column, highlight_name)
                    highlights[node_start_row].append(highlight)
                else:
                    # Add the first line of the node range
                    highlights[node_start_row].append(
                        (node_start_column, None, highlight_name)
                    )

                    # Add the middle lines - entire row of this node is highlighted
                    for node_row in range(node_start_row + 1, node_end_row):
                        highlights[node_row].append((0, None, highlight_name))

                    # Add the last line of the node range
                    highlights[node_end_row].append(
                        (0, node_end_column, highlight_name)
                    )


    def _watch_selection(
        self, previous_selection: Selection, selection: Selection
    ) -> None:
        """When the cursor moves, scroll it into view."""
        pass



    def _recompute_cursor_offset(self):
        """Recompute the (x, y) coordinate of the cursor in the wrapped document."""
        self._cursor_offset = self.wrapped_document.location_to_offset(
            self.cursor_location
        )

    def find_matching_bracket(
        self, bracket: str, search_from: Location
    ) -> Location | None:
        """If the character is a bracket, find the matching bracket.

        Args:
            bracket: The character we're searching for the matching bracket of.
            search_from: The location to start the search.

        Returns:
            The `Location` of the matching bracket, or `None` if it's not found.
            If the character is not available for bracket matching, `None` is returned.
        """
        pass

    def _validate_selection(self, selection: Selection) -> Selection:
        """Clamp the selection to valid locations."""
        pass

    def _watch_language(self, language: str | None) -> None:
        """When the language is updated, update the type of document."""
        pass

    def _watch_show_line_numbers(self) -> None:
        """The line number gutter contributes to virtual size, so recalculate."""
        pass

    def _watch_line_number_start(self) -> None:
        """The line number gutter max size might change and contributes to virtual size, so recalculate."""
        pass

    def _watch_indent_width(self) -> None:
        """Changing width of tabs will change the document display width."""
        pass


    def _watch_theme(self, theme: str) -> None:
        """We set the styles on this widget when the theme changes, to ensure that
        if padding is applied, the colors match."""
        pass



    @property
    def available_themes(self) -> set[str]:
        """A list of the names of the themes available to the `TextArea`.

        The values in this list can be assigned `theme` reactive attribute of
        `TextArea`.

        You can retrieve the full specification for a theme by passing one of
        the strings from this list into `TextAreaTheme.get_by_name(theme_name: str)`.

        Alternatively, you can directly retrieve a list of `TextAreaTheme` objects
        (which contain the full theme specification) by calling
        `TextAreaTheme.builtin_themes()`.
        """
        pass

    def register_theme(self, theme: TextAreaTheme) -> None:
        """Register a theme for use by the `TextArea`.

        After registering a theme, you can set themes by assigning the theme
        name to the `TextArea.theme` reactive attribute. For example
        `text_area.theme = "my_custom_theme"` where `"my_custom_theme"` is the
        name of the theme you registered.

        If you supply a theme with a name that already exists that theme
        will be overwritten.
        """
        pass

    @property
    def available_languages(self) -> set[str]:
        """A set of the names of languages available to the `TextArea`.

        The values in this set can be assigned to the `language` reactive attribute
        of `TextArea`.

        The returned set contains the builtin languages installed with the syntax extras,
        plus those registered via the `register_language` method.
        """
        pass

    def register_language(
        self,
        name: str,
        language: "Language",
        highlight_query: str,
    ) -> None:
        """Register a language and corresponding highlight query.

        Calling this method does not change the language of the `TextArea`.
        On switching to this language (via the `language` reactive attribute),
        syntax highlighting will be performed using the given highlight query.

        If a string `name` is supplied for a builtin supported language, then
        this method will update the default highlight query for that language.

        Registering a language only registers it to this instance of `TextArea`.

        Args:
            name: The name of the language.
            language: A tree-sitter `Language` object.
            highlight_query: The highlight query to use for syntax highlighting this language.
        """
        pass

    def update_highlight_query(self, name: str, highlight_query: str) -> None:
        """Update the highlight query for an already registered language.

        Args:
            name: The name of the language.
            highlight_query: The highlight query to use for syntax highlighting this language.
        """
        pass

    def _set_document(self, text: str, language: str | None) -> None:
        """Construct and return an appropriate document.

        Args:
            text: The text of the document.
            language: The name of the language to use. This must correspond to a tree-sitter
                language available in the current environment (e.g. use `python` for `tree-sitter-python`).
                If None, the document will be treated as plain text.
        """
        self._highlight_query = None
        if TREE_SITTER and language:
            if language in self._languages:
                # User-registered languages take priority.
                highlight_query = self._languages[language].highlight_query
                document_language = self._languages[language].language
                if document_language is None:
                    document_language = get_language(language)
            else:
                # No user-registered language, so attempt to use a built-in language.
                highlight_query = self._get_builtin_highlight_query(language)
                document_language = get_language(language)

            # No built-in language, and no user-registered language: use plain text and warn.
            if document_language is None:
                raise LanguageDoesNotExist(
                    f"tree-sitter is available, but no built-in or user-registered language called {language!r}.\n"
                    f"Ensure the language is installed (e.g. `pip install tree-sitter-ruby`)\n"
                    f"Falling back to plain text."
                )
            else:
                document: DocumentBase
                try:
                    document = SyntaxAwareDocument(text, document_language)
                except SyntaxAwareDocumentError:
                    document = Document(text)
                    log.warning(
                        f"Parser not found for language {document_language!r}. Parsing disabled."
                    )
                else:
                    self._highlight_query = document.prepare_query(highlight_query)
        elif language and not TREE_SITTER:
            # User has supplied a language i.e. `TextArea(language="python")`, but they
            # don't have tree-sitter available in the environment. We fallback to plain text.
            log.warning(
                "tree-sitter not available in this environment. Parsing disabled.\n"
                "You may need to install the `syntax` extras alongside textual.\n"
                "Try `pip install 'textual[syntax]'` or '`poetry add textual[syntax]' to get started quickly.\n\n"
                "Alternatively, install tree-sitter manually (`pip install tree-sitter`) and then\n"
                "install the required language (e.g. `pip install tree-sitter-ruby`), then register it.\n"
                "and its highlight query using TextArea.register_language().\n\n"
                "Falling back to plain text for now."
            )
            document = Document(text)
        else:
            # tree-sitter is available, but the user has supplied None or "" for the language.
            # Use a regular plain-text document.
            document = Document(text)

        self.document = document
        self.wrapped_document = WrappedDocument(document, tab_width=self.indent_width)
        self.navigator = DocumentNavigator(self.wrapped_document)
        self._build_highlight_map()
        self.move_cursor((0, 0))
        self._rewrap_and_refresh_virtual_size()

    @property
    def _visible_line_indices(self) -> tuple[int, int]:
        """Return the visible line indices as a tuple (top, bottom).

        Returns:
            A tuple (top, bottom) indicating the top and bottom visible line indices.
        """
        pass



    def load_text(self, text: str) -> None:
        """Load text into the TextArea.

        This will replace the text currently in the TextArea and clear the edit history.

        Args:
            text: The text to load into the TextArea.
        """
        self.history.clear()
        self._set_document(text, self.language)
        self.post_message(self.Changed(self).set_sender(self))
        self.update_suggestion()



    @property
    def wrap_width(self) -> int:
        """The width which gets used when the document wraps.

        Accounts for gutter, scrollbars, etc.
        """
        pass

    def _rewrap_and_refresh_virtual_size(self) -> None:
        self.wrapped_document.wrap(self.wrap_width, tab_width=self.indent_width)
        self._line_cache.clear()
        self._refresh_size()

    @property
    def is_syntax_aware(self) -> bool:
        """True if the TextArea is currently syntax aware - i.e. it's parsing document content."""
        pass

    def _yield_character_locations(
        self, start: Location
    ) -> Iterable[tuple[str, Location]]:
        """Yields character locations starting from the given location.

        Does not yield location of line separator characters like `\\n`.

        Args:
            start: The location to start yielding from.

        Returns:
            Yields tuples of (character, (row, column)).
        """
        pass


    def _refresh_size(self) -> None:
        """Update the virtual size of the TextArea."""
        if self.soft_wrap:
            self.virtual_size = Size(0, self.wrapped_document.height)
        else:
            # +1 width to make space for the cursor resting at the end of the line
            width, height = self.document.get_size(self.indent_width)
            self.virtual_size = Size(width + self.gutter_width + 1, height)
        self._refresh_scrollbars()

    @property
    def _draw_cursor(self) -> bool:
        """Draw the cursor?"""
        pass

    @property
    def _has_cursor(self) -> bool:
        """Is there a usable cursor?"""
        pass

    def get_line(self, line_index: int) -> Text:
        """Retrieve the line at the given line index.

        You can stylize the Text object returned here to apply additional
        styling to TextArea content.

        Args:
            line_index: The index of the line.

        Returns:
            A `rich.Text` object containing the requested line.
        """
        line_string = self.document.get_line(line_index)
        return Text(line_string, end="", no_wrap=True)

    def render_lines(self, crop: Region) -> list[Strip]:
        theme = self._theme
        if theme:
            theme.apply_css(self)
        return super().render_lines(crop)

    def render_line(self, y: int) -> Strip:
        """Render a single line of the TextArea. Called by Textual.

        Args:
            y: Y Coordinate of line relative to the widget region.

        Returns:
            A rendered line.
        """

        if not self.text and self.placeholder:
            placeholder_lines = Content.from_text(self.placeholder).wrap(
                self.content_size.width
            )
            if y < len(placeholder_lines):
                style = self.get_visual_style("text-area--placeholder")
                content = placeholder_lines[y].stylize(style)
                if self._draw_cursor and y == 0:
                    theme = self._theme
                    cursor_style = theme.cursor_style if theme else None
                    if cursor_style:
                        content = content.stylize(
                            ContentStyle.from_rich_style(cursor_style), 0, 1
                        )
                return Strip(
                    content.render_segments(self.visual_style), content.cell_length
                )

        scroll_x, scroll_y = self.scroll_offset
        absolute_y = scroll_y + y
        selection = self.selection
        _, cursor_y = self._cursor_offset
        cache_key = (
            self.size,
            scroll_x,
            absolute_y,
            (
                selection
                if selection.contains_line(absolute_y) or self.soft_wrap
                else selection.end[0] == absolute_y
            ),
            (
                selection.end
                if (
                    self._cursor_visible
                    and self.cursor_blink
                    and absolute_y == cursor_y
                )
                else None
            ),
            self.theme,
            self._matching_bracket_location,
            self.match_cursor_bracket,
            self.soft_wrap,
            self.show_line_numbers,
            self.read_only,
            self.show_cursor,
            self.suggestion,
        )
        if (cached_line := self._line_cache.get(cache_key)) is not None:
            return cached_line
        line = self._render_line(y)
        self._line_cache[cache_key] = line
        return line

    def _render_line(self, y: int) -> Strip:
        """Render a single line of the TextArea. Called by Textual.

        Args:
            y: Y Coordinate of line relative to the widget region.

        Returns:
            A rendered line.
        """
        theme = self._theme
        base_style = (
            theme.base_style
            if theme and theme.base_style is not None
            else self.rich_style
        )

        wrapped_document = self.wrapped_document
        scroll_x, scroll_y = self.scroll_offset

        # Account for how much the TextArea is scrolled.
        y_offset = y + scroll_y

        # If we're beyond the height of the document, render blank lines
        out_of_bounds = y_offset >= wrapped_document.height

        if out_of_bounds:
            return Strip.blank(self.size.width, base_style)

        # Get the line corresponding to this offset
        try:
            line_info = wrapped_document._offset_to_line_info[y_offset]
        except IndexError:
            line_info = None

        if line_info is None:
            return Strip.blank(self.size.width, base_style)

        line_index, section_offset = line_info

        line = self.get_line(line_index)
        line_character_count = len(line)
        line.tab_size = self.indent_width
        line.set_length(line_character_count + 1)  # space at end for cursor
        virtual_width, _virtual_height = self.virtual_size

        selection = self.selection
        start, end = selection
        cursor_row, cursor_column = end

        selection_top, selection_bottom = sorted(selection)
        selection_top_row, selection_top_column = selection_top
        selection_bottom_row, selection_bottom_column = selection_bottom

        highlight_cursor_line = self.highlight_cursor_line and self._has_cursor
        cursor_line_style = (
            theme.cursor_line_style if (theme and highlight_cursor_line) else None
        )
        has_cursor = self._has_cursor

        if has_cursor and cursor_line_style and cursor_row == line_index:
            line.stylize(cursor_line_style)

        # Selection styling
        if start != end and selection_top_row <= line_index <= selection_bottom_row:
            # If this row intersects with the selection range
            selection_style = theme.selection_style if theme else None
            cursor_row, _ = end
            if selection_style:
                if line_character_count == 0 and line_index != cursor_row:
                    # A simple highlight to show empty lines are included in the selection
                    line.plain = "▌"
                    line.stylize(Style(color=selection_style.bgcolor))
                else:
                    if line_index == selection_top_row == selection_bottom_row:
                        # Selection within a single line
                        line.stylize(
                            selection_style,
                            start=selection_top_column,
                            end=selection_bottom_column,
                        )
                    else:
                        # Selection spanning multiple lines
                        if line_index == selection_top_row:
                            line.stylize(
                                selection_style,
                                start=selection_top_column,
                                end=line_character_count,
                            )
                        elif line_index == selection_bottom_row:
                            line.stylize(selection_style, end=selection_bottom_column)
                        else:
                            line.stylize(selection_style, end=line_character_count)

        highlights = self._highlights
        if highlights and theme:
            line_bytes = _utf8_encode(line.plain)
            byte_to_codepoint = build_byte_to_codepoint_dict(line_bytes)
            get_highlight_from_theme = theme.syntax_styles.get
            line_highlights = highlights[line_index]
            for highlight_start, highlight_end, highlight_name in line_highlights:
                node_style = get_highlight_from_theme(highlight_name)
                if node_style is not None:
                    line.stylize(
                        node_style,
                        byte_to_codepoint.get(highlight_start, 0),
                        byte_to_codepoint.get(highlight_end) if highlight_end else None,
                    )

        # Highlight the cursor
        matching_bracket = self._matching_bracket_location
        match_cursor_bracket = self.match_cursor_bracket
        draw_matched_brackets = (
            has_cursor
            and match_cursor_bracket
            and matching_bracket is not None
            and start == end
        )

        if cursor_row == line_index:
            draw_cursor = self._draw_cursor
            if draw_matched_brackets:
                matching_bracket_style = theme.bracket_matching_style if theme else None
                if matching_bracket_style:
                    line.stylize(
                        matching_bracket_style,
                        cursor_column,
                        cursor_column + 1,
                    )

            if self.suggestion and (self.has_focus or not self.hide_suggestion_on_blur):
                suggestion_style = self.get_component_rich_style(
                    "text-area--suggestion"
                )
                line = Text.assemble(
                    line[:cursor_column],
                    (self.suggestion, suggestion_style),
                    line[cursor_column:],
                )

            if draw_cursor:
                cursor_style = theme.cursor_style if theme else None
                if cursor_style:
                    line.stylize(cursor_style, cursor_column, cursor_column + 1)

        # Highlight the partner opening/closing bracket.
        if draw_matched_brackets:
            # mypy doesn't know matching bracket is guaranteed to be non-None
            assert matching_bracket is not None
            bracket_match_row, bracket_match_column = matching_bracket
            if theme and bracket_match_row == line_index:
                matching_bracket_style = theme.bracket_matching_style
                if matching_bracket_style:
                    line.stylize(
                        matching_bracket_style,
                        bracket_match_column,
                        bracket_match_column + 1,
                    )

        # Build the gutter text for this line
        gutter_width = self.gutter_width
        if self.show_line_numbers:
            if cursor_row == line_index and highlight_cursor_line:
                gutter_style = theme.cursor_line_gutter_style
            else:
                gutter_style = theme.gutter_style

            gutter_width_no_margin = gutter_width - 2
            gutter_content = (
                str(line_index + self.line_number_start) if section_offset == 0 else ""
            )
            gutter = [
                Segment(f"{gutter_content:>{gutter_width_no_margin}}  ", gutter_style)
            ]
        else:
            gutter = []

        # TODO: Lets not apply the division each time through render_line.
        #  We should cache sections with the edit counts.
        wrap_offsets = wrapped_document.get_offsets(line_index)
        if wrap_offsets:
            sections = line.divide(wrap_offsets)  # TODO cache result with edit count
            line = sections[section_offset]
            line_tab_widths = wrapped_document.get_tab_widths(line_index)
            line.end = ""

            # Get the widths of the tabs corresponding only to the section of the
            # line that is currently being rendered. We don't care about tabs in
            # other sections of the same line.

            # Count the tabs before this section.
            tabs_before = 0
            for section_index in range(section_offset):
                tabs_before += sections[section_index].plain.count("\t")

            # Count the tabs in this section.
            tabs_within = line.plain.count("\t")
            section_tab_widths = line_tab_widths[
                tabs_before : tabs_before + tabs_within
            ]
            line = expand_text_tabs_from_widths(line, section_tab_widths)
        else:
            line.expand_tabs(self.indent_width)

        base_width = (
            self.scrollable_content_region.size.width
            if self.soft_wrap
            else max(virtual_width, self.region.size.width)
        )
        target_width = base_width - self.gutter_width

        # Crop the line to show only the visible part (some may be scrolled out of view)
        console = self.app.console
        text_strip = Strip(line.render(console), cell_length=line.cell_len)
        if not self.soft_wrap:
            text_strip = text_strip.crop(scroll_x, scroll_x + virtual_width)

        # Stylize the line the cursor is currently on.
        if cursor_row == line_index and self.highlight_cursor_line:
            line_style = cursor_line_style
        else:
            line_style = theme.base_style if theme else None

        text_strip = text_strip.extend_cell_length(target_width, line_style)
        if gutter:
            strip = Strip.join([Strip(gutter, cell_length=gutter_width), text_strip])
        else:
            strip = text_strip

        return strip.apply_style(base_style)

    @property
    def text(self) -> str:
        """The entire text content of the document."""
        pass

    @text.setter
    def text(self, value: str) -> None:
        """Replace the text currently in the TextArea. This is an alias of `load_text`.

        Setting this value will clear the edit history.

        Args:
            value: The text to load into the TextArea.
        """
        pass

    @property
    def selected_text(self) -> str:
        """The text between the start and end points of the current selection."""
        pass

    @property
    def matching_bracket_location(self) -> Location | None:
        """The location of the matching bracket, if there is one."""
        pass

    def get_text_range(self, start: Location, end: Location) -> str:
        """Get the text between a start and end location.

        Args:
            start: The start location.
            end: The end location.

        Returns:
            The text between start and end.
        """
        start, end = sorted((start, end))
        return self.document.get_text_range(start, end)

    def edit(self, edit: Edit) -> EditResult:
        """Perform an Edit.

        Args:
            edit: The Edit to perform.

        Returns:
            Data relating to the edit that may be useful. The data returned
            may be different depending on the edit performed.
        """
        if self.suggestion.startswith(edit.text):
            self.suggestion = self.suggestion[len(edit.text) :]
        else:
            self.suggestion = ""
        old_gutter_width = self.gutter_width
        result = edit.do(self)
        self.history.record(edit)
        new_gutter_width = self.gutter_width

        if old_gutter_width != new_gutter_width:
            self.wrapped_document.wrap(self.wrap_width, self.indent_width)
        else:
            self.wrapped_document.wrap_range(
                edit.top,
                edit.bottom,
                result.end_location,
            )

        edit.after(self)
        self._build_highlight_map()
        self.post_message(self.Changed(self))
        self.update_suggestion()
        self._refresh_size()
        return result

    def undo(self) -> None:
        """Undo the edits since the last checkpoint (the most recent batch of edits)."""
        pass

    def action_undo(self) -> None:
        """Undo the edits since the last checkpoint (the most recent batch of edits)."""
        pass

    def redo(self) -> None:
        """Redo the most recently undone batch of edits."""
        pass

    def action_redo(self) -> None:
        """Redo the most recently undone batch of edits."""
        pass

    def _undo_batch(self, edits: Sequence[Edit]) -> None:
        """Undo a batch of Edits.

        The sequence must be chronologically ordered by edit time.

        There must be no edits missing from the sequence, or the resulting content
        will be incorrect.

        Args:
            edits: The edits to undo, in the order they were originally performed.
        """
        pass

    def _redo_batch(self, edits: Sequence[Edit]) -> None:
        """Redo a batch of Edits in order.

        The sequence must be chronologically ordered by edit time.

        Edits are applied from the start of the sequence to the end.

        There must be no edits missing from the sequence, or the resulting content
        will be incorrect.

        Args:
            edits: The edits to redo.
        """
        pass

    async def _on_key(self, event: events.Key) -> None:
        """Handle key presses which correspond to document inserts."""
        pass

    def _find_columns_to_next_tab_stop(self) -> int:
        """Get the location of the next tab stop after the cursors position on the current line.

        If the cursor is already at a tab stop, this returns the *next* tab stop location.

        Returns:
            The number of cells to the next tab stop from the current cursor column.
        """
        pass

    def get_target_document_location(self, event: MouseEvent) -> Location:
        """Given a MouseEvent, return the row and column offset of the event in document-space.

        Args:
            event: The MouseEvent.

        Returns:
            The location of the mouse event within the document.
        """
        pass

    @property
    def gutter_width(self) -> int:
        """The width of the gutter (the left column containing line numbers).

        Returns:
            The cell-width of the line number column. If `show_line_numbers` is `False` returns 0.
        """
        pass


    def _toggle_cursor_blink_visible(self) -> None:
        """Toggle visibility of the cursor for the purposes of 'cursor blink'."""
        pass

    def _watch__cursor_visible(self) -> None:
        """When the cursor visibility is toggled, ensure the row is refreshed."""
        pass

    def _restart_blink(self) -> None:
        """Reset the cursor blink timer."""
        if self.cursor_blink:
            self._cursor_visible = True
            if self.is_mounted:
                self.blink_timer.reset()

    def _pause_blink(self, visible: bool = True) -> None:
        """Pause the cursor blinking but ensure it stays visible."""
        pass

    async def _on_mouse_down(self, event: events.MouseDown) -> None:
        """Update the cursor position, and begin a selection using the mouse."""
        pass

    async def _on_mouse_move(self, event: events.MouseMove) -> None:
        """Handles click and drag to expand and contract the selection."""
        pass

    def _end_mouse_selection(self) -> None:
        """Finalize the selection that has been made using the mouse."""
        pass

    async def _on_mouse_up(self, event: events.MouseUp) -> None:
        """Finalize the selection that has been made using the mouse."""
        pass

    async def _on_hide(self, event: events.Hide) -> None:
        """Finalize the selection that has been made using the mouse when the widget is hidden."""
        pass

    async def _on_paste(self, event: events.Paste) -> None:
        """When a paste occurs, insert the text from the paste event into the document."""
        pass

    def cell_width_to_column_index(self, cell_width: int, row_index: int) -> int:
        """Return the column that the cell width corresponds to on the given row.

        Args:
            cell_width: The cell width to convert.
            row_index: The index of the row to examine.

        Returns:
            The column corresponding to the cell width on that row.
        """
        line = self.document[row_index]
        return cell_width_to_column_index(line, cell_width, self.indent_width)

    def clamp_visitable(self, location: Location) -> Location:
        """Clamp the given location to the nearest visitable location.

        Args:
            location: The location to clamp.

        Returns:
            The nearest location that we could conceivably navigate to using the cursor.
        """
        pass

    # --- Cursor/selection utilities
    def scroll_cursor_visible(
        self, center: bool = False, animate: bool = False
    ) -> Offset:
        """Scroll the `TextArea` such that the cursor is visible on screen.

        Args:
            center: True if the cursor should be scrolled to the center.
            animate: True if we should animate while scrolling.

        Returns:
            The offset that was scrolled to bring the cursor into view.
        """
        if not self._has_cursor:
            return Offset(0, 0)
        self._recompute_cursor_offset()

        x, y = self._cursor_offset
        scroll_offset = self.scroll_to_region(
            Region(x, y, width=3, height=1),
            spacing=Spacing(right=self.gutter_width),
            animate=animate,
            force=True,
            center=center,
        )
        return scroll_offset

    def move_cursor(
        self,
        location: Location,
        select: bool = False,
        center: bool = False,
        record_width: bool = True,
    ) -> None:
        """Move the cursor to a location.

        Args:
            location: The location to move the cursor to.
            select: If True, select text between the old and new location.
            center: If True, scroll such that the cursor is centered.
            record_width: If True, record the cursor column cell width after navigating
                so that we jump back to the same width the next time we move to a row
                that is wide enough.
        """
        if not self._has_cursor:
            return
        if select:
            start, _end = self.selection
            self.selection = Selection(start, location)
        else:
            self.selection = Selection.cursor(location)

        if record_width:
            self.record_cursor_width()

        if center:
            self.scroll_cursor_visible(center)

        self.history.checkpoint()

    def move_cursor_relative(
        self,
        rows: int = 0,
        columns: int = 0,
        select: bool = False,
        center: bool = False,
        record_width: bool = True,
    ) -> None:
        """Move the cursor relative to its current location in document-space.

        Args:
            rows: The number of rows to move down by (negative to move up)
            columns:  The number of columns to move right by (negative to move left)
            select: If True, select text between the old and new location.
            center: If True, scroll such that the cursor is centered.
            record_width: If True, record the cursor column cell width after navigating
                so that we jump back to the same width the next time we move to a row
                that is wide enough.
        """
        pass

    def select_line(self, index: int) -> None:
        """Select all the text in the specified line.

        Args:
            index: The index of the line to select (starting from 0).
        """
        pass

    def action_select_line(self) -> None:
        """Select all the text on the current line."""
        pass

    def select_all(self) -> None:
        """Select all of the text in the `TextArea`."""
        pass

    def action_select_all(self) -> None:
        """Select all the text in the document."""
        pass

    @property
    def cursor_location(self) -> Location:
        """The current location of the cursor in the document.

        This is a utility for accessing the `end` of `TextArea.selection`.
        """
        pass

    @cursor_location.setter
    def cursor_location(self, location: Location) -> None:
        """Set the cursor_location to a new location.

        If a selection is in progress, the anchor point will remain.
        """
        pass

    @property
    def cursor_screen_offset(self) -> Offset:
        """The offset of the cursor relative to the screen."""
        pass

    @property
    def cursor_at_first_line(self) -> bool:
        """True if and only if the cursor is on the first line."""
        pass

    @property
    def cursor_at_last_line(self) -> bool:
        """True if and only if the cursor is on the last line."""
        pass

    @property
    def cursor_at_start_of_line(self) -> bool:
        """True if and only if the cursor is at column 0."""
        pass

    @property
    def cursor_at_end_of_line(self) -> bool:
        """True if and only if the cursor is at the end of a row."""
        pass

    @property
    def cursor_at_start_of_text(self) -> bool:
        """True if and only if the cursor is at location (0, 0)"""
        pass

    @property
    def cursor_at_end_of_text(self) -> bool:
        """True if and only if the cursor is at the very end of the document."""
        pass

    # ------ Cursor movement actions
    def action_cursor_left(self, select: bool = False) -> None:
        """Move the cursor one location to the left.

        If the cursor is at the left edge of the document, try to move it to
        the end of the previous line.

        If text is selected, move the cursor to the start of the selection.

        Args:
            select: If True, select the text while moving.
        """
        if not self._has_cursor:
            self.scroll_left()
            return
        target = (
            self.get_cursor_left_location()
            if select or self.selection.is_empty
            else min(*self.selection)
        )
        self.move_cursor(target, select=select)

    def get_cursor_left_location(self) -> Location:
        """Get the location the cursor will move to if it moves left.

        Returns:
            The location of the cursor if it moves left.
        """
        return self.navigator.get_location_left(self.cursor_location)

    def action_cursor_right(self, select: bool = False) -> None:
        """Move the cursor one location to the right.

        If the cursor is at the end of a line, attempt to go to the start of the next line.

        If text is selected, move the cursor to the end of the selection.

        Args:
            select: If True, select the text while moving.
        """
        pass

    def get_cursor_right_location(self) -> Location:
        """Get the location the cursor will move to if it moves right.

        Returns:
            the location the cursor will move to if it moves right.
        """
        pass

    def action_cursor_down(self, select: bool = False) -> None:
        """Move the cursor down one cell.

        Args:
            select: If True, select the text while moving.
        """
        pass

    def get_cursor_down_location(self) -> Location:
        """Get the location the cursor will move to if it moves down.

        Returns:
            The location the cursor will move to if it moves down.
        """
        pass

    def action_cursor_up(self, select: bool = False) -> None:
        """Move the cursor up one cell.

        Args:
            select: If True, select the text while moving.
        """
        pass

    def get_cursor_up_location(self) -> Location:
        """Get the location the cursor will move to if it moves up.

        Returns:
            The location the cursor will move to if it moves up.
        """
        pass

    def action_cursor_line_end(self, select: bool = False) -> None:
        """Move the cursor to the end of the line."""
        pass

    def get_cursor_line_end_location(self) -> Location:
        """Get the location of the end of the current line.

        Returns:
            The (row, column) location of the end of the cursors current line.
        """
        pass

    def action_cursor_line_start(self, select: bool = False) -> None:
        """Move the cursor to the start of the line."""
        pass

    def get_cursor_line_start_location(self, smart_home: bool = False) -> Location:
        """Get the location of the start of the current line.

        Args:
            smart_home: If True, use "smart home key" behavior - go to the first
                non-whitespace character on the line, and if already there, go to
                offset 0. Smart home only works when wrapping is disabled.

        Returns:
            The (row, column) location of the start of the cursors current line.
        """
        pass

    def action_cursor_word_left(self, select: bool = False) -> None:
        """Move the cursor left by a single word, skipping trailing whitespace.

        Args:
            select: Whether to select while moving the cursor.
        """
        pass

    def get_cursor_word_left_location(self) -> Location:
        """Get the location the cursor will jump to if it goes 1 word left.

        Returns:
            The location the cursor will jump on "jump word left".
        """
        pass

    def action_cursor_word_right(self, select: bool = False) -> None:
        """Move the cursor right by a single word, skipping leading whitespace."""
        pass

    def get_cursor_word_right_location(self) -> Location:
        """Get the location the cursor will jump to if it goes 1 word right.

        Returns:
            The location the cursor will jump on "jump word right".
        """
        pass

    def action_cursor_page_up(self) -> None:
        """Move the cursor and scroll up one page."""
        pass

    def action_cursor_page_down(self) -> None:
        """Move the cursor and scroll down one page."""
        pass

    def get_column_width(self, row: int, column: int) -> int:
        """Get the cell offset of the column from the start of the row.

        Args:
            row: The row index.
            column: The column index (codepoint offset from start of row).

        Returns:
            The cell width of the column relative to the start of the row.
        """
        pass

    def record_cursor_width(self) -> None:
        """Record the current cell width of the cursor.

        This is used where we navigate up and down through rows.
        If we're in the middle of a row, and go down to a row with no
        content, then we go down to another row, we want our cursor to
        jump back to the same offset that we were originally at.
        """
        cursor_x_offset, _ = self.wrapped_document.location_to_offset(
            self.cursor_location
        )
        self.navigator.last_x_offset = cursor_x_offset

    # --- Editor operations
    def insert(
        self,
        text: str,
        location: Location | None = None,
        *,
        maintain_selection_offset: bool = True,
    ) -> EditResult:
        """Insert text into the document.

        Args:
            text: The text to insert.
            location: The location to insert text, or None to use the cursor location.
            maintain_selection_offset: If True, the active Selection will be updated
                such that the same text is selected before and after the selection,
                if possible. Otherwise, the cursor will jump to the end point of the
                edit.

        Returns:
            An `EditResult` containing information about the edit.
        """
        if len(text) > 1:
            self._restart_blink()
        if location is None:
            location = self.cursor_location
        return self.edit(Edit(text, location, location, maintain_selection_offset))

    def delete(
        self,
        start: Location,
        end: Location,
        *,
        maintain_selection_offset: bool = True,
    ) -> EditResult:
        """Delete the text between two locations in the document.

        Args:
            start: The start location.
            end: The end location.
            maintain_selection_offset: If True, the active Selection will be updated
                such that the same text is selected before and after the selection,
                if possible. Otherwise, the cursor will jump to the end point of the
                edit.

        Returns:
            An `EditResult` containing information about the edit.
        """
        return self.edit(Edit("", start, end, maintain_selection_offset))

    def replace(
        self,
        insert: str,
        start: Location,
        end: Location,
        *,
        maintain_selection_offset: bool = True,
    ) -> EditResult:
        """Replace text in the document with new text.

        Args:
            insert: The text to insert.
            start: The start location
            end: The end location.
            maintain_selection_offset: If True, the active Selection will be updated
                such that the same text is selected before and after the selection,
                if possible. Otherwise, the cursor will jump to the end point of the
                edit.

        Returns:
            An `EditResult` containing information about the edit.
        """
        return self.edit(Edit(insert, start, end, maintain_selection_offset))

    def clear(self) -> EditResult:
        """Delete all text from the document.

        Returns:
            An EditResult relating to the deletion of all content.
        """
        return self.delete((0, 0), self.document.end, maintain_selection_offset=False)

    def _delete_via_keyboard(
        self,
        start: Location,
        end: Location,
    ) -> EditResult | None:
        """Handle a deletion performed using a keyboard (as opposed to the API).

        Args:
            start: The start location of the text to delete.
            end: The end location of the text to delete.

        Returns:
            An EditResult or None if no edit was performed (e.g. on read-only mode).
        """
        pass

    def _replace_via_keyboard(
        self,
        insert: str,
        start: Location,
        end: Location,
    ) -> EditResult | None:
        """Handle a replacement performed using a keyboard (as opposed to the API).

        Args:
            insert: The text to insert into the document.
            start: The start location of the text to replace.
            end: The end location of the text to replace.

        Returns:
            An EditResult or None if no edit was performed (e.g. on read-only mode).
        """
        pass

    def action_delete_left(self) -> None:
        """Deletes the character to the left of the cursor and updates the cursor location.

        If there's a selection, then the selected range is deleted."""
        pass

    def action_delete_right(self) -> None:
        """Deletes the character to the right of the cursor and keeps the cursor at the same location.

        If there's a selection, then the selected range is deleted."""
        pass

    def action_delete_line(self) -> None:
        """Deletes the lines which intersect with the selection."""
        pass

    def _delete_cursor_line(self) -> EditResult | None:
        """Deletes the line (including the line terminator) that the cursor is on."""
        pass

    def action_cut(self) -> None:
        """Cut text (remove and copy to clipboard)."""
        pass

    def action_copy(self) -> None:
        """Copy selection to clipboard."""
        pass

    def action_paste(self) -> None:
        """Paste from local clipboard."""
        pass

    def action_delete_to_start_of_line(self) -> None:
        """Deletes from the cursor location to the start of the line."""
        pass

    def action_delete_to_end_of_line(self) -> None:
        """Deletes from the cursor location to the end of the line."""
        pass

    async def action_delete_to_end_of_line_or_delete_line(self) -> None:
        """Deletes from the cursor location to the end of the line, or deletes the line.

        The line will be deleted if the line is empty.
        """
        pass

    def action_delete_word_left(self) -> None:
        """Deletes the word to the left of the cursor and updates the cursor location."""
        pass

    def action_delete_word_right(self) -> None:
        """Deletes the word to the right of the cursor and keeps the cursor at the same location.

        Note that the location that we delete to using this action is not the same
        as the location we move to when we move the cursor one word to the right.
        This action does not skip leading whitespace, whereas cursor movement does.
        """
        pass


@lru_cache(maxsize=128)
def build_byte_to_codepoint_dict(data: bytes) -> dict[int, int]:
    """Build a mapping of utf-8 byte offsets to codepoint offsets for the given data.

    Args:
        data: utf-8 bytes.

    Returns:
        A `dict[int, int]` mapping byte indices to codepoint indices within `data`.
    """
    byte_to_codepoint: dict[int, int] = {}
    current_byte_offset = 0
    code_point_offset = 0

    while current_byte_offset < len(data):
        byte_to_codepoint[current_byte_offset] = code_point_offset
        first_byte = data[current_byte_offset]

        # Single-byte character
        if (first_byte & 0b10000000) == 0:
            current_byte_offset += 1
        # 2-byte character
        elif (first_byte & 0b11100000) == 0b11000000:
            current_byte_offset += 2
        # 3-byte character
        elif (first_byte & 0b11110000) == 0b11100000:
            current_byte_offset += 3
        # 4-byte character
        elif (first_byte & 0b11111000) == 0b11110000:
            current_byte_offset += 4
        else:
            raise ValueError(f"Invalid UTF-8 byte: {first_byte}")

        code_point_offset += 1

    # Mapping for the end of the string
    byte_to_codepoint[current_byte_offset] = code_point_offset
    return byte_to_codepoint
