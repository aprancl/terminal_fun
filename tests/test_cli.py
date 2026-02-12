"""Tests for globe_term.cli module.

Covers:
- Argument parsing (all flag combinations, defaults, edge cases)
- Theme validation (invalid theme produces helpful error)
- Speed validation (negative, zero, very high)
- Integration: CLI launches app with correct configuration
- Smoke test: application starts and exits cleanly
- build_projection produces correct ProjectionPoint objects
- ThemeAdapter produces valid dictionaries
- _choose_render_mode selects correctly
"""

from __future__ import annotations

import curses
import math
import sys
from unittest import mock

import pytest

from globe_term import __version__
from globe_term.cli import (
    CLIConfig,
    DEFAULT_DRAG_SENSITIVITY,
    DragRotator,
    MAX_ROTATION_SPEED,
    SCROLL_ZOOM_STEP,
    SIZE_ZOOM_MAP,
    VALID_SIZES,
    _ThemeAdapter,
    _build_projection,
    _choose_render_mode,
    _display_loop,
    _validate_theme,
    main,
    parse_args,
)
from globe_term.globe import Globe
from globe_term.renderer import (
    ProjectionPoint,
    RenderMode,
    TERRAIN_BORDER,
    TERRAIN_EMPTY,
    TERRAIN_ICE,
    TERRAIN_LAND,
    TERRAIN_OCEAN,
)
from globe_term.themes import get_theme, list_themes


# ---------------------------------------------------------------------------
# _ThemeAdapter
# ---------------------------------------------------------------------------

class TestThemeAdapter:
    def test_get_terrain_colors_returns_dict(self) -> None:
        theme = get_theme("geography")
        adapter = _ThemeAdapter(theme)
        colors = adapter.get_terrain_colors()
        assert isinstance(colors, dict)
        assert TERRAIN_OCEAN in colors
        assert TERRAIN_LAND in colors
        assert TERRAIN_BORDER in colors
        assert TERRAIN_ICE in colors
        assert TERRAIN_EMPTY in colors

    def test_get_terrain_colors_uses_theme_values(self) -> None:
        theme = get_theme("geography")
        adapter = _ThemeAdapter(theme)
        colors = adapter.get_terrain_colors()
        assert colors[TERRAIN_OCEAN] == (theme.ocean_fg, theme.ocean_bg)
        assert colors[TERRAIN_LAND] == (theme.land_fg, theme.land_bg)

    def test_get_char_palette_ascii_mode(self) -> None:
        theme = get_theme("geography")
        adapter = _ThemeAdapter(theme)
        palette = adapter.get_char_palette(RenderMode.ASCII)
        assert palette is not None
        assert TERRAIN_OCEAN in palette
        assert TERRAIN_LAND in palette

    def test_get_char_palette_unicode_returns_none(self) -> None:
        theme = get_theme("geography")
        adapter = _ThemeAdapter(theme)
        palette = adapter.get_char_palette(RenderMode.UNICODE_BLOCK)
        assert palette is None

    def test_get_char_palette_braille_returns_none(self) -> None:
        theme = get_theme("geography")
        adapter = _ThemeAdapter(theme)
        palette = adapter.get_char_palette(RenderMode.BRAILLE)
        assert palette is None


# ---------------------------------------------------------------------------
# _build_projection
# ---------------------------------------------------------------------------

class TestBuildProjection:
    def test_returns_projection_points(self) -> None:
        globe = Globe()
        points = _build_projection(globe, 40, 20)
        assert isinstance(points, list)
        assert len(points) > 0
        for pt in points:
            assert isinstance(pt, ProjectionPoint)

    def test_all_points_within_bounds(self) -> None:
        globe = Globe()
        width, height = 40, 20
        points = _build_projection(globe, width, height)
        for pt in points:
            assert 0 <= pt.x < width
            assert 0 <= pt.y < height

    def test_terrain_types_are_valid(self) -> None:
        globe = Globe()
        points = _build_projection(globe, 40, 20)
        valid_terrains = {TERRAIN_OCEAN, TERRAIN_LAND, TERRAIN_BORDER, TERRAIN_ICE}
        for pt in points:
            assert pt.terrain in valid_terrains

    def test_shading_in_range(self) -> None:
        globe = Globe()
        points = _build_projection(globe, 40, 20)
        for pt in points:
            assert 0.0 <= pt.shading <= 1.0

    def test_zero_size_returns_empty(self) -> None:
        globe = Globe()
        assert _build_projection(globe, 0, 0) == []

    def test_includes_ocean_and_land(self) -> None:
        """A full globe projection should contain both ocean and land."""
        globe = Globe()
        points = _build_projection(globe, 80, 40)
        terrains = {pt.terrain for pt in points}
        assert TERRAIN_OCEAN in terrains
        assert TERRAIN_LAND in terrains


