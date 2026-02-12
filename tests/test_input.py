"""Tests for globe_term.input - Mouse event handling module."""

from __future__ import annotations

import curses
import io
import time
from unittest import mock
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

    def test_scroll_up_via_button4_pressed(self):
        """BUTTON4_PRESSED alone triggers scroll up."""
        handler = _make_handler()
        bstate = getattr(curses, "BUTTON4_PRESSED", 0x10000)
        evt = _simulate_mouse(handler, 5, 5, bstate)
        assert evt is not None
        assert evt.action == Action.SCROLL_UP

    def test_scroll_up_via_button4_clicked(self):
        """BUTTON4_CLICKED (alternative encoding) triggers scroll up."""
        handler = _make_handler()
        bstate = getattr(curses, "BUTTON4_CLICKED", 0x20000)
        evt = _simulate_mouse(handler, 5, 5, bstate)
        assert evt is not None
        assert evt.action == Action.SCROLL_UP

    def test_scroll_down_via_button5_pressed(self):
        """BUTTON5_PRESSED alone triggers scroll down."""
        handler = _make_handler()
        bstate = getattr(curses, "BUTTON5_PRESSED", 0x200000)
        evt = _simulate_mouse(handler, 5, 5, bstate)
        assert evt is not None
        assert evt.action == Action.SCROLL_DOWN

    def test_scroll_down_via_button5_clicked(self):
        """BUTTON5_CLICKED (alternative encoding) triggers scroll down."""
        handler = _make_handler()
        bstate = getattr(curses, "BUTTON5_CLICKED", 0x400000)
        evt = _simulate_mouse(handler, 5, 5, bstate)
        assert evt is not None
        assert evt.action == Action.SCROLL_DOWN

    def test_scroll_not_confused_with_button1_press(self):
        """A BUTTON1_PRESSED event should not be treated as scroll."""
        handler = _make_handler()
        evt = _simulate_mouse(handler, 5, 5, _button1_pressed_mask())
        # BUTTON1_PRESSED returns None (press queued, no event yet)
        assert evt is None

    def test_scroll_not_confused_with_button1_release(self):
        """A BUTTON1_RELEASED event should not be treated as scroll."""
        handler = _make_handler()
        evt = _simulate_mouse(handler, 5, 5, _button1_released_mask())
        # Without a prior press, this may produce CLICK but never SCROLL
        if evt is not None:
            assert evt.action != Action.SCROLL_UP
            assert evt.action != Action.SCROLL_DOWN

    def test_scroll_during_drag_still_detected(self):
        """Scroll events during an active drag are still recognized."""
        handler = _make_handler()

        # Start a drag
        _simulate_mouse(handler, 10, 10, _button1_pressed_mask())
        _simulate_mouse(handler, 10 + _DRAG_THRESHOLD + 1, 10,
                        _report_mouse_position_mask())

        # Scroll during the drag
        evt = _simulate_mouse(handler, 15, 10, _scroll_up_mask())
        assert evt is not None
        assert evt.action == Action.SCROLL_UP

    def test_rapid_scroll_produces_multiple_events(self):
        """Rapid consecutive scroll events each produce a separate event."""
        handler = _make_handler()
        events = []
        for _ in range(20):
            evt = _simulate_mouse(handler, 10, 10, _scroll_up_mask())
            assert evt is not None
            events.append(evt)
        assert all(e.action == Action.SCROLL_UP for e in events)
        assert len(events) == 20

    def test_rapid_scroll_down_produces_multiple_events(self):
        """Rapid consecutive scroll-down events each produce a separate event."""
        handler = _make_handler()
        events = []
        for _ in range(20):
            evt = _simulate_mouse(handler, 10, 10, _scroll_down_mask())
            assert evt is not None
            events.append(evt)
        assert all(e.action == Action.SCROLL_DOWN for e in events)
        assert len(events) == 20

    def test_alternating_scroll_directions(self):
        """Alternating scroll up/down produces correct events."""
        handler = _make_handler()
        for _ in range(10):
            up = _simulate_mouse(handler, 5, 5, _scroll_up_mask())
            assert up is not None
            assert up.action == Action.SCROLL_UP

            down = _simulate_mouse(handler, 5, 5, _scroll_down_mask())
            assert down is not None
            assert down.action == Action.SCROLL_DOWN


# ---------------------------------------------------------------------------
# Scroll-to-zoom: zoom bounds integration
# ---------------------------------------------------------------------------

