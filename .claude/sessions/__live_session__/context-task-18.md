### Task [18]: Fix mouse drag-to-rotate across all target terminals - PASS
- Files modified: `tests/test_input.py` (added 20 new tests)
- Key learnings:
  - Position-based drag detection was already correctly implemented in input.py - detects motion by comparing (mx, my) to (last_x, last_y), not relying on bstate flags
  - The `is_release` guard on line 264 of input.py prevents release/click events from being treated as motion events
  - DragRotator speed capping (MAX_ROTATION_SPEED = 0.15) works correctly with independent axis clamping
  - Escape sequence cleanup (1006l/1003l/1002l/1000l) is in reverse order of enable and called in finally block
  - Drag threshold uses Manhattan distance (abs(dx) + abs(dy) >= 2)
  - No code changes were needed to input.py or cli.py - implementation was already correct
  - Main gap was missing test coverage for cross-terminal position-based drag detection
- Issues encountered: None - implementation was solid, only needed test additions

## Additional Patterns
- Test for cross-terminal mouse behavior: simulate with bstate=0 (some terminals report motion with no bstate flags set)
- Escape sequence cleanup order matters: disable in reverse order of enable
- Source inspection tests (using `inspect.getsource()`) can verify structural properties like finally blocks

## File Map Updates
- `tests/test_input.py` - Now 63 tests (was 43), includes cross-terminal drag detection, escape sequence, threshold, and edge case tests
