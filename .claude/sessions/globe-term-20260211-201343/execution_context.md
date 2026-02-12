# Execution Context

## Project Patterns
- Python package with `globe_term/` directory structure
- Build system: hatchling via uv
- No external runtime dependencies -- standard library only (curses, argparse)
- pytest is dev dependency
- Tests go in `tests/` directory with `test_` prefix, class-based organization
- Type hints with `from __future__ import annotations` for 3.9+ compat
- Frozen dataclasses for immutable data (Cell, Theme, InputEvent, CLIConfig)
- Mock curses with unittest.mock.patch for terminal-dependent code
- _ThemeAdapter bridges frozen Theme dataclass to renderer duck-typed interface
- CLI pipeline: Globe -> project() -> get_terrain() -> ProjectionPoint list -> Renderer.render_frame()

## Key Decisions
- Console script: `globe_term = "globe_term.cli:main"`
- Orthographic projection with inverse ray-sphere intersection
- Aspect ratio correction: horizontal / 2.0
- RenderMode enum: ASCII, UNICODE_BLOCK, BRAILLE
- TerrainType enum: OCEAN=0, LAND=1, COASTLINE=2, ICE=3
- ThemeRegistry: lazy auto-discovery, pkgutil.iter_modules + importlib
- CLIConfig dataclass holds all parsed args (speed, theme, no_color, size)
- SIZE_ZOOM_MAP: small=0.5, medium=0.75, large=1.2, auto=1.0
- InputHandler: Action enum (DRAG_START, DRAG_MOVE, DRAG_END, SCROLL_UP, SCROLL_DOWN, CLICK)
- ResizeDebouncer: 100ms debounce interval for SIGWINCH
- Matrix theme: green(2) for land, cyan(6) for ocean, digital chars "0~/|"

## Known Issues
- `from __future__ import annotations` needs `_resolve_type()` helper for runtime type checking
- curses color_pair cache uses global state; needs `_reset_color_pairs()` between tests
- _ThemeAdapter bridges Theme dataclass to renderer duck-typed interface (no direct methods)
- TerrainType→TERRAIN_* mapping needed via _TERRAIN_MAP dict

## File Map
- `pyproject.toml` - Project metadata, entry points, build config, pytest dev dep
- `globe_term/__init__.py` - Package root, __version__ = "0.1.0"
- `globe_term/__main__.py` - `python -m globe_term` entry
- `globe_term/cli.py` - CLIConfig, parse_args(), _ThemeAdapter, _build_projection(), _display_loop(), main()
- `globe_term/globe.py` - Globe class, rotation matrices, orthographic projection, shading
- `globe_term/renderer.py` - Cell, RenderMode, ProjectionPoint, Renderer class, buffer diffing, curses wrapper
- `globe_term/map_data.py` - TerrainType enum, compressed bitmap, get_terrain(), get_raw_grid()
- `globe_term/themes/__init__.py` - ThemeRegistry class, get_theme/list_themes
- `globe_term/themes/base.py` - Theme dataclass (15 fields, frozen)
- `globe_term/themes/geography.py` - GEOGRAPHY_THEME
- `globe_term/themes/matrix.py` - MATRIX_THEME (green-on-black)
- `globe_term/input.py` - InputHandler, InputEvent, Action enum
- `globe_term/utils.py` - detect_unicode/color/mouse_support, get_terminal_size, is_terminal, ResizeDebouncer

## Task History
### Tasks [1-5]: Foundation — PASS (all)
### Task [6]: Display loop — PASS
### Task [7]: Mouse input handling — PASS (36 tests)
### Task [11]: Theme registry — PASS (40 tests)
### Task [12]: Matrix theme — PASS (18 new tests)
### Task [13]: Full CLI — PASS (36 new tests, CLIConfig, parse_args, theme validation)
### Task [14]: Resize + degradation — PASS (28 new tests, ResizeDebouncer, detect_color_count, is_terminal)