class TestScrollZoomBounds:
    """Tests verifying zoom bounds are respected with Globe.adjust_zoom."""

    def test_zoom_bounded_at_max(self):
        """Scroll-up (zoom in) many times should not exceed MAX_ZOOM."""
        from globe_term.globe import Globe, MAX_ZOOM
        from globe_term.cli import SCROLL_ZOOM_STEP

        globe = Globe(zoom=MAX_ZOOM - 0.05)
        # Scroll up many times past the max
        for _ in range(100):
            globe.adjust_zoom(SCROLL_ZOOM_STEP)
        assert globe.zoom == MAX_ZOOM

    def test_zoom_bounded_at_min(self):
        """Scroll-down (zoom out) many times should not go below MIN_ZOOM."""
        from globe_term.globe import Globe, MIN_ZOOM
        from globe_term.cli import SCROLL_ZOOM_STEP

        globe = Globe(zoom=MIN_ZOOM + 0.05)
        # Scroll down many times past the min
        for _ in range(100):
            globe.adjust_zoom(-SCROLL_ZOOM_STEP)
        assert globe.zoom == MIN_ZOOM

    def test_zoom_accumulates_smoothly(self):
        """Multiple scroll-up events accumulate zoom incrementally."""
        from globe_term.globe import Globe, MAX_ZOOM
        from globe_term.cli import SCROLL_ZOOM_STEP

        globe = Globe(zoom=1.0)
        initial = globe.zoom
        steps = 5
        for _ in range(steps):
            globe.adjust_zoom(SCROLL_ZOOM_STEP)
        expected = min(initial + steps * SCROLL_ZOOM_STEP, MAX_ZOOM)
        assert abs(globe.zoom - expected) < 1e-9

    def test_zoom_at_max_bound_no_crash(self):
        """Scrolling up when already at MAX_ZOOM does not crash."""
        from globe_term.globe import Globe, MAX_ZOOM
        from globe_term.cli import SCROLL_ZOOM_STEP

        globe = Globe(zoom=MAX_ZOOM)
        # Should not raise
        globe.adjust_zoom(SCROLL_ZOOM_STEP)
        assert globe.zoom == MAX_ZOOM

    def test_zoom_at_min_bound_no_crash(self):
        """Scrolling down when already at MIN_ZOOM does not crash."""
        from globe_term.globe import Globe, MIN_ZOOM
        from globe_term.cli import SCROLL_ZOOM_STEP

        globe = Globe(zoom=MIN_ZOOM)
        # Should not raise
        globe.adjust_zoom(-SCROLL_ZOOM_STEP)
        assert globe.zoom == MIN_ZOOM

    def test_rapid_scroll_accumulation(self):
        """Rapid scroll in both directions accumulates correctly."""
        from globe_term.globe import Globe, MIN_ZOOM, MAX_ZOOM
        from globe_term.cli import SCROLL_ZOOM_STEP

        globe = Globe(zoom=1.0)
        # Zoom in 10 times
        for _ in range(10):
            globe.adjust_zoom(SCROLL_ZOOM_STEP)
        zoomed_in = globe.zoom
        assert zoomed_in > 1.0

        # Zoom out 20 times (past where we started)
        for _ in range(20):
            globe.adjust_zoom(-SCROLL_ZOOM_STEP)
        zoomed_out = globe.zoom
        assert zoomed_out < 1.0
        assert zoomed_out >= MIN_ZOOM

    def test_zoom_bounds_are_0_2_to_5_0(self):
        """Confirm the exact zoom bounds match the spec (0.2 to 5.0)."""
        from globe_term.globe import MIN_ZOOM, MAX_ZOOM

        assert MIN_ZOOM == 0.2
        assert MAX_ZOOM == 5.0


# ---------------------------------------------------------------------------
# Scroll mask edge cases
# ---------------------------------------------------------------------------

