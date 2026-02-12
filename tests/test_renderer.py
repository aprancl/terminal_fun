"""Tests for globe_term.renderer module.

Covers:
- Buffer diffing correctly identifies changed cells
- Character selection maps terrain + shading to correct chars
- Color fallback activates when colors unavailable
- Double-buffering swap logic
- Edge cases for small/large buffers
"""

from __future__ import annotations

import curses
from unittest import mock

import pytest

from globe_term.renderer import (
    Cell,
    DEFAULT_CHAR_PALETTES,
    DEFAULT_TERRAIN_COLORS,
    MIN_TERM_COLS,
    MIN_TERM_ROWS,
    ProjectionPoint,
    Renderer,
    RenderMode,
    SIZE_WARNING,
    TERRAIN_BORDER,
    TERRAIN_EMPTY,
    TERRAIN_ICE,
    TERRAIN_LAND,
    TERRAIN_OCEAN,
    diff_buffers,
    get_color_pair,
    make_buffer,
    select_character,
    _reset_color_pairs,
)


# ---------------------------------------------------------------------------
# Cell dataclass
# ---------------------------------------------------------------------------

class TestCell:
    def test_default_values(self) -> None:
        cell = Cell()
        assert cell.char == " "
        assert cell.fg_color == -1
        assert cell.bg_color == -1
        assert cell.attrs == 0

    def test_custom_values(self) -> None:
        cell = Cell(char="A", fg_color=1, bg_color=2, attrs=4)
        assert cell.char == "A"
        assert cell.fg_color == 1
        assert cell.bg_color == 2
        assert cell.attrs == 4

    def test_frozen(self) -> None:
        cell = Cell()
        with pytest.raises(AttributeError):
            cell.char = "X"  # type: ignore[misc]

    def test_equality(self) -> None:
        a = Cell(char="X", fg_color=1, bg_color=2, attrs=0)
        b = Cell(char="X", fg_color=1, bg_color=2, attrs=0)
        c = Cell(char="Y", fg_color=1, bg_color=2, attrs=0)
        assert a == b
        assert a != c


# ---------------------------------------------------------------------------
# Buffer creation and diffing
# ---------------------------------------------------------------------------

class TestMakeBuffer:
    def test_dimensions(self) -> None:
        buf = make_buffer(5, 10)
        assert len(buf) == 5
        assert all(len(row) == 10 for row in buf)

    def test_default_fill(self) -> None:
        buf = make_buffer(2, 3)
        for row in buf:
            for cell in row:
                assert cell == Cell()

    def test_custom_fill(self) -> None:
        fill = Cell(char="X")
        buf = make_buffer(2, 3, fill=fill)
        for row in buf:
            for cell in row:
                assert cell.char == "X"

    def test_zero_size(self) -> None:
        buf = make_buffer(0, 0)
        assert buf == []


class TestDiffBuffers:
    """Unit: Buffer diffing correctly identifies changed cells."""

    def test_identical_buffers_no_changes(self) -> None:
        front = make_buffer(3, 4)
        back = make_buffer(3, 4)
        changes = diff_buffers(front, back)
        assert changes == []

    def test_single_cell_changed(self) -> None:
        front = make_buffer(3, 4)
        back = make_buffer(3, 4)
        new_cell = Cell(char="X", fg_color=1, bg_color=2, attrs=0)
        back[1][2] = new_cell
        changes = diff_buffers(front, back)
        assert len(changes) == 1
        assert changes[0] == (1, 2, new_cell)

    def test_multiple_cells_changed(self) -> None:
        front = make_buffer(5, 5)
        back = make_buffer(5, 5)
        back[0][0] = Cell(char="A")
        back[2][3] = Cell(char="B")
        back[4][4] = Cell(char="C")
        changes = diff_buffers(front, back)
        assert len(changes) == 3
        positions = {(r, c) for r, c, _ in changes}
        assert positions == {(0, 0), (2, 3), (4, 4)}

    def test_all_cells_changed(self) -> None:
        front = make_buffer(3, 3)
        back = make_buffer(3, 3, fill=Cell(char="Z"))
        changes = diff_buffers(front, back)
        assert len(changes) == 9

    def test_different_sized_buffers(self) -> None:
        """Compare buffers of different sizes -- uses overlapping region."""
        front = make_buffer(2, 3)
        back = make_buffer(4, 5)
        back[0][0] = Cell(char="X")
        changes = diff_buffers(front, back)
        # Only checks the 2x3 overlap region
        assert len(changes) == 1
        assert changes[0] == (0, 0, Cell(char="X"))

    def test_dirty_region_percentage(self) -> None:
        """Verify that small changes result in far fewer diffs than total cells."""
        size = 50
        front = make_buffer(size, size)
        back = make_buffer(size, size)
        # Change only 5% of cells
        changed_count = int(size * size * 0.05)
        for i in range(changed_count):
            r = i // size
            c = i % size
            if r < size and c < size:
                back[r][c] = Cell(char="X")
        changes = diff_buffers(front, back)
        assert len(changes) == changed_count
        # Confirm >50% reduction in writes
        total_cells = size * size
        assert len(changes) < total_cells * 0.5