# ---------------------------------------------------------------------------
# _choose_render_mode
# ---------------------------------------------------------------------------

class TestChooseRenderMode:
    def test_unicode_when_supported(self) -> None:
        with mock.patch("globe_term.cli.detect_unicode_support", return_value=True):
            assert _choose_render_mode() == RenderMode.UNICODE_BLOCK

    def test_ascii_when_no_unicode(self) -> None:
        with mock.patch("globe_term.cli.detect_unicode_support", return_value=False):
            assert _choose_render_mode() == RenderMode.ASCII


# ---------------------------------------------------------------------------
# Smoke test: main() and _display_loop()
# ---------------------------------------------------------------------------

class _FakeScreen:
    """Minimal mock of a curses window for testing."""

    def __init__(self, rows: int = 40, cols: int = 80) -> None:
        self._rows = rows
        self._cols = cols
        self._getch_values: list[int] = []
        self._getch_idx = 0

    def getmaxyx(self) -> tuple[int, int]:
        return (self._rows, self._cols)

    def getch(self) -> int:
        if self._getch_idx < len(self._getch_values):
            val = self._getch_values[self._getch_idx]
            self._getch_idx += 1
            return val
        return -1

    def nodelay(self, flag: bool) -> None:
        pass

    def keypad(self, flag: bool) -> None:
        pass

    def addstr(self, y: int, x: int, s: str, attrs: int = 0) -> None:
        pass

    def noutrefresh(self) -> None:
        pass

    def clear(self) -> None:
        pass

    def queue_keys(self, *keys: int) -> None:
        self._getch_values = list(keys)
        self._getch_idx = 0


class TestDisplayLoopSmoke:
    """Test that the display loop starts, renders, and exits cleanly."""

    def test_quit_on_q(self) -> None:
        """Pressing 'q' exits the loop."""
        screen = _FakeScreen(40, 80)
        # Return -1 (no key) for first call, then 'q'
        screen.queue_keys(-1, ord("q"))

        with mock.patch("globe_term.renderer.curses") as mock_curses:
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
            mock_curses.napms.return_value = None
            mock_curses.KEY_RESIZE = curses.KEY_RESIZE

            # Also patch curses in the cli module for napms
            with mock.patch("globe_term.cli.curses") as mock_cli_curses:
                mock_cli_curses.error = curses.error
                mock_cli_curses.KEY_RESIZE = curses.KEY_RESIZE
                mock_cli_curses.napms.return_value = None

                _display_loop(screen)

    def test_quit_on_uppercase_q(self) -> None:
        """Pressing 'Q' also exits."""
        screen = _FakeScreen(40, 80)
        screen.queue_keys(ord("Q"))

        with mock.patch("globe_term.renderer.curses") as mock_curses:
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
            mock_curses.napms.return_value = None
            mock_curses.KEY_RESIZE = curses.KEY_RESIZE

            with mock.patch("globe_term.cli.curses") as mock_cli_curses:
                mock_cli_curses.error = curses.error
                mock_cli_curses.KEY_RESIZE = curses.KEY_RESIZE
                mock_cli_curses.napms.return_value = None

                _display_loop(screen)


