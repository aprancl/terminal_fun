"""Tests for globe_term.utils module.

Covers:
- detect_unicode_support() with various environment variables
- detect_color_support() with various environment variables
- detect_color_count() returns correct number of colors
- detect_mouse_support() with various TERM values
- is_terminal() pipe/tty detection
- get_terminal_size() returns sensible tuple
- ResizeDebouncer debounce logic
"""

from __future__ import annotations

import os
from unittest import mock

import pytest

from globe_term.utils import (
    ResizeDebouncer,
    detect_color_count,
    detect_color_support,
    detect_mouse_support,
    detect_unicode_support,
    get_terminal_size,
    is_terminal,
)


# ---------------------------------------------------------------------------
# detect_unicode_support
# ---------------------------------------------------------------------------

class TestDetectUnicodeSupport:
    def test_utf8_lang(self) -> None:
        with mock.patch.dict(os.environ, {"LANG": "en_US.UTF-8"}, clear=False):
            assert detect_unicode_support() is True

    def test_utf8_lc_all(self) -> None:
        with mock.patch.dict(os.environ, {"LC_ALL": "en_US.utf8"}, clear=False):
            assert detect_unicode_support() is True

    def test_utf8_lc_ctype(self) -> None:
        with mock.patch.dict(
            os.environ,
            {"LC_CTYPE": "UTF-8", "LC_ALL": "", "LANG": ""},
            clear=False,
        ):
            assert detect_unicode_support() is True

    def test_no_utf_env_falls_back_to_encoding(self) -> None:
        """When env vars don't indicate UTF, check preferred encoding."""
        with mock.patch.dict(
            os.environ, {"LC_ALL": "", "LC_CTYPE": "", "LANG": ""}, clear=False
        ):
            with mock.patch("globe_term.utils.locale.getpreferredencoding", return_value="UTF-8"):
                assert detect_unicode_support() is True

    def test_stdout_encoding_fallback(self) -> None:
        with mock.patch.dict(
            os.environ, {"LC_ALL": "", "LC_CTYPE": "", "LANG": ""}, clear=False
        ):
            with mock.patch("globe_term.utils.locale.getpreferredencoding", return_value="ascii"):
                with mock.patch("globe_term.utils.sys") as mock_sys:
                    mock_sys.stdout.encoding = "utf-8"
                    assert detect_unicode_support() is True

    def test_no_unicode_support(self) -> None:
        with mock.patch.dict(
            os.environ, {"LC_ALL": "", "LC_CTYPE": "", "LANG": "C"}, clear=False
        ):
            with mock.patch("globe_term.utils.locale.getpreferredencoding", return_value="ascii"):
                with mock.patch("globe_term.utils.sys") as mock_sys:
                    mock_sys.stdout.encoding = "ascii"
                    assert detect_unicode_support() is False


# ---------------------------------------------------------------------------
# detect_color_support
# ---------------------------------------------------------------------------

class TestDetectColorSupport:
    def test_no_color_env_disables(self) -> None:
        with mock.patch.dict(os.environ, {"NO_COLOR": "1"}, clear=False):
            assert detect_color_support() is False

    def test_no_color_empty_value_disables(self) -> None:
        """NO_COLOR convention: presence of the variable is sufficient."""
        with mock.patch.dict(os.environ, {"NO_COLOR": ""}, clear=False):
            assert detect_color_support() is False

    def test_mono_term_disables(self) -> None:
        env = {"TERM": "xterm-mono"}
        # Make sure NO_COLOR is not set
        with mock.patch.dict(os.environ, env, clear=False):
            os.environ.pop("NO_COLOR", None)
            assert detect_color_support() is False

    def test_colorterm_enables(self) -> None:
        env = {"TERM": "xterm", "COLORTERM": "truecolor"}
        with mock.patch.dict(os.environ, env, clear=False):
            os.environ.pop("NO_COLOR", None)
            assert detect_color_support() is True

    def test_dumb_term_disables(self) -> None:
        env = {"TERM": "dumb"}
        with mock.patch.dict(os.environ, env, clear=False):
            os.environ.pop("NO_COLOR", None)
            os.environ.pop("COLORTERM", None)
            assert detect_color_support() is False

    def test_default_assumes_colors(self) -> None:
        env = {"TERM": "xterm-256color"}
        with mock.patch.dict(os.environ, env, clear=False):
            os.environ.pop("NO_COLOR", None)
            os.environ.pop("COLORTERM", None)
            assert detect_color_support() is True


# ---------------------------------------------------------------------------
# get_terminal_size
# ---------------------------------------------------------------------------