# ---------------------------------------------------------------------------
# Character selection
# ---------------------------------------------------------------------------

class TestSelectCharacter:
    """Unit: Character selection maps terrain + shading to correct chars."""

    def test_ocean_darkest(self) -> None:
        ch = select_character(TERRAIN_OCEAN, 0.0, render_mode=RenderMode.ASCII)
        palette = DEFAULT_CHAR_PALETTES[RenderMode.ASCII][TERRAIN_OCEAN]
        assert ch == palette[0]

    def test_ocean_brightest(self) -> None:
        ch = select_character(TERRAIN_OCEAN, 1.0, render_mode=RenderMode.ASCII)
        palette = DEFAULT_CHAR_PALETTES[RenderMode.ASCII][TERRAIN_OCEAN]
        assert ch == palette[-1]

    def test_land_mid_shading(self) -> None:
        ch = select_character(TERRAIN_LAND, 0.5, render_mode=RenderMode.ASCII)
        palette = DEFAULT_CHAR_PALETTES[RenderMode.ASCII][TERRAIN_LAND]
        expected_idx = int(0.5 * (len(palette) - 1))
        assert ch == palette[expected_idx]

    def test_shading_clamped_below_zero(self) -> None:
        ch = select_character(TERRAIN_LAND, -0.5, render_mode=RenderMode.ASCII)
        palette = DEFAULT_CHAR_PALETTES[RenderMode.ASCII][TERRAIN_LAND]
        assert ch == palette[0]

    def test_shading_clamped_above_one(self) -> None:
        ch = select_character(TERRAIN_LAND, 1.5, render_mode=RenderMode.ASCII)
        palette = DEFAULT_CHAR_PALETTES[RenderMode.ASCII][TERRAIN_LAND]
        assert ch == palette[-1]

    def test_unknown_terrain_returns_space(self) -> None:
        ch = select_character("unknown_terrain", 0.5)
        assert ch == " "

    def test_empty_terrain(self) -> None:
        ch = select_character(TERRAIN_EMPTY, 0.5, render_mode=RenderMode.ASCII)
        assert ch == " "

    def test_custom_palette(self) -> None:
        custom = {TERRAIN_OCEAN: "AB", TERRAIN_LAND: "CD"}
        assert select_character(TERRAIN_OCEAN, 0.0, char_palette=custom) == "A"
        assert select_character(TERRAIN_OCEAN, 1.0, char_palette=custom) == "B"
        assert select_character(TERRAIN_LAND, 0.0, char_palette=custom) == "C"
        assert select_character(TERRAIN_LAND, 1.0, char_palette=custom) == "D"

    def test_unicode_block_mode(self) -> None:
        ch = select_character(TERRAIN_LAND, 1.0, render_mode=RenderMode.UNICODE_BLOCK)
        palette = DEFAULT_CHAR_PALETTES[RenderMode.UNICODE_BLOCK][TERRAIN_LAND]
        assert ch == palette[-1]

    def test_braille_mode(self) -> None:
        ch = select_character(TERRAIN_LAND, 1.0, render_mode=RenderMode.BRAILLE)
        palette = DEFAULT_CHAR_PALETTES[RenderMode.BRAILLE][TERRAIN_LAND]
        assert ch == palette[-1]

    def test_all_render_modes_have_palettes(self) -> None:
        for mode in RenderMode:
            assert mode in DEFAULT_CHAR_PALETTES
            palette = DEFAULT_CHAR_PALETTES[mode]
            for terrain in [TERRAIN_OCEAN, TERRAIN_LAND, TERRAIN_BORDER, TERRAIN_ICE, TERRAIN_EMPTY]:
                assert terrain in palette

    def test_border_terrain(self) -> None:
        ch = select_character(TERRAIN_BORDER, 0.5, render_mode=RenderMode.ASCII)
        palette = DEFAULT_CHAR_PALETTES[RenderMode.ASCII][TERRAIN_BORDER]
        expected_idx = int(0.5 * (len(palette) - 1))
        assert ch == palette[expected_idx]

    def test_ice_terrain(self) -> None:
        ch = select_character(TERRAIN_ICE, 0.5, render_mode=RenderMode.ASCII)
        palette = DEFAULT_CHAR_PALETTES[RenderMode.ASCII][TERRAIN_ICE]
        expected_idx = int(0.5 * (len(palette) - 1))
        assert ch == palette[expected_idx]


