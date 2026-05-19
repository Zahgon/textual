"""

The Remote driver uses the following packet structure.

1 byte for packet type. "D" for data, "M" for meta.
4 byte little endian integer for the size of the payload.
Arbitrary payload.


"""

from __future__ import annotations

import asyncio
import json
import os
import signal
import sys
from codecs import getincrementaldecoder
from functools import partial
from pathlib import Path
from threading import Event, Thread
from typing import Any, BinaryIO, Literal, TextIO, cast

from textual import events, log, messages
from textual._binary_encode import dump as binary_dump
from textual._xterm_parser import XTermParser
from textual.app import App
from textual.driver import Driver
from textual.drivers._byte_stream import ByteStream
from textual.drivers._input_reader import InputReader
from textual.geometry import Size

WINDOWS = sys.platform == "win32"


class _ExitInput(Exception):
    """Internal exception to force exit of input loop."""


class WebDriver(Driver):
    """A headless driver that may be run remotely."""

    def __init__(
        self,
        app: App[Any],
        *,
        debug: bool = False,
        mouse: bool = True,
        size: tuple[int, int] | None = None,
    ):
        if size is None:
            try:
                width = int(os.environ.get("COLUMNS", 80))
                height = int(os.environ.get("ROWS", 24))
            except ValueError:
                pass
            else:
                size = width, height
        super().__init__(app, debug=debug, mouse=mouse, size=size)
        self.stdout = sys.__stdout__
        self.fileno = sys.__stdout__.fileno()
        self._write = partial(os.write, self.fileno)
        self.exit_event = Event()
        self._key_thread: Thread = Thread(
            target=self.run_input_thread, name="textual-input"
        )
        self._input_reader = InputReader()

        self._deliveries: dict[str, BinaryIO | TextIO] = {}
        """Maps delivery keys to file-like objects, used
        for delivering files to the browser."""


    def write(self, data: str) -> None:
        """Write string data to the output device, which may be piped to
        the parent process (i.e. textual-web/textual-serve).

        Args:
            data: Raw data.
        """

        data_bytes = data.encode("utf-8")
        self._write(b"D%s%s" % (len(data_bytes).to_bytes(4, "big"), data_bytes))

    def write_meta(self, data: dict[str, object]) -> None:
        """Write a dictionary containing some metadata to stdout, which
        may be piped to the parent process (i.e. textual-web/textual-serve).

        Args:
            data: Meta dict.
        """
        meta_bytes = json.dumps(data).encode("utf-8", errors="ignore")
        self._write(b"M%s%s" % (len(meta_bytes).to_bytes(4, "big"), meta_bytes))

    def write_binary_encoded(self, data: tuple[str | bytes, ...]) -> None:
        """Binary encode a data-structure and write to stdout.

        Args:
            data: The data to binary encode and write.
        """
        pass

    def flush(self) -> None:
        pass

    def _enable_mouse_support(self) -> None:
        """Enable reporting of mouse events."""
        write = self.write
        write("\x1b[?1000h")  # SET_VT200_MOUSE
        write("\x1b[?1003h")  # SET_ANY_EVENT_MOUSE
        write("\x1b[?1015h")  # SET_VT200_HIGHLIGHT_MOUSE
        write("\x1b[?1006h")  # SET_SGR_EXT_MODE_MOUSE

    def _enable_bracketed_paste(self) -> None:
        """Enable bracketed paste mode."""
        self.write("\x1b[?2004h")

    def _disable_bracketed_paste(self) -> None:
        """Disable bracketed paste mode."""
        self.write("\x1b[?2004l")

    def _disable_mouse_support(self) -> None:
        """Disable reporting of mouse events."""
        write = self.write
        write("\x1b[?1000l")  #
        write("\x1b[?1003l")  #
        write("\x1b[?1015l")
        write("\x1b[?1006l")

    def _request_terminal_sync_mode_support(self) -> None:
        """Writes an escape sequence to query the terminal support for the sync protocol."""
        self.write("\033[?2026$p")

    def start_application_mode(self) -> None:
        """Start application mode."""

        loop = asyncio.get_running_loop()

        def do_exit() -> None:
            """Callback to force exit."""
            pass

        if not WINDOWS:
            for _signal in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(_signal, do_exit)

        self._write(b"__GANGLION__\n")

        self.write("\x1b[?1049h")  # Alt screen
        self._enable_mouse_support()

        self.write("\x1b[?25l")  # Hide cursor
        self.write("\033[?1003h")

        size = Size(80, 24) if self._size is None else Size(*self._size)
        event = events.Resize(size, size)
        asyncio.run_coroutine_threadsafe(
            self._app._post_message(event),
            loop=loop,
        )

        self._request_terminal_sync_mode_support()
        self._enable_bracketed_paste()
        self.flush()
        self._key_thread.start()
        self._app.call_later(self._app.post_message, events.AppBlur())

    def disable_input(self) -> None:
        """Disable further input."""

    def stop_application_mode(self) -> None:
        """Stop application mode, restore state."""
        self.exit_event.set()
        self._input_reader.close()
        self.write_meta({"type": "exit"})

    def run_input_thread(self) -> None:
        """Wait for input and dispatch events."""
        pass

    def _on_meta(self, packet_type: str, payload: bytes) -> None:
        """Private method to dispatch meta.

        Args:
            packet_type: Packet type (currently always "M")
            payload: Meta payload (JSON encoded as bytes).
        """
        pass

    def on_meta(self, packet_type: str, payload: dict[str, object]) -> None:
        """Process a dictionary containing information received from the controlling process.

        Args:
            packet_type: The type of the packet.
            payload: meta dict.
        """
        pass

    def open_url(self, url: str, new_tab: bool = True) -> None:
        """Open a URL in the default web browser.

        Args:
            url: The URL to open.
            new_tab: Whether to open the URL in a new tab.
        """
        pass


    def _deliver_file(
        self,
        binary: BinaryIO | TextIO,
        *,
        delivery_key: str,
        save_path: Path,
        open_method: Literal["browser", "download"],
        encoding: str | None = None,
        mime_type: str | None = None,
        name: str | None = None,
    ) -> None:
        """Deliver a file to the end-user of the application."""
        pass
