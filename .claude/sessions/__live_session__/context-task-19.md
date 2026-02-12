### Task [19]: Fix scroll-to-zoom across all target terminals - PASS
- Files modified: `globe_term/input.py` (scroll mask functions), `tests/test_input.py` (41 new tests)
- Key learnings:
  - On Linux/WSL ncurses, BUTTON4_PRESSED=0x10000, BUTTON5_PRESSED=0x200000; the old fallback 0x80000 was actually BUTTON4_TRIPLE_CLICKED
  - Some terminals encode scroll as BUTTON4_CLICKED/BUTTON5_CLICKED instead of BUTTON4_PRESSED/BUTTON5_PRESSED; ORing both variants covers all 4 target terminals
  - Scroll masks (BUTTON4/5) have no bit overlap with BUTTON1 masks, so scroll vs click/drag disambiguation is clean
  - Globe.adjust_zoom uses _clamp_zoom which enforces [0.2, 5.0] bounds; no overflow possible
  - Scroll events are stateless in the InputHandler (no press/drag state changes), so rapid scroll always works
- Issues encountered: None; the existing architecture was already well-structured, needed only mask broadening and tests

## Project Patterns
- Scroll mask functions use `getattr(curses, CONST, fallback)` with OR of pressed|clicked variants for cross-terminal compatibility

## File Map
- `globe_term/globe.py` lines 27-29: MIN_ZOOM=0.2, MAX_ZOOM=5.0 constants
- `globe_term/cli.py` line 88: SCROLL_ZOOM_STEP=0.1 constant
