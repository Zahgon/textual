"""
An implementation of the "Sliding Tile" puzzle.

Textual isn't a game engine exactly, but it wasn't hard to build this.

"""

from __future__ import annotations

from asyncio import sleep
from collections import defaultdict
from dataclasses import dataclass
from itertools import product
from random import choice
from time import monotonic

from rich.console import ConsoleRenderable
from rich.syntax import Syntax

from textual import containers, events, on, work
from textual._loop import loop_last
from textual.app import ComposeResult
from textual.binding import Binding
from textual.demo.page import PageScreen
from textual.geometry import Offset, Size
from textual.reactive import reactive
from textual.screen import ModalScreen, Screen
from textual.timer import Timer
from textual.widgets import Button, Digits, Footer, Markdown, Select, Static


@dataclass
class NewGame:
    """A dataclass to report the desired game type."""

    language: str
    code: str
    size: tuple[int, int]


PYTHON_CODE = '''\
class SpatialMap(Generic[ValueType]):
    """A spatial map allows for data to be associated with rectangular regions
    in Euclidean space, and efficiently queried.

    When the SpatialMap is populated, a reference to each value is placed into one or
    more buckets associated with a regular grid that covers 2D space.

    The SpatialMap is able to quickly retrieve the values under a given "window" region
    by combining the values in the grid squares under the visible area.
    """

    def __init__(self, grid_width: int = 100, grid_height: int = 20) -> None:
        """Create a spatial map with the given grid size.

        Args:
            grid_width: Width of a grid square.
            grid_height: Height of a grid square.
        """
        self._grid_size = (grid_width, grid_height)
        self.total_region = Region()
        self._map: defaultdict[GridCoordinate, list[ValueType]] = defaultdict(list)
        self._fixed: list[ValueType] = []

    def _region_to_grid_coordinates(self, region: Region) -> Iterable[GridCoordinate]:
        """Get the grid squares under a region.

        Args:
            region: A region.

        Returns:
            Iterable of grid coordinates (tuple of 2 values).
        """
        # (x1, y1) is the coordinate of the top left cell
        # (x2, y2) is the coordinate of the bottom right cell
        x1, y1, width, height = region
        x2 = x1 + width - 1
        y2 = y1 + height - 1
        grid_width, grid_height = self._grid_size

        return product(
            range(x1 // grid_width, x2 // grid_width + 1),
            range(y1 // grid_height, y2 // grid_height + 1),
        )
'''

XML_CODE = """\
<?xml version="1.0" encoding="UTF-8"?>
<movies>
    <movie>
        <title>Back to the Future</title> <year>1985</year> <director>Robert Zemeckis</director>
        <genre>Science Fiction</genre> <rating>PG</rating>
        <cast>
            <actor> <name>Michael J. Fox</name> <role>Marty McFly</role> </actor>
            <actor> <name>Christopher Lloyd</name> <role>Dr. Emmett Brown</role> </actor>
        </cast>
    </movie>
    <movie>
        <title>The Breakfast Club</title> <year>1985</year> <director>John Hughes</director>
        <genre>Drama</genre> <rating>R</rating>
        <cast>
            <actor> <name>Emilio Estevez</name> <role>Andrew Clark</role> </actor>
            <actor> <name>Molly Ringwald</name> <role>Claire Standish</role> </actor>
        </cast>
    </movie>
    <movie>
        <title>Ghostbusters</title> <year>1984</year> <director>Ivan Reitman</director>
        <genre>Comedy</genre> <rating>PG</rating>
        <cast>
            <actor> <name>Bill Murray</name> <role>Dr. Peter Venkman</role> </actor>
            <actor> <name>Dan Aykroyd</name> <role>Dr. Raymond Stantz</role> </actor>
        </cast>
    </movie>
    <movie>
        <title>Die Hard</title> <year>1988</year> <director>John McTiernan</director>
        <genre>Action</genre> <rating>R</rating>
        <cast>
            <actor> <name>Bruce Willis</name> <role>John McClane</role> </actor>
            <actor> <name>Alan Rickman</name> <role>Hans Gruber</role> </actor>
        </cast>
    </movie>
    <movie>
        <title>E.T. the Extra-Terrestrial</title> <year>1982</year> <director>Steven Spielberg</director>
        <genre>Science Fiction</genre> <rating>PG</rating>
        <cast>
            <actor> <name>Henry Thomas</name> <role>Elliott</role> </actor>
            <actor> <name>Drew Barrymore</name> <role>Gertie</role> </actor>
        </cast>
    </movie>
</movies>"""

