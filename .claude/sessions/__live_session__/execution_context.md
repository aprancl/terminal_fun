# Execution Context

## Project Patterns
- Env var detection functions: use `os.environ.get(VAR, "").lower()` for case-insensitive matching
- Test organization: class-based with `Test{FunctionName}` naming, separated by `# ---` comment blocks
- Env var test pattern: helper method `_clean_env()` returning dict of zeroed-out vars, then override specific ones
- Tests use `mock.patch.dict(os.environ, env, clear=False)` pattern extensively
- `from __future__ import annotations` in all modules

## Key Decisions
- `detect_terminal()` returns string identifiers: "kitty", "iterm2", "apple_terminal", "windows_terminal", "unknown"
- Priority order: TERM_PROGRAM checked first, then TERM=xterm-kitty, then WT_SESSION

## Known Issues
- None so far

## Additional Patterns (from Task #17)
- Kitty protocol: `\033[>0u` (push+disable), `\033[<u` (pop/restore)
- Protocol negotiation placed BEFORE `curses.mousemask()` call
- Error handling for escape sequence writes: wrap in try/except OSError
- Test stdout capture: `patch("sys.stdout", io.StringIO())` then `.getvalue()`
- Test terminal mock: `patch("globe_term.input.detect_terminal", return_value="kitty")`

## File Map
- `globe_term/utils.py` — Terminal detection utilities (includes `detect_terminal()`, `detect_mouse_support()`, etc.)
- `globe_term/input.py` — Mouse event handling, drag state machine, enable/disable mouse
- `globe_term/cli.py` — Main display loop, keyboard controls, entry point
- `tests/test_utils.py` — Tests for all utils functions (415 tests total)
- `tests/test_input.py` — Tests for mouse handling

## Task History
- Task #16 (Add terminal emulator detection): PASS — Added `detect_terminal()` to utils.py, 13 new tests, 415 total passing
- Task #17 (Kitty keyboard protocol negotiation): PASS — Added protocol disable/restore in input.py, 10 new tests, 425 total passing
- Task #18 (Fix mouse drag-to-rotate): PASS — No code changes needed, position-based detection already correct. Added 20 tests for edge cases.
- Task #19 (Fix scroll-to-zoom): PASS — Fixed scroll masks (OR'd PRESSED|CLICKED variants, fixed fallback value). Added 41 tests.
- Task #20 (Verify keyboard controls): PASS — Added reset_idle() method, fixed idle timer reset in cli.py. Added 37 tests. 504 total passing.
