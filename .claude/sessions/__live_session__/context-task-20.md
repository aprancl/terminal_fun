### Task [20]: Verify and fix keyboard controls across all target terminals - PASS
- Files modified:
  - `globe_term/input.py` — Added `reset_idle()` public method to InputHandler for cleanly resetting the idle timer from keyboard events
  - `globe_term/cli.py` — Replaced direct `_last_event_time` access with `reset_idle()` calls in all keyboard control branches
  - `tests/test_cli.py` — Added 34 new keyboard control tests (arrow rotation, zoom keys, quit keys, idle timer reset, edge cases)
  - `tests/test_input.py` — Added 3 new tests for `reset_idle()` method
- Key learnings:
  - Keyboard controls use standard curses key codes (KEY_LEFT/RIGHT/UP/DOWN) and ASCII ord() values which work on all 4 target terminals
  - Kitty protocol negotiation (Task #17) disables progressive keyboard protocol, ensuring standard xterm key codes work on Kitty
  - The Renderer sets `nodelay(True)` on the curses screen, enabling non-blocking getch() needed for the frame-timed event loop
  - KEY_ROTATION_STEP = ~5 degrees per keypress, KEY_ZOOM_STEP = 0.15 per keypress
  - Testing pattern: `_FakeScreen.queue_keys()` followed by `ord("q")` to exit the display loop, with both renderer and cli curses mocks needed
  - When mocking curses for keyboard tests, must set KEY_LEFT/RIGHT/UP/DOWN on the cli_mock in addition to KEY_RESIZE
- Issues encountered: None — the implementation was already correct, just needed public API cleanup (reset_idle) and comprehensive test coverage

## Project Patterns
- InputHandler has a public `reset_idle()` method for non-mouse input events to reset the idle timer
- Display loop keyboard test helper: `_make_display_loop_mocks()` creates both renderer and cli curses mocks with all needed key constants
- Display loop integration test helper: `_run_display_loop_with_keys()` captures Globe instance for state inspection after key processing

## File Map
- `tests/test_cli.py` — Now includes keyboard control tests (TestArrowKeyRotation, TestZoomKeys, TestQuitKeys, TestKeyboardIdleTimerReset, TestKeyboardEdgeCases, TestKeyboardConstants)
