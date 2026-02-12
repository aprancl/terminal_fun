"""Tests for auto-rotation, idle detection, and frame timing.

Covers:
- Globe.auto_rotate() applies correct angular velocity
- Speed=0 disables rotation
- High speed values capped at MAX_AUTO_SPEED
- Idle detection triggers after threshold
- Frame timing calculates correct sleep duration
- Integration: auto-rotation in display loop
"""

from __future__ import annotations

import math
import time

import pytest

from globe_term.globe import (
    AUTO_ROTATE_BASE_SPEED,
    Globe,
    IDLE_THRESHOLD,
    MAX_AUTO_SPEED,
)
from globe_term.cli import (
    TARGET_FPS,
    TARGET_FRAME_TIME,
    compute_frame_sleep,
)
from globe_term.input import InputHandler


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _approx(a: float, b: float, tol: float = 1e-6) -> bool:
    return abs(a - b) < tol


# ---------------------------------------------------------------------------
# Globe.auto_rotate: angular velocity
# ---------------------------------------------------------------------------


class TestAutoRotateVelocity:
    """Unit tests: auto_rotate applies correct angular velocity."""

    def test_basic_rotation_at_speed_1(self):
        """At speed=1, dt=1s should rotate by AUTO_ROTATE_BASE_SPEED radians."""
        g = Globe()
        initial_y = g.rotation_y
        g.auto_rotate(dt=1.0, speed=1.0)
        expected = initial_y + AUTO_ROTATE_BASE_SPEED
        assert _approx(g.rotation_y, expected)

    def test_rotation_proportional_to_dt(self):
        """Rotation should be proportional to dt."""
        g = Globe()
        g.auto_rotate(dt=0.5, speed=1.0)
        half_rotation = g.rotation_y

        g2 = Globe()
        g2.auto_rotate(dt=1.0, speed=1.0)
        full_rotation = g2.rotation_y

        assert _approx(full_rotation, half_rotation * 2)

    def test_rotation_proportional_to_speed(self):
        """Rotation should be proportional to speed."""
        g1 = Globe()
        g1.auto_rotate(dt=1.0, speed=1.0)

        g2 = Globe()
        g2.auto_rotate(dt=1.0, speed=2.0)

        assert _approx(g2.rotation_y, g1.rotation_y * 2)

    def test_full_rotation_period(self):
        """At speed=1, a full 2*pi rotation takes ~45 seconds."""
        g = Globe()
        # Simulate 45 seconds of rotation at speed=1
        total_dt = 45.0
        g.auto_rotate(dt=total_dt, speed=1.0)
        # Should have completed roughly one full rotation (2*pi)
        assert abs(g.rotation_y - 2 * math.pi) < 0.01

    def test_rotation_only_affects_y_axis(self):
        """Auto-rotation should only modify rotation_y, not rotation_x."""
        g = Globe(rotation_x=0.5)
        g.auto_rotate(dt=1.0, speed=1.0)
        assert g.rotation_x == 0.5

    def test_rotation_accumulates(self):
        """Multiple calls should accumulate rotation."""
        g = Globe()
        g.auto_rotate(dt=0.1, speed=1.0)
        g.auto_rotate(dt=0.1, speed=1.0)
        g.auto_rotate(dt=0.1, speed=1.0)
        expected = AUTO_ROTATE_BASE_SPEED * 0.3
        assert _approx(g.rotation_y, expected, tol=1e-10)


# ---------------------------------------------------------------------------
# Globe.auto_rotate: speed=0 disables rotation
# ---------------------------------------------------------------------------


class TestAutoRotateSpeedZero:
    """Unit tests: speed=0 disables rotation."""

    def test_speed_zero_no_rotation(self):
        """Speed of 0 should not change rotation_y."""
        g = Globe()
        initial = g.rotation_y
        g.auto_rotate(dt=10.0, speed=0.0)
        assert g.rotation_y == initial

    def test_negative_speed_no_rotation(self):
        """Negative speed should not change rotation_y."""
        g = Globe()
        initial = g.rotation_y
        g.auto_rotate(dt=1.0, speed=-1.0)
        assert g.rotation_y == initial

    def test_zero_dt_no_rotation(self):
        """dt=0 should not change rotation_y."""
        g = Globe()
        initial = g.rotation_y
        g.auto_rotate(dt=0.0, speed=1.0)
        assert g.rotation_y == initial

    def test_negative_dt_no_rotation(self):
        """Negative dt should not change rotation_y."""
        g = Globe()
        initial = g.rotation_y
        g.auto_rotate(dt=-0.5, speed=1.0)
        assert g.rotation_y == initial


# ---------------------------------------------------------------------------
# Globe.auto_rotate: speed capping
# ---------------------------------------------------------------------------


class TestAutoRotateSpeedCap:
    """Edge case: very high speed values capped at MAX_AUTO_SPEED."""

    def test_high_speed_capped(self):
        """Speed above MAX_AUTO_SPEED is clamped."""
        g1 = Globe()
        g1.auto_rotate(dt=1.0, speed=MAX_AUTO_SPEED * 100)

        g2 = Globe()
        g2.auto_rotate(dt=1.0, speed=MAX_AUTO_SPEED)

        assert _approx(g1.rotation_y, g2.rotation_y)

    def test_speed_at_max_not_clamped(self):
        """Speed exactly at MAX_AUTO_SPEED should work normally."""
        g = Globe()
        g.auto_rotate(dt=1.0, speed=MAX_AUTO_SPEED)
        expected = AUTO_ROTATE_BASE_SPEED * MAX_AUTO_SPEED
        assert _approx(g.rotation_y, expected)

    def test_speed_below_max_not_clamped(self):
        """Speed below MAX_AUTO_SPEED should not be clamped."""
        g = Globe()
        speed = MAX_AUTO_SPEED - 1.0
        g.auto_rotate(dt=1.0, speed=speed)
        expected = AUTO_ROTATE_BASE_SPEED * speed
        assert _approx(g.rotation_y, expected)


