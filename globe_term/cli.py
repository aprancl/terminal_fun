"""CLI argument parsing and entry point.

Sets up the curses display loop and integrates the globe projection,
map data lookup, renderer, and geography theme to display a static
Earth globe in the terminal.
"""

from __future__ import annotations

import argparse
import curses
import math
import sys
import time
from dataclasses import dataclass
from typing import Any, List, Optional, Sequence

from globe_term import __version__
from globe_term.globe import Globe, IDLE_THRESHOLD
from globe_term.map_data import TerrainType, get_terrain
from globe_term.renderer import (
    ProjectionPoint,
    RenderMode,
    Renderer,
    TERRAIN_BORDER,
    TERRAIN_EMPTY,
    TERRAIN_ICE,
    TERRAIN_LAND,
    TERRAIN_OCEAN,
)
from globe_term.themes import get_theme, list_themes
from globe_term.input import Action, InputHandler
from globe_term.utils import (
    ResizeDebouncer,
    detect_color_count,
    detect_color_support,
    detect_mouse_support,
    detect_unicode_support,
    is_terminal,
)


# ---------------------------------------------------------------------------
# CLI configuration dataclass
# ---------------------------------------------------------------------------

VALID_SIZES = ("small", "medium", "large", "auto")

# Zoom multipliers for each size option.  "auto" defers to the default
# Globe zoom of 1.0, while explicit sizes scale the globe relative to the
# terminal window.
SIZE_ZOOM_MAP = {
    "small": 0.5,
    "medium": 0.75,
    "large": 1.0,
    "auto": 1.0,
}


@dataclass
class CLIConfig:
    """Parsed CLI configuration passed to the display loop."""

    speed: float = 1.0
    theme: str = "geography"
    no_color: bool = False
    size: str = "auto"


# ---------------------------------------------------------------------------
# Drag-to-rotate mapping
# ---------------------------------------------------------------------------

# Default sensitivity: how many radians of rotation per terminal cell of drag.
# A value of 0.01 gives smooth, controllable rotation.
DEFAULT_DRAG_SENSITIVITY = 0.01

# Maximum rotation delta per drag event (radians).  Prevents disorienting
# spins when the user moves the mouse very quickly.
MAX_ROTATION_SPEED = 0.15  # ~8.6 degrees per event

# ---------------------------------------------------------------------------
# Scroll-to-zoom mapping
# ---------------------------------------------------------------------------

# Zoom delta applied per scroll event.  A small value yields smooth,
# incremental zoom steps while still feeling responsive.
SCROLL_ZOOM_STEP = 0.1

# ---------------------------------------------------------------------------
# Frame timing
# ---------------------------------------------------------------------------

# Target frame rate for the render loop.
TARGET_FPS = 30
# Target frame duration (seconds).
TARGET_FRAME_TIME = 1.0 / TARGET_FPS


class DragRotator:
    """Maps mouse drag deltas to globe rotation angles.

    Converts terminal-cell drag distances (dx, dy) into rotation angles
    (radians) suitable for :meth:`Globe.rotate`, applying a tunable
    sensitivity factor and capping the maximum rotation speed.

    Attributes:
        sensitivity: Radians of rotation per terminal cell of drag.
        max_speed: Maximum rotation delta per event (radians).
    """

    def __init__(
        self,
        sensitivity: float = DEFAULT_DRAG_SENSITIVITY,
        max_speed: float = MAX_ROTATION_SPEED,
    ) -> None:
        self.sensitivity = sensitivity
        self.max_speed = max_speed

    def map_drag(self, dx: int, dy: int) -> tuple[float, float]:
        """Convert drag deltas to rotation angles.

        Args:
            dx: Horizontal drag distance in terminal cells.
                Positive = rightward drag = spin globe right (positive Y rotation).
            dy: Vertical drag distance in terminal cells.
                Positive = downward drag = tilt globe down (positive X rotation).

        Returns:
            (rot_y, rot_x) rotation deltas in radians, clamped to max_speed.
        """
        # Scale drag distance to rotation angle
        rot_y = dx * self.sensitivity
        rot_x = dy * self.sensitivity

        # Clamp each axis independently
        rot_y = max(-self.max_speed, min(self.max_speed, rot_y))
        rot_x = max(-self.max_speed, min(self.max_speed, rot_x))

        return (rot_y, rot_x)


