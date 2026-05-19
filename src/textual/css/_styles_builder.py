from __future__ import annotations

from typing import Iterable, NoReturn, cast

import rich.repr

from textual._border import BorderValue, normalize_border_value
from textual._cells import cell_len
from textual._duration import _duration_as_seconds
from textual._easing import EASING
from textual.color import TRANSPARENT, Color, ColorParseError
from textual.css._error_tools import friendly_list
from textual.css._help_renderables import HelpText
from textual.css._help_text import (
    align_help_text,
    border_property_help_text,
    color_property_help_text,
    dock_property_help_text,
    expand_help_text,
    fractional_property_help_text,
    integer_help_text,
    keyline_help_text,
    layout_property_help_text,
    offset_property_help_text,
    offset_single_axis_help_text,
    position_help_text,
    property_invalid_value_help_text,
    scalar_help_text,
    scrollbar_size_property_help_text,
    scrollbar_size_single_axis_help_text,
    spacing_invalid_value_help_text,
    spacing_wrong_number_of_values_help_text,
    split_property_help_text,
    string_enum_help_text,
    style_flags_property_help_text,
    table_rows_or_columns_help_text,
    text_align_help_text,
)
from textual.css.constants import (
    HATCHES,
    VALID_ALIGN_HORIZONTAL,
    VALID_ALIGN_VERTICAL,
    VALID_BORDER,
    VALID_BOX_SIZING,
    VALID_CONSTRAIN,
    VALID_DISPLAY,
    VALID_EDGE,
    VALID_EXPAND,
    VALID_HATCH,
    VALID_KEYLINE,
    VALID_OVERFLOW,
    VALID_OVERLAY,
    VALID_POINTER,
    VALID_POSITION,
    VALID_SCROLLBAR_GUTTER,
    VALID_SCROLLBAR_VISIBILITY,
    VALID_STYLE_FLAGS,
    VALID_TEXT_ALIGN,
    VALID_TEXT_OVERFLOW,
    VALID_TEXT_WRAP,
    VALID_VISIBILITY,
)
from textual.css.errors import DeclarationError, StyleValueError
from textual.css.model import Declaration
from textual.css.scalar import (
    Scalar,
    ScalarError,
    ScalarOffset,
    ScalarParseError,
    Unit,
    percentage_string_to_float,
)
from textual.css.styles import Styles
from textual.css.tokenize import Token
from textual.css.transition import Transition
from textual.css.types import (
    BoxSizing,
    Display,
    EdgeType,
    Overflow,
    ScrollbarVisibility,
    TextOverflow,
    TextWrap,
    Visibility,
)
from textual.geometry import Spacing, SpacingDimensions, clamp
from textual.suggestions import get_suggestion


