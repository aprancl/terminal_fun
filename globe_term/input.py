"""Mouse event handling (curses mouse events).

Translates raw curses mouse events into high-level input actions such as
DRAG_START, DRAG_MOVE, DRAG_END, SCROLL_UP, SCROLL_DOWN, and CLICK.

The :class:`InputHandler` class manages all mouse state including button
tracking, drag detection, and idle-time measurement.  The main entry point
is :meth:`InputHandler.process_event`, which accepts a raw curses key code
and returns an :class:`InputEvent` (or ``None`` when the event is not
mouse-related or is not actionable).

Usage inside a curses loop::

    handler = InputHandler(stdscr)
    while True:
        key = stdscr.getch()
        event = handler.process_event(key)
        if event is not None:
            # React to event.action, event.x, event.y, event.dx, event.dy
            ...
"""

from __future__ import annotations

import curses
import enum
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Optional, Tuple


# ---------------------------------------------------------------------------
# Action types
# ---------------------------------------------------------------------------

class Action(enum.Enum):
    """High-level input action types."""

    CLICK = "click"
    DRAG_START = "drag_start"
    DRAG_MOVE = "drag_move"
    DRAG_END = "drag_end"
    SCROLL_UP = "scroll_up"
    SCROLL_DOWN = "scroll_down"


# ---------------------------------------------------------------------------
# InputEvent dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class InputEvent:
    """A processed input event carrying action type and coordinates.

    Attributes:
        action: The high-level action type.
        x: Screen column of the event.
        y: Screen row of the event.
        dx: Horizontal delta since the last event (meaningful for drags).
        dy: Vertical delta since the last event (meaningful for drags).
    """

    action: Action
    x: int = 0
    y: int = 0
    dx: int = 0
    dy: int = 0


# ---------------------------------------------------------------------------
# InputHandler
# ---------------------------------------------------------------------------

# Distance (in cells) a mouse must move while pressed before we promote the
# gesture from a potential click to a drag.
_DRAG_THRESHOLD = 2