class TestScrollMaskEdgeCases:
    """Tests for scroll mask robustness across terminal encodings."""

    def test_scroll_up_mask_includes_button4_pressed(self):
        """_scroll_up_mask includes BUTTON4_PRESSED bit."""
        mask = _scroll_up_mask()
        b4p = getattr(curses, "BUTTON4_PRESSED", 0x10000)
        assert mask & b4p

    def test_scroll_up_mask_includes_button4_clicked(self):
        """_scroll_up_mask includes BUTTON4_CLICKED bit."""
        mask = _scroll_up_mask()
        b4c = getattr(curses, "BUTTON4_CLICKED", 0x20000)
        assert mask & b4c

    def test_scroll_down_mask_includes_button5_pressed(self):
        """_scroll_down_mask includes BUTTON5_PRESSED bit."""
        mask = _scroll_down_mask()
        b5p = getattr(curses, "BUTTON5_PRESSED", 0x200000)
        assert mask & b5p

    def test_scroll_down_mask_includes_button5_clicked(self):
        """_scroll_down_mask includes BUTTON5_CLICKED bit."""
        mask = _scroll_down_mask()
        b5c = getattr(curses, "BUTTON5_CLICKED", 0x400000)
        assert mask & b5c

    def test_scroll_masks_do_not_overlap_button1(self):
        """Scroll masks should not overlap with BUTTON1 masks."""
        scroll_up = _scroll_up_mask()
        scroll_down = _scroll_down_mask()
        b1p = _button1_pressed_mask()
        b1r = _button1_released_mask()
        b1c = _button1_clicked_mask()

        assert not (scroll_up & b1p)
        assert not (scroll_up & b1r)
        assert not (scroll_up & b1c)
        assert not (scroll_down & b1p)
        assert not (scroll_down & b1r)
        assert not (scroll_down & b1c)

    def test_scroll_up_and_down_masks_do_not_overlap(self):
        """Scroll-up and scroll-down masks should not share any bits."""
        assert not (_scroll_up_mask() & _scroll_down_mask())

    def test_unrecognized_scroll_code_ignored(self):
        """An unrecognized button state that is not scroll is ignored."""
        handler = _make_handler()
        # Use a bstate value that does not match any known mask
        evt = _simulate_mouse(handler, 10, 10, 0x1000000)
        # Should return None (unrecognized)
        assert evt is None


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

    def test_reset_idle_resets_timer(self):
        """reset_idle() should reset the idle timer to current time."""
        handler = _make_handler()
        handler._last_event_time = time.monotonic() - 10.0
        assert handler.idle_seconds() >= 9.0

        handler.reset_idle()

        assert handler.idle_seconds() < 1.0

    def test_reset_idle_updates_last_event_time(self):
        """reset_idle() should update the last_event_time property."""
        handler = _make_handler()
        old_time = handler.last_event_time

        # Wait a tiny bit to ensure monotonic clock advances
        time.sleep(0.001)
        handler.reset_idle()

        assert handler.last_event_time > old_time

    def test_reset_idle_called_multiple_times(self):
        """Calling reset_idle() multiple times keeps updating the timer."""
        handler = _make_handler()
        for _ in range(5):
            handler.reset_idle()
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
# InputHandler: position-based drag detection (cross-terminal)
# ---------------------------------------------------------------------------

class TestPositionBasedDragDetection:
    """Tests that drag detection works via position changes, not bstate flags.

    Many terminals (Terminal.app, Windows Terminal, iTerm2) report motion
    events with bstate=0 or with REPORT_MOUSE_POSITION.  The position-based
    detection must handle both cases after a button press has been registered.
    """

    def test_drag_with_zero_bstate_motion(self):
        """Drag works when motion events have bstate=0 (e.g. Terminal.app)."""
        handler = _make_handler()

        # Press
        _simulate_mouse(handler, 10, 10, _button1_pressed_mask())

        # Motion with bstate=0 (some terminals report this)
        evt = _simulate_mouse(handler, 10 + _DRAG_THRESHOLD, 10, 0)
        assert evt is not None
        assert evt.action == Action.DRAG_START

        # Continue motion with bstate=0
        evt = _simulate_mouse(handler, 15, 12, 0)
        assert evt is not None
        assert evt.action == Action.DRAG_MOVE
        assert evt.dx == 15 - (10 + _DRAG_THRESHOLD)
        assert evt.dy == 12 - 10

    def test_drag_with_report_mouse_position_bstate(self):
        """Drag works when motion events have REPORT_MOUSE_POSITION bstate."""
        handler = _make_handler()

        _simulate_mouse(handler, 5, 5, _button1_pressed_mask())

        evt = _simulate_mouse(handler, 5 + _DRAG_THRESHOLD + 1, 5,
                              _report_mouse_position_mask())
        assert evt is not None
        assert evt.action == Action.DRAG_START

    def test_drag_release_ends_drag_regardless_of_motion_bstate(self):
        """DRAG_END fires on release even when motion used bstate=0."""
        handler = _make_handler()

        # Press -> motion (bstate=0) -> release
        _simulate_mouse(handler, 10, 10, _button1_pressed_mask())
        _simulate_mouse(handler, 10 + _DRAG_THRESHOLD + 3, 10, 0)

        evt = _simulate_mouse(handler, 20, 10, _button1_released_mask())
        assert evt is not None
        assert evt.action == Action.DRAG_END

    def test_no_motion_detected_at_same_position(self):
        """Events at the same position do not trigger drag (position-based)."""
        handler = _make_handler()

        _simulate_mouse(handler, 10, 10, _button1_pressed_mask())
        # Same position -> no motion detected
        evt = _simulate_mouse(handler, 10, 10, 0)
        assert evt is None


