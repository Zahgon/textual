from __future__ import annotations

import re
from typing import TYPE_CHECKING, NamedTuple

import rich.repr
from rich.console import Group, RenderableType
from rich.highlighter import ReprHighlighter
from rich.padding import Padding
from rich.panel import Panel
from rich.text import Text

from textual.css._error_tools import friendly_list
from textual.css.constants import VALID_PSEUDO_CLASSES
from textual.suggestions import get_suggestion

if TYPE_CHECKING:
    from textual.css.types import CSSLocation


class TokenError(Exception):
    """Error raised when the CSS cannot be tokenized (syntax error)."""

    def __init__(
        self,
        read_from: CSSLocation,
        code: str,
        start: tuple[int, int],
        message: str,
        end: tuple[int, int] | None = None,
    ) -> None:
        """
        Args:
            read_from: The location where the CSS was read from.
            code: The code being parsed.
            start: Line and column number of the error (1-indexed).
            message: A message associated with the error.
            end: End location of token (1-indexed), or None if not known.
        """

        self.read_from = read_from
        self.code = code
        self.start = start
        self.end = end or start
        super().__init__(message)

    def _get_snippet(self) -> Panel:
        """Get a short snippet of code around a given line number.

        Returns:
            A renderable.
        """
        pass

    def __rich__(self) -> RenderableType:
        highlighter = ReprHighlighter()
        errors: list[RenderableType] = []

        message = str(self)
        errors.append(Text(" Error in stylesheet:", style="bold red"))

        line_no, col_no = self.start

        path, widget_variable = self.read_from
        if widget_variable:
            css_location = f" {path}, {widget_variable}:{line_no}:{col_no}"
        else:
            css_location = f" {path}:{line_no}:{col_no}"
        errors.append(highlighter(css_location))
        errors.append(self._get_snippet())

        final_message = "\n".join(
            f"• {message_part.strip()}" for message_part in message.split(";")
        )
        errors.append(
            Padding(
                highlighter(
                    Text(final_message, "red"),
                ),
                pad=(0, 1),
            )
        )

        return Group(*errors)


class UnexpectedEnd(TokenError):
    """Indicates that the text being tokenized ended prematurely."""


@rich.repr.auto
class Expect:
    """Object that describes the format of tokens."""

    def __init__(self, description: str, **tokens: str) -> None:
        """Create Expect object.

        Args:
            description: Description of this class of tokens, used in errors.
        """
        self.description = f"Expected {description}"
        self.names = list(tokens.keys())
        self.regexes = list(tokens.values())
        self._regex = re.compile(
            "("
            + "|".join(f"(?P<{name}>{regex})" for name, regex in tokens.items())
            + ")"
        )
        self.match = self._regex.match
        self.search = self._regex.search
        self._expect_eof = False
        self._expect_semicolon = True
        self._extract_text = False

    def expect_eof(self, eof: bool = True) -> Expect:
        """Expect an end of file."""
        self._expect_eof = eof
        return self

    def expect_semicolon(self, semicolon: bool = True) -> Expect:
        """Tokenizer expects text to be terminated with a semi-colon."""
        self._expect_semicolon = semicolon
        return self

    def extract_text(self, extract: bool = True) -> Expect:
        self._extract_text = extract
        return self

    def __rich_repr__(self) -> rich.repr.Result:
        yield from zip(self.names, self.regexes)


class ReferencedBy(NamedTuple):
    name: str
    location: tuple[int, int]
    length: int
    code: str


@rich.repr.auto(angular=True)
class Token(NamedTuple):
    name: str
    value: str
    read_from: CSSLocation
    code: str
    location: tuple[int, int]
    """Token starting location, 0-indexed."""
    referenced_by: ReferencedBy | None = None

    @property
    def start(self) -> tuple[int, int]:
        """Start line and column (1-indexed)."""
        line, offset = self.location
        return (line + 1, offset + 1)

    @property
    def end(self) -> tuple[int, int]:
        """End line and column (1-indexed)."""
        line, offset = self.location
        return (line + 1, offset + len(self.value) + 1)

    def with_reference(self, by: ReferencedBy | None) -> "Token":
        """Return a copy of the Token, with reference information attached.
        This is used for variable substitution, where a variable reference
        can refer to tokens which were defined elsewhere. With the additional
        ReferencedBy data attached, we can track where the token we are referring
        to is used.
        """
        return Token(
            name=self.name,
            value=self.value,
            read_from=self.read_from,
            code=self.code,
            location=self.location,
            referenced_by=by,
        )

    def __str__(self) -> str:
        return self.value

    def __rich_repr__(self) -> rich.repr.Result:
        yield "name", self.name
        yield "value", self.value
        yield (
            "read_from",
            self.read_from[0] if not self.read_from[1] else self.read_from,
        )
        yield "code", self.code if len(self.code) < 40 else self.code[:40] + "..."
        yield "location", self.location
        yield "referenced_by", self.referenced_by, None


class Tokenizer:
    """Tokenizes Textual CSS."""

    def __init__(self, text: str, read_from: CSSLocation = ("", "")) -> None:
        """Initialize the tokenizer.

        Args:
            text: String containing CSS.
            read_from: Information regarding where the CSS was read from.
        """
        self.read_from = read_from
        self.code = text
        self.lines = text.splitlines(keepends=True)
        self.line_no = 0
        self.col_no = 0

    def get_token(self, expect: Expect) -> Token:
        """Get the next token.

        Args:
            expect: Expect object which describes which tokens may be read.

        Raises:
            UnexpectedEnd: If there is an unexpected end of file.
            TokenError: If there is an error with the token.

        Returns:
            A new Token.
        """
        pass

    def skip_to(self, expect: Expect) -> Token:
        """Skip tokens.

        Args:
            expect: Expect object describing the expected token.

        Raises:
            UnexpectedEndOfText: If end of file is reached.

        Returns:
            A new token.
        """
        pass
