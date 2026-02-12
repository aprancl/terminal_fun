"""Tests for globe_term.input - Mouse event handling module."""

from __future__ import annotations

import curses
import time
from unittest.mock import MagicMock, patch

import pytest

from globe_term.input import (
    Action,
    InputEvent,
    InputHandler,
    _DRAG_THRESHOLD,
    _button1_clicked_mask,
    _button1_pressed_mask,
    _button1_released_mask,
    _report_mouse_position_mask,
    _scroll_down_mask,
    _scroll_up_mask,
)


# ---------------------------------------------------------------------------
# InputEvent dataclass construction
# ---------------------------------------------------------------------------

class TestInputEvent:
    """Unit tests for InputEvent dataclass construction."""

    def test_basic_construction(self):
        evt = InputEvent(action=Action.CLICK, x=10, y=20)
        assert evt.action == Action.CLICK
        assert evt.x == 10
        assert evt.y == 20
        assert evt.dx == 0
        assert evt.dy == 0

    def test_construction_with_deltas(self):
        evt = InputEvent(action=Action.DRAG_MOVE, x=5, y=6, dx=3, dy=-2)
        assert evt.action == Action.DRAG_MOVE
        assert evt.x == 5
        assert evt.y == 6
        assert evt.dx == 3
        assert evt.dy == -2

    def test_defaults(self):
        evt = InputEvent(action=Action.SCROLL_UP)
        assert evt.x == 0
        assert evt.y == 0
        assert evt.dx == 0
        assert evt.dy == 0

    def test_frozen(self):
        evt = InputEvent(action=Action.CLICK, x=1, y=2)
        with pytest.raises(AttributeError):
            evt.x = 99  # type: ignore[misc]

    def test_all_action_types(self):
        """Every Action enum value can be used in an InputEvent."""
        for action in Action:
            evt = InputEvent(action=action)
            assert evt.action == action

    def test_equality(self):
        a = InputEvent(action=Action.CLICK, x=1, y=2)
        b = InputEvent(action=Action.CLICK, x=1, y=2)
        assert a == b

    def test_inequality(self):
        a = InputEvent(action=Action.CLICK, x=1, y=2)
        b = InputEvent(action=Action.CLICK, x=1, y=3)
        assert a != b


# ---------------------------------------------------------------------------
# Action enum
# ---------------------------------------------------------------------------

class TestAction:
    def test_all_expected_actions_exist(self):
        expected = {"CLICK", "DRAG_START", "DRAG_MOVE", "DRAG_END",
                    "SCROLL_UP", "SCROLL_DOWN"}
        actual = {a.name for a in Action}
        assert expected == actual


# ---------------------------------------------------------------------------
# Helper: create an InputHandler without a real curses screen
# ---------------------------------------------------------------------------

def _make_handler() -> InputHandler:
    """Create an InputHandler with no screen (for unit tests)."""
    handler = InputHandler(stdscr=None)
    # Simulate that mouse is supported
    handler.mouse_supported = True
    return handler


def _simulate_mouse(handler: InputHandler, mx: int, my: int, bstate: int):
    """Simulate a curses mouse event through the handler.

    Patches curses.getmouse to return the given coordinates and bstate,
    then calls process_event with KEY_MOUSE.
    """
    with patch("curses.getmouse", return_value=(0, mx, my, 0, bstate)):
        return handler.process_event(curses.KEY_MOUSE)


# ---------------------------------------------------------------------------
# InputHandler: enable_mouse
# ---------------------------------------------------------------------------

class TestEnableMouse:
    def test_enable_mouse_success(self):
        handler = InputHandler(stdscr=None)
        with patch("curses.mousemask", return_value=(0xFFFF, 0)):
            result = handler.enable_mouse()
        assert result is True
        assert handler.mouse_supported is True

    def test_enable_mouse_not_supported(self):
        handler = InputHandler(stdscr=None)
        with patch("curses.mousemask", return_value=(0, 0)):
            result = handler.enable_mouse()
        assert result is False
        assert handler.mouse_supported is False

    def test_enable_mouse_curses_error(self):
        """curses.error from mousemask is caught gracefully."""
        handler = InputHandler(stdscr=None)
        with patch("curses.mousemask", side_effect=curses.error("no mouse")):
            result = handler.enable_mouse()
        assert result is False
        assert handler.mouse_supported is False


# ---------------------------------------------------------------------------
# InputHandler: non-mouse keys are ignored
# ---------------------------------------------------------------------------

class TestNonMouseKeys:
    def test_regular_key_returns_none(self):
        handler = _make_handler()
        assert handler.process_event(ord("q")) is None

    def test_arrow_key_returns_none(self):
        handler = _make_handler()
        assert handler.process_event(curses.KEY_UP) is None

    def test_resize_key_returns_none(self):
        handler = _make_handler()
        assert handler.process_event(curses.KEY_RESIZE) is None