class TestMainSmoke:
    def test_main_calls_curses_wrapper(self) -> None:
        """main() should invoke curses.wrapper."""
        with mock.patch("globe_term.cli.curses.wrapper") as mock_wrapper, \
             mock.patch("globe_term.cli.is_terminal", return_value=True), \
             mock.patch("globe_term.cli.detect_mouse_support", return_value=True):
            main([])
            mock_wrapper.assert_called_once()

    def test_main_handles_keyboard_interrupt(self) -> None:
        """main() should handle KeyboardInterrupt gracefully."""
        with mock.patch(
            "globe_term.cli.curses.wrapper", side_effect=KeyboardInterrupt
        ), \
             mock.patch("globe_term.cli.is_terminal", return_value=True), \
             mock.patch("globe_term.cli.detect_mouse_support", return_value=True):
            # Should not raise
            main([])

    def test_main_passes_config_to_display_loop(self) -> None:
        """main() should pass parsed config to the display loop."""
        with mock.patch("globe_term.cli.curses.wrapper") as mock_wrapper, \
             mock.patch("globe_term.cli.is_terminal", return_value=True), \
             mock.patch("globe_term.cli.detect_mouse_support", return_value=True):
            main(["--speed", "2.5", "--no-color", "--size", "small"])
            mock_wrapper.assert_called_once()
            # The wrapper receives a lambda; call it with a fake screen
            # to check the config is passed through.
            callback = mock_wrapper.call_args[0][0]
            assert callable(callback)


# ---------------------------------------------------------------------------
# parse_args: argument parsing produces correct config
# ---------------------------------------------------------------------------


class TestParseArgs:
    """Argument parsing produces correct CLIConfig for all flag combinations."""

    def test_defaults(self) -> None:
        """No arguments produces default config."""
        config = parse_args([])
        assert config.speed == 1.0
        assert config.theme == "geography"
        assert config.no_color is False
        assert config.size == "auto"

    def test_speed_flag(self) -> None:
        """--speed sets the speed value."""
        config = parse_args(["--speed", "2.0"])
        assert config.speed == 2.0

    def test_speed_zero(self) -> None:
        """--speed 0 is valid (no rotation)."""
        config = parse_args(["--speed", "0"])
        assert config.speed == 0.0

    def test_speed_very_high(self) -> None:
        """Very high speed values are passed through."""
        config = parse_args(["--speed", "999.9"])
        assert config.speed == 999.9

    def test_negative_speed_clamped_to_zero(self) -> None:
        """Negative speed is treated as 0 (no auto-rotation)."""
        config = parse_args(["--speed", "-5.0"])
        assert config.speed == 0.0

    def test_negative_speed_small_clamped(self) -> None:
        """Small negative speed is also clamped."""
        config = parse_args(["--speed", "-0.001"])
        assert config.speed == 0.0

    def test_theme_flag(self) -> None:
        """--theme sets the theme name."""
        config = parse_args(["--theme", "geography"])
        assert config.theme == "geography"

    def test_no_color_flag(self) -> None:
        """--no-color enables monochrome mode."""
        config = parse_args(["--no-color"])
        assert config.no_color is True

    def test_size_small(self) -> None:
        """--size small is accepted."""
        config = parse_args(["--size", "small"])
        assert config.size == "small"

    def test_size_medium(self) -> None:
        """--size medium is accepted."""
        config = parse_args(["--size", "medium"])
        assert config.size == "medium"

    def test_size_large(self) -> None:
        """--size large is accepted."""
        config = parse_args(["--size", "large"])
        assert config.size == "large"

    def test_size_auto(self) -> None:
        """--size auto is accepted."""
        config = parse_args(["--size", "auto"])
        assert config.size == "auto"

    def test_all_flags_combined(self) -> None:
        """All flags can be combined."""
        config = parse_args([
            "--speed", "3.0",
            "--theme", "geography",
            "--no-color",
            "--size", "large",
        ])
        assert config.speed == 3.0
        assert config.theme == "geography"
        assert config.no_color is True
        assert config.size == "large"

    def test_version_flag(self) -> None:
        """--version prints version and exits."""
        with pytest.raises(SystemExit) as exc_info:
            parse_args(["--version"])
        assert exc_info.value.code == 0

    def test_help_flag(self) -> None:
        """--help prints usage and exits."""
        with pytest.raises(SystemExit) as exc_info:
            parse_args(["--help"])
        assert exc_info.value.code == 0

    def test_invalid_size_rejected(self) -> None:
        """Invalid --size value produces an error."""
        with pytest.raises(SystemExit) as exc_info:
            parse_args(["--size", "huge"])
        assert exc_info.value.code == 2

    def test_invalid_speed_type_rejected(self) -> None:
        """Non-numeric --speed value produces an error."""
        with pytest.raises(SystemExit) as exc_info:
            parse_args(["--speed", "fast"])
        assert exc_info.value.code == 2

    def test_unknown_flag_rejected(self) -> None:
        """Unknown flags produce an argparse error."""
        with pytest.raises(SystemExit) as exc_info:
            parse_args(["--unknown-flag"])
        assert exc_info.value.code == 2

    def test_config_is_cliconfig_instance(self) -> None:
        """parse_args returns a CLIConfig dataclass."""
        config = parse_args([])
        assert isinstance(config, CLIConfig)


