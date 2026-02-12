### Task [17]: Implement Kitty keyboard protocol negotiation - PASS
- Files modified: `globe_term/input.py`, `tests/test_input.py`
- Key learnings:
  - Kitty progressive keyboard protocol disabled via `\033[>0u` (push mode + set legacy mode 0), restored via `\033[<u` (pop mode stack)
  - Protocol negotiation placed BEFORE `curses.mousemask()` call so key events are already in legacy mode
  - `_kitty_protocol_disabled` boolean flag tracks whether restore is needed on cleanup
  - `disable_mouse()` now wraps mouse cleanup and Kitty restore in separate try/except OSError blocks for resilience
  - `io.StringIO()` works well as a fake stdout for capturing escape sequence writes in tests
  - Tests use `patch("globe_term.input.detect_terminal", return_value="kitty")` to simulate terminal detection
- Issues encountered: None

## File Map Updates
- `globe_term/input.py` — Now imports `detect_terminal` from utils.py; `enable_mouse()` negotiates Kitty protocol; `disable_mouse()` restores it

## Project Patterns Updates
- Error handling pattern for escape sequence writes: wrap in try/except OSError, continue gracefully
- Kitty protocol escape sequences: `\033[>0u` (push+disable), `\033[<u` (pop/restore)
- Test pattern for stdout capture: `patch("sys.stdout", io.StringIO())` then check `.getvalue()`
