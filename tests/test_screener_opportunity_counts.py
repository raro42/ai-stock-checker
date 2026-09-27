"""Offline tests for Screener scalar opportunity counts (display only)."""

from openbb_backend.desk import build_screener_opportunity_counts


def test_empty_and_non_mapping():
    empty = build_screener_opportunity_counts(None)
    assert empty["n_total"] == 0
    assert empty["n_unique"] == 0
    assert empty["n_dup"] == 0
    assert empty["lists_populated"] == 0
    assert empty["weight"] == "row slots"
    assert empty["unique_share_pct"] is None
    assert empty["dup_share_pct"] is None
    assert empty["dup_share_severity"] == ""
    assert empty["unique_vs_dup"] == ""
    assert empty["unique_vs_dup_warn"] is False
    assert empty["unique_vs_dup_delta_pp"] is None
    assert empty["unique_vs_dup_delta_severity"] == ""
    assert empty["unique_vs_dup_lean_vs_delta"] == ""
    assert empty["unique_vs_dup_lean_vs_delta_warn"] is False
    assert empty["unique_vs_dup_delta_lead"] == ""
    assert empty["unique_vs_dup_delta_lead_size"] is None
    assert empty["tone"] == "flat"
    assert build_screener_opportunity_counts("bad")["n_total"] == 0


def test_scalar_list_lengths():
    c = build_screener_opportunity_counts(
        {
            "recommendations": [{"symbol": "AAPL"}, {"symbol": "MSFT"}],
            "crypto_leaders": [{"symbol": "BTC-USD"}],
            "stock_breakouts": [],
        }
    )
    assert c["n_rec"] == 2
    assert c["n_crypto"] == 1
    assert c["n_brk"] == 0
    assert c["n_total"] == 3
    assert c["n_unique"] == 3
    assert c["n_dup"] == 0
    assert c["lists_populated"] == 2
    assert c["overlap"] is False
    assert c["unique_share_pct"] is None
    assert c["dup_share_pct"] is None
    assert c["dup_share_severity"] == ""
    assert c["unique_vs_dup"] == ""
    assert c["weight"] == "row slots"
    assert c["tone"] == "flat"


def test_overlap_speaks_unique_share_ok():
    c = build_screener_opportunity_counts(
        {
            "recommendations": [{"symbol": "NVDA"}, {"symbol": "AAPL"}],
            "crypto_leaders": [{"symbol": "BTC-USD"}],
            "stock_breakouts": [{"symbol": "NVDA"}],
        }
    )
    assert c["n_total"] == 4
    assert c["n_unique"] == 3
    assert c["n_dup"] == 1
    assert c["overlap"] is True
    assert c["unique_share_pct"] == 75.0
    assert c["dup_share_pct"] == 25.0
    assert c["unique_share_severity"] == "strong"
    assert c["dup_share_severity"] == "quiet"
    assert c["unique_vs_dup"] == "align · strong|quiet"
    assert c["unique_vs_dup_warn"] is False
    assert c["unique_vs_dup_delta_pp"] == 50.0
    assert c["unique_vs_dup_delta_severity"] == "wide"
    assert c["unique_vs_dup_lean_vs_delta"] == "align · wide"
    assert c["unique_vs_dup_lean_vs_delta_warn"] is False
    assert c["unique_vs_dup_delta_lead"] == "unique"
    assert c["unique_vs_dup_delta_lead_size"] == 3.0
    assert (
        c["weight"]
        == "3 unique · strong · 75% · 1 dup · quiet · 25% · unique vs dup align · strong|quiet · Δ wide · +50pp · lean vs Δ align · wide · Δ lead · unique · Δ lead size · 3×"
    )
    assert c["tone"] == "flat"
    assert c["lists_populated"] == 3