# ---------------------------------------------------------------------------
# InputHandler: scroll events
# ---------------------------------------------------------------------------

class TestScrollEvents:
    def test_scroll_up(self):
        handler = _make_handler()
        evt = _simulate_mouse(handler, 10, 20, _scroll_up_mask())
        assert evt is not None
        assert evt.action == Action.SCROLL_UP
        assert evt.x == 10
        assert evt.y == 20

    def test_scroll_down(self):
        handler = _make_handler()
        evt = _simulate_mouse(handler, 15, 25, _scroll_down_mask())
        assert evt is not None
        assert evt.action == Action.SCROLL_DOWN
        assert evt.x == 15
        assert evt.y == 25


# ---------------------------------------------------------------------------
# InputHandler: click detection (press + release without drag)
# ---------------------------------------------------------------------------

class TestClickDetection:
    def test_press_then_release_produces_click(self):
        """A press followed by a release at the same position -> CLICK."""
        handler = _make_handler()

        # Press
        evt = _simulate_mouse(handler, 10, 10, _button1_pressed_mask())
        assert evt is None  # press alone doesn't emit an event

        # Release at same position
        evt = _simulate_mouse(handler, 10, 10, _button1_released_mask())
        assert evt is not None
        assert evt.action == Action.CLICK
        assert evt.x == 10
        assert evt.y == 10

    def test_click_without_drag_is_click_not_drag(self):
        """Click without sufficient motion should NOT produce DRAG events."""
        handler = _make_handler()

        # Press
        _simulate_mouse(handler, 5, 5, _button1_pressed_mask())
        # Release at nearly the same position (below threshold)
        evt = _simulate_mouse(handler, 6, 5, _button1_released_mask())
        assert evt is not None
        assert evt.action == Action.CLICK

    def test_button1_clicked_event(self):
        """Some terminals report BUTTON1_CLICKED directly."""
        handler = _make_handler()
        evt = _simulate_mouse(handler, 7, 8, _button1_clicked_mask())
        assert evt is not None
        assert evt.action == Action.CLICK
        assert evt.x == 7
        assert evt.y == 8


# ---------------------------------------------------------------------------
# InputHandler: drag detection state machine
# ---------------------------------------------------------------------------

class TestDragDetection:
    def test_drag_sequence(self):
        """Full drag: press -> move beyond threshold -> move -> release."""
        handler = _make_handler()

        # 1. Press
        evt = _simulate_mouse(handler, 10, 10, _button1_pressed_mask())
        assert evt is None

        # 2. Move just below threshold -> no event yet
        evt = _simulate_mouse(handler, 11, 10, _report_mouse_position_mask())
        assert evt is None

        # 3. Move beyond threshold -> DRAG_START
        evt = _simulate_mouse(handler, 10 + _DRAG_THRESHOLD, 10,
                              _report_mouse_position_mask())
        assert evt is not None
        assert evt.action == Action.DRAG_START

        # 4. Continue moving -> DRAG_MOVE
        evt = _simulate_mouse(handler, 15, 12, _report_mouse_position_mask())
        assert evt is not None
        assert evt.action == Action.DRAG_MOVE

        # 5. Release -> DRAG_END
        evt = _simulate_mouse(handler, 16, 13, _button1_released_mask())
        assert evt is not None
        assert evt.action == Action.DRAG_END

    def test_drag_delta_computed_correctly(self):
        """Verify dx/dy values in DRAG_MOVE events."""
        handler = _make_handler()

        # Press at (10, 10)
        _simulate_mouse(handler, 10, 10, _button1_pressed_mask())

        # Move far enough for DRAG_START
        _simulate_mouse(handler, 10 + _DRAG_THRESHOLD + 5, 10,
                         _report_mouse_position_mask())

        # The position is now (10 + _DRAG_THRESHOLD + 5, 10).
        # Next move to (20, 15).
        evt = _simulate_mouse(handler, 20, 15, _report_mouse_position_mask())
        assert evt is not None
        assert evt.action == Action.DRAG_MOVE
        # dx = 20 - (10 + _DRAG_THRESHOLD + 5) = 20 - 17 = 3  (with default threshold=2)
        expected_dx = 20 - (10 + _DRAG_THRESHOLD + 5)
        expected_dy = 15 - 10
        assert evt.dx == expected_dx
        assert evt.dy == expected_dy

    def test_drag_start_contains_total_delta(self):
        """DRAG_START should carry the total delta from press to start."""
        handler = _make_handler()

        _simulate_mouse(handler, 10, 20, _button1_pressed_mask())

        # Exceed threshold diagonally
        target_x = 10 + _DRAG_THRESHOLD
        target_y = 20 + 1
        evt = _simulate_mouse(handler, target_x, target_y,
                              _report_mouse_position_mask())
        assert evt is not None
        assert evt.action == Action.DRAG_START
        assert evt.dx == target_x - 10
        assert evt.dy == target_y - 20

    def test_release_after_drag_resets_state(self):
        """After DRAG_END, a new press should start fresh."""
        handler = _make_handler()

        # Complete a drag
        _simulate_mouse(handler, 10, 10, _button1_pressed_mask())
        _simulate_mouse(handler, 10 + _DRAG_THRESHOLD + 3, 10,
                         _report_mouse_position_mask())
        _simulate_mouse(handler, 20, 10, _button1_released_mask())

        # New press at a different position
        evt = _simulate_mouse(handler, 50, 50, _button1_pressed_mask())
        assert evt is None  # fresh press, no event

        # Release without motion -> CLICK
        evt = _simulate_mouse(handler, 50, 50, _button1_released_mask())
        assert evt is not None
        assert evt.action == Action.CLICK

    def test_rapid_press_release_no_state_confusion(self):
        """Rapid press/release cycles shouldn't confuse the state machine."""
        handler = _make_handler()

        for _ in range(20):
            _simulate_mouse(handler, 10, 10, _button1_pressed_mask())
            evt = _simulate_mouse(handler, 10, 10, _button1_released_mask())
            assert evt is not None
            assert evt.action == Action.CLICK


