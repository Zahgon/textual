from __future__ import annotations

import asyncio
import threading
from abc import ABC, abstractmethod
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, BinaryIO, Iterator, Literal, TextIO

from textual import events, log, messages
from textual.events import MouseUp

if TYPE_CHECKING:
    from textual.app import App


class Driver(ABC):
    """A base class for drivers."""

    def __init__(
        self,
        app: App[Any],
        *,
        debug: bool = False,
        mouse: bool = True,
        size: tuple[int, int] | None = None,
    ) -> None:
        """Initialize a driver.

        Args:
            app: The App instance.
            debug: Enable debug mode.
            mouse: Enable mouse support,
            size: Initial size of the terminal or `None` to detect.
        """
        self._app = app
        self._debug = debug
        self._mouse = mouse
        self._size = size
        self._loop = asyncio.get_running_loop()
        self._down_buttons: list[int] = []
        self._last_move_event: events.MouseMove | None = None
        self._auto_restart = True
        """Should the application auto-restart (where appropriate)?"""
        self.cursor_origin: tuple[int, int] | None = None

    @property
    def is_headless(self) -> bool:
        """Is the driver 'headless' (no output)?"""
        pass

    @property
    def is_inline(self) -> bool:
        """Is the driver 'inline' (not full-screen)?"""
        pass

    @property
    def is_web(self) -> bool:
        """Is the driver 'web' (running via a browser)?"""
        pass

    @property
    def can_suspend(self) -> bool:
        """Can this driver be suspended?"""
        pass

    def send_message(self, message: messages.Message) -> None:
        """Send a message to the target app.

        Args:
            message: A message.
        """
        asyncio.run_coroutine_threadsafe(
            self._app._post_message(message), loop=self._loop
        )

    def process_message(self, message: messages.Message) -> None:
        """Perform additional processing on a message, prior to sending.

        Args:
            event: A message to process.
        """
        pass

    @abstractmethod
    def write(self, data: str) -> None:
        """Write data to the output device.

        Args:
            data: Raw data.
        """

    def flush(self) -> None:
        """Flush any buffered data."""

    @abstractmethod
    def start_application_mode(self) -> None:
        """Start application mode."""

    @abstractmethod
    def disable_input(self) -> None:
        """Disable further input."""

    @abstractmethod
    def stop_application_mode(self) -> None:
        """Stop application mode, restore state."""

    def suspend_application_mode(self) -> None:
        """Suspend application mode.

        Used to suspend application mode and allow uninhibited access to the
        terminal.
        """
        pass

    def resume_application_mode(self) -> None:
        """Resume application mode.

        Used to resume application mode after it has been previously
        suspended.
        """
        pass

    class SignalResume(events.Event):
        """Event sent to the app when a resume signal should be published."""

    @contextmanager
    def no_automatic_restart(self) -> Iterator[None]:
        """A context manager used to tell the driver to not auto-restart.

        For drivers that support the application being suspended by the
        operating system, this context manager is used to mark a body of
        code as one that will manage its own stop and start.
        """
        pass

    def close(self) -> None:
        """Perform any final cleanup."""

    def open_url(self, url: str, new_tab: bool = True) -> None:
        """Open a URL in the default web browser.

        Args:
            url: The URL to open.
            new_tab: Whether to open the URL in a new tab.
                This is only relevant when running via the WebDriver,
                and is ignored when called while running through the terminal.
        """
        pass

    def deliver_binary(
        self,
        binary: BinaryIO | TextIO,
        *,
        delivery_key: str,
        save_path: Path,
        open_method: Literal["browser", "download"] = "download",
        encoding: str | None = None,
        mime_type: str | None = None,
        name: str | None = None,
    ) -> None:
        """Save the file `path_or_file` to `save_path`.

        If running via web through Textual Web or Textual Serve,
        this will initiate a download in the web browser.

        Args:
            binary: The binary file to save.
            delivery_key: The unique key that was used to deliver the file.
            save_path: The location to save the file to.
            open_method: *web only* Whether to open the file in the browser or
                to prompt the user to download it. When running via a standard
                (non-web) terminal, this is ignored.
            encoding: *web only* The text encoding to use when saving the file.
                This will be passed to Python's `open()` built-in function.
                When running via web, this will be used to set the charset
                in the `Content-Type` header.
            mime_type: *web only* The MIME type of the file. This will be used to
                set the `Content-Type` header in the HTTP response.
            name: A user-defined name which will be returned in [`DeliveryComplete`][textual.events.DeliveryComplete]
                and [`DeliveryFailed`][textual.events.DeliveryFailed].

        """
        pass

    def _delivery_complete(
        self, delivery_key: str, save_path: Path | None, name: str | None
    ) -> None:
        """Called when a file has been delivered successfully.

        Delivers a DeliveryComplete event to the app.
        """
        pass

    def _delivery_failed(
        self, delivery_key: str, exception: BaseException, name: str | None
    ) -> None:
        """Called when a file delivery fails.

        Delivers a DeliveryFailed event to the app.
        """
        pass
