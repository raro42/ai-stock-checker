"""Gate roles — avoid stacking redundant market-context filters (review A14)."""

# Regime (SPY SMA200 / BTC SMA50): absolute market posture — risk-on vs risk-off.
# RS (asset vs SPY/BTC over ~63d): relative strength vs the same benchmarks.
# They overlap in "don't buy weakness" spirit but answer different questions:
#   - Regime: is the *benchmark* itself in an uptrend?
#   - RS: is *this name* at least keeping up with the benchmark?
# Keep both for now; prefer turning RS off first if the book starves (Ops toggle).
# Do not add a third market-context gate until promote A/B is measured.

REGIME_ROLE = "benchmark trend (absolute)"
RS_ROLE = "name vs benchmark (relative)"
BREADTH_ROLE = "scan-list A/D (local, not full universe)"
