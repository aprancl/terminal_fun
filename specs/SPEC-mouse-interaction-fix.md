# Mouse Interaction Fix PRD

**Version**: 1.0
**Author**: aprancl
**Date**: 2026-02-11
**Status**: Draft
**Spec Type**: New feature
**Spec Depth**: Detailed specifications
**Description**: Fix mouse and keyboard input handling across multiple terminal emulators. Currently all input fails on Kitty (macOS), and mouse drag/scroll fails on Windows Terminal (WSL).

---

## 1. Executive Summary

Globe_term's core interactive features — mouse drag-to-rotate, scroll-to-zoom, and keyboard controls — fail across multiple terminal emulators due to terminal protocol incompatibilities. This spec defines the changes needed to make input handling work reliably on Kitty, Terminal.app, iTerm2, and Windows Terminal + WSL, with mouse drag-to-rotate as the primary priority.

## 2. Problem Statement

### 2.1 The Problem

Globe_term input handling is broken on the terminals where the developer actually uses it:

- **Kitty (macOS):** ALL input is broken — mouse, keyboard, even 'q' to quit. The globe renders and auto-rotates fine, but no user interaction is possible. Users must Ctrl+C to exit.
- **Windows Terminal (WSL):** Basic mouse clicks work (stop auto-rotation), but drag-to-rotate and scroll-to-zoom do not function. Keyboard controls have not been verified on this platform.

### 2.2 Current State

The input system has three layers:

1. **Terminal escape sequences** (`\033[?1000h`, `\033[?1002h`, `\033[?1003h`, `\033[?1006h`) written to stdout to enable xterm mouse tracking modes.
2. **Curses `mousemask()`** to tell the curses library to listen for mouse events.
3. **InputHandler state machine** that translates raw curses events into high-level actions (DRAG_START, DRAG_MOVE, SCROLL_UP, etc.) using position-based motion detection.

The root causes are:

- **Kitty:** Uses its own "progressive enhancement" keyboard protocol (`CSI u`) that encodes ALL key events differently than standard xterm sequences. Curses cannot parse these, so `getch()` never returns expected key codes. This breaks everything — keyboard and mouse alike.
- **Windows Terminal + WSL:** The xterm mouse tracking modes may not be fully supported, or the ncurses build in WSL may not properly decode mouse motion events. Basic button events (press/release) work, but motion tracking during drag does not.

### 2.3 Impact Analysis

The interactive experience IS the product. Without working mouse/keyboard input, globe_term is a non-interactive auto-rotating globe — which defeats its entire purpose as a fun, hackable toy.

### 2.4 Business Value

This is the most critical fix for the project. No user engagement is possible without working input on the developer's own terminals.

## 3. Goals & Success Metrics

### 3.1 Primary Goals
1. Mouse drag-to-rotate works smoothly on all 4 target terminals
2. Scroll-to-zoom works on all 4 target terminals
3. Keyboard controls (arrow keys, +/-, q) work on all 4 target terminals

### 3.2 Success Metrics

| Metric | Current Baseline | Target | Measurement Method |
|--------|------------------|--------|--------------------|
| Terminals with working drag | 0/4 | 4/4 | Manual test on each terminal |
| Terminals with working scroll | 0/4 | 4/4 | Manual test on each terminal |
| Terminals with working keyboard | 1/4 (WSL partial) | 4/4 | Manual test on each terminal |
| Input latency | N/A (broken) | <1 frame (33ms) | Perceived responsiveness |

### 3.3 Non-Goals
- Touch/trackpad gesture support (pinch-to-zoom, two-finger drag)
- Additional keyboard shortcuts (WASD, reset view, etc.)
- Support for terminals not in the target list (e.g., Alacritty, WezTerm, rxvt)
- Automated terminal compatibility testing framework

## 4. User Research

### 4.1 Target Users

#### Primary Persona: Terminal Enthusiast
- **Role/Description**: Developer who uses modern terminal emulators (Kitty, iTerm2) and appreciates ASCII art, terminal toys, and hackable tools
- **Goals**: Run globe_term and interact with it — spin the globe with mouse, zoom in/out, explore
- **Pain Points**: Can't interact with the globe at all; forced to Ctrl+C to exit
- **Context**: Daily terminal session on macOS or Linux (WSL)

### 4.2 User Journey Map

```
[Launch globe_term] --> [Globe renders and auto-rotates] --> [Try to click/drag] --> [Nothing happens] --> [Ctrl+C to exit]
```

**Desired journey:**
```
[Launch globe_term] --> [Globe renders] --> [Drag to rotate] --> [Scroll to zoom] --> [Press q to quit]
```

