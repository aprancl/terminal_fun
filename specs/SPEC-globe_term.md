# globe_term PRD

**Version**: 1.0
**Author**: aprancl
**Date**: 2026-02-11
**Status**: Draft
**Spec Type**: New product
**Spec Depth**: Detailed specifications
**Description**: An interactive ASCII globe rendered in the terminal with mouse-driven rotation and zoom. A fun, visually impressive terminal art project built for developers and terminal enthusiasts.

---

## 1. Executive Summary

globe_term is a terminal-based interactive ASCII globe that renders a recognizable Earth with continents and oceans using a mix of shading characters, ANSI colors, and Unicode block/Braille elements. Users can rotate the globe with click & drag and zoom with scroll. It auto-rotates when idle, supports customizable themes, and is designed to be both a standalone CLI tool and an importable Python library.

## 2. Problem Statement

### 2.1 The Problem
Terminal art tools exist, but there's no fun, interactive ASCII globe that you can spin around with your mouse. The terminal is a canvas that deserves more creative, playful experiences.

### 2.2 Current State
Existing terminal globe projects are typically static, non-interactive, or use minimal rendering techniques. Most are novelty scripts rather than polished, installable tools with real interactivity.

### 2.3 Impact Analysis
No business impact — this is a creative project. The "cost" of not building it is simply missing out on the joy of spinning an ASCII Earth in your terminal.

### 2.4 Business Value
Pure fun and creative expression. Secondary value as a showcase of terminal rendering techniques, a portfolio piece, and a contribution to the terminal art community.

## 3. Goals & Success Metrics

### 3.1 Primary Goals
1. Render a visually impressive ASCII Earth globe in the terminal
2. Provide fluid, responsive mouse interaction (rotate and zoom)
3. Build a hackable, extensible tool that others can customize and build on

### 3.2 Success Metrics

| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| Render FPS | 30+ FPS sustained | Built-in FPS counter (debug mode) |
| Visual quality | Recognizable continents, smooth shading | Visual inspection |
| Interaction latency | < 33ms input-to-render response | Profiling |
| Extensibility | Theme API documented, importable as library | Can create new theme without modifying core code |
| Install experience | Single `pip install` command | Test on clean venv |

### 3.3 Non-Goals
- Geographic accuracy (this is art, not cartography)
- Windows support (may revisit later)
- Day/night terminator shading
- Click-to-select or hover-to-inspect regions
- Network features or data fetching

## 4. User Research

### 4.1 Target Users

#### Primary Persona: Terminal Enthusiast
- **Role/Description**: Developer or power user who spends significant time in the terminal and appreciates aesthetic CLI tools
- **Goals**: Wants fun, visually impressive terminal experiences; enjoys discovering and customizing CLI tools
- **Pain Points**: Most terminal art tools are static or low-quality; hard to find interactive terminal toys
- **Context**: Running in their daily terminal environment (iTerm2, Alacritty, kitty, GNOME Terminal, etc.)

#### Secondary Persona: Open Source Contributor
- **Role/Description**: Developer who wants to fork, customize, or extend the project
- **Goals**: Add new themes, modify rendering, use the globe engine in their own projects
- **Pain Points**: Many terminal projects have monolithic, hard-to-modify codebases

### 4.2 User Journey Map

```
[Install via pip] --> [Run `globe_term`] --> [See auto-rotating Earth] --> [Grab & drag to spin] --> [Scroll to zoom] --> [Try different themes via --theme] --> [Create own theme]
```

The initial experience should be immediate and delightful: run the command, see a beautiful spinning globe.

## 5. Functional Requirements

### 5.1 Feature: Earth Globe Rendering

**Priority**: P0 (Critical)

#### User Stories

**US-001**: As a terminal user, I want to see a recognizable Earth globe rendered in ASCII so that I can appreciate terminal art.

**Acceptance Criteria**:
- [ ] Globe renders as a 3D sphere with visible curvature
- [ ] Continents are distinguishable from oceans using different characters and/or colors
- [ ] Rendering uses a mix of shading characters (`.:-=+*#%@`), ANSI colors, and Unicode block/Braille elements
- [ ] Globe fills available terminal space while maintaining aspect ratio
- [ ] Rendering maintains 30+ FPS on a modern machine
- [ ] Map data is embedded in the source code (no external data files required)

