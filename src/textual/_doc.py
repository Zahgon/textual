from __future__ import annotations

import hashlib
import inspect
import os
import shlex
from pathlib import Path
from typing import Awaitable, Callable, Iterable, cast

from textual._import_app import import_app
from textual.app import App
from textual.pilot import Pilot

SCREENSHOT_CACHE = ".screenshot_cache"


# This module defines our "Custom Fences", powered by SuperFences
# @link https://facelessuser.github.io/pymdown-extensions/extensions/superfences/#custom-fences
def format_svg(source, language, css_class, options, md, attrs, **kwargs) -> str:
    """A superfences formatter to insert an SVG screenshot."""
    pass


def take_svg_screenshot(
    app: App | None = None,
    app_path: str | None = None,
    press: Iterable[str] = (),
    hover: str = "",
    title: str | None = None,
    terminal_size: tuple[int, int] = (80, 24),
    run_before: Callable[[Pilot], Awaitable[None] | None] | None = None,
    wait_for_animation: bool = True,
    simplify=True,
) -> str:
    """

    Args:
        app: An app instance. Must be supplied if app_path is not.
        app_path: A path to an app. Must be supplied if app is not.
        press: Key presses to run before taking screenshot. "_" is a short pause.
        hover: Hover over the given widget.
        title: The terminal title in the output image.
        terminal_size: A pair of integers (rows, columns), representing terminal size.
        run_before: An arbitrary callable that runs arbitrary code before taking the
            screenshot. Use this to simulate complex user interactions with the app
            that cannot be simulated by key presses.
        wait_for_animation: Wait for animation to complete before taking screenshot.
        simplify: Simplify the segments by combining contiguous segments with the same style.

    Returns:
        An SVG string, showing the content of the terminal window at the time
            the screenshot was taken.
    """
    pass


def rich(source, language, css_class, options, md, attrs, **kwargs) -> str:
    """A superfences formatter to insert an SVG screenshot."""
    pass