def test_overlap_unique_share_thin_warns():
    # 2 unique across 5 slots → 40% thin · 60% dup hot → align
    c = build_screener_opportunity_counts(
        {
            "recommendations": [{"symbol": "AAPL"}, {"symbol": "AAPL"}],
            "crypto_leaders": [{"symbol": "AAPL"}],
            "stock_breakouts": [{"symbol": "MSFT"}, {"symbol": "AAPL"}],
        }
    )
    assert c["n_total"] == 5
    assert c["n_unique"] == 2
    assert c["n_dup"] == 3
    assert c["unique_share_pct"] == 40.0
    assert c["dup_share_pct"] == 60.0
    assert c["unique_share_severity"] == "thin"
    assert c["dup_share_severity"] == "hot"
    assert c["unique_vs_dup"] == "align · thin|hot"
    assert c["unique_vs_dup_warn"] is False
    assert c["unique_vs_dup_delta_pp"] == -20.0
    assert c["unique_vs_dup_delta_severity"] == "wide"
    assert c["unique_vs_dup_lean_vs_delta"] == "align · wide"
    assert c["unique_vs_dup_lean_vs_delta_warn"] is False
    assert c["unique_vs_dup_delta_lead"] == "dup"
    assert c["unique_vs_dup_delta_lead_size"] == 1.5
    assert (
        c["weight"]
        == "2 unique · thin · 40% · 3 dup · hot · 60% · unique vs dup align · thin|hot · Δ wide · -20pp · lean vs Δ align · wide · Δ lead · dup · Δ lead size · 1.5×"
    )
    assert c["tone"] == "warn"


def test_overlap_unique_share_mid_ok():
    # 3 unique / 5 slots → 60% mid (ok) · 40% dup mid (ok) → both mid silent
    c = build_screener_opportunity_counts(
        {
            "recommendations": [{"symbol": "A"}, {"symbol": "B"}, {"symbol": "C"}],
            "crypto_leaders": [{"symbol": "A"}],
            "stock_breakouts": [{"symbol": "B"}],
        }
    )
    assert c["n_total"] == 5
    assert c["n_unique"] == 3
    assert c["n_dup"] == 2
    assert c["unique_share_pct"] == 60.0
    assert c["dup_share_pct"] == 40.0
    assert c["unique_share_severity"] == "ok"
    assert c["dup_share_severity"] == "ok"
    assert c["unique_vs_dup"] == ""
    assert c["unique_vs_dup_warn"] is False
    assert c["unique_vs_dup_delta_pp"] is None
    assert c["unique_vs_dup_delta_severity"] == ""
    assert c["unique_vs_dup_lean_vs_delta"] == ""
    assert c["unique_vs_dup_lean_vs_delta_warn"] is False
    assert c["unique_vs_dup_delta_lead"] == ""
    assert c["unique_vs_dup_delta_lead_size"] is None
    assert c["weight"] == "3 unique · 60% · 2 dup · 40%"
    assert c["tone"] == "flat"


def test_overlap_unique_vs_dup_clash_at_half():
    # 2 unique / 4 slots → 50% unique ok · 50% dup hot → exactly one lean
    # Δ 0pp is thin (<10) so lean clash speaks; Δ thin · 0pp also speaks
    # zero Δ → no Δ lead (even)
    c = build_screener_opportunity_counts(
        {
            "recommendations": [{"symbol": "AAPL"}, {"symbol": "MSFT"}],
            "crypto_leaders": [{"symbol": "AAPL"}],
            "stock_breakouts": [{"symbol": "MSFT"}],
        }
    )
    assert c["n_total"] == 4
    assert c["n_unique"] == 2
    assert c["n_dup"] == 2
    assert c["unique_share_pct"] == 50.0
    assert c["dup_share_pct"] == 50.0
    assert c["unique_share_severity"] == "ok"
    assert c["dup_share_severity"] == "hot"
    assert c["unique_vs_dup"] == "clash · unique ok · dup hot"
    assert c["unique_vs_dup_warn"] is True
    assert c["unique_vs_dup_delta_pp"] == 0.0
    assert c["unique_vs_dup_delta_severity"] == "thin"
    assert c["unique_vs_dup_lean_vs_delta"] == "align · thin"
    assert c["unique_vs_dup_lean_vs_delta_warn"] is False
    assert c["unique_vs_dup_delta_lead"] == ""
    assert c["unique_vs_dup_delta_lead_size"] is None
    assert (
        c["weight"]
        == "2 unique · 50% · 2 dup · hot · 50% · unique vs dup clash · unique ok · dup hot · Δ thin · 0pp · lean vs Δ align · thin"
    )
    assert c["tone"] == "warn"