**Edge Cases**:
- Very small terminal (< 40 cols): Render a minimal globe or display a size warning
- Very large terminal (> 300 cols): Scale up gracefully without performance degradation
- Terminal without Unicode support: Fall back to ASCII-only rendering
- Terminal without color support: Fall back to monochrome shading characters

---

### 5.2 Feature: Mouse Interaction — Rotate

**Priority**: P0 (Critical)

#### User Stories

**US-002**: As a user, I want to click and drag the globe to rotate it so that I can explore different sides of the Earth.

**Acceptance Criteria**:
- [ ] Left-click and drag rotates the globe in the direction of the drag
- [ ] Rotation feels natural and proportional to drag distance
- [ ] Globe rotation is smooth (no visible stuttering or jumping)
- [ ] Releasing the mouse stops rotation (no momentum/inertia required, but nice-to-have)
- [ ] Rotation works on both X and Y axes

**Edge Cases**:
- Dragging outside terminal window: Stop tracking, resume when mouse returns
- Very fast drag: Cap rotation speed to prevent disorienting spins
- Click without drag: No effect (don't snap or jump)

---

### 5.3 Feature: Mouse Interaction — Zoom

**Priority**: P0 (Critical)

#### User Stories

**US-003**: As a user, I want to scroll to zoom in and out of the globe so that I can see details or the full sphere.

**Acceptance Criteria**:
- [ ] Scroll up zooms in (globe gets larger / more detail)
- [ ] Scroll down zooms out (globe gets smaller / wider view)
- [ ] Zoom has reasonable min/max bounds
- [ ] Zoom level transitions are smooth
- [ ] Globe remains centered during zoom

**Edge Cases**:
- Zoom at maximum: Ignore further zoom-in scrolls
- Zoom at minimum: Ignore further zoom-out scrolls
- Rapid scrolling: Handle gracefully without lag

---

### 5.4 Feature: Auto-Rotation

**Priority**: P1 (High)

#### User Stories

**US-004**: As a user, I want the globe to slowly spin on its own when I'm not interacting with it so that it looks alive and dynamic.

**Acceptance Criteria**:
- [ ] Globe rotates slowly around Y-axis when no mouse input is detected
- [ ] Auto-rotation pauses immediately when user starts dragging
- [ ] Auto-rotation resumes after a brief idle period (e.g., 2-3 seconds after last interaction)
- [ ] Rotation speed is configurable via `--speed` CLI flag
- [ ] Default speed is visually pleasant (roughly one full rotation per 30-60 seconds)

**Edge Cases**:
- User sets speed to 0: Auto-rotation is disabled
- Very high speed value: Cap at a reasonable maximum

---

### 5.5 Feature: Customizable Themes

**Priority**: P1 (High)

#### User Stories

**US-005**: As a user, I want to switch between different visual themes so that I can personalize the globe's appearance.

**US-006**: As a contributor, I want to create new themes using a simple format so that I can share creative designs.

**Acceptance Criteria**:
- [ ] At least 2 built-in themes ship with initial release:
  - **"geography"**: Standard earth tones — blue oceans, green land, white ice caps
  - **"matrix"**: Green-on-black, digital/futuristic aesthetic
- [ ] Themes are defined in a declarative format (TOML or Python dataclass)
- [ ] Each theme specifies: color palette, character set, ocean/land/border chars, optional decorative elements
- [ ] Themes are selectable via `--theme <name>` CLI flag
- [ ] Theme system is documented so users can create their own
- [ ] Adding a new theme requires no modifications to core code

**Edge Cases**:
- Invalid theme name: Show available themes and exit with helpful error
- Theme with characters unsupported by terminal: Fall back to safe characters

**Future Theme Ideas** (not in initial release):
- "pirate" / "navy" — aged parchment look, compass rose, nautical styling
- "retro" — CRT green phosphor, scanlines
- "neon" — Bright colors, cyberpunk aesthetic

---

### 5.6 Feature: CLI Interface

**Priority**: P1 (High)

#### User Stories

**US-007**: As a user, I want to configure the globe via command-line flags so that I can customize its behavior without editing code.

**Acceptance Criteria**:
- [ ] `globe_term` command launches the globe with default settings
- [ ] `--speed <float>` sets auto-rotation speed (default: 1.0)
- [ ] `--theme <name>` selects a visual theme (default: "geography")
- [ ] `--no-color` disables color output (monochrome mode)
- [ ] `--size <small|medium|large|auto>` controls globe size (default: "auto" = fill terminal)
- [ ] `--help` shows usage information
- [ ] `--version` shows version number
- [ ] Invalid flags produce clear error messages

**Edge Cases**:
- Conflicting flags: Define precedence (e.g., `--no-color` overrides theme colors)

---

### 5.7 Feature: Responsive Terminal Resize

**Priority**: P2 (Medium)

#### User Stories

**US-008**: As a user, I want the globe to adapt when I resize my terminal window so that it always looks right.

**Acceptance Criteria**:
- [ ] Globe detects terminal resize events (SIGWINCH)
- [ ] Globe re-renders at appropriate size for new terminal dimensions
- [ ] Resize handling is smooth (no crash, no garbled output)
- [ ] Aspect ratio is maintained after resize

**Edge Cases**:
- Resize to very small terminal: Show minimum size warning or render minimal globe
- Rapid successive resizes: Debounce re-renders to avoid thrashing

## 6. Non-Functional Requirements

### 6.1 Performance
- Sustained 30+ FPS rendering during interaction and auto-rotation
- Input-to-render latency under 33ms
- CPU usage should be reasonable (not spike a core to 100% during idle auto-rotation)
- Double-buffering to prevent flicker: render to off-screen buffer, flush to terminal in one write
- Dirty-region tracking: only redraw characters that changed between frames

### 6.2 Compatibility
- Linux: All major terminal emulators (GNOME Terminal, Konsole, Alacritty, kitty, xterm, tmux, etc.)
- macOS: Terminal.app, iTerm2, Alacritty, kitty
- Python 3.9+ required
- Graceful degradation when terminal lacks Unicode or color support

### 6.3 Code Quality
- Type hints throughout
- Modular architecture (see Section 7)
- Importable as a Python library, not just a CLI tool
- Documented public API for theme creation and globe rendering

## 7. Technical Considerations

### 7.1 Architecture Overview

The project follows a modular architecture with clear separation of concerns:

```
globe_term/
  __init__.py          # Public API exports
  __main__.py          # Entry point for `python -m globe_term`
  cli.py               # CLI argument parsing and entry point
  globe.py             # 3D sphere math, rotation, projection
  renderer.py          # ASCII rendering engine, double-buffering, screen output
  map_data.py          # Embedded simplified world map data
  themes/
    __init__.py        # Theme registry and loading
    base.py            # Theme base class / dataclass definition
    geography.py       # Built-in geography theme
    matrix.py          # Built-in matrix theme
  input.py             # Mouse event handling (curses mouse events)
  utils.py             # Terminal detection, capability checking
```

**Key Design Principles**:
- **Rendering engine** is independent of globe math — could render any 3D-to-2D projected data
- **Globe math** handles sphere geometry, rotation matrices, and map-to-sphere projection
- **Theme system** is purely declarative — themes define data, not behavior
- **Input handling** translates raw terminal events into high-level actions (rotate, zoom)

### 7.2 Tech Stack
- **Language**: Python 3.9+
- **Terminal Library**: curses (standard library)
- **CLI Parsing**: argparse (standard library)
- **Build/Package**: uv for dependency management and virtual environments
- **Distribution**: PyPI (pip installable)

### 7.3 Rendering Pipeline

```
[Input Events] --> [Update Globe State (rotation, zoom)]
                          |
                          v
[Globe Math: 3D sphere --> 2D projection] --> [Apply Theme (chars, colors)]
                                                      |
                                                      v
                                          [Render to Buffer] --> [Diff with Previous Buffer]
                                                                          |
                                                                          v
                                                              [Flush Changed Chars to Terminal]
```

### 7.4 Technical Constraints
- curses does not natively support Windows — Linux and macOS only
- Terminal mouse event resolution varies (some terminals report fewer positions)
- Braille/Unicode character support depends on terminal font
- curses color support is limited to 256 colors in most terminals (some support true color via escape sequences)

## 8. Scope Definition

### 8.1 In Scope
- 3D sphere rendering with ASCII/Unicode characters and ANSI colors
- Embedded simplified Earth map data
- Click & drag rotation
- Scroll zoom
- Auto-rotation when idle
- 2 built-in themes (geography, matrix)
- Declarative theme system with documented format
- CLI with `--speed`, `--theme`, `--no-color`, `--size`, `--help`, `--version`
- Responsive terminal resize handling
- pip-installable package on PyPI
- Importable as a Python library
- uv-managed project

### 8.2 Out of Scope
- **Windows support**: curses limitation; may revisit with alternative library later
- **Day/night terminator**: Real-time sun position shading — potential future feature
- **Click-to-select regions**: Identifying and selecting countries/regions
- **Hover information**: Displaying location names or coordinates on hover
- **Network features**: Fetching real-time data, weather overlays, etc.
- **3D terrain/elevation**: Height maps or topographic rendering
- **Sound/audio**: Terminal bell or audio feedback

### 8.3 Future Considerations
- Pirate/navy theme, retro CRT theme, neon/cyberpunk theme
- Momentum/inertia after drag release
- Keyboard controls (arrow keys for rotation)
- Location markers (pin specific lat/long coordinates)
- Day/night terminator line
- Windows support via alternative terminal library
- TOML-based user theme files loadable from `~/.config/globe_term/themes/`

## 9. Implementation Plan

### 9.1 Phase 1: Foundation — Static Globe Rendering
**Completion Criteria**: A static, non-interactive Earth globe renders correctly in the terminal with embedded map data.

| Deliverable | Description | Dependencies |
|-------------|-------------|--------------|
| Project scaffolding | uv project setup, package structure, `__main__.py`, basic CLI | None |
| Sphere math module | 3D sphere geometry, rotation matrices, sphere-to-screen projection | None |
| Embedded map data | Simplified world map as embedded Python data (continent outlines) | None |
| Rendering engine | ASCII/Unicode rendering with double-buffering, ANSI color support | Sphere math |
| Basic theme | Geography theme (blue oceans, green land) applied to renderer | Rendering engine |
| Static display | Curses screen setup, render loop, clean exit on `q` or `Ctrl+C` | All above |

**Checkpoint Gate**: Visual review — does the static globe look good? Are continents recognizable? Is rendering clean (no flicker)?

---

### 9.2 Phase 2: Interaction — Mouse Controls & Auto-Rotation
**Completion Criteria**: User can rotate the globe by dragging and zoom with scroll. Globe auto-rotates when idle.

| Deliverable | Description | Dependencies |
|-------------|-------------|--------------|
| Mouse input handling | Capture curses mouse events (click, drag, scroll) | Phase 1 |
| Drag-to-rotate | Translate mouse drag into globe rotation on X/Y axes | Mouse input, sphere math |
| Scroll-to-zoom | Translate scroll events into zoom level changes | Mouse input, rendering engine |
| Auto-rotation | Idle detection, slow Y-axis rotation, pause on interaction | Mouse input, sphere math |
| FPS management | Frame timing, consistent 30+ FPS render loop | Rendering engine |

**Checkpoint Gate**: Interaction review — does rotation feel natural? Is zoom smooth? Does auto-rotation pause/resume correctly?

---

### 9.3 Phase 3: Polish & Extras — Themes, CLI, Packaging
**Completion Criteria**: Full CLI interface, theme system, responsive resize, and pip-installable package.

| Deliverable | Description | Dependencies |
|-------------|-------------|--------------|
| Theme system | Base theme class, theme registry, declarative format | Rendering engine |
| Matrix theme | Second built-in theme (green-on-black, digital aesthetic) | Theme system |
| Full CLI | argparse with all flags (`--speed`, `--theme`, `--no-color`, `--size`, `--help`, `--version`) | Theme system |
| Terminal resize | SIGWINCH handling, responsive re-render, debouncing | Rendering engine |
| Graceful degradation | Detect terminal capabilities, fall back for no-Unicode/no-color | Rendering engine, utils |
| Packaging | pyproject.toml, entry point, PyPI-ready package | All above |
| Documentation | README, theme creation guide, library API docs | All above |

## 10. Dependencies

### 10.1 Technical Dependencies

| Dependency | Type | Status | Notes |
|------------|------|--------|-------|
| Python 3.9+ | Runtime | Available | Standard |
| curses | Library | Built-in | Part of Python standard library on Unix |
| uv | Tooling | Available | For venv and dependency management |
| argparse | Library | Built-in | Part of Python standard library |

No external runtime dependencies required — the project uses only the Python standard library. uv is a development/tooling dependency only.

## 11. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation Strategy |
|------|--------|------------|---------------------|
| Terminal rendering performance varies across emulators | Medium | High | Profile across popular terminals; optimize hot paths; provide `--size` flag to reduce rendering load |
| Mouse event handling differs between terminals | Medium | Medium | Test across major terminals; graceful fallback if mouse events are unavailable |
| Unicode/Braille character support varies by terminal and font | Low | Medium | Detect capabilities at startup; fall back to ASCII-only rendering |
| Embedded map data is too large or too imprecise | Medium | Low | Start with a simplified coastline dataset; iterate on resolution |
| curses API differences between Linux and macOS | Low | Medium | Test on both platforms; abstract curses calls behind utility functions |
| 30 FPS target difficult with complex rendering | Medium | Medium | Dirty-region tracking, efficient projection math, profiling early |

## 12. Open Questions

| # | Question | Notes |
|---|----------|-------|
| 1 | What resolution/detail level for embedded map data? | Need to balance file size, rendering quality, and recognizability. May need experimentation. |
| 2 | Exact Braille character mapping strategy? | Braille dots give 2x4 sub-character resolution — need to define how this maps to sphere projection. |
| 3 | Theme file format: TOML vs Python dataclass? | TOML is more user-friendly for non-programmers; dataclass is more flexible. Could support both. |
| 4 | Auto-rotation resume delay after interaction? | Suggested 2-3 seconds — may need user testing to find the right feel. |

## 13. Appendix

### 13.1 Glossary

| Term | Definition |
|------|------------|
| ASCII art | Visual art created using text characters from the ASCII or Unicode character sets |
| Braille characters | Unicode block (U+2800-U+28FF) providing 2x4 dot patterns per character cell, enabling higher-resolution rendering |
| Double-buffering | Rendering technique where frames are drawn to an off-screen buffer before being displayed, preventing flicker |
| Dirty-region tracking | Optimization that only redraws characters that changed since the last frame |
| ANSI colors | Terminal color codes defined by ANSI escape sequences (typically 8, 16, or 256 colors) |
| SIGWINCH | Unix signal sent to a process when its controlling terminal changes size |
| curses | Python standard library for terminal UI programming, providing screen management and input handling |

### 13.2 References
- Python curses documentation: https://docs.python.org/3/library/curses.html
- Unicode Braille Patterns: https://en.wikipedia.org/wiki/Braille_Patterns
- ANSI escape codes: https://en.wikipedia.org/wiki/ANSI_escape_code
- Sphere point projection techniques for ASCII rendering
- uv documentation: https://docs.astral.sh/uv/

### 13.3 Agent Recommendations (Accepted)

The following recommendations were suggested based on best practices and accepted during the interview:

1. **Modular Architecture**: Clean separation between rendering engine, globe math, theme system, and CLI interface as distinct modules — enables independent testing, library usage, and extensibility.

2. **Double-Buffering & Dirty-Region Tracking**: Render to off-screen buffer, flush to terminal in one write, and only redraw characters that changed — prevents flicker and enables smooth 30 FPS rendering.

3. **Declarative Theme System**: Themes defined via a declarative format (TOML or dataclass) specifying color palette, character set, ocean/land/border chars, and optional decorative elements — allows new themes without writing Python code.

---

*Document generated by SDD Tools*
