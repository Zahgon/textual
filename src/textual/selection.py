from __future__ import annotations

from operator import attrgetter
from typing import TYPE_CHECKING, Iterable, Iterator, NamedTuple

from textual.geometry import Offset, Shape

if TYPE_CHECKING:
    from textual.widget import Widget


class Selection(NamedTuple):
    """A selected range of lines."""

    start: Offset | None
    """Offset or None for `start`."""
    end: Offset | None
    """Offset or None for `end`."""

    @classmethod
    def from_offsets(cls, offset1: Offset, offset2: Offset) -> Selection:
        """Create selection from 2 offsets.

        Args:
            offset1: First offset.
            offset2: Second offset.

        Returns:
            New Selection.
        """
        offsets = sorted([offset1, offset2], key=(lambda offset: (offset.y, offset.x)))
        return cls(*offsets)

    def extract(self, text: str) -> str:
        """Extract selection from text.

        Args:
            text: Raw text pulled from widget.

        Returns:
            Extracted text.
        """
        pass

    def get_span(self, y: int) -> tuple[int, int] | None:
        """Get the selected span in a given line.

        Args:
            y: Offset of the line.

        Returns:
            A tuple of x start and end offset, or None for no selection.
        """
        start, end = self
        if start is None and end is None:
            # Selection covers everything
            return 0, -1

        if start is not None and end is not None:
            if y < start.y or y > end.y:
                # Outside
                return None
            if y == start.y and start.y == end.y:
                # Same line
                return start.x, end.x
            if y == end.y:
                # Last line
                return 0, end.x
            if y == start.y:
                return start.x, -1
            # Remaining lines
            return 0, -1

        if start is None and end is not None:
            if y == end.y:
                return 0, end.x
            if y > end.y:
                return None
            return 0, -1

        if end is None and start is not None:
            if y == start.y:
                return start.x, -1
            if y > start.y:
                return 0, -1
            return None
        return 0, -1


SELECT_ALL = Selection(None, None)


class SelectStart(NamedTuple):
    """Describes the start of a select."""

    container: Widget
    """The container under the cursor."""
    container_pointer_delta: Offset
    """The delta between the initial container offset and pointer."""
    container_initial_offset: Offset
    """The initial offset of the container."""
    container_initial_scroll_offset: Offset
    """The initial scroll offset of the container."""
    content_widget: Widget | None
    """The content widget under the pointer (if any)."""
    content_offset: Offset | None
    """The content offset of the widget under the pointer (if appropriate)."""

    @property
    def pointer_start_offset(self) -> Offset:
        """The pointer start offset adjusted for scroll."""
        pass


class SelectEnd(NamedTuple):
    """The end of a select."""

    container: Widget
    """The container widget under the pointer."""
    content_widget: Widget | None
    """The content widget under the pointer (if any)."""
    content_offset: Offset | None
    """The content offset of the widget under the pointer."""


class SelectState(NamedTuple):
    """An object which describes the current select state."""

    screen_offset: Offset
    """The current mouse position, in screen space."""
    start: SelectStart
    """Describes the select start."""
    end: SelectEnd | None = None
    """Describes the select end."""

    def is_attached_to_dom(self) -> bool:
        """Are the widgets involved attached to the DOM?"""
        pass

    @property
    def is_single_content_widget(self) -> bool:
        """Does the start and end fall on the same widget?"""
        pass

    @property
    def content_offsets(self) -> tuple[Offset, Offset]:
        """Get the content offset in select order."""
        pass

    @property
    def select_container(self) -> Widget:
        """A widget that contains both ends of the select."""
        pass

    @property
    def selection_bounds(self) -> Shape:
        """A shape which overlays the area of selected text."""

        selection_bounds = Shape.selection_bounds(
            self.select_container.region,
            self.start.pointer_start_offset,
            self.screen_offset,
        )
        return selection_bounds

    @property
    def ordered_offsets(self) -> tuple[Offset, Offset]:
        """Offsets used in selection bounds, in selection order."""
        pass

    def update_end(self, pointer_offset: Offset, select_end: SelectEnd) -> SelectState:
        """Update the state with the selction end.

        Args:
            pointer_offset: Current mosue position.
            select_end: Selection end.

        Returns:
            SelectState: New select state.

        """
        return SelectState(pointer_offset, self.start, select_end)

    def _apply_content_selections(self, selections: dict[Widget, Selection]):
        assert (
            self.end is not None
        ), "Unavailable until there is an end point to the selection"
        start_widget = self.start.content_widget
        start_content_offset = self.start.content_offset
        start_offset = self.start.pointer_start_offset

        end_widget = self.end.content_widget
        end_content_offset = self.end.content_offset
        end_offset = self.screen_offset

        if end_offset.transpose < start_offset.transpose:
            start_widget, end_widget = end_widget, start_widget
            start_content_offset, end_content_offset = (
                end_content_offset,
                start_content_offset,
            )

        if start_widget is not None and start_content_offset is not None:
            selections[start_widget] = Selection(start_content_offset, None)
        if end_widget is not None and end_content_offset is not None:
            selections[end_widget] = Selection(None, end_content_offset)

    def _walk_selected_widgets(self) -> list[Widget]:
        assert (
            self.end is not None
        ), "Unavailable until there is an end point to the selection"

        selection_bounds = self.selection_bounds
        select_container = self.select_container

        # Endpoints sorted by screen position.
        ordered_start, ordered_end = self.ordered_offsets
        start_y = ordered_start.y
        end_y = ordered_end.y

        # Identify the content widgets at each end of the selection, in
        # selection order. Either may be `None` if the pointer was not over a
        # content widget at that end.
        if self.start.pointer_start_offset.transpose <= self.screen_offset.transpose:
            first_content_widget = self.start.content_widget
            last_content_widget = self.end.content_widget
        else:
            first_content_widget = self.end.content_widget
            last_content_widget = self.start.content_widget

        get_selection_order = attrgetter("_selection_order")
        selected: list[Widget] = []

        def walk_in_select_order(root: Widget) -> Iterable[Widget]:
            """Walk descendants of `root` depth-first in selection order."""
            pass

        def collect_range(
            container: Widget,
            from_widget: Widget | None,
            to_widget: Widget | None,
            *,
            from_y: int | None = None,
            to_y: int | None = None,
        ) -> None:
            """Collect selectable descendants between two content widgets.

            Walks `container` in selection order, including selectable
            non-container descendants.

            When the start or end pointer lands on a gap (no content widget),
            `from_y` / `to_y` fall back to a vertical bound on the widget's
            `content_region.y` so the selection grows continuously as the
            pointer moves, rather than snapping to the whole container.

            Args:
                container: Top level widget, that is parent of `from_widget` and `to_widget.
                from_widget: First widget in sslection order or first in selection order.
                to_widget: Last widget in selection order or `None` for end of container.

                from_y: Start `y` of selection, or `None` for top.
                to_y: End `y` of selection, or `None` for end.
            """
            pass

        def visit(root: Widget) -> None:
            """Walk children of `parent`, deciding inclusion per child.

            Args:
                root: Initial node to walk from.
            """
            pass

        visit(select_container)
        return selected
