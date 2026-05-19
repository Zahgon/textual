"""
Contains the widgets that manage Textual scrollbars.

!!! note

    You will not typically need this for most apps.

"""

from __future__ import annotations

from math import ceil
from typing import ClassVar, Type

import rich.repr
from rich.color import Color
from rich.console import Console, ConsoleOptions, RenderableType, RenderResult
from rich.segment import Segment, Segments
from rich.style import Style, StyleType

from textual import events
from textual.geometry import Offset
from textual.message import Message
from textual.reactive import Reactive
from textual.renderables.blank import Blank
from textual.widget import Widget


class ScrollMessage(Message, bubble=False):
    """Base class for all scrollbar messages."""


@rich.repr.auto
class ScrollUp(ScrollMessage, verbose=True):
    """Message sent when clicking above handle."""


@rich.repr.auto
class ScrollDown(ScrollMessage, verbose=True):
    """Message sent when clicking below handle."""


@rich.repr.auto
class ScrollLeft(ScrollMessage, verbose=True):
    """Message sent when clicking above handle."""


@rich.repr.auto
class ScrollRight(ScrollMessage, verbose=True):
    """Message sent when clicking below handle."""


class ScrollTo(ScrollMessage, verbose=True):
    """Message sent when click and dragging handle."""

    __slots__ = ["x", "y", "animate"]

    def __init__(
        self,
        x: float | None = None,
        y: float | None = None,
        animate: bool = True,
    ) -> None:
        self.x = x
        self.y = y
        self.animate = animate
        super().__init__()

    def __rich_repr__(self) -> rich.repr.Result:
        yield "x", self.x, None
        yield "y", self.y, None
        yield "animate", self.animate, True


class ScrollBarRender:
    VERTICAL_BARS: ClassVar[list[str]] = ["▁", "▂", "▃", "▄", "▅", "▆", "▇", " "]
    """Glyphs used for vertical scrollbar ends, for smoother display."""
    HORIZONTAL_BARS: ClassVar[list[str]] = ["▉", "▊", "▋", "▌", "▍", "▎", "▏", " "]
    """Glyphs used for horizontal scrollbar ends, for smoother display."""
    BLANK_GLYPH: ClassVar[str] = " "
    """Glyph used for the main body of the scrollbar"""

    def __init__(
        self,
        virtual_size: int = 100,
        window_size: int = 0,
        position: float = 0,
        thickness: int = 1,
        vertical: bool = True,
        style: StyleType = "bright_magenta on #555555",
    ) -> None:
        self.virtual_size = virtual_size
        self.window_size = window_size
        self.position = position
        self.thickness = thickness
        self.vertical = vertical
        self.style = style


    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        size = (
            (options.height or console.height)
            if self.vertical
            else (options.max_width or console.width)
        )
        thickness = (
            (options.max_width or console.width)
            if self.vertical
            else (options.height or console.height)
        )

        _style = console.get_style(self.style)

        bar = self.render_bar(
            size=size,
            window_size=self.window_size,
            virtual_size=self.virtual_size,
            position=self.position,
            vertical=self.vertical,
            thickness=thickness,
            back_color=_style.bgcolor or Color.parse("#555555"),
            bar_color=_style.color or Color.parse("bright_magenta"),
        )
        yield bar


@rich.repr.auto
class ScrollBar(Widget):
    renderer: ClassVar[Type[ScrollBarRender]] = ScrollBarRender
    """The class used for rendering scrollbars.
    This can be overridden and set to a ScrollBarRender-derived class
    in order to delegate all scrollbar rendering to that class. E.g.:

    ```
    class MyScrollBarRender(ScrollBarRender): ...

    app = MyApp()
    ScrollBar.renderer = MyScrollBarRender
    app.run()
    ```

    Because this variable is accessed through specific instances
    (rather than through the class ScrollBar itself) it is also possible
    to set this on specific scrollbar instance to change only that
    instance:

    ```
    my_widget.horizontal_scrollbar.renderer = MyScrollBarRender
    ```
    """

    DEFAULT_CLASSES = "-textual-system"

    # Nothing to select in scrollbars
    ALLOW_SELECT = False

    def __init__(
        self, vertical: bool = True, name: str | None = None, *, thickness: int = 1
    ) -> None:
        self.vertical = vertical
        self.thickness = thickness
        self.grabbed_position: float = 0
        super().__init__(name=name)
        self.set_reactive(ScrollBar.auto_links, False)

    window_virtual_size: Reactive[int] = Reactive(100)
    window_size: Reactive[int] = Reactive(0)
    position: Reactive[float] = Reactive(0)
    mouse_over: Reactive[bool] = Reactive(False)
    grabbed: Reactive[Offset | None] = Reactive(None)

    def __rich_repr__(self) -> rich.repr.Result:
        yield from super().__rich_repr__()
        yield "window_virtual_size", self.window_virtual_size
        yield "window_size", self.window_size
        yield "position", self.position
        if self.thickness > 1:
            yield "thickness", self.thickness

    def validate_position(self, position: float) -> float:
        """Position has a granulatory of 1/8 of a cell."""
        pass

    def render(self) -> RenderableType:
        assert self.parent is not None
        styles = self.parent.styles
        if self.grabbed:
            background = styles.scrollbar_background_active
            color = styles.scrollbar_color_active
        elif self.mouse_over:
            background = styles.scrollbar_background_hover
            color = styles.scrollbar_color_hover
        else:
            background = styles.scrollbar_background
            color = styles.scrollbar_color
        if background.a < 1:
            base_background, _ = self.parent.background_colors
            background = base_background + background
        color = background + color
        scrollbar_style = Style.from_color(color.rich_color, background.rich_color)
        if self.screen.styles.scrollbar_color.a == 0:
            return self.renderer(vertical=self.vertical, style=scrollbar_style)
        return self._render_bar(scrollbar_style)

    def _render_bar(self, scrollbar_style: Style) -> RenderableType:
        """Get a renderable for the scrollbar with given style.

        Args:
            scrollbar_style: Scrollbar style.

        Returns:
            Scrollbar renderable.
        """
        window_size = (
            self.window_size if self.window_size < self.window_virtual_size else 0
        )
        virtual_size = self.window_virtual_size

        return self.renderer(
            virtual_size=ceil(virtual_size),
            window_size=ceil(window_size),
            position=self.position,
            thickness=self.thickness,
            vertical=self.vertical,
            style=scrollbar_style,
        )




    def action_scroll_down(self) -> None:
        """Scroll vertical scrollbars down, horizontal scrollbars right."""
        pass

    def action_scroll_up(self) -> None:
        """Scroll vertical scrollbars up, horizontal scrollbars left."""
        pass

    def action_grab(self) -> None:
        """Begin capturing the mouse cursor."""
        pass








class ScrollBarCorner(Widget):
    """Widget which fills the gap between horizontal and vertical scrollbars,
    should they both be present."""

    def render(self) -> Blank:
        assert self.parent is not None
        styles = self.parent.styles
        color = styles.scrollbar_corner_color
        return Blank(color)
