"""ASCII rendering engine, double-buffering, screen output.

This module manages:
- A 2D character buffer (front buffer + back buffer) for double-buffering
- Converting projected globe data + theme into characters with colors
- Dirty-region tracking: comparing buffers to find changed cells
- Flushing only changed characters to the terminal via curses
- Supporting multiple rendering modes: ASCII-only, Unicode blocks, Braille characters
- Applying ANSI colors from the active theme
"""

from __future__ import annotations

import curses
import enum
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

class RenderMode(enum.Enum):
    """Supported rendering modes."""
    ASCII = "ascii"
    UNICODE_BLOCK = "unicode_block"
    BRAILLE = "braille"


@dataclass(frozen=True)
class Cell:
    """A single terminal cell with character and color attributes.

    Attributes:
        char: The character to display (single character string).
        fg_color: Foreground color index (curses color pair number component).
        bg_color: Background color index (curses color pair number component).
        attrs: Extra curses attributes (e.g. ``curses.A_BOLD``).
    """
    char: str = " "
    fg_color: int = -1   # -1 means default terminal color
    bg_color: int = -1
    attrs: int = 0


# Terrain type constants used in projection data.
TERRAIN_OCEAN = "ocean"
TERRAIN_LAND = "land"
TERRAIN_BORDER = "border"
TERRAIN_ICE = "ice"
TERRAIN_EMPTY = "empty"  # outside globe circle

# Default character palettes keyed by render mode then terrain type.
# Each palette maps terrain type -> sequence of chars ordered from dark to light.
DEFAULT_CHAR_PALETTES: Dict[RenderMode, Dict[str, str]] = {
    RenderMode.ASCII: {
        TERRAIN_OCEAN: " .:-~",
        TERRAIN_LAND:  ".:-=+*#%@",
        TERRAIN_BORDER: "#@",
        TERRAIN_ICE:   ".:+*",
        TERRAIN_EMPTY: " ",
    },
    RenderMode.UNICODE_BLOCK: {
        TERRAIN_OCEAN:  " \u2591\u2592\u2593\u2588",
        TERRAIN_LAND:   "\u2591\u2592\u2593\u2588",
        TERRAIN_BORDER: "\u2588",
        TERRAIN_ICE:    "\u2591\u2592\u2593",
        TERRAIN_EMPTY:  " ",
    },
    RenderMode.BRAILLE: {
        TERRAIN_OCEAN:  " \u2801\u2803\u2807\u281f\u283f\u287f\u28ff",
        TERRAIN_LAND:   "\u2801\u2803\u2807\u280f\u281f\u283f\u287f\u28ff",
        TERRAIN_BORDER: "\u28ff",
        TERRAIN_ICE:    "\u2801\u2803\u2807\u281f",
        TERRAIN_EMPTY:  " ",
    },
}

# Default colors by terrain type: (fg, bg) using curses color constants.
DEFAULT_TERRAIN_COLORS: Dict[str, Tuple[int, int]] = {
    TERRAIN_OCEAN:  (curses.COLOR_CYAN, curses.COLOR_BLUE),
    TERRAIN_LAND:   (curses.COLOR_GREEN, curses.COLOR_BLACK),
    TERRAIN_BORDER: (curses.COLOR_YELLOW, curses.COLOR_BLACK),
    TERRAIN_ICE:    (curses.COLOR_WHITE, curses.COLOR_WHITE),
    TERRAIN_EMPTY:  (-1, -1),
}


# ---------------------------------------------------------------------------
# Projection point protocol / data
# ---------------------------------------------------------------------------

@dataclass
class ProjectionPoint:
    """A single point in a 2D projection of the globe.

    Attributes:
        x: Screen column.
        y: Screen row.
        terrain: Terrain type string (one of the TERRAIN_* constants).
        shading: Shading value in [0.0, 1.0] where 0 is dark and 1 is bright.
    """
    x: int = 0
    y: int = 0
    terrain: str = TERRAIN_EMPTY
    shading: float = 0.5


# ---------------------------------------------------------------------------
# Character selection
# ---------------------------------------------------------------------------

