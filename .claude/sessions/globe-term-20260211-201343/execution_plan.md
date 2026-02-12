# Execution Plan

Task execution ID: globe-term-20260211-201343
Task group: globe-term
Max parallel: 5
Retries: 3
Total tasks: 15
Total waves: 5

## Wave 1 (1 task)
- [#1] Set up project scaffolding with uv (critical, S)

## Wave 2 (4 tasks)
- [#2] Implement sphere math module (critical, L) — after [#1]
- [#3] Create embedded world map data (critical, M) — after [#1]
- [#4] Build rendering engine with double-buffering (critical, L) — after [#1]
- [#5] Create theme base class and geography theme (critical, S) — after [#1]

## Wave 3 (2 tasks)
- [#6] Implement curses display loop with static globe (critical, M) — after [#2,#3,#4,#5]
- [#11] Build theme system with registry (high, M) — after [#5]

## Wave 4 (4 tasks)
- [#7] Implement mouse input handling (critical, M) — after [#6]
- [#12] Create matrix theme (high, S) — after [#11]
- [#13] Implement full CLI with argparse (high, M) — after [#6,#11]
- [#14] Implement resize handling + degradation (medium, M) — after [#6]

## Wave 5 (4 tasks)
- [#8] Implement drag-to-rotate (critical, M) — after [#7]
- [#9] Implement scroll-to-zoom (critical, S) — after [#7]
- [#10] Implement auto-rotation + FPS (high, M) — after [#7]
- [#15] Set up packaging + distribution (high, S) — after [#13]
