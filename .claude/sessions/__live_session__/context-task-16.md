### Task [16]: Add terminal emulator detection - PASS
- Files modified: `globe_term/utils.py` (added `detect_terminal()` function), `tests/test_utils.py` (added 13 tests in `TestDetectTerminal` class)
- Key learnings:
  - Existing detection functions in `utils.py` follow a consistent pattern: check env vars via `os.environ.get()` with empty string defaults, return simple types (bool/int/str)
  - Tests use `mock.patch.dict(os.environ, env, clear=False)` pattern extensively for env var mocking
  - Test classes are organized by function with section-header comments separating them
  - `from __future__ import annotations` is used in all modules
  - Test suite was 402 tests, now 415 with the new tests
  - Import in test file is alphabetically ordered in the import block
- Issues encountered: None

## Project Patterns
- Env var detection functions: use `os.environ.get(VAR, "").lower()` for case-insensitive matching
- Test organization: class-based with `Test{FunctionName}` naming, separated by `# ---` comment blocks
- Env var test pattern: helper method `_clean_env()` returning dict of zeroed-out vars, then override specific ones

## File Map
- `globe_term/utils.py` — Terminal detection utilities (now includes `detect_terminal()` for emulator identification)
- `tests/test_utils.py` — Tests for all utils functions (415 tests total after this task)
