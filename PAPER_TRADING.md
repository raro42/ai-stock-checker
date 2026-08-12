# Deprecated — see README / FRIENDS

Historical paper-trading notes (stale €10k defaults). Live paper path is **`intelligent-trader`** with Ops book limits (default **5 positions / 24h hold**, Revolut-like fees).

**Use instead:** [README.md](README.md), [FRIENDS.md](FRIENDS.md), Ops on the desk.

**Honesty:** the overnight champion (`experiment_strategy.py`) is an optional **entry filter** when promote is on. Live exits are always `exit_policy` (±5% TP/SL, no loss-rotation). Offline `val_score` ≠ live edge.