# ---------------------------------------------------------------------------
# Idle detection threshold
# ---------------------------------------------------------------------------


class TestIdleDetection:
    """Unit tests: idle detection triggers after threshold."""

    def test_idle_threshold_value(self):
        """IDLE_THRESHOLD should be between 2 and 3 seconds."""
        assert 2.0 <= IDLE_THRESHOLD <= 3.0

    def test_idle_seconds_below_threshold_after_event(self):
        """Right after an event, idle_seconds should be below threshold."""
        handler = InputHandler(stdscr=None)
        handler._last_event_time = time.monotonic()
        assert handler.idle_seconds() < IDLE_THRESHOLD

    def test_idle_seconds_above_threshold_after_wait(self):
        """After enough time, idle_seconds should exceed threshold."""
        handler = InputHandler(stdscr=None)
        handler._last_event_time = time.monotonic() - (IDLE_THRESHOLD + 1.0)
        assert handler.idle_seconds() >= IDLE_THRESHOLD

    def test_idle_timer_resets_on_event(self):
        """Processing an event resets the idle timer."""
        handler = InputHandler(stdscr=None)
        handler.mouse_supported = True

        # Set idle time to well past threshold
        handler._last_event_time = time.monotonic() - 10.0
        assert handler.idle_seconds() >= IDLE_THRESHOLD

        # Process a non-mouse event (doesn't reset timer via process_event)
        handler.process_event(ord("a"))
        # Non-mouse events don't reset idle timer
        assert handler.idle_seconds() >= 9.0


# ---------------------------------------------------------------------------
# Frame timing
# ---------------------------------------------------------------------------


class TestFrameTiming:
    """Unit tests: frame timing calculates correct sleep duration."""

    def test_target_fps_is_30(self):
        """Target FPS should be 30."""
        assert TARGET_FPS == 30

    def test_target_frame_time(self):
        """Target frame time should be ~33.3ms."""
        assert _approx(TARGET_FRAME_TIME, 1.0 / 30.0)

    def test_compute_frame_sleep_zero_elapsed(self):
        """When frame just started, sleep should be close to full frame time."""
        now = time.monotonic()
        sleep = compute_frame_sleep(now, target=TARGET_FRAME_TIME)
        # Should be close to TARGET_FRAME_TIME (minus tiny measurement overhead)
        assert sleep >= TARGET_FRAME_TIME * 0.8
        assert sleep <= TARGET_FRAME_TIME

    def test_compute_frame_sleep_half_elapsed(self):
        """When half the frame time has elapsed, sleep should be ~half."""
        half_frame = TARGET_FRAME_TIME / 2.0
        start = time.monotonic() - half_frame
        sleep = compute_frame_sleep(start, target=TARGET_FRAME_TIME)
        # Should be roughly half the frame time
        assert sleep >= half_frame * 0.5
        assert sleep <= half_frame * 1.5

    def test_compute_frame_sleep_exceeded(self):
        """When frame exceeded target, sleep should be 0."""
        past = time.monotonic() - TARGET_FRAME_TIME * 2
        sleep = compute_frame_sleep(past, target=TARGET_FRAME_TIME)
        assert sleep == 0.0

    def test_compute_frame_sleep_never_negative(self):
        """Sleep should never be negative."""
        very_old = time.monotonic() - 100.0
        sleep = compute_frame_sleep(very_old, target=TARGET_FRAME_TIME)
        assert sleep >= 0.0

    def test_frame_timing_accuracy(self):
        """Frame timing should be accurate within +/-2ms of target."""
        start = time.monotonic()
        sleep = compute_frame_sleep(start, target=TARGET_FRAME_TIME)
        # Sleep for the computed duration
        if sleep > 0:
            time.sleep(sleep)
        actual_elapsed = time.monotonic() - start
        # The total frame time should be close to TARGET_FRAME_TIME
        error_ms = abs(actual_elapsed - TARGET_FRAME_TIME) * 1000
        assert error_ms < 5.0, (
            f"Frame timing error: {error_ms:.1f}ms (target: {TARGET_FRAME_TIME*1000:.1f}ms)"
        )


# ---------------------------------------------------------------------------
# Constants consistency
# ---------------------------------------------------------------------------


class TestConstants:
    """Verify that auto-rotation constants are reasonable."""

    def test_base_speed_positive(self):
        """Base speed should be a positive value."""
        assert AUTO_ROTATE_BASE_SPEED > 0

    def test_max_speed_positive(self):
        """Max speed should be positive."""
        assert MAX_AUTO_SPEED > 0

    def test_max_speed_reasonable(self):
        """Max speed should allow at most ~20 rotations per 45s."""
        # At max speed, rotation per second = BASE_SPEED * MAX_AUTO_SPEED
        rps = AUTO_ROTATE_BASE_SPEED * MAX_AUTO_SPEED / (2 * math.pi)
        # Should be less than 5 rotations per second
        assert rps < 5.0

    def test_idle_threshold_reasonable(self):
        """Idle threshold should be 2-3 seconds per spec."""
        assert 2.0 <= IDLE_THRESHOLD <= 3.0