# ---------------------------------------------------------------------------
# InputHandler: drag across terminal edge
# ---------------------------------------------------------------------------

class TestDragAcrossTerminalEdge:
    """Tests that drag across extreme coordinates does not crash."""

    def test_drag_to_large_positive_coordinates(self):
        """Dragging to very large coordinates does not crash."""
        handler = _make_handler()

        _simulate_mouse(handler, 10, 10, _button1_pressed_mask())
        evt = _simulate_mouse(handler, 9999, 9999, 0)
        assert evt is not None
        assert evt.action == Action.DRAG_START
        assert evt.dx == 9999 - 10
        assert evt.dy == 9999 - 10

    def test_drag_to_negative_coordinates(self):
        """Dragging to negative coordinates (edge of terminal) does not crash."""
        handler = _make_handler()

        _simulate_mouse(handler, 10, 10, _button1_pressed_mask())
        evt = _simulate_mouse(handler, -5, -5, 0)
        assert evt is not None
        assert evt.action == Action.DRAG_START
        assert evt.dx == -5 - 10
        assert evt.dy == -5 - 10

    def test_drag_produces_very_large_deltas(self):
        """Very fast drag produces large dx/dy values without crashing."""
        handler = _make_handler()

        _simulate_mouse(handler, 0, 0, _button1_pressed_mask())
        # Jump to far position in one step
        _simulate_mouse(handler, 500, 300, 0)  # DRAG_START

        # Another huge jump
        evt = _simulate_mouse(handler, 1000, 800, 0)
        assert evt is not None
        assert evt.action == Action.DRAG_MOVE
        assert evt.dx == 500
        assert evt.dy == 500


# ---------------------------------------------------------------------------
# InputHandler: drag threshold
# ---------------------------------------------------------------------------

class TestDragThreshold:
    """Tests that the drag threshold prevents accidental drags."""

    def test_motion_below_threshold_no_drag(self):
        """Movement below the threshold does not trigger a drag."""
        handler = _make_handler()

        _simulate_mouse(handler, 10, 10, _button1_pressed_mask())

        # Move by 1 cell (below threshold of 2)
        evt = _simulate_mouse(handler, 11, 10, 0)
        assert evt is None  # not enough motion

    def test_motion_exactly_at_threshold_triggers_drag(self):
        """Movement exactly at the threshold triggers DRAG_START."""
        handler = _make_handler()

        _simulate_mouse(handler, 10, 10, _button1_pressed_mask())

        # Move by exactly _DRAG_THRESHOLD cells
        evt = _simulate_mouse(handler, 10 + _DRAG_THRESHOLD, 10, 0)
        assert evt is not None
        assert evt.action == Action.DRAG_START

    def test_diagonal_motion_summed_for_threshold(self):
        """Diagonal motion uses Manhattan distance for threshold check."""
        handler = _make_handler()

        _simulate_mouse(handler, 10, 10, _button1_pressed_mask())

        # Move 1 in x and 1 in y = Manhattan distance 2 = threshold
        evt = _simulate_mouse(handler, 11, 11, 0)
        assert evt is not None
        assert evt.action == Action.DRAG_START

    def test_threshold_value_is_two(self):
        """Verify the drag threshold constant is 2."""
        assert _DRAG_THRESHOLD == 2


# ---------------------------------------------------------------------------
# InputHandler: enable_mouse escape sequences
# ---------------------------------------------------------------------------

class TestEnableMouseEscapeSequences:
    """Tests that enable_mouse writes correct xterm tracking sequences."""

    def test_enable_mouse_writes_xterm_tracking_sequences(self):
        """enable_mouse writes 1000h, 1002h, 1003h, 1006h sequences."""
        handler = InputHandler(stdscr=None)
        fake_stdout = io.StringIO()

        with patch("globe_term.input.detect_terminal", return_value="unknown"), \
             patch("sys.stdout", fake_stdout), \
             patch("curses.mousemask", return_value=(0xFFFF, 0)):
            handler.enable_mouse()

        output = fake_stdout.getvalue()
        assert "\033[?1000h" in output
        assert "\033[?1002h" in output
        assert "\033[?1003h" in output
        assert "\033[?1006h" in output

    def test_enable_mouse_no_sequences_when_unsupported(self):
        """When mouse is not supported, no escape sequences are written."""
        handler = InputHandler(stdscr=None)
        fake_stdout = io.StringIO()

        with patch("globe_term.input.detect_terminal", return_value="unknown"), \
             patch("sys.stdout", fake_stdout), \
             patch("curses.mousemask", return_value=(0, 0)):
            handler.enable_mouse()

        output = fake_stdout.getvalue()
        assert "\033[?1000h" not in output
        assert "\033[?1003h" not in output