class TestGetTerminalSize:
    def test_returns_tuple(self) -> None:
        result = get_terminal_size()
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_positive_dimensions(self) -> None:
        cols, rows = get_terminal_size()
        assert cols > 0
        assert rows > 0

    def test_fallback_on_error(self) -> None:
        with mock.patch("globe_term.utils.shutil.get_terminal_size", side_effect=OSError):
            cols, rows = get_terminal_size()
            assert cols == 80
            assert rows == 24


# ---------------------------------------------------------------------------
# detect_color_count
# ---------------------------------------------------------------------------

class TestDetectColorCount:
    def test_no_color_returns_zero(self) -> None:
        with mock.patch.dict(os.environ, {"NO_COLOR": "1"}, clear=False):
            assert detect_color_count() == 0

    def test_truecolor_returns_16m(self) -> None:
        env = {"COLORTERM": "truecolor", "TERM": "xterm-256color"}
        with mock.patch.dict(os.environ, env, clear=False):
            os.environ.pop("NO_COLOR", None)
            assert detect_color_count() == 16777216

    def test_24bit_returns_16m(self) -> None:
        env = {"COLORTERM": "24bit", "TERM": "xterm"}
        with mock.patch.dict(os.environ, env, clear=False):
            os.environ.pop("NO_COLOR", None)
            assert detect_color_count() == 16777216

    def test_256color_term(self) -> None:
        env = {"TERM": "xterm-256color"}
        with mock.patch.dict(os.environ, env, clear=False):
            os.environ.pop("NO_COLOR", None)
            os.environ.pop("COLORTERM", None)
            assert detect_color_count() == 256

    def test_basic_color_term(self) -> None:
        env = {"TERM": "xterm-color"}
        with mock.patch.dict(os.environ, env, clear=False):
            os.environ.pop("NO_COLOR", None)
            os.environ.pop("COLORTERM", None)
            assert detect_color_count() == 16

    def test_default_8_colors(self) -> None:
        env = {"TERM": "xterm"}
        with mock.patch.dict(os.environ, env, clear=False):
            os.environ.pop("NO_COLOR", None)
            os.environ.pop("COLORTERM", None)
            assert detect_color_count() == 8

    def test_dumb_term_zero(self) -> None:
        env = {"TERM": "dumb"}
        with mock.patch.dict(os.environ, env, clear=False):
            os.environ.pop("NO_COLOR", None)
            os.environ.pop("COLORTERM", None)
            assert detect_color_count() == 0

    def test_tmux_256color(self) -> None:
        """tmux/screen terminals with 256color should return 256."""
        env = {"TERM": "screen-256color"}
        with mock.patch.dict(os.environ, env, clear=False):
            os.environ.pop("NO_COLOR", None)
            os.environ.pop("COLORTERM", None)
            assert detect_color_count() == 256


# ---------------------------------------------------------------------------
# detect_mouse_support
# ---------------------------------------------------------------------------

class TestDetectMouseSupport:
    def test_xterm_has_mouse(self) -> None:
        env = {"TERM": "xterm"}
        with mock.patch.dict(os.environ, env, clear=False):
            with mock.patch("globe_term.utils.is_terminal", return_value=True):
                assert detect_mouse_support() is True

    def test_dumb_no_mouse(self) -> None:
        env = {"TERM": "dumb"}
        with mock.patch.dict(os.environ, env, clear=False):
            with mock.patch("globe_term.utils.is_terminal", return_value=True):
                assert detect_mouse_support() is False

    def test_empty_term_no_mouse(self) -> None:
        env = {"TERM": ""}
        with mock.patch.dict(os.environ, env, clear=False):
            with mock.patch("globe_term.utils.is_terminal", return_value=True):
                assert detect_mouse_support() is False

    def test_not_tty_no_mouse(self) -> None:
        with mock.patch("globe_term.utils.is_terminal", return_value=False):
            assert detect_mouse_support() is False

    def test_tmux_detected_via_env(self) -> None:
        """TMUX env var should signal mouse capability."""
        env = {"TERM": "screen", "TMUX": "/tmp/tmux-1000/default,1234,0"}
        with mock.patch.dict(os.environ, env, clear=False):
            with mock.patch("globe_term.utils.is_terminal", return_value=True):
                assert detect_mouse_support() is True

    def test_screen_term_has_mouse(self) -> None:
        """screen-* TERM values should have mouse support."""
        env = {"TERM": "screen-256color"}
        with mock.patch.dict(os.environ, env, clear=False):
            with mock.patch("globe_term.utils.is_terminal", return_value=True):
                assert detect_mouse_support() is True

    def test_tmux_term_has_mouse(self) -> None:
        """tmux TERM has mouse support."""
        env = {"TERM": "tmux-256color"}
        with mock.patch.dict(os.environ, env, clear=False):
            with mock.patch("globe_term.utils.is_terminal", return_value=True):
                assert detect_mouse_support() is True