class StylesBuilder:
    """
    The StylesBuilder object takes tokens parsed from the CSS and converts
    to the appropriate internal types.
    """

    def __init__(self) -> None:
        self.styles = Styles()

    def __rich_repr__(self) -> rich.repr.Result:
        yield "styles", self.styles

    def __repr__(self) -> str:
        return "StylesBuilder()"

    def error(self, name: str, token: Token, message: str | HelpText) -> NoReturn:
        raise DeclarationError(name, token, message)

    def add_declaration(self, declaration: Declaration) -> None:
        if not declaration.name:
            return
        rule_name = declaration.name.replace("-", "_")

        if not declaration.tokens:
            self.error(
                rule_name,
                declaration.token,
                f"Missing property value for '{declaration.name}:'",
            )

        process_method = getattr(self, f"process_{rule_name}", None)

        if process_method is None:
            suggested_property_name = self._get_suggested_property_name_for_rule(
                declaration.name
            )
            self.error(
                declaration.name,
                declaration.token,
                property_invalid_value_help_text(
                    declaration.name,
                    "css",
                    suggested_property_name=suggested_property_name,
                ),
            )

        tokens = declaration.tokens

        important = tokens[-1].name == "important"
        if important:
            tokens = tokens[:-1]
            self.styles.important.add(rule_name)

        # Check for special token(s)
        if tokens[0].name == "token":
            value = tokens[0].value
            if value == "initial":
                self.styles._rules[rule_name] = None
                return
        try:
            process_method(declaration.name, tokens)
        except DeclarationError:
            raise
        except Exception as error:
            self.error(declaration.name, declaration.token, str(error))

    def _process_enum_multiple(
        self, name: str, tokens: list[Token], valid_values: set[str], count: int
    ) -> tuple[str, ...]:
        """Generic code to process a declaration with two enumerations, like overflow: auto auto"""
        pass

    def _process_enum(
        self, name: str, tokens: list[Token], valid_values: set[str]
    ) -> str:
        """Process a declaration that expects an enum.

        Args:
            name: Name of declaration.
            tokens: Tokens from parser.
            valid_values: A set of valid values.

        Returns:
            True if the value is valid or False if it is invalid (also generates an error)
        """
        pass



    def _distribute_importance(self, prefix: str, suffixes: tuple[str, ...]) -> None:
        """Distribute importance amongst all aspects of the given style.

        Args:
            prefix: The prefix of the style.
            suffixes: The suffixes to distribute amongst.

        A number of styles can be set with the 'prefix' of the style,
        providing the values as a series of parameters; or they can be set
        with specific suffixes. Think `border` vs `border-left`, etc. This
        method is used to ensure that if the former is set, `!important` is
        distributed amongst all the suffixes.
        """
        pass















    process_opacity = _process_fractional
    process_text_opacity = _process_fractional


    def _process_space_partial(self, name: str, tokens: list[Token]) -> None:
        """Process granular margin / padding declarations."""
        pass

    process_padding = _process_space
    process_margin = _process_space

    process_margin_top = _process_space_partial
    process_margin_right = _process_space_partial
    process_margin_bottom = _process_space_partial
    process_margin_left = _process_space_partial

    process_padding_top = _process_space_partial
    process_padding_right = _process_space_partial
    process_padding_bottom = _process_space_partial
    process_padding_left = _process_space_partial















    def process_offset(self, name: str, tokens: list[Token]) -> None:
        def offset_error(name: str, token: Token) -> None:
            self.error(name, token, offset_property_help_text(context="css"))

        if not tokens:
            return
        if len(tokens) != 2:
            offset_error(name, tokens[0])
        else:
            token1, token2 = tokens

            if token1.name not in ("scalar", "number"):
                offset_error(name, token1)
            if token2.name not in ("scalar", "number"):
                offset_error(name, token2)

            scalar_x = Scalar.parse(token1.value, Unit.WIDTH)
            scalar_y = Scalar.parse(token2.value, Unit.HEIGHT)
            self.styles._rules["offset"] = ScalarOffset(scalar_x, scalar_y)




    def process_layout(self, name: str, tokens: list[Token]) -> None:
        from textual.layouts.factory import MissingLayout, get_layout

        if tokens:
            if len(tokens) != 1:
                self.error(
                    name, tokens[0], layout_property_help_text(name, context="css")
                )
            else:
                value = tokens[0].value
                layout_name = value
                try:
                    self.styles._rules["layout"] = get_layout(layout_name)
                except MissingLayout:
                    self.error(
                        name,
                        tokens[0],
                        layout_property_help_text(name, context="css"),
                    )

    def process_color(self, name: str, tokens: list[Token]) -> None:
        """Processes a simple color declaration."""
        pass

    process_tint = process_color
    process_background = process_color
    process_background_tint = process_color
    process_scrollbar_color = process_color
    process_scrollbar_color_hover = process_color
    process_scrollbar_color_active = process_color
    process_scrollbar_corner_color = process_color
    process_scrollbar_background = process_color
    process_scrollbar_background_hover = process_color
    process_scrollbar_background_active = process_color

    def process_scrollbar_visibility(self, name: str, tokens: list[Token]) -> None:
        """Process scrollbar visibility rules."""
        pass

    process_link_color = process_color
    process_link_background = process_color
    process_link_color_hover = process_color
    process_link_background_hover = process_color

    process_border_title_color = process_color
    process_border_title_background = process_color
    process_border_subtitle_color = process_color
    process_border_subtitle_background = process_color


    process_link_style = process_text_style
    process_link_style_hover = process_text_style

    process_border_title_style = process_text_style
    process_border_subtitle_style = process_text_style

    def process_text_align(self, name: str, tokens: list[Token]) -> None:
        """Process a text-align declaration"""
        pass









    process_content_align = process_align
    process_content_align_horizontal = process_align_horizontal
    process_content_align_vertical = process_align_vertical

    process_border_title_align = process_align_horizontal
    process_border_subtitle_align = process_align_horizontal






    process_grid_rows = _process_grid_rows_or_columns
    process_grid_columns = _process_grid_rows_or_columns


    process_grid_gutter_horizontal = _process_integer
    process_grid_gutter_vertical = _process_integer
    process_column_span = _process_integer
    process_row_span = _process_integer
    process_grid_size_columns = _process_integer
    process_grid_size_rows = _process_integer
    process_line_pad = _process_integer










    def _get_suggested_property_name_for_rule(self, rule_name: str) -> str | None:
        """
        Returns a valid CSS property "Python" name, or None if no close matches could be found.

        Args:
            rule_name: An invalid "Python-ised" CSS property (i.e. "offst_x" rather than "offst-x")

        Returns:
            The closest valid "Python-ised" CSS property.
                Returns `None` if no close matches could be found.

        Example: returns "background" for rule_name "bkgrund", "offset_x" for "ofset_x"
        """
        processable_rules_name = [
            attr[8:] for attr in dir(self) if attr.startswith("process_")
        ]
        return get_suggestion(rule_name, processable_rules_name)