def test_string_symbols_and_bad_list_type():
    c = build_screener_opportunity_counts(
        {
            "recommendations": ["aapl", "msft"],
            "crypto_leaders": "not-a-list",
            "stock_breakouts": [{"symbol": "AAPL"}],
        }
    )
    assert c["n_rec"] == 2
    assert c["n_crypto"] == 0
    assert c["n_brk"] == 1
    assert c["n_total"] == 3
    assert c["n_unique"] == 2
    assert c["n_dup"] == 1
    assert c["overlap"] is True
    assert c["unique_share_pct"] == 66.7
    assert c["dup_share_pct"] == 33.3
    assert c["unique_share_severity"] == "ok"
    assert c["dup_share_severity"] == "ok"
    assert c["unique_vs_dup"] == ""
    assert c["unique_vs_dup_delta_pp"] is None
    assert c["weight"] == "2 unique · 66.7% · 1 dup · 33.3%"
    assert c["tone"] == "flat"


def test_overlap_unique_vs_dup_delta_mid_silent():
    # 11 unique / 20 slots → 55% ok · 45% ok → no lean; no Δ
    # Force lean via 12/20 = 60% ok unique · 40% ok dup — still no lean words
    # Use 14 unique / 20 = 70% ok · 30% ok — still mid unique (ok) + mid-ish dup
    # Need lean spoken + mid Δ: 11 slots with lean? Use clash path with |Δ| mid.
    # 3 unique / 5.5? Use integers: 7 unique / 13 ≈ 53.8% unique ok · 46.2% dup ok → no lean.
    # Lean + mid Δ: unique thin needs <50%, so Δ = unique−dup = 2u−100.
    # For |Δ| in [10, 20): e.g. unique 45% → Δ = −10 → mid (|Δ|=10 not <10, not ≥20).
    # 9 unique / 20 = 45% thin · 55% hot → align · |Δ|=10 → mid silent.
    c = build_screener_opportunity_counts(
        {
            "recommendations": [{"symbol": f"S{i}"} for i in range(9)],
            "crypto_leaders": [{"symbol": "S0"}, {"symbol": "S1"}],
            "stock_breakouts": [
                {"symbol": "S2"},
                {"symbol": "S3"},
                {"symbol": "S4"},
                {"symbol": "S5"},
                {"symbol": "S6"},
                {"symbol": "S7"},
                {"symbol": "S8"},
                {"symbol": "S0"},
                {"symbol": "S1"},
            ],
        }
    )
    assert c["n_total"] == 20
    assert c["n_unique"] == 9
    assert c["n_dup"] == 11
    assert c["unique_share_pct"] == 45.0
    assert c["dup_share_pct"] == 55.0
    assert c["unique_vs_dup"] == "align · thin|hot"
    assert c["unique_vs_dup_delta_pp"] is None
    assert c["unique_vs_dup_delta_severity"] == ""
    assert c["unique_vs_dup_lean_vs_delta"] == "clash · lean · Δ mid"
    assert c["unique_vs_dup_lean_vs_delta_warn"] is True
    assert c["unique_vs_dup_delta_lead"] == ""
    assert c["unique_vs_dup_delta_lead_size"] is None
    assert (
        c["weight"]
        == "9 unique · thin · 45% · 11 dup · hot · 55% · unique vs dup align · thin|hot · lean vs Δ clash · lean · Δ mid"
    )
    assert c["tone"] == "warn"