# ---------------------------------------------------------------------------
# Color pair management
# ---------------------------------------------------------------------------

class TestColorPair:
    """Unit: Color fallback activates when colors unavailable."""

    def test_no_color_returns_zero(self) -> None:
        pair = get_color_pair(curses.COLOR_RED, curses.COLOR_BLACK, has_colors=False)
        assert pair == 0

    def test_no_color_all_terrains_return_zero(self) -> None:
        for terrain, (fg, bg) in DEFAULT_TERRAIN_COLORS.items():
            pair = get_color_pair(fg, bg, has_colors=False)
            assert pair == 0, f"terrain={terrain} should return 0 without color"


# ---------------------------------------------------------------------------
# Renderer (with mocked curses)
# ---------------------------------------------------------------------------

def _make_mock_stdscr(rows: int = 50, cols: int = 200) -> mock.MagicMock:
    """Create a mock curses stdscr for testing."""
    stdscr = mock.MagicMock()
    stdscr.getmaxyx.return_value = (rows, cols)
    return stdscr


@pytest.fixture(autouse=True)
def _patch_curses() -> "pytest.Generator[None, None, None]":
    """Patch curses functions that require a real terminal."""
    with mock.patch("curses.curs_set"), \
         mock.patch("curses.start_color"), \
         mock.patch("curses.use_default_colors"), \
         mock.patch("curses.has_colors", return_value=True), \
         mock.patch("curses.init_pair"), \
         mock.patch("curses.color_pair", side_effect=lambda x: x), \
         mock.patch("curses.doupdate"), \
         mock.patch.object(curses, "COLOR_PAIRS", 256, create=True):
        _reset_color_pairs()
        yield
        _reset_color_pairs()


