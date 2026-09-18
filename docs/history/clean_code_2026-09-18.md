# Clean-code agent report — 2026-09-18

Mode: `apply` · model review: `gemma4:latest`

## Findings

- **ruff** (`open`) `.` — unused import/var findings:
F841 Local variable `empty` is assigned to but never used
    --> openbb_backend/desk.py:2451:5
     |
2449 |     from stock_checker.risk_halts import DEFAULT_POST_SL_COOLDOWN_SEC
2450 |
2451 |     empty = {
     |     ^^^^^
2452 |         "ready": False,
2453 |         "tone": "flat",
     |
help: Remove assignment to unused variable `empty`

F401 [*] `math` imported but unused
  --> stock_checker/experiment_strategy.py:14:8
   |
13 | from typing import Dict, List
14 | import math
   |        ^^^^
help: Remove unused import: `math`
   |
13 | from typing import Dict, List
   - import math
14 |
   |

F401 [*] `typing.Iterable` imported but unused
  --> stock_checker/scan_breadth_gate.py:12:25
   |
11 | import os
12 | from typing import Any, Iterable, Mapping, Optional, Sequence, Tuple
   |                         ^^^^^^^^
13 |
14 | # Fraction of directional names that must be "up" (crypto) before new crypto buys.
   |
help: Remove unused import: `typing.Iterable`
   |
11 | import os
   - from typing import Any, Iterable, Mapping, Optional, Sequence, Tuple
12 + from typing import Any, Mapping, Optional, Sequence, Tuple
13 |
   |

F841 Local variable `before` is assigned to but never 
- **ruff_fix** (`fixed`) `.` — openbb_backend/desk.py:2451:5
     |
2449 |     from stock_checker.risk_halts import DEFAULT_POST_SL_COOLDOWN_SEC
2450 |
2451 |     empty = {
     |     ^^^^^
2452 |         "ready": False,
2453 |         "tone": "flat",
     |
help: Remove assignment to unused variable `empty`

F841 Local variable `before` is assigned to but never used
   --> stock_checker/stock_universe_manager.py:251:9
    |
249 |         Returns count of newly added symbols.
250 |         """
251 |         before = len(self.universe.get("stocks") or {})
    |         ^^^^^^
252 |         removed = False
253 |         for dead in ("PXD",):
    |
help: Remove assignment to unused variable `before`

Found 9 errors (7 fixed, 2 remaining).
No fixes available (2 hidden fixes can be enabled with the `--unsafe-fixes` option).


## Ollama review (advisory)

*   **`intelligent_trader.py`**: Remove the unused variables `AI_VALIDATE_TOP_N` and `AI_FULL_TOP_N` if they are not used in the class methods or initialization.
*   **`intelligent_trader.py`**: The comment `rebalance_threshold: float = 0.15, # unused (legacy print only)` should be removed or the variable should be removed if it serves no current purpose.
*   **`intelligent_trader.py`**: The assignment `self.rebalance_threshold = rebalance` uses an undefined variable `rebalance` (it should likely be `self.rebalance_threshold` or `rebalance_threshold`).
*   **`recommender.py`**: The extensive `try...except Exception` blocks surrounding the calculation of primary, secondary, tertiary, and quaternary scores are overly broad and mask potential bugs; they should be replaced with more specific error handling or simplified.
*   **`recommender.py`**: The repeated pattern of checking `if score is not None else 0.0` and subsequent `float()` casting is redundant and can be simplified by ensuring the helper methods return `float` or `0.0` directly.
*   **`recommender.py`**: The final `try...except Exception` block that resets `reasons = []` and `score = 0.0` is a catch-all that hides all logic failures and should be removed or significantly narrowed.
*   **`main.py`**: The variable `_BACKEND_DIR = Path(__file__).parent` is defined but never used in the provided snippet.
*   **`main.py`**: The `_DESK_CSP` constant is excessively detailed and could be simplified or moved to a dedicated configuration file if it is not strictly necessary for the current scope.
*   **`main.py`**: The function `_desk_page_context` calculates `path` twice (once inside the function, and implicitly when constructing the canonical URL). This logic can be streamlined.
*   **`main.py`**: The `from __future__ import annotations` import is often unnecessary unless complex type hinting features are required, and its inclusion here adds noise.


## Next

- Re-run with `--apply` after dry-run review
- Keep trading log emoji (product voice); do not “sanitize” UX prints