BF_CODE = """\
[life.b -- John Horton Conway's Game of Life
(c) 2021 Daniel B. Cristofani
]

>>>->+>+++++>(++++++++++)[[>>>+<<<-]>+++++>+>>+[<<+>>>>>+<<<-]<-]>>>>[
  [>>>+>+<<<<-]+++>>+[<+>>>+>+<<<-]>>[>[[>>>+<<<-]<]<<++>+>>>>>>-]<-
]+++>+>[[-]<+<[>+++++++++++++++++<-]<+]>>[
  [+++++++++.-------->>>]+[-<<<]>>>[>>,----------[>]<]<<[
    <<<[
      >--[<->>+>-<<-]<[[>>>]+>-[+>>+>-]+[<<<]<-]>++>[<+>-]
      >[[>>>]+[<<<]>>>-]+[->>>]<-[++>]>[------<]>+++[<<<]>
    ]<
  ]>[
    -[+>>+>-]+>>+>>>+>[<<<]>->+>[
      >[->+>+++>>++[>>>]+++<<<++<<<++[>>>]>>>]<<<[>[>>>]+>>>]
      <<<<<<<[<<++<+[-<<<+]->++>>>++>>>++<<<<]<<<+[-<<<+]+>->>->>
    ]<<+<<+<<<+<<-[+<+<<-]+<+[
      ->+>[-<-<<[<<<]>[>>[>>>]<<+<[<<<]>-]]
      <[<[<[<<<]>+>>[>>>]<<-]<[<<<]]>>>->>>[>>>]+>
    ]>+[-<<[-]<]-[
      [>>>]<[<<[<<<]>>>>>+>[>>>]<-]>>>[>[>>>]<<<<+>[<<<]>>-]>
    ]<<<<<<[---<-----[-[-[<->>+++<+++++++[-]]]]<+<+]>
  ]>>
]

[This program simulates the Game of Life cellular automaton.

Type e.g. "be" to toggle the fifth cell in the second row, "q" to quit,
or a bare linefeed to advance one generation.

Grid wraps toroidally. Board size in parentheses in first line (2-166 work).

This program is licensed under a Creative Commons Attribution-ShareAlike 4.0
International License (http://creativecommons.org/licenses/by-sa/4.0/).]
"""


LEVELS = {"Python": PYTHON_CODE, "XML": XML_CODE, "BF": BF_CODE}


class Tile(containers.Vertical):
    """An individual tile in the puzzle.

    A Tile is a container with a static inside it.
    The static contains the code (as a Rich Syntax object), scrolled so the
    relevant portion is visible.
    """

    DEFAULT_CSS = """
    Tile {
        position: absolute;
        Static {
            width: auto;
            height: auto;
            &:hover { tint: $primary 30%; }
        }       
        &#blank { visibility: hidden; }
    }
    """

    position: reactive[Offset] = reactive(Offset)

    def __init__(
        self,
        renderable: ConsoleRenderable,
        tile: int | None,
        size: Size,
        position: Offset,
    ) -> None:
        self.renderable = renderable
        self.tile = tile
        self.tile_size = size
        self.start_position = position

        super().__init__(id="blank" if tile is None else f"tile{self.tile}")
        self.set_reactive(Tile.position, position)

    def compose(self) -> ComposeResult:
        static = Static(
            self.renderable,
            classes="tile",
            name="blank" if self.tile is None else str(self.tile),
        )
        assert self.parent is not None
        static.styles.width = self.parent.styles.width
        static.styles.height = self.parent.styles.height
        yield static


    def watch_position(self, position: Offset) -> None:
        """The 'position' is in tile coordinate.
        When it changes we animate it to the cell coordinates."""
        pass


class GameDialog(containers.VerticalGroup):
    """A dialog to ask the user for the initial game parameters."""

    DEFAULT_CSS = """
        GameDialog {
            background: $boost;
            border: thick $primary-muted;
            padding: 0 2;
            width: 50;
            #values {
                width: 1fr;
                Select { margin: 1 0;}
            }
            Button {
                margin: 0 1 1 1;
                width: 1fr;
            }
        }        
    """

    def compose(self) -> ComposeResult:
        with containers.VerticalGroup(id="values"):
            yield Select.from_values(
                LEVELS.keys(),
                prompt="Language",
                value="Python",
                id="language",
                allow_blank=False,
            )
            yield Select(
                [
                    ("Easy (3x3)", (3, 3)),
                    ("Medium (4x4)", (4, 4)),
                    ("Hard (5x5)", (5, 5)),
                ],
                prompt="Level",
                value=(4, 4),
                id="level",
                allow_blank=False,
            )
        yield Button("Start", variant="primary")