class TestRenderer:
    def _make_renderer(
        self, rows: int = 50, cols: int = 200, mode: RenderMode = RenderMode.ASCII,
        force_monochrome: bool = False,
    ) -> Renderer:
        stdscr = _make_mock_stdscr(rows, cols)
        return Renderer(stdscr, mode, force_monochrome=force_monochrome)

    # -- Initialization --

    def test_init_dimensions(self) -> None:
        r = self._make_renderer(50, 200)
        assert r.rows == 50
        assert r.cols == 200

    def test_init_has_colors(self) -> None:
        r = self._make_renderer()
        assert r.has_colors is True

    def test_init_monochrome_fallback(self) -> None:
        r = self._make_renderer(force_monochrome=True)
        assert r.has_colors is False

    def test_render_mode_default(self) -> None:
        r = self._make_renderer()
        assert r.render_mode == RenderMode.ASCII

    def test_render_mode_setter(self) -> None:
        r = self._make_renderer()
        r.render_mode = RenderMode.BRAILLE
        assert r.render_mode == RenderMode.BRAILLE

    # -- Double-buffering --

    def test_double_buffering_swap(self) -> None:
        """Verify buffers are swapped after render_frame."""
        r = self._make_renderer(20, 20)
        front_before = id(r._front)
        back_before = id(r._back)
        r.render_frame([])
        assert id(r._front) == back_before
        assert id(r._back) == front_before

    def test_empty_projection_no_crash(self) -> None:
        r = self._make_renderer()
        changes = r.render_frame([])
        # First frame: may have changes if front was non-empty, or 0 if both blank
        assert isinstance(changes, int)

    # -- Dirty region tracking --

    def test_dirty_region_second_frame_identical(self) -> None:
        """Second identical frame should produce zero changes."""
        r = self._make_renderer(20, 20)
        pts = [ProjectionPoint(x=5, y=5, terrain=TERRAIN_LAND, shading=0.5)]
        r.render_frame(pts)
        # Same projection again
        changes = r.render_frame(pts)
        assert changes == 0

    def test_dirty_region_detects_change(self) -> None:
        """A changed projection point should be detected."""
        r = self._make_renderer(20, 20)
        pts1 = [ProjectionPoint(x=5, y=5, terrain=TERRAIN_LAND, shading=0.5)]
        r.render_frame(pts1)

        pts2 = [ProjectionPoint(x=5, y=5, terrain=TERRAIN_OCEAN, shading=0.5)]
        changes = r.render_frame(pts2)
        assert changes > 0

    def test_dirty_region_moved_point(self) -> None:
        """Moving a projection point should cause changes at old and new positions."""
        r = self._make_renderer(20, 20)
        pts1 = [ProjectionPoint(x=5, y=5, terrain=TERRAIN_LAND, shading=0.5)]
        r.render_frame(pts1)

        pts2 = [ProjectionPoint(x=10, y=10, terrain=TERRAIN_LAND, shading=0.5)]
        changes = r.render_frame(pts2)
        # At least 2 changes: old position cleared, new position written
        assert changes >= 2

    # -- Projection rendering --

    def test_projection_out_of_bounds_ignored(self) -> None:
        """Points outside the terminal area should not crash."""
        r = self._make_renderer(20, 20)
        pts = [
            ProjectionPoint(x=-1, y=-1, terrain=TERRAIN_LAND, shading=0.5),
            ProjectionPoint(x=100, y=100, terrain=TERRAIN_LAND, shading=0.5),
        ]
        changes = r.render_frame(pts)
        assert isinstance(changes, int)

    def test_character_from_theme(self) -> None:
        """Theme provides a char palette that is used in rendering."""
        theme = mock.MagicMock()
        theme.get_char_palette.return_value = {
            TERRAIN_LAND: "AB",
            TERRAIN_OCEAN: "CD",
        }
        theme.get_terrain_colors.return_value = DEFAULT_TERRAIN_COLORS

        r = self._make_renderer(20, 20)
        pts = [ProjectionPoint(x=5, y=5, terrain=TERRAIN_LAND, shading=1.0)]
        r.render_frame(pts, theme=theme)

        # Inspect the front buffer (after swap, front holds the just-rendered frame)
        cell = r._front[5][5]
        assert cell.char == "B"  # shading=1.0 picks last char in "AB"

    # -- Globe centering --

    def test_globe_centered(self) -> None:
        """Globe params should be centered in the terminal."""
        r = self._make_renderer(50, 200)
        cy, cx, radius = r.compute_globe_params()
        assert cy == 25  # rows // 2
        assert cx == 100  # cols // 2
        assert radius > 0

    def test_globe_aspect_ratio(self) -> None:
        """Radius should account for character aspect ratio."""
        r = self._make_renderer(50, 200)
        cy, cx, radius = r.compute_globe_params(aspect_ratio=2.0)
        # max_radius_y = 24, max_radius_x = int(99 / 2) = 49
        # radius = min(24, 49) = 24
        assert radius == 24

    # -- Size warning --

    def test_small_terminal_warning(self) -> None:
        r = self._make_renderer(5, 10)
        assert r.is_terminal_too_small() is True

    def test_adequate_terminal_no_warning(self) -> None:
        r = self._make_renderer(50, 200)
        assert r.is_terminal_too_small() is False

    def test_render_frame_small_terminal_shows_warning(self) -> None:
        r = self._make_renderer(5, 10)
        changes = r.render_frame([])
        # Should have written the warning text
        assert changes > 0

    # -- Resize handling --

    def test_handle_resize(self) -> None:
        stdscr = _make_mock_stdscr(50, 200)
        r = Renderer(stdscr, RenderMode.ASCII)
        # Simulate terminal resize
        stdscr.getmaxyx.return_value = (30, 100)
        with mock.patch("curses.update_lines_cols"):
            r.handle_resize()
        assert r.rows == 30
        assert r.cols == 100

    # -- Monochrome fallback --

    def test_monochrome_no_color_attrs(self) -> None:
        """In monochrome mode, cells should have attrs=0 (no color)."""
        r = self._make_renderer(20, 20, force_monochrome=True)
        pts = [ProjectionPoint(x=5, y=5, terrain=TERRAIN_LAND, shading=0.5)]
        r.render_frame(pts)
        cell = r._front[5][5]
        assert cell.attrs == 0

    # -- Rendering modes --

    def test_all_modes_can_render(self) -> None:
        for mode in RenderMode:
            r = self._make_renderer(20, 20, mode=mode)
            pts = [ProjectionPoint(x=5, y=5, terrain=TERRAIN_LAND, shading=0.5)]
            changes = r.render_frame(pts)
            assert isinstance(changes, int)

    # -- Clear --

    def test_clear_resets_buffers(self) -> None:
        r = self._make_renderer(20, 20)
        pts = [ProjectionPoint(x=5, y=5, terrain=TERRAIN_LAND, shading=0.5)]
        r.render_frame(pts)
        r.clear()
        # After clear, all cells should be blank
        for row in r._front:
            for cell in row:
                assert cell == Cell()


# ---------------------------------------------------------------------------
# RenderMode enum
# ---------------------------------------------------------------------------

class TestRenderMode:
    def test_values(self) -> None:
        assert RenderMode.ASCII.value == "ascii"
        assert RenderMode.UNICODE_BLOCK.value == "unicode_block"
        assert RenderMode.BRAILLE.value == "braille"

    def test_all_modes(self) -> None:
        modes = list(RenderMode)
        assert len(modes) == 3