def select_character(
    terrain: str,
    shading: float,
    char_palette: Optional[Dict[str, str]] = None,
    render_mode: RenderMode = RenderMode.ASCII,
) -> str:
    """Choose a character for a terrain type and shading value.

    Args:
        terrain: One of the ``TERRAIN_*`` constants.
        shading: Value in [0.0, 1.0] controlling which character in the
            palette is selected (0 = darkest, 1 = brightest).
        char_palette: Optional override mapping terrain -> character string.
            If ``None``, uses the default palette for *render_mode*.
        render_mode: The rendering mode to select the default palette from.

    Returns:
        A single character string.
    """
    if char_palette is None:
        char_palette = DEFAULT_CHAR_PALETTES.get(render_mode, DEFAULT_CHAR_PALETTES[RenderMode.ASCII])

    chars = char_palette.get(terrain, " ")
    if not chars:
        return " "

    # Clamp shading to [0, 1]
    shading = max(0.0, min(1.0, shading))
    idx = int(shading * (len(chars) - 1))
    idx = max(0, min(idx, len(chars) - 1))
    return chars[idx]


# ---------------------------------------------------------------------------
# Color pair management
# ---------------------------------------------------------------------------

_color_pair_cache: Dict[Tuple[int, int], int] = {}
_next_pair_id: int = 1


def _reset_color_pairs() -> None:
    """Reset the colour-pair cache (useful for tests or re-init)."""
    global _next_pair_id
    _color_pair_cache.clear()
    _next_pair_id = 1


def get_color_pair(fg: int, bg: int, has_colors: bool = True) -> int:
    """Return a curses color-pair number for the given fg/bg combination.

    If the terminal does not support colors (*has_colors* is ``False``), returns
    0 (the default pair).

    Color pairs are lazily initialized and cached.
    """
    if not has_colors:
        return 0

    key = (fg, bg)
    if key in _color_pair_cache:
        return _color_pair_cache[key]

    global _next_pair_id
    pair_id = _next_pair_id

    # curses supports a limited number of color pairs. Pair 0 is reserved.
    max_pairs = curses.COLOR_PAIRS if hasattr(curses, "COLOR_PAIRS") else 256
    if pair_id >= max_pairs:
        # Reuse pair 0 (default) when we run out
        return 0

    try:
        curses.init_pair(pair_id, fg, bg)
    except curses.error:
        return 0

    _color_pair_cache[key] = pair_id
    _next_pair_id += 1
    return pair_id


# ---------------------------------------------------------------------------
# Buffer helpers
# ---------------------------------------------------------------------------

def diff_buffers(
    front: List[List[Cell]],
    back: List[List[Cell]],
) -> List[Tuple[int, int, Cell]]:
    """Compare *front* and *back* buffers and return a list of changed cells.

    Each entry in the result is ``(row, col, new_cell)`` where *new_cell*
    comes from the *back* buffer.

    If the buffers have different dimensions the comparison is performed over
    the overlapping region.
    """
    changes: List[Tuple[int, int, Cell]] = []
    rows = min(len(front), len(back))
    for r in range(rows):
        cols = min(len(front[r]), len(back[r]))
        for c in range(cols):
            if front[r][c] != back[r][c]:
                changes.append((r, c, back[r][c]))
    return changes


def make_buffer(rows: int, cols: int, fill: Cell | None = None) -> List[List[Cell]]:
    """Create a 2D buffer of *rows* x *cols* filled with *fill* (default blank)."""
    if fill is None:
        fill = Cell()
    return [[fill for _ in range(cols)] for _ in range(rows)]


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------

# Minimum terminal size to render a useful globe.
MIN_TERM_COLS = 20
MIN_TERM_ROWS = 10
SIZE_WARNING = "Terminal too small!"