class GameDialogScreen(ModalScreen):
    """Modal screen containing the dialog."""

    CSS = """
    GameDialogScreen {      
        align: center middle;              
    }
    """

    BINDINGS = [("escape", "dismiss")]

    def compose(self) -> ComposeResult:
        yield GameDialog()


class Game(containers.Vertical, can_focus=True):
    """Widget for the game board."""

    ALLOW_MAXIMIZE = False
    DEFAULT_CSS = """
    Game {
        visibility: hidden;
        align: center middle;
        hatch: right $panel;
        border: heavy transparent;
        &:focus {
            border: heavy $success;
        }
        #grid {
            border: heavy $primary;           
            hatch: right $panel;
            box-sizing: content-box;
        }
        Digits {
            width: auto;
            color: $foreground;
        }
    }
    """

    BINDINGS = [
        Binding("up", "move('up')", "up", priority=True),
        Binding("down", "move('down')", "down", priority=True),
        Binding("left", "move('left')", "left", priority=True),
        Binding("right", "move('right')", "right", priority=True),
    ]

    state = reactive("waiting")
    play_start_time: reactive[float] = reactive(monotonic)
    play_time = reactive(0.0, init=False)
    code = reactive("")
    dimensions = reactive(Size(3, 3))
    code = reactive("")
    language = reactive("")

    def __init__(
        self,
        code: str,
        language: str,
        dimensions: tuple[int, int],
        tile_size: tuple[int, int],
    ) -> None:
        self.set_reactive(Game.code, code)
        self.set_reactive(Game.language, language)
        self.locations: defaultdict[Offset, int | None] = defaultdict(None)
        super().__init__()
        self.dimensions = Size(*dimensions)
        self.tile_size = Size(*tile_size)
        self.play_timer: Timer | None = None



    def compose(self) -> ComposeResult:
        syntax = Syntax(
            self.code,
            self.language.lower(),
            indent_guides=True,
            line_numbers=True,
            theme="material",
        )
        tile_width, tile_height = self.dimensions
        self.state = "waiting"
        yield Digits("")
        with containers.HorizontalGroup(id="grid") as grid:
            grid.styles.width = tile_width * self.tile_size[0]
            grid.styles.height = tile_height * self.tile_size[1]
            for row, column in product(range(tile_width), range(tile_height)):
                position = Offset(row, column)
                tile_no = self.locations[position]
                yield Tile(syntax, tile_no, self.tile_size, position)
        if self.language:
            self.call_after_refresh(self.shuffle)




    def get_tile(self, tile: int | None) -> Tile:
        """Get a tile (int) or the blank (None)."""
        pass

    def get_tile_at(self, position: Offset) -> Tile:
        """Get a tile at the given position, or raise an IndexError."""
        pass

    def move_tile(self, tile_no: int | None) -> None:
        """Move a tile to the blank.
        Note: this doesn't do any validation of legal moves.
        """
        pass

    def can_move(self, tile: int) -> bool:
        """Check if a tile may move."""
        pass


    def get_legal_moves(self) -> set[Offset]:
        """Get the positions of all tiles that can move."""
        pass

    @work(exclusive=True)
    async def shuffle(self, shuffles: int = 150) -> None:
        """A worker to do the shuffling."""
        pass



class GameInstructions(containers.VerticalGroup):
    DEFAULT_CSS = """\
    GameInstructions {        
        layer: instructions;
        width: 60;
        background: $panel;
        border: thick $primary-darken-2; 
        Markdown {
            background: $panel;
        }
        
    }

"""
    INSTRUCTIONS = """\
# Instructions

This is an implementation of the *sliding tile puzzle*.

The board consists of a number of tiles and a blank space.
After shuffling, the goal is to restore the original "image" by moving a square either horizontally or vertically into the blank space.

This version is like the physical game, but rather than an image, you need to restore code.
    """

    def compose(self) -> ComposeResult:
        yield Markdown(self.INSTRUCTIONS)
        with containers.Center():
            yield Button("New Game", action="screen.new_game", variant="success")


class GameScreen(PageScreen):
    """The screen containing the game."""

    DEFAULT_CSS = """
    GameScreen{       
        #container {
            align: center middle;
            layers: instructions game;     
        }
    }
    """

    BINDINGS = [("n", "new_game", "New Game")]

    def compose(self) -> ComposeResult:
        with containers.Vertical(id="container"):
            yield GameInstructions()
            yield Game("\n" * 100, "", dimensions=(4, 4), tile_size=(16, 8))
            yield Footer()




    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action == "shuffle" and self.query_one(Game).state == "waiting":
            return None
        return True


if __name__ == "__main__":
    from textual.app import App

    class GameApp(App):
        def get_default_screen(self) -> Screen:
            return GameScreen()

    app = GameApp()
    app.run()