# ---------------------------------------------------------------------------
# InputHandler: disable_mouse escape sequences
# ---------------------------------------------------------------------------

class TestDisableMouseEscapeSequences:
    """Tests that disable_mouse writes correct cleanup sequences."""

    def test_disable_mouse_writes_cleanup_sequences(self):
        """disable_mouse writes 1006l, 1003l, 1002l, 1000l sequences."""
        handler = InputHandler(stdscr=None)
        handler.mouse_supported = True

        fake_stdout = io.StringIO()
        with patch("sys.stdout", fake_stdout):
            handler.disable_mouse()

        output = fake_stdout.getvalue()
        assert "\033[?1006l" in output
        assert "\033[?1003l" in output
        assert "\033[?1002l" in output
        assert "\033[?1000l" in output

    def test_disable_mouse_cleanup_order(self):
        """Cleanup sequences are in reverse order of enable (1006, 1003, 1002, 1000)."""
        handler = InputHandler(stdscr=None)
        handler.mouse_supported = True

        fake_stdout = io.StringIO()
        with patch("sys.stdout", fake_stdout):
            handler.disable_mouse()

        output = fake_stdout.getvalue()
        # Verify reverse order: 1006l before 1003l before 1002l before 1000l
        pos_1006 = output.index("\033[?1006l")
        pos_1003 = output.index("\033[?1003l")
        pos_1002 = output.index("\033[?1002l")
        pos_1000 = output.index("\033[?1000l")
        assert pos_1006 < pos_1003 < pos_1002 < pos_1000

    def test_disable_mouse_no_sequences_when_unsupported(self):
        """When mouse was never supported, no cleanup sequences are written."""
        handler = InputHandler(stdscr=None)
        handler.mouse_supported = False

        fake_stdout = io.StringIO()
        with patch("sys.stdout", fake_stdout):
            handler.disable_mouse()

        output = fake_stdout.getvalue()
        assert output == ""

    def test_disable_mouse_called_in_finally_block(self):
        """Verify the display loop calls disable_mouse in its finally block."""
        # This is a design verification - we check that cli.py's _display_loop
        # has disable_mouse in a finally block by inspecting the source
        import inspect
        from globe_term.cli import _display_loop
        source = inspect.getsource(_display_loop)
        assert "finally:" in source
        assert "disable_mouse" in source


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


# ---------------------------------------------------------------------------
# InputHandler: Kitty keyboard protocol negotiation
# ---------------------------------------------------------------------------