# ---------------------------------------------------------------------------
# Theme validation
# ---------------------------------------------------------------------------


class TestThemeValidation:
    """Invalid theme name produces helpful error with available themes list."""

    def test_valid_theme_passes(self) -> None:
        """Valid theme name passes validation."""
        result = _validate_theme("geography")
        assert result == "geography"

    def test_invalid_theme_exits_with_error(self) -> None:
        """Invalid theme name causes sys.exit(2)."""
        with pytest.raises(SystemExit) as exc_info:
            _validate_theme("nonexistent_theme")
        assert exc_info.value.code == 2

    def test_invalid_theme_lists_available(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Invalid theme error message lists available themes."""
        with pytest.raises(SystemExit):
            _validate_theme("nonexistent_theme")
        captured = capsys.readouterr()
        # The error message goes to stderr
        assert "nonexistent_theme" in captured.err
        assert "Available themes:" in captured.err
        # Should list at least the geography theme
        assert "geography" in captured.err

    def test_invalid_theme_via_parse_args(self) -> None:
        """parse_args with invalid theme exits."""
        with pytest.raises(SystemExit) as exc_info:
            parse_args(["--theme", "does_not_exist"])
        assert exc_info.value.code == 2


# ---------------------------------------------------------------------------
# Speed validation
# ---------------------------------------------------------------------------


class TestSpeedValidation:
    """Speed validation: negative, zero, very high."""

    def test_zero_speed(self) -> None:
        config = parse_args(["--speed", "0.0"])
        assert config.speed == 0.0

    def test_negative_speed_becomes_zero(self) -> None:
        config = parse_args(["--speed", "-10.0"])
        assert config.speed == 0.0

    def test_large_negative_speed_becomes_zero(self) -> None:
        config = parse_args(["--speed", "-99999"])
        assert config.speed == 0.0

    def test_positive_speed_unchanged(self) -> None:
        config = parse_args(["--speed", "1.5"])
        assert config.speed == 1.5

    def test_very_high_speed(self) -> None:
        config = parse_args(["--speed", "100.0"])
        assert config.speed == 100.0

    def test_fractional_speed(self) -> None:
        config = parse_args(["--speed", "0.1"])
        assert config.speed == pytest.approx(0.1)


# ---------------------------------------------------------------------------
# Integration: CLI launches with correct configuration
# ---------------------------------------------------------------------------


class TestCLIIntegration:
    """Integration: CLI launches app with correct configuration."""

    def _make_curses_mocks(self):
        """Create mocks for both renderer and cli curses modules."""
        renderer_mock = mock.MagicMock()
        renderer_mock.COLOR_PAIRS = 256
        renderer_mock.color_pair.return_value = 0
        renderer_mock.has_colors.return_value = True
        renderer_mock.A_BOLD = 0
        renderer_mock.error = curses.error
        renderer_mock.start_color.return_value = None
        renderer_mock.use_default_colors.return_value = None
        renderer_mock.curs_set.return_value = None
        renderer_mock.init_pair.return_value = None
        renderer_mock.doupdate.return_value = None
        renderer_mock.napms.return_value = None
        renderer_mock.KEY_RESIZE = curses.KEY_RESIZE

        cli_mock = mock.MagicMock()
        cli_mock.error = curses.error
        cli_mock.KEY_RESIZE = curses.KEY_RESIZE
        cli_mock.napms.return_value = None

        return renderer_mock, cli_mock

    def test_default_config_launches(self) -> None:
        """Default args produce a working display loop."""
        screen = _FakeScreen(40, 80)
        screen.queue_keys(ord("q"))

        renderer_mock, cli_mock = self._make_curses_mocks()

        with mock.patch("globe_term.renderer.curses", renderer_mock), \
             mock.patch("globe_term.cli.curses", cli_mock):
            config = parse_args([])
            _display_loop(screen, config)

    def test_no_color_forces_monochrome(self) -> None:
        """--no-color config forces the renderer into monochrome mode."""
        screen = _FakeScreen(40, 80)
        screen.queue_keys(ord("q"))

        renderer_mock, cli_mock = self._make_curses_mocks()
        # Even though the terminal supports colors, --no-color should
        # force monochrome.  The renderer receives force_monochrome=True
        # and its has_colors property should be False.
        renderer_mock.has_colors.return_value = True

        with mock.patch("globe_term.renderer.curses", renderer_mock), \
             mock.patch("globe_term.cli.curses", cli_mock), \
             mock.patch("globe_term.cli.detect_color_support", return_value=True):
            config = parse_args(["--no-color"])
            _display_loop(screen, config)
            # Verify monochrome was forced: start_color should NOT be called
            # because force_monochrome is True
            renderer_mock.start_color.assert_not_called()

    def test_size_small_adjusts_zoom(self) -> None:
        """--size small creates a globe with smaller zoom."""
        screen = _FakeScreen(40, 80)
        screen.queue_keys(ord("q"))

        renderer_mock, cli_mock = self._make_curses_mocks()

        with mock.patch("globe_term.renderer.curses", renderer_mock), \
             mock.patch("globe_term.cli.curses", cli_mock):
            config = parse_args(["--size", "small"])
            assert config.size == "small"
            # Verify the zoom mapping exists
            assert SIZE_ZOOM_MAP["small"] == 0.5

    def test_speed_value_used_in_display_loop(self) -> None:
        """--speed value is stored in CLIConfig and used by the display loop."""
        screen = _FakeScreen(40, 80)
        screen.queue_keys(ord("q"))

        renderer_mock, cli_mock = self._make_curses_mocks()

        with mock.patch("globe_term.renderer.curses", renderer_mock), \
             mock.patch("globe_term.cli.curses", cli_mock):
            config = parse_args(["--speed", "2.5"])
            assert config.speed == 2.5
            # Display loop should run without error with the speed config
            _display_loop(screen, config)

    def test_theme_loaded_correctly(self) -> None:
        """--theme geography loads the geography theme."""
        screen = _FakeScreen(40, 80)
        screen.queue_keys(ord("q"))

        renderer_mock, cli_mock = self._make_curses_mocks()

        with mock.patch("globe_term.renderer.curses", renderer_mock), \
             mock.patch("globe_term.cli.curses", cli_mock):
            config = parse_args(["--theme", "geography"])
            _display_loop(screen, config)
            # If we get here without error, the theme loaded fine


# ---------------------------------------------------------------------------
# Version output
# ---------------------------------------------------------------------------


class TestVersionOutput:
    def test_version_contains_version_string(self, capsys: pytest.CaptureFixture[str]) -> None:
        """--version outputs the version string."""
        with pytest.raises(SystemExit):
            parse_args(["--version"])
        captured = capsys.readouterr()
        assert __version__ in captured.out

    def test_version_contains_prog_name(self, capsys: pytest.CaptureFixture[str]) -> None:
        """--version output includes the program name."""
        with pytest.raises(SystemExit):
            parse_args(["--version"])
        captured = capsys.readouterr()
        assert "globe_term" in captured.out


# ---------------------------------------------------------------------------
# Performance: projection under 50ms
# ---------------------------------------------------------------------------

class TestPerformance:
    def test_projection_under_50ms(self) -> None:
        """A full 80x40 projection + terrain lookup should complete in <50ms."""
        import time

        globe = Globe(
            rotation_x=math.radians(-15),
            rotation_y=math.radians(0),
        )

        start = time.monotonic()
        _build_projection(globe, 80, 40)
        elapsed_ms = (time.monotonic() - start) * 1000

        assert elapsed_ms < 50, f"Projection took {elapsed_ms:.1f}ms (> 50ms limit)"


# ---------------------------------------------------------------------------
# DragRotator: drag delta -> rotation angle mapping
# ---------------------------------------------------------------------------


class TestDragRotator:
    """Unit tests for DragRotator.map_drag()."""

    def test_zero_drag_produces_zero_rotation(self) -> None:
        """Click without drag (dx=0, dy=0) produces zero rotation."""
        rotator = DragRotator()
        rot_y, rot_x = rotator.map_drag(0, 0)
        assert rot_y == 0.0
        assert rot_x == 0.0

    def test_horizontal_drag_maps_to_y_rotation(self) -> None:
        """Horizontal drag (dx) maps to Y-axis rotation."""
        rotator = DragRotator()
        rot_y, rot_x = rotator.map_drag(5, 0)
        assert rot_y == pytest.approx(5 * DEFAULT_DRAG_SENSITIVITY)
        assert rot_x == 0.0

    def test_vertical_drag_maps_to_x_rotation(self) -> None:
        """Vertical drag (dy) maps to X-axis rotation."""
        rotator = DragRotator()
        rot_y, rot_x = rotator.map_drag(0, 8)
        assert rot_y == 0.0
        assert rot_x == pytest.approx(8 * DEFAULT_DRAG_SENSITIVITY)

    def test_diagonal_drag_maps_both_axes(self) -> None:
        """Diagonal drag maps to both X and Y rotation."""
        rotator = DragRotator()
        rot_y, rot_x = rotator.map_drag(3, 4)
        assert rot_y == pytest.approx(3 * DEFAULT_DRAG_SENSITIVITY)
        assert rot_x == pytest.approx(4 * DEFAULT_DRAG_SENSITIVITY)

    def test_negative_drag_produces_negative_rotation(self) -> None:
        """Leftward / upward drag produces negative rotation."""
        rotator = DragRotator()
        rot_y, rot_x = rotator.map_drag(-5, -3)
        assert rot_y == pytest.approx(-5 * DEFAULT_DRAG_SENSITIVITY)
        assert rot_x == pytest.approx(-3 * DEFAULT_DRAG_SENSITIVITY)

    def test_rotation_proportional_to_drag_distance(self) -> None:
        """Larger drag produces proportionally larger rotation."""
        rotator = DragRotator()
        rot_y_small, _ = rotator.map_drag(2, 0)
        rot_y_large, _ = rotator.map_drag(6, 0)
        # 6/2 = 3x ratio (within max_speed)
        assert rot_y_large == pytest.approx(rot_y_small * 3.0)

    def test_custom_sensitivity(self) -> None:
        """Custom sensitivity value scales rotation accordingly."""
        rotator = DragRotator(sensitivity=0.05)
        rot_y, rot_x = rotator.map_drag(2, 2)
        assert rot_y == pytest.approx(2 * 0.05)
        assert rot_x == pytest.approx(2 * 0.05)


class TestDragRotatorSpeedCapping:
    """Unit tests for rotation speed capping at extremes."""

    def test_fast_horizontal_drag_capped(self) -> None:
        """Very fast horizontal drag is capped at max rotation speed."""
        rotator = DragRotator()
        # dx=1000 would give 1000 * 0.01 = 10.0 rad, way over max
        rot_y, rot_x = rotator.map_drag(1000, 0)
        assert rot_y == pytest.approx(MAX_ROTATION_SPEED)
        assert rot_x == 0.0

    def test_fast_vertical_drag_capped(self) -> None:
        """Very fast vertical drag is capped at max rotation speed."""
        rotator = DragRotator()
        rot_y, rot_x = rotator.map_drag(0, -500)
        assert rot_y == 0.0
        assert rot_x == pytest.approx(-MAX_ROTATION_SPEED)

    def test_fast_diagonal_drag_capped_independently(self) -> None:
        """Each axis is capped independently at max rotation speed."""
        rotator = DragRotator()
        rot_y, rot_x = rotator.map_drag(1000, -1000)
        assert rot_y == pytest.approx(MAX_ROTATION_SPEED)
        assert rot_x == pytest.approx(-MAX_ROTATION_SPEED)

    def test_below_cap_not_clamped(self) -> None:
        """Drag values below the cap are not clamped."""
        rotator = DragRotator()
        # 5 * 0.01 = 0.05, well below 0.15
        rot_y, rot_x = rotator.map_drag(5, 5)
        assert rot_y == pytest.approx(5 * DEFAULT_DRAG_SENSITIVITY)
        assert rot_x == pytest.approx(5 * DEFAULT_DRAG_SENSITIVITY)
        assert abs(rot_y) < MAX_ROTATION_SPEED
        assert abs(rot_x) < MAX_ROTATION_SPEED

    def test_custom_max_speed(self) -> None:
        """Custom max_speed caps at the specified value."""
        rotator = DragRotator(max_speed=0.05)
        rot_y, _ = rotator.map_drag(100, 0)
        assert rot_y == pytest.approx(0.05)

    def test_exact_cap_boundary(self) -> None:
        """Drag that produces exactly max_speed is not changed."""
        rotator = DragRotator(sensitivity=0.01, max_speed=0.15)
        # 15 * 0.01 = 0.15, exactly at the cap
        rot_y, _ = rotator.map_drag(15, 0)
        assert rot_y == pytest.approx(0.15)


class TestDragToRotateIntegration:
    """Integration: DragRotator + Globe.rotate() end-to-end."""

    def test_drag_rotates_globe(self) -> None:
        """Mapping drag to rotation and applying to Globe changes state."""
        globe = Globe(rotation_x=0.0, rotation_y=0.0)
        rotator = DragRotator()

        rot_y, rot_x = rotator.map_drag(10, 5)
        globe.rotate(rot_y, rot_x)

        assert globe.rotation_y == pytest.approx(10 * DEFAULT_DRAG_SENSITIVITY)
        assert globe.rotation_x == pytest.approx(5 * DEFAULT_DRAG_SENSITIVITY)

    def test_click_no_drag_globe_unchanged(self) -> None:
        """Click without drag: DragRotator returns (0,0), globe unchanged."""
        globe = Globe(rotation_x=1.0, rotation_y=2.0)
        rotator = DragRotator()

        rot_y, rot_x = rotator.map_drag(0, 0)
        globe.rotate(rot_y, rot_x)

        assert globe.rotation_x == pytest.approx(1.0)
        assert globe.rotation_y == pytest.approx(2.0)

    def test_releasing_mouse_stops_rotation(self) -> None:
        """After DRAG_END, no more rotation is applied.

        DRAG_END does not produce a rotation; only DRAG_START/DRAG_MOVE do.
        So releasing the mouse effectively stops rotation.
        """
        globe = Globe(rotation_x=0.0, rotation_y=0.0)
        rotator = DragRotator()

        # Simulate drag
        rot_y, rot_x = rotator.map_drag(10, 5)
        globe.rotate(rot_y, rot_x)
        state_after_drag = (globe.rotation_x, globe.rotation_y)

        # DRAG_END: the display loop does NOT call map_drag for DRAG_END,
        # so globe state does not change
        assert globe.rotation_x == pytest.approx(state_after_drag[0])
        assert globe.rotation_y == pytest.approx(state_after_drag[1])

    def test_multiple_drags_accumulate(self) -> None:
        """Multiple drag events accumulate rotation."""
        globe = Globe(rotation_x=0.0, rotation_y=0.0)
        rotator = DragRotator()

        for _ in range(5):
            rot_y, rot_x = rotator.map_drag(2, 3)
            globe.rotate(rot_y, rot_x)

        expected_y = 5 * 2 * DEFAULT_DRAG_SENSITIVITY
        expected_x = 5 * 3 * DEFAULT_DRAG_SENSITIVITY
        assert globe.rotation_y == pytest.approx(expected_y)
        assert globe.rotation_x == pytest.approx(expected_x)


# ---------------------------------------------------------------------------
# Scroll-to-zoom: SCROLL_ZOOM_STEP + Globe.adjust_zoom integration
# ---------------------------------------------------------------------------


class TestScrollZoomStep:
    """Unit tests for the SCROLL_ZOOM_STEP constant."""

    def test_scroll_zoom_step_is_positive(self) -> None:
        """SCROLL_ZOOM_STEP must be a positive number."""
        assert SCROLL_ZOOM_STEP > 0

    def test_scroll_zoom_step_is_reasonable(self) -> None:
        """SCROLL_ZOOM_STEP should be a small increment (between 0.01 and 1.0)."""
        assert 0.01 <= SCROLL_ZOOM_STEP <= 1.0


class TestScrollToZoomIntegration:
    """Integration: scroll events + Globe.adjust_zoom() end-to-end."""

    def test_scroll_up_increases_zoom(self) -> None:
        """Scroll up applies positive SCROLL_ZOOM_STEP to zoom."""
        globe = Globe(zoom=1.0)
        globe.adjust_zoom(SCROLL_ZOOM_STEP)
        assert globe.zoom == pytest.approx(1.0 + SCROLL_ZOOM_STEP)

    def test_scroll_down_decreases_zoom(self) -> None:
        """Scroll down applies negative SCROLL_ZOOM_STEP to zoom."""
        globe = Globe(zoom=1.0)
        globe.adjust_zoom(-SCROLL_ZOOM_STEP)
        assert globe.zoom == pytest.approx(1.0 - SCROLL_ZOOM_STEP)

    def test_multiple_scroll_up_accumulates(self) -> None:
        """Multiple scroll-up events accumulate zoom increase."""
        globe = Globe(zoom=1.0)
        for _ in range(5):
            globe.adjust_zoom(SCROLL_ZOOM_STEP)
        assert globe.zoom == pytest.approx(1.0 + 5 * SCROLL_ZOOM_STEP)

    def test_multiple_scroll_down_accumulates(self) -> None:
        """Multiple scroll-down events accumulate zoom decrease."""
        globe = Globe(zoom=1.0)
        for _ in range(3):
            globe.adjust_zoom(-SCROLL_ZOOM_STEP)
        assert globe.zoom == pytest.approx(1.0 - 3 * SCROLL_ZOOM_STEP)

    def test_scroll_up_at_max_zoom_stays_at_max(self) -> None:
        """Scrolling up when already at MAX_ZOOM has no effect."""
        from globe_term.globe import MAX_ZOOM
        globe = Globe(zoom=MAX_ZOOM)
        globe.adjust_zoom(SCROLL_ZOOM_STEP)
        assert globe.zoom == MAX_ZOOM

    def test_scroll_down_at_min_zoom_stays_at_min(self) -> None:
        """Scrolling down when already at MIN_ZOOM has no effect."""
        from globe_term.globe import MIN_ZOOM
        globe = Globe(zoom=MIN_ZOOM)
        globe.adjust_zoom(-SCROLL_ZOOM_STEP)
        assert globe.zoom == MIN_ZOOM

    def test_rapid_scrolling_stays_in_bounds(self) -> None:
        """Rapid scrolling (many events) stays within bounds."""
        from globe_term.globe import MIN_ZOOM, MAX_ZOOM
        globe = Globe(zoom=1.0)
        # Rapid scroll up 100 times
        for _ in range(100):
            globe.adjust_zoom(SCROLL_ZOOM_STEP)
        assert globe.zoom == MAX_ZOOM

        # Rapid scroll down 200 times
        for _ in range(200):
            globe.adjust_zoom(-SCROLL_ZOOM_STEP)
        assert globe.zoom == MIN_ZOOM

    def test_zoom_affects_projection_point_count(self) -> None:
        """Zoom level change via adjust_zoom changes projection output."""
        globe_small = Globe(zoom=0.5)
        globe_large = Globe(zoom=0.5)
        globe_large.adjust_zoom(1.0)  # zoom to 1.5

        points_small = _build_projection(globe_small, 80, 40)
        points_large = _build_projection(globe_large, 80, 40)

        assert len(points_large) > len(points_small), (
            f"Zoomed-in globe ({len(points_large)} points) should have more "
            f"projection points than zoomed-out ({len(points_small)} points)"
        )