## 5. Functional Requirements

### 5.1 Feature: Terminal Protocol Negotiation

**Priority**: P0 (Critical)

#### User Stories

**US-001**: As a Kitty user, I want globe_term to automatically negotiate the correct keyboard/mouse protocol so that all input works without any configuration.

**Acceptance Criteria**:
- [ ] On Kitty: detect Kitty terminal (via `TERM_PROGRAM` env var or `TERM=xterm-kitty`)
- [ ] On Kitty: disable Kitty's progressive keyboard protocol at startup (send `\033[>0u` or equivalent to request legacy xterm mode)
- [ ] On Kitty: restore keyboard protocol on exit (cleanup escape sequences)
- [ ] Basic key input works on Kitty: 'q' quits, arrow keys are recognized
- [ ] On non-Kitty terminals: no behavioral change from current implementation

**Edge Cases**:
- Kitty running inside tmux/screen: Protocol negotiation may need to pass through the multiplexer
- Unknown terminal that uses Kitty protocol but doesn't set `TERM_PROGRAM=kitty`: Fallback to generic approach

---

### 5.2 Feature: Mouse Drag-to-Rotate

**Priority**: P0 (Critical)

#### User Stories

**US-002**: As a user, I want to click and drag on the globe to rotate it smoothly, regardless of which terminal I'm using.

**Acceptance Criteria**:
- [ ] Click and hold, then move mouse, rotates the globe on Kitty (macOS)
- [ ] Click and hold, then move mouse, rotates the globe on Terminal.app (macOS)
- [ ] Click and hold, then move mouse, rotates the globe on iTerm2 (macOS)
- [ ] Click and hold, then move mouse, rotates the globe on Windows Terminal (WSL)
- [ ] Drag rotation feels smooth and responsive (no visible stutter or lag)
- [ ] Releasing the mouse button stops the rotation
- [ ] Small mouse movements (below threshold) do not trigger rotation (prevent accidental drags)
- [ ] Mouse escape sequences are properly cleaned up on exit (terminal returns to normal)

**Edge Cases**:
- Drag across terminal edge: Should not crash, just stop tracking
- Very fast drag: Speed capping prevents disorienting spins (max 0.15 rad/event)
- Drag while terminal is resizing: Should not crash

---

### 5.3 Feature: Scroll-to-Zoom

**Priority**: P1 (High)

#### User Stories

**US-003**: As a user, I want to scroll up/down to zoom in/out on the globe.

**Acceptance Criteria**:
- [ ] Scroll up zooms in on all 4 target terminals
- [ ] Scroll down zooms out on all 4 target terminals
- [ ] Zoom is bounded (min 0.2, max 5.0) and doesn't overflow
- [ ] Scroll events are correctly distinguished from other mouse button events

**Edge Cases**:
- Different terminals may use different button codes for scroll (BUTTON4/BUTTON5 vs. alternatives)
- Rapid scroll should smoothly accumulate zoom changes

---

### 5.4 Feature: Keyboard Controls

**Priority**: P1 (High)

#### User Stories

**US-004**: As a user, I want to use arrow keys to rotate the globe and +/- to zoom, especially when mouse is unavailable.

**Acceptance Criteria**:
- [ ] Arrow keys rotate the globe on all 4 target terminals
- [ ] +/- (and =/_ as aliases) zoom in/out on all 4 target terminals
- [ ] q/Q quits the application on all 4 target terminals
- [ ] Key presses reset the idle timer (stop auto-rotation temporarily)

---

### 5.5 Feature: Startup Input Diagnostic

**Priority**: P2 (Medium)

#### User Stories

**US-005**: As a user, I want to see a brief hint if mouse support isn't available, so I know to use keyboard controls.

**Acceptance Criteria**:
- [ ] If mouse support is not detected, show a brief message (e.g., "Mouse not detected. Use arrow keys to rotate, +/- to zoom.")
- [ ] Message is shown briefly at startup (1-2 seconds) and does not obstruct the globe
- [ ] Message is not shown if mouse support is successfully detected

## 6. Non-Functional Requirements

### 6.1 Performance
- Input event processing must not exceed 1 frame duration (33ms at 30 FPS)
- No perceptible lag between mouse movement and globe rotation
- Terminal protocol negotiation must complete within 100ms at startup

### 6.2 Compatibility
- No new external dependencies — pure Python standard library only
- Must not break existing rendering, auto-rotation, or theme functionality
- Escape sequences must be cleaned up on both normal exit (q) and interrupt (Ctrl+C)