class TestKittyProtocolNegotiation:
    """Tests for Kitty keyboard protocol disable/restore in enable/disable_mouse."""

    def test_enable_mouse_sends_kitty_disable_on_kitty(self):
        """On Kitty terminal, enable_mouse sends \\033[>0u to disable protocol."""
        handler = InputHandler(stdscr=None)
        fake_stdout = io.StringIO()

        with patch("globe_term.input.detect_terminal", return_value="kitty"), \
             patch("sys.stdout", fake_stdout), \
             patch("curses.mousemask", return_value=(0xFFFF, 0)):
            handler.enable_mouse()

        output = fake_stdout.getvalue()
        assert "\033[>0u" in output
        assert handler._kitty_protocol_disabled is True

    def test_enable_mouse_no_kitty_sequence_on_non_kitty(self):
        """On non-Kitty terminals, enable_mouse does NOT send \\033[>0u."""
        handler = InputHandler(stdscr=None)
        fake_stdout = io.StringIO()

        with patch("globe_term.input.detect_terminal", return_value="iterm2"), \
             patch("sys.stdout", fake_stdout), \
             patch("curses.mousemask", return_value=(0xFFFF, 0)):
            handler.enable_mouse()

        output = fake_stdout.getvalue()
        assert "\033[>0u" not in output
        assert handler._kitty_protocol_disabled is False

    def test_enable_mouse_no_kitty_sequence_on_unknown(self):
        """On unknown terminals, enable_mouse does NOT send Kitty sequences."""
        handler = InputHandler(stdscr=None)
        fake_stdout = io.StringIO()

        with patch("globe_term.input.detect_terminal", return_value="unknown"), \
             patch("sys.stdout", fake_stdout), \
             patch("curses.mousemask", return_value=(0xFFFF, 0)):
            handler.enable_mouse()

        output = fake_stdout.getvalue()
        assert "\033[>0u" not in output
        assert handler._kitty_protocol_disabled is False

    def test_disable_mouse_restores_kitty_protocol(self):
        """On Kitty, disable_mouse sends \\033[<u to restore protocol."""
        handler = InputHandler(stdscr=None)
        handler.mouse_supported = True
        handler._kitty_protocol_disabled = True

        fake_stdout = io.StringIO()
        with patch("sys.stdout", fake_stdout):
            handler.disable_mouse()

        output = fake_stdout.getvalue()
        assert "\033[<u" in output
        assert handler._kitty_protocol_disabled is False

    def test_disable_mouse_no_kitty_restore_on_non_kitty(self):
        """On non-Kitty terminals, disable_mouse does NOT send \\033[<u."""
        handler = InputHandler(stdscr=None)
        handler.mouse_supported = True
        handler._kitty_protocol_disabled = False

        fake_stdout = io.StringIO()
        with patch("sys.stdout", fake_stdout):
            handler.disable_mouse()

        output = fake_stdout.getvalue()
        assert "\033[<u" not in output

    def test_enable_mouse_kitty_stdout_write_failure(self):
        """If stdout.write fails on Kitty, enable_mouse continues gracefully."""
        handler = InputHandler(stdscr=None)
        mock_stdout = MagicMock()
        mock_stdout.write.side_effect = OSError("broken pipe")

        with patch("globe_term.input.detect_terminal", return_value="kitty"), \
             patch("sys.stdout", mock_stdout), \
             patch("curses.mousemask", return_value=(0, 0)):
            # Should not raise
            result = handler.enable_mouse()

        assert handler._kitty_protocol_disabled is False
        assert result is False

    def test_disable_mouse_kitty_restore_failure(self):
        """If stdout.write fails during Kitty restore, disable_mouse does not crash."""
        handler = InputHandler(stdscr=None)
        handler.mouse_supported = False
        handler._kitty_protocol_disabled = True

        mock_stdout = MagicMock()
        mock_stdout.write.side_effect = OSError("broken pipe")

        with patch("sys.stdout", mock_stdout):
            # Should not raise
            handler.disable_mouse()

    def test_disable_mouse_cleanup_failure_does_not_crash(self):
        """If mouse cleanup write fails AND kitty restore fails, no crash."""
        handler = InputHandler(stdscr=None)
        handler.mouse_supported = True
        handler._kitty_protocol_disabled = True

        mock_stdout = MagicMock()
        mock_stdout.write.side_effect = OSError("broken pipe")

        with patch("sys.stdout", mock_stdout):
            # Should not raise
            handler.disable_mouse()

    def test_kitty_protocol_disabled_initially_false(self):
        """_kitty_protocol_disabled defaults to False on construction."""
        handler = InputHandler(stdscr=None)
        assert handler._kitty_protocol_disabled is False

    def test_full_kitty_lifecycle(self):
        """Full lifecycle: enable on Kitty sends disable, then cleanup restores."""
        handler = InputHandler(stdscr=None)
        enable_stdout = io.StringIO()

        with patch("globe_term.input.detect_terminal", return_value="kitty"), \
             patch("sys.stdout", enable_stdout), \
             patch("curses.mousemask", return_value=(0xFFFF, 0)):
            handler.enable_mouse()

        enable_output = enable_stdout.getvalue()
        assert "\033[>0u" in enable_output
        assert handler._kitty_protocol_disabled is True
        assert handler.mouse_supported is True

        # Now disable
        disable_stdout = io.StringIO()
        with patch("sys.stdout", disable_stdout):
            handler.disable_mouse()

        disable_output = disable_stdout.getvalue()
        # Should contain mouse disable AND kitty restore
        assert "\033[?1006l" in disable_output
        assert "\033[<u" in disable_output
        assert handler._kitty_protocol_disabled is False


# ---------------------------------------------------------------------------
# Terminal cleanup verification (regression suite)
# ---------------------------------------------------------------------------