class Renderer:
    """Curses-based rendering engine with double-buffering.

    The renderer manages two equally-sized character buffers (*front* and
    *back*).  Each frame is written into the back buffer, then diffed
    against the front buffer; only the changed cells are flushed to the
    curses window.  After the flush the buffers are swapped.

    Usage (inside a curses wrapper)::

        def main(stdscr):
            renderer = Renderer(stdscr)
            while True:
                renderer.render_frame(projection_points, theme)
    """

    def __init__(
        self,
        stdscr: Any,
        render_mode: RenderMode = RenderMode.ASCII,
        *,
        force_monochrome: bool = False,
    ) -> None:
        self._stdscr = stdscr
        self._render_mode = render_mode
        self._force_monochrome = force_monochrome

        # Terminal capability detection
        self._has_colors: bool = False
        self._setup_curses()

        # Buffer dimensions match the current terminal size.
        self._rows: int = 0
        self._cols: int = 0
        self._front: List[List[Cell]] = []
        self._back: List[List[Cell]] = []
        self._resize_buffers()

    # -- Initialization helpers ------------------------------------------------

    def _setup_curses(self) -> None:
        """Configure the curses screen for rendering."""
        try:
            curses.curs_set(0)  # hide cursor
        except curses.error:
            pass  # some terminals don't support cursor visibility

        self._stdscr.nodelay(True)   # non-blocking getch
        self._stdscr.keypad(True)

        if not self._force_monochrome:
            try:
                curses.start_color()
                curses.use_default_colors()
                self._has_colors = curses.has_colors()
            except curses.error:
                self._has_colors = False
        else:
            self._has_colors = False

        _reset_color_pairs()

    def _resize_buffers(self) -> None:
        """Re-create buffers to match the current terminal size."""
        try:
            max_y, max_x = self._stdscr.getmaxyx()
        except curses.error:
            max_y, max_x = 24, 80

        self._rows = max_y
        self._cols = max_x
        self._front = make_buffer(self._rows, self._cols)
        self._back = make_buffer(self._rows, self._cols)

    # -- Properties ------------------------------------------------------------

    @property
    def rows(self) -> int:
        """Number of rows in the current terminal."""
        return self._rows

    @property
    def cols(self) -> int:
        """Number of columns in the current terminal."""
        return self._cols

    @property
    def has_colors(self) -> bool:
        """Whether the terminal supports colors."""
        return self._has_colors

    @property
    def render_mode(self) -> RenderMode:
        """The current rendering mode."""
        return self._render_mode

    @render_mode.setter
    def render_mode(self, mode: RenderMode) -> None:
        self._render_mode = mode

    # -- Globe geometry helpers -----------------------------------------------

    def compute_globe_params(
        self,
        aspect_ratio: float = 2.0,
    ) -> Tuple[int, int, int]:
        """Compute globe centre and radius for the current terminal size.

        Terminal characters are typically ~2x taller than wide, so the
        *aspect_ratio* parameter (default 2.0) compensates by stretching
        the horizontal axis.

        Returns:
            ``(center_y, center_x, radius)`` in terminal coordinates.
        """
        center_y = self._rows // 2
        center_x = self._cols // 2

        # Radius limited by whichever axis is smaller, accounting for the
        # character aspect ratio.
        max_radius_y = (self._rows // 2) - 1
        max_radius_x = int(((self._cols // 2) - 1) / aspect_ratio)
        radius = max(1, min(max_radius_y, max_radius_x))

        return center_y, center_x, radius

    # -- Frame rendering -------------------------------------------------------

    def render_frame(
        self,
        projection: Sequence[ProjectionPoint],
        theme: Any = None,
    ) -> int:
        """Render a full frame from projection data.

        The *projection* is a sequence of :class:`ProjectionPoint` instances
        describing each visible point on the globe.  The *theme* is an
        optional theme object providing ``get_char_palette()`` and
        ``get_terrain_colors()`` methods.  When *theme* is ``None``, default
        palettes and colours are used.

        Returns:
            The number of cells flushed (changed) in this frame.
        """
        # Check for terminal resize
        try:
            max_y, max_x = self._stdscr.getmaxyx()
        except curses.error:
            max_y, max_x = self._rows, self._cols

        if max_y != self._rows or max_x != self._cols:
            self._resize_buffers()

        # Handle very small terminal
        if self._rows < MIN_TERM_ROWS or self._cols < MIN_TERM_COLS:
            return self._render_size_warning()

        # Clear back buffer
        blank = Cell()
        for r in range(self._rows):
            for c in range(self._cols):
                self._back[r][c] = blank

        # Resolve palette / colours from theme
        char_palette = None
        terrain_colors = DEFAULT_TERRAIN_COLORS

        if theme is not None:
            if hasattr(theme, "get_char_palette"):
                char_palette = theme.get_char_palette(self._render_mode)
            if hasattr(theme, "get_terrain_colors"):
                terrain_colors = theme.get_terrain_colors()

        # Write projection points into back buffer
        for pt in projection:
            if pt.y < 0 or pt.y >= self._rows or pt.x < 0 or pt.x >= self._cols:
                continue

            ch = select_character(
                pt.terrain, pt.shading,
                char_palette=char_palette,
                render_mode=self._render_mode,
            )

            fg, bg = terrain_colors.get(pt.terrain, (-1, -1))
            pair_num = get_color_pair(fg, bg, self._has_colors)
            attrs = curses.color_pair(pair_num) if self._has_colors and pair_num else 0

            self._back[pt.y][pt.x] = Cell(
                char=ch,
                fg_color=fg,
                bg_color=bg,
                attrs=attrs,
            )

        # Diff and flush
        changes = diff_buffers(self._front, self._back)
        self._flush_changes(changes)

        # Swap buffers
        self._front, self._back = self._back, self._front

        return len(changes)

    def _render_size_warning(self) -> int:
        """Display a size warning when the terminal is too small."""
        blank = Cell()
        for r in range(self._rows):
            for c in range(self._cols):
                self._back[r][c] = blank

        msg = SIZE_WARNING
        if self._cols < len(msg):
            msg = msg[:self._cols]

        row = self._rows // 2
        col = max(0, (self._cols - len(msg)) // 2)
        for i, ch in enumerate(msg):
            if col + i < self._cols:
                self._back[row][col + i] = Cell(char=ch)

        changes = diff_buffers(self._front, self._back)
        self._flush_changes(changes)
        self._front, self._back = self._back, self._front
        return len(changes)

    # -- Terminal output -------------------------------------------------------

    def _flush_changes(self, changes: List[Tuple[int, int, Cell]]) -> None:
        """Write only the changed cells to the curses window."""
        for row, col, cell in changes:
            try:
                # curses raises an error when writing to the last cell of the
                # last row, so we guard with a try/except.
                if row >= self._rows or col >= self._cols:
                    continue
                # addstr at the very last position (bottom-right) can raise
                # an error in curses; use addch with insstr fallback.
                self._stdscr.addstr(row, col, cell.char, cell.attrs)
            except curses.error:
                # Silently skip cells that curses cannot write (e.g. bottom-
                # right corner).
                pass

        try:
            self._stdscr.noutrefresh()
            curses.doupdate()
        except curses.error:
            pass

    # -- Public helpers -------------------------------------------------------

    def clear(self) -> None:
        """Clear both buffers and the screen."""
        self._front = make_buffer(self._rows, self._cols)
        self._back = make_buffer(self._rows, self._cols)
        try:
            self._stdscr.clear()
            self._stdscr.noutrefresh()
            curses.doupdate()
        except curses.error:
            pass

    def handle_resize(self) -> None:
        """Call after receiving a ``curses.KEY_RESIZE`` event."""
        try:
            curses.update_lines_cols()
        except (curses.error, AttributeError):
            pass
        self._resize_buffers()
        self.clear()

    def is_terminal_too_small(self) -> bool:
        """Return ``True`` when the terminal is below minimum usable size."""
        return self._rows < MIN_TERM_ROWS or self._cols < MIN_TERM_COLS


# ---------------------------------------------------------------------------
# Convenience wrapper for safe curses initialisation / teardown
# ---------------------------------------------------------------------------

def run_with_curses(func: Any, render_mode: RenderMode = RenderMode.ASCII,
                    force_monochrome: bool = False) -> None:
    """Run *func(renderer)* inside a safely managed curses session.

    This ensures clean teardown even when an exception is raised, preventing
    garbled terminal output.
    """
    stdscr = None
    try:
        stdscr = curses.initscr()
        curses.noecho()
        curses.cbreak()
        stdscr.keypad(True)

        renderer = Renderer(stdscr, render_mode, force_monochrome=force_monochrome)
        func(renderer)
    except KeyboardInterrupt:
        pass  # clean exit on Ctrl-C
    except curses.error:
        pass  # curses setup/teardown issue
    finally:
        if stdscr is not None:
            try:
                stdscr.keypad(False)
            except curses.error:
                pass
            try:
                curses.nocbreak()
            except curses.error:
                pass
            try:
                curses.echo()
            except curses.error:
                pass
            try:
                curses.endwin()
            except curses.error:
                pass