# ---------------------------------------------------------------------------
# is_terminal
# ---------------------------------------------------------------------------

class TestIsTerminal:
    def test_tty_returns_true(self) -> None:
        with mock.patch("globe_term.utils.sys") as mock_sys:
            mock_sys.stdout.isatty.return_value = True
            assert is_terminal() is True

    def test_pipe_returns_false(self) -> None:
        with mock.patch("globe_term.utils.sys") as mock_sys:
            mock_sys.stdout.isatty.return_value = False
            assert is_terminal() is False

    def test_exception_returns_false(self) -> None:
        with mock.patch("globe_term.utils.sys") as mock_sys:
            mock_sys.stdout.isatty.side_effect = OSError("broken")
            assert is_terminal() is False


# ---------------------------------------------------------------------------
# ResizeDebouncer
# ---------------------------------------------------------------------------

class TestResizeDebouncer:
    def test_first_event_is_handled(self) -> None:
        """The very first resize event should always be handled."""
        clock = mock.Mock(return_value=1.0)
        d = ResizeDebouncer(interval=0.1, clock=clock)
        assert d.should_handle() is True

    def test_rapid_events_debounced(self) -> None:
        """Events arriving within the interval should be suppressed."""
        t = 1.0
        clock = mock.Mock(side_effect=lambda: t)
        d = ResizeDebouncer(interval=0.1, clock=clock)

        assert d.should_handle() is True  # t=1.0, first event

        t = 1.05  # 50ms later
        clock.side_effect = lambda: t
        assert d.should_handle() is False  # too soon
        assert d.pending is True

    def test_event_after_interval_is_handled(self) -> None:
        """Events arriving after the interval should be handled."""
        t = 1.0
        clock = mock.Mock(side_effect=lambda: t)
        d = ResizeDebouncer(interval=0.1, clock=clock)

        assert d.should_handle() is True

        t = 1.15  # 150ms later
        clock.side_effect = lambda: t
        assert d.should_handle() is True

    def test_flush_handles_pending(self) -> None:
        """flush() should handle a pending event after the interval."""
        t = 1.0
        clock = mock.Mock(side_effect=lambda: t)
        d = ResizeDebouncer(interval=0.1, clock=clock)

        d.should_handle()  # t=1.0, handled

        t = 1.05
        clock.side_effect = lambda: t
        d.should_handle()  # suppressed, now pending
        assert d.pending is True

        t = 1.15
        clock.side_effect = lambda: t
        assert d.flush() is True
        assert d.pending is False

    def test_flush_returns_false_when_no_pending(self) -> None:
        clock = mock.Mock(return_value=1.0)
        d = ResizeDebouncer(interval=0.1, clock=clock)
        assert d.flush() is False

    def test_flush_returns_false_when_too_soon(self) -> None:
        t = 1.0
        clock = mock.Mock(side_effect=lambda: t)
        d = ResizeDebouncer(interval=0.1, clock=clock)
        d.should_handle()

        t = 1.05
        clock.side_effect = lambda: t
        d.should_handle()  # pending

        # Still at 1.05, not enough time
        assert d.flush() is False

    def test_reset_clears_state(self) -> None:
        clock = mock.Mock(return_value=1.0)
        d = ResizeDebouncer(interval=0.1, clock=clock)
        d.should_handle()
        d.reset()
        assert d.pending is False
        # After reset, the next event should be handled immediately
        assert d.should_handle() is True

    def test_negative_interval_raises(self) -> None:
        with pytest.raises(ValueError, match="interval must be non-negative"):
            ResizeDebouncer(interval=-1.0)

    def test_zero_interval_always_handles(self) -> None:
        """With interval=0, every event should be handled."""
        clock = mock.Mock(return_value=1.0)
        d = ResizeDebouncer(interval=0.0, clock=clock)
        assert d.should_handle() is True
        assert d.should_handle() is True
        assert d.should_handle() is True

    def test_multiple_rapid_only_one_pending(self) -> None:
        """Multiple rapid events should only result in one pending flush."""
        t = 1.0
        clock = mock.Mock(side_effect=lambda: t)
        d = ResizeDebouncer(interval=0.1, clock=clock)

        d.should_handle()  # handled at t=1.0

        t = 1.02
        clock.side_effect = lambda: t
        d.should_handle()  # suppressed

        t = 1.04
        clock.side_effect = lambda: t
        d.should_handle()  # suppressed again

        t = 1.06
        clock.side_effect = lambda: t
        d.should_handle()  # still suppressed

        assert d.pending is True

        # Now advance past the interval
        t = 1.15
        clock.side_effect = lambda: t
        assert d.flush() is True
        assert d.pending is False
        # Subsequent flush has nothing pending
        assert d.flush() is False