class InputHandler:
    """Manages mouse state and translates curses events into :class:`InputEvent`.

    Call :meth:`enable_mouse` once after curses initialisation to request
    mouse event reporting.  Then feed every ``stdscr.getch()`` result into
    :meth:`process_event`.

    Attributes:
        mouse_supported: Whether the terminal accepted mouse event reporting.
    """

    def __init__(self, stdscr: Any | None = None) -> None:
        self._stdscr = stdscr

        # Mouse button state
        self._button_pressed: bool = False
        self._dragging: bool = False

        # Position tracking
        self._press_x: int = 0
        self._press_y: int = 0
        self._last_x: int = 0
        self._last_y: int = 0

        # Idle tracking
        self._last_event_time: float = time.monotonic()

        # Whether the terminal supports mouse events
        self.mouse_supported: bool = False

        # Enable mouse reporting automatically if a screen was provided
        if stdscr is not None:
            self.enable_mouse()

    # -- Setup ----------------------------------------------------------------

    def enable_mouse(self) -> bool:
        """Request mouse event reporting from curses.

        In addition to calling ``curses.mousemask()``, this writes xterm
        escape sequences to enable mouse motion tracking.  Most terminals
        need these sequences to report drag/motion events — the curses
        mask alone is not sufficient.

        Returns:
            ``True`` if the terminal accepted mouse events, ``False`` otherwise.
        """
        try:
            available, _ = curses.mousemask(
                curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION
            )
            self.mouse_supported = available != 0
        except curses.error:
            self.mouse_supported = False

        if self.mouse_supported:
            # Enable xterm mouse tracking escape sequences:
            #   1000 = basic button events
            #   1002 = button-event tracking (reports motion while pressed)
            #   1006 = SGR extended mode (supports large coordinates)
            sys.stdout.write("\033[?1000h\033[?1002h\033[?1006h")
            sys.stdout.flush()

        return self.mouse_supported

    def disable_mouse(self) -> None:
        """Disable mouse tracking escape sequences.

        Call this during cleanup to restore the terminal to normal state.
        """
        if self.mouse_supported:
            sys.stdout.write("\033[?1006l\033[?1002l\033[?1000l")
            sys.stdout.flush()

    # -- Idle tracking --------------------------------------------------------

    @property
    def last_event_time(self) -> float:
        """Monotonic timestamp of the most recent input event."""
        return self._last_event_time

    def idle_seconds(self) -> float:
        """Seconds elapsed since the last input event."""
        return time.monotonic() - self._last_event_time

    # -- Event processing -----------------------------------------------------

    def process_event(self, key: int) -> Optional[InputEvent]:
        """Translate a raw curses key code into an :class:`InputEvent`.

        Only ``curses.KEY_MOUSE`` triggers mouse processing.  All other key
        codes are ignored (returns ``None``).

        Args:
            key: The value returned by ``stdscr.getch()``.

        Returns:
            An :class:`InputEvent` if the event was actionable, otherwise ``None``.
        """
        if key != curses.KEY_MOUSE:
            return None

        # Update idle timer for every mouse event
        self._last_event_time = time.monotonic()

        try:
            _id, mx, my, _mz, bstate = curses.getmouse()
        except curses.error:
            # Terminal may report KEY_MOUSE without valid mouse data
            return None

        return self._handle_mouse(mx, my, bstate)

    # -- Internal mouse state machine -----------------------------------------

    def _handle_mouse(self, mx: int, my: int, bstate: int) -> Optional[InputEvent]:
        """Core mouse state machine.

        Handles press / release / motion / scroll and returns the
        appropriate :class:`InputEvent`.
        """
        # ---- Scroll events (independent of button state) -------------------
        if bstate & _scroll_up_mask():
            return InputEvent(action=Action.SCROLL_UP, x=mx, y=my)

        if bstate & _scroll_down_mask():
            return InputEvent(action=Action.SCROLL_DOWN, x=mx, y=my)

        # ---- Button press --------------------------------------------------
        if bstate & _button1_pressed_mask():
            self._button_pressed = True
            self._dragging = False
            self._press_x = mx
            self._press_y = my
            self._last_x = mx
            self._last_y = my
            # Don't emit an event yet -- wait for motion or release
            return None

        # ---- Motion while button held (drag) --------------------------------
        if self._button_pressed and (bstate & _report_mouse_position_mask()):
            dx = mx - self._last_x
            dy = my - self._last_y

            if not self._dragging:
                # Check if we've moved far enough to call it a drag
                total_dx = mx - self._press_x
                total_dy = my - self._press_y
                if abs(total_dx) + abs(total_dy) >= _DRAG_THRESHOLD:
                    self._dragging = True
                    self._last_x = mx
                    self._last_y = my
                    return InputEvent(
                        action=Action.DRAG_START,
                        x=mx,
                        y=my,
                        dx=total_dx,
                        dy=total_dy,
                    )
                # Not enough motion yet -- still a potential click
                return None

            # Already dragging
            self._last_x = mx
            self._last_y = my
            return InputEvent(action=Action.DRAG_MOVE, x=mx, y=my, dx=dx, dy=dy)

        # ---- Button release -------------------------------------------------
        if bstate & _button1_released_mask():
            was_dragging = self._dragging
            self._button_pressed = False
            self._dragging = False

            if was_dragging:
                dx = mx - self._last_x
                dy = my - self._last_y
                self._last_x = mx
                self._last_y = my
                return InputEvent(
                    action=Action.DRAG_END, x=mx, y=my, dx=dx, dy=dy
                )

            # Button released without dragging -> CLICK
            self._last_x = mx
            self._last_y = my
            return InputEvent(action=Action.CLICK, x=mx, y=my)

        # ---- Button click (some terminals report BUTTON1_CLICKED) -----------
        if bstate & _button1_clicked_mask():
            self._button_pressed = False
            self._dragging = False
            self._last_x = mx
            self._last_y = my
            return InputEvent(action=Action.CLICK, x=mx, y=my)

        # Unrecognised or irrelevant button state
        return None


# ---------------------------------------------------------------------------
# Curses bitmask helpers
# ---------------------------------------------------------------------------
# Wrapped in functions to allow safe access even when curses constants are
# not fully defined (e.g. in headless test environments).


def _button1_pressed_mask() -> int:
    return getattr(curses, "BUTTON1_PRESSED", 0x2)


def _button1_released_mask() -> int:
    return getattr(curses, "BUTTON1_RELEASED", 0x1)


def _button1_clicked_mask() -> int:
    return getattr(curses, "BUTTON1_CLICKED", 0x4)


def _scroll_up_mask() -> int:
    # BUTTON4_PRESSED is the traditional curses constant for scroll-up.
    # Some ncurses builds also provide BUTTON_SCROLL_UP.
    return getattr(curses, "BUTTON4_PRESSED", 0x80000)


def _scroll_down_mask() -> int:
    # BUTTON5_PRESSED may not exist on older ncurses.  Fall back to a
    # commonly used value (0x200000) and also check REPORT_MOUSE_POSITION
    # as some systems map scroll-down there.
    if hasattr(curses, "BUTTON5_PRESSED"):
        return curses.BUTTON5_PRESSED
    # Fallback value used by many ncurses builds
    return 0x200000


def _report_mouse_position_mask() -> int:
    return getattr(curses, "REPORT_MOUSE_POSITION", 0x10000000)
