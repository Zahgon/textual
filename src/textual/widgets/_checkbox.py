"""Provides a check box widget."""

from __future__ import annotations

from textual.widgets._toggle_button import ToggleButton


class Checkbox(ToggleButton):
    """A check box widget that represents a boolean value."""

    class Changed(ToggleButton.Changed):
        """Posted when the value of the checkbox changes.

        This message can be handled using an `on_checkbox_changed` method.
        """

        @property
        def checkbox(self) -> Checkbox:
            """The checkbox that was changed."""
            pass

        @property
        def control(self) -> Checkbox:
            """An alias for [Changed.checkbox][textual.widgets.Checkbox.Changed.checkbox]."""
            pass