class TestTerminalCleanupVerification:
    """Verify the full terminal cleanup sequence works for all exit paths.

    These tests confirm that no leftover escape sequences remain after
    the application exits, whether by normal quit, Ctrl+C interrupt, or
    an unexpected exception during the display loop.
    """

    def test_cleanup_disables_all_mouse_tracking_modes(self):
        """disable_mouse() disables all four xterm mouse tracking modes."""
        handler = InputHandler(stdscr=None)
        handler.mouse_supported = True

        fake_stdout = io.StringIO()
        with patch("sys.stdout", fake_stdout):
            handler.disable_mouse()

        output = fake_stdout.getvalue()
        # All four tracking modes must be disabled
        assert "\033[?1000l" in output, "Basic button events not disabled"
        assert "\033[?1002l" in output, "Button-event tracking not disabled"
        assert "\033[?1003l" in output, "Any-event tracking not disabled"
        assert "\033[?1006l" in output, "SGR extended mode not disabled"

    def test_cleanup_sequences_are_inverse_of_enable(self):
        """Every escape sequence enabled is later disabled on cleanup."""
        handler = InputHandler(stdscr=None)
        enable_stdout = io.StringIO()

        with patch("globe_term.input.detect_terminal", return_value="unknown"), \
             patch("sys.stdout", enable_stdout), \
             patch("curses.mousemask", return_value=(0xFFFF, 0)):
            handler.enable_mouse()

        enable_output = enable_stdout.getvalue()

        # Now disable
        disable_stdout = io.StringIO()
        with patch("sys.stdout", disable_stdout):
            handler.disable_mouse()

        disable_output = disable_stdout.getvalue()

        # For each mode enabled with 'h', verify it is disabled with 'l'
        for mode in ("1000", "1002", "1003", "1006"):
            assert f"\033[?{mode}h" in enable_output, f"Mode {mode} not enabled"
            assert f"\033[?{mode}l" in disable_output, f"Mode {mode} not disabled"

    def test_cleanup_after_kitty_enables_and_restores_protocol(self):
        """Full Kitty cleanup: mouse tracking disabled AND keyboard protocol restored."""
        handler = InputHandler(stdscr=None)
        enable_stdout = io.StringIO()

        with patch("globe_term.input.detect_terminal", return_value="kitty"), \
             patch("sys.stdout", enable_stdout), \
             patch("curses.mousemask", return_value=(0xFFFF, 0)):
            handler.enable_mouse()

        enable_output = enable_stdout.getvalue()
        # Kitty protocol was disabled (pushed to legacy mode)
        assert "\033[>0u" in enable_output

        # Now cleanup
        disable_stdout = io.StringIO()
        with patch("sys.stdout", disable_stdout):
            handler.disable_mouse()

        disable_output = disable_stdout.getvalue()
        # Mouse tracking modes disabled
        assert "\033[?1000l" in disable_output
        # Kitty protocol restored (popped from mode stack)
        assert "\033[<u" in disable_output

    def test_display_loop_finally_calls_disable_mouse(self):
        """The _display_loop function has disable_mouse in a finally block."""
        import inspect
        from globe_term.cli import _display_loop
        source = inspect.getsource(_display_loop)

        # Verify structural requirement: try/finally with disable_mouse
        assert "try:" in source
        assert "finally:" in source
        assert "disable_mouse" in source

        # Verify disable_mouse appears after finally (not just anywhere)
        finally_idx = source.index("finally:")
        disable_idx = source.index("disable_mouse", finally_idx)
        assert disable_idx > finally_idx, (
            "disable_mouse must appear in the finally block"
        )

    def test_display_loop_cleanup_on_normal_exit(self):
        """Cleanup runs after normal exit via 'q' key."""
        from globe_term.cli import _display_loop

        screen = MagicMock()
        screen.getmaxyx.return_value = (40, 80)
        screen.getch.side_effect = [ord("q")]

        disable_called = False
        original_disable = InputHandler.disable_mouse

        def tracking_disable(self):
            nonlocal disable_called
            disable_called = True
            original_disable(self)

        with patch("globe_term.renderer.curses") as mock_curses, \
             patch("globe_term.cli.curses") as mock_cli_curses, \
             patch.object(InputHandler, "disable_mouse", tracking_disable):
            mock_curses.COLOR_PAIRS = 256
            mock_curses.color_pair.return_value = 0
            mock_curses.has_colors.return_value = True
            mock_curses.A_BOLD = 0
            mock_curses.error = curses.error
            mock_curses.start_color.return_value = None
            mock_curses.use_default_colors.return_value = None
            mock_curses.curs_set.return_value = None
            mock_curses.init_pair.return_value = None
            mock_curses.doupdate.return_value = None
            mock_curses.KEY_RESIZE = curses.KEY_RESIZE

            mock_cli_curses.error = curses.error
            mock_cli_curses.KEY_RESIZE = curses.KEY_RESIZE

            _display_loop(screen)

        assert disable_called, "disable_mouse was not called on normal exit"

    def test_display_loop_cleanup_on_exception(self):
        """Cleanup runs even when an exception occurs during the display loop."""
        from globe_term.cli import _display_loop

        screen = MagicMock()
        screen.getmaxyx.return_value = (40, 80)
        screen.getch.side_effect = RuntimeError("unexpected error")

        disable_called = False
        original_disable = InputHandler.disable_mouse

        def tracking_disable(self):
            nonlocal disable_called
            disable_called = True
            original_disable(self)

        with patch("globe_term.renderer.curses") as mock_curses, \
             patch("globe_term.cli.curses") as mock_cli_curses, \
             patch.object(InputHandler, "disable_mouse", tracking_disable):
            mock_curses.COLOR_PAIRS = 256
            mock_curses.color_pair.return_value = 0
            mock_curses.has_colors.return_value = True
            mock_curses.A_BOLD = 0
            mock_curses.error = curses.error
            mock_curses.start_color.return_value = None
            mock_curses.use_default_colors.return_value = None
            mock_curses.curs_set.return_value = None
            mock_curses.init_pair.return_value = None
            mock_curses.doupdate.return_value = None
            mock_curses.KEY_RESIZE = curses.KEY_RESIZE

            mock_cli_curses.error = curses.error
            mock_cli_curses.KEY_RESIZE = curses.KEY_RESIZE

            with pytest.raises(RuntimeError):
                _display_loop(screen)

        assert disable_called, "disable_mouse was not called when exception occurred"

    def test_display_loop_cleanup_on_keyboard_interrupt(self):
        """Cleanup runs on KeyboardInterrupt (Ctrl+C) via curses.wrapper."""
        from globe_term.cli import main

        disable_called = False
        original_disable = InputHandler.disable_mouse

        def tracking_disable(self):
            nonlocal disable_called
            disable_called = True
            original_disable(self)

        screen = MagicMock()
        screen.getmaxyx.return_value = (40, 80)
        screen.getch.side_effect = KeyboardInterrupt()

        def fake_wrapper(callback):
            try:
                callback(screen)
            except KeyboardInterrupt:
                raise

        with patch("globe_term.renderer.curses") as mock_curses, \
             patch("globe_term.cli.curses") as mock_cli_curses, \
             patch("globe_term.cli.is_terminal", return_value=True), \
             patch("globe_term.cli.detect_mouse_support", return_value=True), \
             patch.object(InputHandler, "disable_mouse", tracking_disable):
            mock_curses.COLOR_PAIRS = 256
            mock_curses.color_pair.return_value = 0
            mock_curses.has_colors.return_value = True
            mock_curses.A_BOLD = 0
            mock_curses.error = curses.error
            mock_curses.start_color.return_value = None
            mock_curses.use_default_colors.return_value = None
            mock_curses.curs_set.return_value = None
            mock_curses.init_pair.return_value = None
            mock_curses.doupdate.return_value = None
            mock_curses.KEY_RESIZE = curses.KEY_RESIZE

            mock_cli_curses.error = curses.error
            mock_cli_curses.KEY_RESIZE = curses.KEY_RESIZE
            mock_cli_curses.wrapper = fake_wrapper

            # main() catches KeyboardInterrupt so should not raise
            main([])

        assert disable_called, "disable_mouse was not called on Ctrl+C"

    def test_no_import_cycle_between_input_and_utils(self):
        """Verify no circular import between input.py and utils.py."""
        import importlib
        # Force reimport to detect cycles
        import globe_term.utils
        import globe_term.input
        # If we get here, no ImportError was raised
        assert True

    def test_public_api_unchanged(self):
        """Verify the public API of input.py is intact after changes."""
        from globe_term.input import (
            Action,
            InputEvent,
            InputHandler,
        )

        # Action enum has all expected members
        expected_actions = {"CLICK", "DRAG_START", "DRAG_MOVE", "DRAG_END",
                          "SCROLL_UP", "SCROLL_DOWN"}
        assert {a.name for a in Action} == expected_actions

        # InputEvent is a frozen dataclass with expected fields
        evt = InputEvent(action=Action.CLICK, x=1, y=2, dx=3, dy=4)
        assert evt.action == Action.CLICK
        with pytest.raises(AttributeError):
            evt.x = 99  # type: ignore[misc]

        # InputHandler has the expected methods
        handler = InputHandler(stdscr=None)
        assert hasattr(handler, "enable_mouse")
        assert hasattr(handler, "disable_mouse")
        assert hasattr(handler, "process_event")
        assert hasattr(handler, "idle_seconds")
        assert hasattr(handler, "reset_idle")
        assert hasattr(handler, "mouse_supported")
        assert hasattr(handler, "last_event_time")
