"""Terminal detection, capability checking, resize debouncing.

Provides helper functions for detecting terminal capabilities such as
Unicode support, color support, mouse support, and terminal dimensions.
Also provides a debouncer for resize events and pipe/non-terminal detection.
These are used by the CLI layer to choose an appropriate render mode and
to handle degraded terminals gracefully.
"""

from __future__ import annotations

import locale
import os
import shutil
import sys
import time
from typing import Callable, Optional, Tuple


def detect_unicode_support() -> bool:
    """Check if the current terminal likely supports Unicode output.

    Heuristics (in order):
    1. ``LANG`` / ``LC_ALL`` / ``LC_CTYPE`` environment variable contains
       ``utf`` (case-insensitive).
    2. Python's preferred encoding (from :func:`locale.getpreferredencoding`)
       contains ``utf``.
    3. ``sys.stdout.encoding`` contains ``utf``.

    Returns:
        ``True`` if Unicode is probably supported, ``False`` otherwise.
    """
    # Check environment variables
    for var in ("LC_ALL", "LC_CTYPE", "LANG"):
        value = os.environ.get(var, "")
        if "utf" in value.lower():
            return True

    # Check Python's preferred encoding
    try:
        preferred = locale.getpreferredencoding(False)
        if "utf" in preferred.lower():
            return True
    except Exception:
        pass

    # Check stdout encoding
    try:
        if hasattr(sys.stdout, "encoding") and sys.stdout.encoding:
            if "utf" in sys.stdout.encoding.lower():
                return True
    except Exception:
        pass

    return False


def detect_color_support() -> bool:
    """Check if the current terminal likely supports colors.

    Heuristics:
    1. ``NO_COLOR`` environment variable is set -> no colors.
    2. ``TERM`` contains ``mono`` -> no colors.
    3. ``COLORTERM`` is set -> yes.
    4. ``TERM`` is ``dumb`` or empty -> no colors.
    5. Otherwise assume yes (curses will do its own check at runtime).

    Returns:
        ``True`` if colors are probably supported, ``False`` otherwise.
    """
    # Respect the NO_COLOR convention (https://no-color.org/)
    if os.environ.get("NO_COLOR") is not None:
        return False

    term = os.environ.get("TERM", "")

    # Explicit monochrome terminal
    if "mono" in term.lower():
        return False

    # COLORTERM is a strong signal
    if os.environ.get("COLORTERM"):
        return True

    # Dumb or empty TERM -> no colors
    if term.lower() in ("", "dumb"):
        return False

    # Default: assume colors are available
    return True


def detect_color_count() -> int:
    """Detect the number of colors the terminal likely supports.

    Heuristics:
    1. If ``NO_COLOR`` is set or colors not supported -> 0.
    2. ``COLORTERM`` is ``truecolor`` or ``24bit`` -> 16777216 (2**24).
    3. ``TERM`` contains ``256color`` -> 256.
    4. ``TERM`` contains ``color`` -> 16.
    5. Default fallback -> 8.

    Returns:
        Number of colors the terminal is expected to support.
    """
    if not detect_color_support():
        return 0

    colorterm = os.environ.get("COLORTERM", "").lower()
    if colorterm in ("truecolor", "24bit"):
        return 16777216  # 2**24

    term = os.environ.get("TERM", "").lower()
    if "256color" in term:
        return 256

    if "color" in term:
        return 16

    # Default: basic 8 colors
    return 8


def detect_mouse_support() -> bool:
    """Detect whether the terminal likely supports mouse events.

    Heuristics:
    1. Not a real terminal (piped) -> no mouse.
    2. ``TERM`` is ``dumb`` or empty -> no mouse.
    3. Running inside tmux or screen -> check ``TERM`` inside.
    4. ``TERM`` contains ``xterm``, ``rxvt``, ``screen``, ``tmux``,
       ``linux``, or ``vt100`` variants -> yes.
    5. Default -> no.

    Returns:
        ``True`` if mouse events are probably supported.
    """
    if not is_terminal():
        return False

    term = os.environ.get("TERM", "").lower()

    if term in ("", "dumb"):
        return False

    # Most modern terminals support mouse
    mouse_capable_prefixes = (
        "xterm", "rxvt", "screen", "tmux", "linux",
        "vt100", "vt220", "ansi", "cygwin", "mintty",
    )
    for prefix in mouse_capable_prefixes:
        if prefix in term:
            return True

    # tmux/screen sets TERM_PROGRAM or TMUX env
    if os.environ.get("TMUX") or os.environ.get("STY"):
        return True

    return False