def compute_frame_sleep(frame_start: float, target: float = TARGET_FRAME_TIME) -> float:
    """Compute the sleep duration needed to hit the target frame time.

    Args:
        frame_start: Monotonic timestamp of the frame start.
        target: Desired frame duration in seconds.

    Returns:
        Seconds to sleep (>= 0).  Returns 0 when the frame already
        exceeded the target duration.
    """
    elapsed = time.monotonic() - frame_start
    remaining = target - elapsed
    return max(0.0, remaining)


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


def _validate_theme(name: str) -> str:
    """Validate the theme name against available themes.

    Returns the theme name if valid; otherwise prints available themes
    and exits with an error.
    """
    available = list_themes()
    if name not in available:
        available_str = ", ".join(available) if available else "(none)"
        print(
            f"Error: Unknown theme '{name}'. "
            f"Available themes: {available_str}",
            file=sys.stderr,
        )
        sys.exit(2)
    return name


def parse_args(argv: Optional[Sequence[str]] = None) -> CLIConfig:
    """Parse CLI arguments and return a :class:`CLIConfig`.

    Parameters
    ----------
    argv : sequence of str or None
        Command-line arguments to parse.  When ``None``, reads from
        ``sys.argv[1:]`` (the default argparse behavior).

    Returns
    -------
    CLIConfig
        Validated configuration ready for the display loop.
    """
    parser = argparse.ArgumentParser(
        prog="globe_term",
        description="An interactive ASCII globe rendered in the terminal.",
    )

    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        metavar="SPEED",
        help="Auto-rotation speed multiplier (default: 1.0)",
    )
    parser.add_argument(
        "--theme",
        type=str,
        default="geography",
        metavar="NAME",
        help="Visual theme name (default: geography)",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        default=False,
        help="Disable color output (monochrome mode)",
    )
    parser.add_argument(
        "--size",
        type=str,
        default="auto",
        choices=VALID_SIZES,
        metavar="SIZE",
        help="Globe size: small, medium, large, or auto (default: auto)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    args = parser.parse_args(argv)

    # Validate theme name
    _validate_theme(args.theme)

    # Clamp negative speed to 0
    speed = max(0.0, args.speed)

    return CLIConfig(
        speed=speed,
        theme=args.theme,
        no_color=args.no_color,
        size=args.size,
    )


# ---------------------------------------------------------------------------
# Terrain mapping
# ---------------------------------------------------------------------------

# Mapping from TerrainType enum to renderer terrain-type string constants.
_TERRAIN_MAP = {
    TerrainType.OCEAN: TERRAIN_OCEAN,
    TerrainType.LAND: TERRAIN_LAND,
    TerrainType.COASTLINE: TERRAIN_BORDER,
    TerrainType.ICE: TERRAIN_ICE,
}


class _ThemeAdapter:
    """Adapt a :class:`Theme` dataclass to the duck-typed interface
    expected by :meth:`Renderer.render_frame`.

    The renderer checks for ``get_char_palette()`` and
    ``get_terrain_colors()`` via ``hasattr``.  This adapter provides
    those methods by reading fields from the underlying Theme dataclass.
    """

    def __init__(self, theme: Any) -> None:
        self._theme = theme

    def get_terrain_colors(self) -> dict[str, tuple[int, int]]:
        """Return a terrain-type -> (fg, bg) mapping derived from the theme."""
        t = self._theme
        return {
            TERRAIN_OCEAN: (t.ocean_fg, t.ocean_bg),
            TERRAIN_LAND: (t.land_fg, t.land_bg),
            TERRAIN_BORDER: (t.border_fg, t.land_bg),
            TERRAIN_ICE: (7, 0),  # white on black
            TERRAIN_EMPTY: (-1, -1),
        }

    def get_char_palette(self, render_mode: RenderMode) -> dict[str, str] | None:
        """Return a custom character palette or ``None`` for defaults."""
        t = self._theme
        if render_mode == RenderMode.ASCII:
            return {
                TERRAIN_OCEAN: t.shading_chars,
                TERRAIN_LAND: t.shading_chars,
                TERRAIN_BORDER: t.shading_chars,
                TERRAIN_ICE: t.shading_chars,
                TERRAIN_EMPTY: t.background_char,
            }
        # For Unicode/Braille modes, fall back to the default palettes.
        return None


def _build_projection(
    globe: Globe, width: int, height: int
) -> List[ProjectionPoint]:
    """Project the globe and convert each cell into a :class:`ProjectionPoint`.

    For every screen cell that falls on the sphere, look up the terrain
    from the map data and pack the result into the list consumed by
    :meth:`Renderer.render_frame`.
    """
    raw = globe.project(width, height)
    points: List[ProjectionPoint] = []

    for row_idx, row in enumerate(raw):
        for col_idx, cell in enumerate(row):
            if cell is None:
                # Outside the sphere -> skip (background)
                continue

            lat, lon, shade = cell
            terrain_type = get_terrain(lat, lon)
            terrain_str = _TERRAIN_MAP.get(terrain_type, TERRAIN_EMPTY)

            points.append(
                ProjectionPoint(
                    x=col_idx,
                    y=row_idx,
                    terrain=terrain_str,
                    shading=shade,
                )
            )

    return points


def _choose_render_mode() -> RenderMode:
    """Select the best render mode based on terminal capabilities."""
    if detect_unicode_support():
        return RenderMode.UNICODE_BLOCK
    return RenderMode.ASCII


def _handle_resize(
    renderer: Renderer,
    globe: Globe,
    adapter: _ThemeAdapter,
) -> None:
    """Handle a terminal resize: reallocate buffers and re-render.

    This is extracted as a helper so it can be invoked both from the
    ``KEY_RESIZE`` handler and from the debouncer flush path.
    """
    renderer.handle_resize()
    width = renderer.cols
    height = renderer.rows
    points = _build_projection(globe, width, height)
    renderer.render_frame(points, adapter)


def _display_loop(stdscr: Any, config: Optional[CLIConfig] = None) -> None:
    """Main curses display loop.

    Renders a static globe and waits for the user to press ``q`` or
    send a keyboard interrupt (Ctrl+C) to exit.  Terminal resize events
    are debounced to prevent excessive re-renders during rapid resizing.

    Parameters
    ----------
    stdscr : curses window
        The curses standard screen.
    config : CLIConfig or None
        Parsed CLI configuration.  When ``None``, default settings are
        used.
    """
    if config is None:
        config = CLIConfig()

    # Determine capabilities
    has_color = detect_color_support()
    color_count = detect_color_count()
    render_mode = _choose_render_mode()
    has_mouse = detect_mouse_support()

    # --no-color overrides terminal color detection and theme colors
    force_mono = config.no_color or not has_color

    # Create renderer (handles curses setup, color init, buffers)
    renderer = Renderer(
        stdscr,
        render_mode,
        force_monochrome=force_mono,
    )

    # Determine zoom from --size
    zoom = SIZE_ZOOM_MAP.get(config.size, 1.0)

    # Create globe with a slight tilt to show continents nicely
    # Tilt ~23 degrees (like Earth's axial tilt) for a natural look
    globe = Globe(
        rotation_x=math.radians(-15),  # slight tilt downward
        rotation_y=math.radians(0),    # centered on prime meridian
        zoom=zoom,
    )

    # Auto-rotation speed multiplier (0 = disabled)
    speed = config.speed

    # Load requested theme
    theme = get_theme(config.theme)
    adapter = _ThemeAdapter(theme)

    # Resize debouncer (max one re-render per 100ms)
    debouncer = ResizeDebouncer(interval=0.1)

    # Mouse input handler and drag-to-rotate mapper
    input_handler = InputHandler(stdscr)
    drag_rotator = DragRotator()

    # Initial render
    width = renderer.cols
    height = renderer.rows
    points = _build_projection(globe, width, height)
    renderer.render_frame(points, adapter)

    # Frame timing state
    prev_frame_time = time.monotonic()

    # Event loop with frame timing: process_input -> auto_rotate_if_idle -> render -> sleep
    try:
        while True:
            frame_start = time.monotonic()
            dt = frame_start - prev_frame_time
            prev_frame_time = frame_start

            needs_redraw = False

            # --- Process all pending input events for this frame ---
            try:
                key = stdscr.getch()
            except curses.error:
                key = -1

            if key == ord("q") or key == ord("Q"):
                break

            if key == curses.KEY_RESIZE:
                if debouncer.should_handle():
                    _handle_resize(renderer, globe, adapter)

            # Process mouse input events
            event = input_handler.process_event(key)
            if event is not None:
                if event.action in (Action.DRAG_START, Action.DRAG_MOVE):
                    rot_y, rot_x = drag_rotator.map_drag(event.dx, event.dy)
                    globe.rotate(rot_y, rot_x)
                    needs_redraw = True

                elif event.action == Action.SCROLL_UP:
                    globe.adjust_zoom(SCROLL_ZOOM_STEP)
                    needs_redraw = True

                elif event.action == Action.SCROLL_DOWN:
                    globe.adjust_zoom(-SCROLL_ZOOM_STEP)
                    needs_redraw = True

            # --- Auto-rotate when idle ---
            if input_handler.idle_seconds() >= IDLE_THRESHOLD and speed > 0.0:
                globe.auto_rotate(dt, speed)
                needs_redraw = True

            # --- Render if state changed ---
            if needs_redraw:
                width = renderer.cols
                height = renderer.rows
                points = _build_projection(globe, width, height)
                renderer.render_frame(points, adapter)

            # Flush any pending debounced resize
            if debouncer.flush():
                _handle_resize(renderer, globe, adapter)

            # --- Frame timing: sleep for remainder to hit target FPS ---
            elapsed = time.monotonic() - frame_start
            sleep_time = TARGET_FRAME_TIME - elapsed
            if sleep_time > 0.001:
                time.sleep(sleep_time)
    finally:
        # Restore terminal mouse tracking state
        input_handler.disable_mouse()


def main(argv: Optional[Sequence[str]] = None) -> None:
    """Main entry point for globe_term.

    Parses CLI arguments, detects terminal capabilities, then launches
    the curses display loop with the resulting configuration.  Uses
    ``curses.wrapper`` for safe initialization and cleanup of the
    terminal, ensuring the terminal is restored to its normal state
    even if an exception occurs.

    When stdout is not a terminal (e.g. piped output), prints an error
    message and exits with code 1.

    Parameters
    ----------
    argv : sequence of str or None
        Command-line arguments.  When ``None``, reads from ``sys.argv``.
    """
    config = parse_args(argv)

    # Check for pipe / non-terminal — cannot run curses in a pipe
    if not is_terminal():
        print(
            "Error: globe_term requires an interactive terminal. "
            "Output appears to be piped or redirected.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Informational: warn if mouse not supported
    if not detect_mouse_support():
        print(
            "Note: Mouse support not detected; "
            "drag-to-rotate will not be available.",
            file=sys.stderr,
        )

    try:
        curses.wrapper(lambda stdscr: _display_loop(stdscr, config))
    except KeyboardInterrupt:
        pass  # Clean exit on Ctrl-C
