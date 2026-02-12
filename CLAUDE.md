# CLAUDE.md

## Project Overview
globe_term — An interactive ASCII globe rendered in the terminal with mouse-driven rotation and zoom.

## Tech Stack
- Python 3.9+ (standard library only — no external runtime dependencies)
- curses for terminal rendering
- argparse for CLI
- uv for dependency management and virtual environments
- hatchling build backend

## Project Structure
```
globe_term/
  __init__.py       # Package root, __version__
  __main__.py       # python -m globe_term entry
  cli.py            # CLIConfig, parse_args, display loop, DragRotator, ThemeAdapter
  globe.py          # Globe class, rotation, orthographic projection, shading, auto-rotation
  renderer.py       # Cell, RenderMode, ProjectionPoint, Renderer, buffer diffing
  map_data.py       # TerrainType enum, embedded 360x180 map bitmap, get_terrain()
  input.py          # InputHandler, InputEvent, Action enum (drag/scroll/click)
  utils.py          # Terminal detection, ResizeDebouncer, capability checks
  themes/
    __init__.py     # ThemeRegistry, get_theme(), list_themes()
    base.py         # Theme dataclass (15 fields, frozen)
    geography.py    # GEOGRAPHY_THEME
    matrix.py       # MATRIX_THEME
```

## Commands
- `uv run python -m globe_term` — Run the globe
- `uv run python -m pytest tests/` — Run tests (402 tests)
- `uv build` — Build sdist and wheel

## Key Patterns
- Frozen dataclasses for immutable data (Cell, Theme, InputEvent, CLIConfig)
- `from __future__ import annotations` in all modules for 3.9+ compat
- _ThemeAdapter bridges Theme dataclass to renderer duck-typed interface
- Mock curses in tests via unittest.mock.patch
- Tests use pytest with class-based organization