def detect_terminal() -> str:
    """Identify the terminal emulator in use.

    Checks environment variables to determine which terminal emulator is
    running.  This information is used downstream to select the correct
    mouse-protocol negotiation strategy.

    Detection order:
    1. ``TERM_PROGRAM`` — set by most modern terminal emulators.
    2. ``TERM`` — Kitty sets ``xterm-kitty`` even when ``TERM_PROGRAM``
       is overridden (e.g. inside tmux).
    3. ``WT_SESSION`` — Windows Terminal sets this unconditionally.

    Returns:
        One of ``"kitty"``, ``"iterm2"``, ``"apple_terminal"``,
        ``"windows_terminal"``, or ``"unknown"``.
    """
    term_program = os.environ.get("TERM_PROGRAM", "").lower()

    if term_program == "kitty":
        return "kitty"
    if term_program == "iterm.app":
        return "iterm2"
    if term_program == "apple_terminal":
        return "apple_terminal"

    # Kitty inside tmux: TERM_PROGRAM may be overridden, but TERM is
    # still ``xterm-kitty``.
    term = os.environ.get("TERM", "").lower()
    if term == "xterm-kitty":
        return "kitty"

    # Windows Terminal always sets WT_SESSION.
    if os.environ.get("WT_SESSION"):
        return "windows_terminal"

    return "unknown"


def is_terminal() -> bool:
    """Check whether stdout is connected to a real terminal.

    Returns ``False`` when output is piped or redirected, which means
    the application should not attempt interactive curses rendering.

    Returns:
        ``True`` if stdout is a TTY, ``False`` otherwise.
    """
    try:
        return sys.stdout.isatty()
    except Exception:
        return False


def get_terminal_size() -> Tuple[int, int]:
    """Return the current terminal dimensions as ``(columns, rows)``.

    Uses :func:`shutil.get_terminal_size` with a sensible fallback of
    (80, 24) if the real size cannot be determined (e.g. piped output).

    Returns:
        ``(columns, rows)`` tuple.
    """
    try:
        size = shutil.get_terminal_size(fallback=(80, 24))
        return (size.columns, size.lines)
    except Exception:
        return (80, 24)


# ---------------------------------------------------------------------------
# Resize debouncing
# ---------------------------------------------------------------------------

class ResizeDebouncer:
    """Debounce rapid terminal resize events.

    Prevents re-rendering more than once per *interval* seconds.
    The caller should invoke :meth:`should_handle` on each resize event;
    it returns ``True`` only when enough time has elapsed since the last
    handled resize.

    Args:
        interval: Minimum seconds between handled resizes.  Default is
            0.1 (100 ms).
        clock: Optional callable returning the current time in seconds
            (defaults to :func:`time.monotonic`).  Useful for testing.
    """

    def __init__(
        self,
        interval: float = 0.1,
        clock: Optional[Callable[[], float]] = None,
    ) -> None:
        if interval < 0:
            raise ValueError("interval must be non-negative")
        self._interval = interval
        self._clock = clock or time.monotonic
        self._last_handled: float = 0.0
        self._pending: bool = False

    @property
    def interval(self) -> float:
        """Minimum interval between handled resizes."""
        return self._interval

    @property
    def pending(self) -> bool:
        """Whether a resize event is pending (was suppressed)."""
        return self._pending

    def should_handle(self) -> bool:
        """Record a resize event and return whether it should be processed.

        Returns ``True`` if at least *interval* seconds have elapsed since
        the last handled event, ``False`` otherwise (the event is marked
        as pending so it can be flushed later via :meth:`flush`).
        """
        now = self._clock()
        elapsed = now - self._last_handled
        if elapsed >= self._interval:
            self._last_handled = now
            self._pending = False
            return True
        self._pending = True
        return False

    def flush(self) -> bool:
        """Check whether a pending resize should now be handled.

        Returns ``True`` (and clears the pending flag) if there is a
        pending event and enough time has elapsed.  Returns ``False``
        otherwise.
        """
        if not self._pending:
            return False
        now = self._clock()
        if now - self._last_handled >= self._interval:
            self._last_handled = now
            self._pending = False
            return True
        return False

    def reset(self) -> None:
        """Reset the debouncer state."""
        self._last_handled = 0.0
        self._pending = False
