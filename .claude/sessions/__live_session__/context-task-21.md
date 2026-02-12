### Task [21]: Add startup mouse diagnostic hint - PASS
- Files modified: `globe_term/cli.py` (added MOUSE_HINT_MESSAGE, MOUSE_HINT_DURATION constants, _show_mouse_hint(), _clear_mouse_hint() functions, hint logic in _display_loop), `tests/test_cli.py` (added 10 new tests: TestShowMouseHint, TestClearMouseHint, TestMouseHintIntegration)
- Key learnings: The _display_loop already creates InputHandler with stdscr which calls enable_mouse() automatically, so mouse_supported is set before we need to check it. Bottom row (rows-1) is safe for status display without obstructing the globe. The _FakeScreen pattern from existing tests is easily extensible by overriding addstr to capture calls. Using time.monotonic() for hint duration check integrates naturally with the existing frame timing loop. Total tests: 514 passing.
- Issues encountered: None. Implementation was straightforward.

## Project Patterns
- Hint/overlay pattern: Use try/except around addstr calls for resilient status messages on the bottom row
- Time-based display: Use time.monotonic() start time + duration check in the frame loop for timed overlays

## File Map
- `globe_term/cli.py` — Now also contains MOUSE_HINT_MESSAGE, MOUSE_HINT_DURATION, _show_mouse_hint(), _clear_mouse_hint()