### 6.3 Robustness
- Graceful degradation: if a specific mouse tracking mode isn't supported, fall back to keyboard-only with a hint
- No crashes on unexpected mouse event data or terminal behavior
- Terminal state must be fully restored on exit (no leftover escape sequences affecting the user's shell)

## 7. Technical Considerations

### 7.1 Architecture Overview

The fix primarily modifies the terminal protocol negotiation layer (escape sequences written at startup/cleanup) and the terminal detection logic. The InputHandler state machine and display loop integration remain largely unchanged.

```
[Terminal Detection] → [Protocol Negotiation] → [Curses Setup] → [Input Handler] → [Display Loop]
                          ↑ NEW: Kitty protocol     ↑ EXISTING      ↑ MINOR CHANGES
                            disable + xterm modes
```

### 7.2 Tech Stack
- **Language**: Python 3.9+ (no new dependencies)
- **Terminal I/O**: curses (stdlib)
- **Protocol**: xterm mouse escape sequences, Kitty keyboard protocol negotiation

### 7.3 Codebase Context

#### Existing Architecture

The input system is split across three files:

| File | Role | Lines |
|------|------|-------|
| `globe_term/input.py` | Mouse event state machine, escape sequences, InputHandler class | ~320 |
| `globe_term/cli.py` | Display loop, keyboard controls, DragRotator, event dispatch | ~567 |
| `globe_term/utils.py` | Terminal detection (mouse, color, unicode support) | ~269 |

#### Integration Points

| File/Module | Purpose | How This Fix Connects |
|-------------|---------|----------------------|
| `globe_term/input.py:enable_mouse()` | Writes xterm escape sequences, calls `curses.mousemask()` | Add Kitty protocol disable, improve escape sequence handling |
| `globe_term/input.py:disable_mouse()` | Cleanup escape sequences | Add Kitty protocol restore |
| `globe_term/utils.py:detect_mouse_support()` | Checks `TERM` env var for mouse capability | Add `TERM_PROGRAM` checks for Kitty, iTerm2, Windows Terminal |
| `globe_term/cli.py:_display_loop()` | Main event loop with keyboard + mouse processing | May need adjustments for diagnostic message display |
| `globe_term/cli.py:main()` | Entry point, prints mouse warning | Update diagnostic message logic |

#### Patterns to Follow

- **Escape sequence pairs:** Always write enable at startup and disable at cleanup — used in `enable_mouse()`/`disable_mouse()`
- **Env var detection:** Check `TERM`, `TERM_PROGRAM`, and other env vars for terminal identification — used in `detect_mouse_support()`
- **Graceful fallback:** `try/except curses.error` around all curses calls — used throughout input.py and renderer.py
- **Frozen dataclasses:** `InputEvent`, `Cell`, `Theme` are all `@dataclass(frozen=True)` — maintain this pattern

### 7.4 Technical Constraints
- Must use only Python standard library (no `pynput`, `blessed`, or other terminal libs)
- Must not change the public API of `InputHandler`, `Globe`, or `Renderer`
- Existing 402 tests must continue to pass

## 8. Scope Definition

### 8.1 In Scope
- Fix Kitty keyboard protocol incompatibility
- Fix mouse drag/scroll on Windows Terminal + WSL
- Verify mouse and keyboard work on Terminal.app and iTerm2
- Add startup diagnostic hint for missing mouse support
- Clean up terminal state on exit for all protocol negotiation changes

### 8.2 Out of Scope
- Touch/trackpad gestures: Not a terminal primitive; would require OS-level integration
- Additional keyboard shortcuts (WASD, reset, theme toggle): Feature request, not a bug fix
- Automated terminal compatibility testing: Manual testing is sufficient for 4 terminals
- Support for other terminals (Alacritty, WezTerm, rxvt): Can be added later if requested

### 8.3 Future Considerations
- Terminal compatibility test harness (mock different terminal protocols in tests)
- Configurable mouse sensitivity via CLI flag
- `--debug` flag for verbose input diagnostics
- Support for additional terminal emulators

## 9. Implementation Plan

### 9.1 Phase 1: Terminal Protocol Negotiation
**Completion Criteria**: 'q' quits and arrow keys work on Kitty

| Deliverable | Description | Dependencies |
|-------------|-------------|--------------|
| Kitty detection | Detect Kitty via `TERM_PROGRAM` or `TERM=xterm-kitty` in `utils.py` | None |
| Kitty protocol disable | Send `\033[>0u` at startup to request legacy xterm mode in `input.py` | Kitty detection |
| Kitty protocol restore | Send restore sequence at cleanup in `disable_mouse()` | Kitty protocol disable |
| Terminal detection improvements | Add `TERM_PROGRAM` checks for iTerm2, Windows Terminal (`WT_SESSION`) | None |

**Checkpoint Gate**: Verify 'q', arrow keys, and basic key input work on Kitty before proceeding to mouse fixes.

---

### 9.2 Phase 2: Mouse Input Fix
**Completion Criteria**: Drag-to-rotate and scroll-to-zoom work on all 4 target terminals

| Deliverable | Description | Dependencies |
|-------------|-------------|--------------|
| Mouse tracking verification | Verify xterm mouse modes (1000/1002/1003/1006) work on each target terminal | Phase 1 |
| Drag fix for Kitty | With legacy mode enabled, verify drag-to-rotate works | Phase 1 |
| Drag fix for Windows Terminal | Investigate and fix drag motion events on WSL | Phase 1 |
| Scroll fix | Verify scroll events are correctly detected on all terminals | Phase 1 |
| Cross-terminal manual test | Test full input suite on all 4 terminals | All above |

**Checkpoint Gate**: All 4 terminals pass manual test for drag, scroll, and keyboard.

---

### 9.3 Phase 3: Polish
**Completion Criteria**: Startup hint displays correctly, all tests pass

| Deliverable | Description | Dependencies |
|-------------|-------------|--------------|
| Startup diagnostic | Show "Mouse not detected" hint briefly if mouse unavailable | Phase 2 |
| Test verification | Ensure all 402 existing tests still pass | Phase 2 |
| Cleanup verification | Verify terminal state is fully restored on exit (no leftover escape sequences) | Phase 2 |

## 10. Dependencies

### 10.1 Technical Dependencies

| Dependency | Status | Risk if Delayed |
|------------|--------|-----------------|
| Kitty keyboard protocol documentation | Available (sw.kovidgoyal.net/kitty/keyboard-protocol/) | Low — well-documented |
| xterm mouse tracking specification | Available (invisible-island.net/xterm/ctlseqs/) | Low — well-documented |
| Access to all 4 target terminals for manual testing | Requires macOS + WSL environments | Medium — can't verify fix without hardware |

## 11. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation Strategy |
|------|--------|------------|---------------------|
| Kitty protocol disable doesn't fix input | High | Low | Well-documented protocol; `\033[>0u` is the standard disable sequence |
| Windows Terminal mouse tracking is fundamentally broken in WSL | Medium | Medium | Keyboard controls provide a working fallback; show diagnostic hint |
| Terminal-specific quirks require per-terminal workarounds | Medium | Medium | Keep detection logic centralized in `utils.py`; use env var checks |
| Escape sequence cleanup fails (garbled terminal on exit) | High | Low | Use `try/finally` in display loop; test Ctrl+C exit path |
| Fix breaks one of the 402 existing tests | Low | Low | Run full test suite after each change |

## 12. Open Questions

| # | Question | Resolution |
|---|----------|------------|
| 1 | Does Kitty inside tmux forward the protocol disable sequence correctly? | Test during Phase 1 |
| 2 | What specific ncurses version does the WSL environment use, and does it support SGR mouse mode? | Investigate during Phase 2 |

## 13. Appendix

### 13.1 Glossary

| Term | Definition |
|------|------------|
| CSI u | Control Sequence Introducer "u" — Kitty's progressive keyboard enhancement protocol that encodes key events differently than standard xterm |
| SGR mouse mode | Mode 1006 — extended mouse event encoding that supports coordinates >223 |
| xterm mouse tracking | Escape sequence protocol for reporting mouse events to terminal applications (modes 1000, 1002, 1003) |
| Drag threshold | Minimum Manhattan distance (2 cells) mouse must move while pressed before a click is promoted to a drag |

### 13.2 References
- Kitty keyboard protocol: https://sw.kovidgoyal.net/kitty/keyboard-protocol/
- xterm control sequences: https://invisible-island.net/xterm/ctlseqs/ctlseqs.html
- Existing spec: `specs/SPEC-globe_term.md`

### 13.3 Target Terminal Matrix

| Terminal | OS | TERM value | TERM_PROGRAM | Mouse Tracking | Kitty Protocol |
|----------|-----|-----------|--------------|----------------|----------------|
| Kitty | macOS | xterm-kitty | kitty | Yes (xterm modes) | Yes (must disable) |
| Terminal.app | macOS | xterm-256color | Apple_Terminal | Yes (xterm modes) | No |
| iTerm2 | macOS | xterm-256color | iTerm.app | Yes (xterm modes) | No |
| Windows Terminal | WSL | xterm-256color | (varies) | Partial (check WT_SESSION) | No |

---

*Document generated by SDD Tools*