# ---------------------------------------------------------------------------
# InputHandler: idle time calculation
# ---------------------------------------------------------------------------

class TestIdleTime:
    def test_idle_seconds_increases_over_time(self):
        handler = _make_handler()
        # Force a known last_event_time
        handler._last_event_time = time.monotonic() - 2.0
        idle = handler.idle_seconds()
        assert idle >= 1.9  # allow small timing margin

    def test_event_resets_idle_time(self):
        """Processing a mouse event should reset the idle timer."""
        handler = _make_handler()
        handler._last_event_time = time.monotonic() - 5.0

        # Process a mouse event
        _simulate_mouse(handler, 0, 0, _scroll_up_mask())

        idle = handler.idle_seconds()
        assert idle < 1.0  # should be very close to 0

    def test_last_event_time_property(self):
        handler = _make_handler()
        t = handler.last_event_time
        assert isinstance(t, float)
        assert t > 0

    def test_initial_idle_is_small(self):
        """Right after creation, idle time should be near zero."""
        handler = _make_handler()
        assert handler.idle_seconds() < 1.0


# ---------------------------------------------------------------------------
# InputHandler: getmouse error handling
# ---------------------------------------------------------------------------

class TestGetmouseError:
    def test_getmouse_raises_curses_error(self):
        """If curses.getmouse() raises, process_event returns None."""
        handler = _make_handler()
        with patch("curses.getmouse", side_effect=curses.error("bad mouse")):
            evt = handler.process_event(curses.KEY_MOUSE)
        assert evt is None


# ---------------------------------------------------------------------------
# InputHandler: edge cases - mouse events outside bounds
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_negative_coordinates(self):
        """Negative mouse coordinates should not crash."""
        handler = _make_handler()
        # Scroll at negative coords - should still produce event
        evt = _simulate_mouse(handler, -1, -1, _scroll_up_mask())
        assert evt is not None
        assert evt.action == Action.SCROLL_UP
        assert evt.x == -1
        assert evt.y == -1

    def test_large_coordinates(self):
        """Very large coordinates should be handled gracefully."""
        handler = _make_handler()
        evt = _simulate_mouse(handler, 9999, 9999, _scroll_down_mask())
        assert evt is not None
        assert evt.action == Action.SCROLL_DOWN

    def test_unrecognised_bstate_returns_none(self):
        """An unknown bstate (e.g. right click) should return None."""
        handler = _make_handler()
        # Use a bstate that doesn't match any known mask
        evt = _simulate_mouse(handler, 10, 10, 0)
        assert evt is None

    def test_motion_without_press_ignored(self):
        """Mouse motion without a prior press should not emit events."""
        handler = _make_handler()
        evt = _simulate_mouse(handler, 10, 10, _report_mouse_position_mask())
        assert evt is None

    def test_release_without_press_graceful(self):
        """A release without a preceding press should not crash."""
        handler = _make_handler()
        # This shouldn't raise or produce a spurious DRAG_END
        evt = _simulate_mouse(handler, 10, 10, _button1_released_mask())
        # It may produce a CLICK (press was never set, but dragging was
        # false), which is acceptable behaviour
        if evt is not None:
            assert evt.action == Action.CLICK


# ---------------------------------------------------------------------------
# InputHandler: constructor with stdscr
# ---------------------------------------------------------------------------

class TestConstructorWithScreen:
    def test_auto_enables_mouse(self):
        """Passing a stdscr to the constructor should call enable_mouse."""
        mock_scr = MagicMock()
        with patch("curses.mousemask", return_value=(0xFFFF, 0)):
            handler = InputHandler(stdscr=mock_scr)
        assert handler.mouse_supported is True

    def test_constructor_without_screen(self):
        handler = InputHandler(stdscr=None)
        assert handler.mouse_supported is False
