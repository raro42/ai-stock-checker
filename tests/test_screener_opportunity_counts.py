"""Offline tests for Screener scalar opportunity counts (display only)."""

from openbb_backend.desk import (
    build_screener_opportunity_counts,
    scan_list_junk_count,
    scan_list_rows,
)


def test_scan_list_rows_keeps_objects_only():
    rows = scan_list_rows(
        [{"symbol": "AAPL"}, "MSFT", None, 3, {"symbol": "NVDA"}, []]
    )
    assert [r.get("symbol") for r in rows] == ["AAPL", "NVDA"]
    assert scan_list_rows(None) == []
    assert scan_list_rows({"symbol": "X"}) == []
    assert scan_list_rows("bad") == []


def test_scan_list_junk_count():
    """Non-object slots are counted; wrong containers stay 0."""
    assert (
        scan_list_junk_count(
            [{"symbol": "AAPL"}, "MSFT", None, 3, {"symbol": "NVDA"}, []]
        )
        == 4
    )
    assert scan_list_junk_count([]) == 0
    assert scan_list_junk_count(None) == 0
    assert scan_list_junk_count("not-a-list") == 0
    assert scan_list_junk_count({"symbol": "X"}) == 0


def test_junk_slots_do_not_inflate_counts():
    """xang1234 #498 — list length ≠ object rows; junk speaks (not silent)."""
    c = build_screener_opportunity_counts(
        {
            "recommendations": [
                {"symbol": "AAPL"},
                "MSFT",
                None,
                {"symbol": "MSFT"},
            ],
            "crypto_leaders": ["BTC-USD", {"symbol": "BTC-USD"}],
            "stock_breakouts": [None, "NVDA"],
        }
    )
    assert c["n_rec"] == 2
    assert c["n_crypto"] == 1
    assert c["n_brk"] == 0
    assert c["n_total"] == 3
    assert c["n_unique"] == 3
    assert c["n_dup"] == 0
    assert c["n_junk"] == 5
    assert c["n_junk_rec"] == 2
    assert c["n_junk_crypto"] == 1
    assert c["n_junk_brk"] == 2
    assert c["junk_lists"] == "rec · crypto · brk"
    # rec=2 · crypto=1 · brk=2 → tie at 2; lead silent → tied
    assert c["junk_list_lead"] == ""
    assert c["junk_list_lead_name"] == ""
    assert c["junk_list_lead_share"] is None
    assert c["junk_list_lead_margin"] == ""
    assert c["junk_list_lead_sides"] == ""
    assert c["junk_list_sample_gap"] == "tied"
    # 3 object + 5 junk = 8 slots → 62.5% hot · vs 3 ok · thin · 37.5%
    assert c["junk_share_pct"] == 62.5
    assert c["junk_share_severity"] == "hot"
    assert c["ok_share_pct"] == 37.5
    assert c["ok_share_severity"] == "thin"
    assert c["junk_vs_ok"] == "align · hot|thin"
    assert c["junk_vs_ok_warn"] is False
    assert c["lists_populated"] == 2
    assert (
        c["weight_core"]
        == "row slots · 5 junk · hot · 62.5% · in rec · crypto · brk · tied · vs 3 ok · thin · 37.5%"
    )
    assert c["weight_lean"] == "junk vs ok align · hot|thin"
    assert (
        c["weight"]
        == "row slots · 5 junk · hot · 62.5% · in rec · crypto · brk · tied · vs 3 ok · thin · 37.5% · junk vs ok align · hot|thin"
    )
    assert c["tone"] == "warn"


def test_empty_and_non_mapping():
    empty = build_screener_opportunity_counts(None)
    assert empty["n_total"] == 0
    assert empty["n_unique"] == 0
    assert empty["n_dup"] == 0
    assert empty["n_junk"] == 0
    assert empty["n_junk_rec"] == 0
    assert empty["n_junk_crypto"] == 0
    assert empty["n_junk_brk"] == 0
    assert empty["junk_lists"] == ""
    assert empty["junk_list_lead"] == ""
    assert empty["junk_list_lead_name"] == ""
    assert empty["junk_list_lead_share"] is None
    assert empty["junk_list_lead_margin"] == ""
    assert empty["junk_list_lead_margin_gap"] is None
    assert empty["junk_list_lead_sides"] == ""
    assert empty["junk_list_lead_sides_name"] == ""
    assert empty["junk_list_lead_sides_n"] is None
    assert empty["junk_list_lead_sides_share"] is None
    assert empty["junk_list_sample_gap"] == ""
    assert empty["junk_share_pct"] is None
    assert empty["junk_share_severity"] == ""
    assert empty["ok_share_pct"] is None
    assert empty["ok_share_severity"] == ""
    assert empty["junk_vs_ok"] == ""
    assert empty["junk_vs_ok_warn"] is False
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
    assert empty["unique_vs_dup_delta_lead_size_louder_pct"] is None
    assert empty["unique_vs_dup_delta_lead_size_quieter_pct"] is None
    assert empty["tone"] == "flat"
    assert empty["weight_core"] == "row slots"
    assert empty["weight_lean"] == ""
    assert build_screener_opportunity_counts("bad")["n_total"] == 0
    assert build_screener_opportunity_counts("bad")["n_junk"] == 0


def test_junk_appends_on_overlap_weight():
    """Junk speak sits on weight_core even when unique/dup already spoke."""
    c = build_screener_opportunity_counts(
        {
            "recommendations": [
                {"symbol": "AAPL"},
                {"symbol": "MSFT"},
                "junk",
            ],
            "crypto_leaders": [{"symbol": "AAPL"}],
            "stock_breakouts": [{"symbol": "MSFT"}, None],
        }
    )
    assert c["n_total"] == 4
    assert c["n_unique"] == 2
    assert c["n_dup"] == 2
    assert c["n_junk"] == 2
    assert c["n_junk_rec"] == 1
    assert c["n_junk_crypto"] == 0
    assert c["n_junk_brk"] == 1
    assert c["junk_lists"] == "rec · brk"
    # rec=1 · brk=1 → tie; lead silent → tied
    assert c["junk_list_lead"] == ""
    assert c["junk_list_lead_share"] is None
    assert c["junk_list_sample_gap"] == "tied"
    # 4 object + 2 junk = 6 slots → 33.3% mid (ok) · vs 4 ok · 66.7% mid — no lean
    assert c["junk_share_pct"] == 33.3
    assert c["junk_share_severity"] == "ok"
    assert c["ok_share_pct"] == 66.7
    assert c["ok_share_severity"] == "ok"
    assert c["junk_vs_ok"] == ""
    assert c["junk_vs_ok_warn"] is False
    assert c["overlap"] is True
    assert c["weight_core"].endswith(
        " · 2 junk · 33.3% · in rec · brk · tied · vs 4 ok · 66.7%"
    )
    # junk sits on weight_core; unique/dup lean cascade stays after core
    assert (
        " · 2 junk · 33.3% · in rec · brk · tied · vs 4 ok · 66.7% · unique vs dup"
        in c["weight"]
    )
    assert "junk vs ok" not in c["weight_lean"]
    assert c["tone"] == "warn"


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
    assert c["weight_core"] == "row slots"
    assert c["weight_lean"] == ""
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
    assert c["unique_vs_dup_delta_lead_size_louder_pct"] == 75.0
    assert c["unique_vs_dup_delta_lead_size_quieter_pct"] == 25.0
    assert c["weight_core"] == "3 unique · strong · 75% · 1 dup · quiet · 25%"
    assert (
        c["weight_lean"]
        == "unique vs dup align · strong|quiet · Δ wide · +50pp · lean vs Δ align · wide · Δ lead · unique · Δ lead size · 3× · Δ lead size sides · louder 75% · quieter 25%"
    )
    assert (
        c["weight"]
        == "3 unique · strong · 75% · 1 dup · quiet · 25% · unique vs dup align · strong|quiet · Δ wide · +50pp · lean vs Δ align · wide · Δ lead · unique · Δ lead size · 3× · Δ lead size sides · louder 75% · quieter 25%"
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
    assert c["unique_vs_dup_delta_lead_size_louder_pct"] == 60.0
    assert c["unique_vs_dup_delta_lead_size_quieter_pct"] == 40.0
    assert c["weight_core"] == "2 unique · thin · 40% · 3 dup · hot · 60%"
    assert (
        c["weight_lean"]
        == "unique vs dup align · thin|hot · Δ wide · -20pp · lean vs Δ align · wide · Δ lead · dup · Δ lead size · 1.5× · Δ lead size sides · louder 60% · quieter 40%"
    )
    assert (
        c["weight"]
        == "2 unique · thin · 40% · 3 dup · hot · 60% · unique vs dup align · thin|hot · Δ wide · -20pp · lean vs Δ align · wide · Δ lead · dup · Δ lead size · 1.5× · Δ lead size sides · louder 60% · quieter 40%"
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
    assert c["unique_vs_dup_delta_lead_size_louder_pct"] is None
    assert c["unique_vs_dup_delta_lead_size_quieter_pct"] is None
    assert c["weight_core"] == "3 unique · 60% · 2 dup · 40%"
    assert c["weight_lean"] == ""
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
    assert c["unique_vs_dup_delta_lead_size_louder_pct"] is None
    assert c["unique_vs_dup_delta_lead_size_quieter_pct"] is None
    assert c["weight_core"] == "2 unique · 50% · 2 dup · hot · 50%"
    assert (
        c["weight_lean"]
        == "unique vs dup clash · unique ok · dup hot · Δ thin · 0pp · lean vs Δ align · thin"
    )
    assert (
        c["weight"]
        == "2 unique · 50% · 2 dup · hot · 50% · unique vs dup clash · unique ok · dup hot · Δ thin · 0pp · lean vs Δ align · thin"
    )
    assert c["tone"] == "warn"


def test_string_symbols_and_bad_list_type():
    """Bare strings are junk slots — only Mapping rows count (xang1234 #498)."""
    c = build_screener_opportunity_counts(
        {
            "recommendations": ["aapl", "msft"],
            "crypto_leaders": "not-a-list",
            "stock_breakouts": [{"symbol": "AAPL"}],
        }
    )
    assert c["n_rec"] == 0
    assert c["n_crypto"] == 0
    assert c["n_brk"] == 1
    assert c["n_total"] == 1
    assert c["n_unique"] == 1
    assert c["n_dup"] == 0
    assert c["n_junk"] == 2  # two string slots; wrong-container crypto = 0
    assert c["n_junk_rec"] == 2
    assert c["n_junk_crypto"] == 0
    assert c["n_junk_brk"] == 0
    assert c["junk_lists"] == "rec"
    # sole-list → lead silent; sample gap speaks n=1 (pointer alone ≠ thin sample)
    assert c["junk_list_lead"] == ""
    assert c["junk_list_lead_share"] is None
    assert c["junk_list_sample_gap"] == "n=1"
    # 1 object + 2 junk = 3 slots → 66.7% hot · vs 1 ok · thin · 33.3%
    assert c["junk_share_pct"] == 66.7
    assert c["junk_share_severity"] == "hot"
    assert c["ok_share_pct"] == 33.3
    assert c["ok_share_severity"] == "thin"
    assert c["junk_vs_ok"] == "align · hot|thin"
    assert c["overlap"] is False
    assert c["unique_share_pct"] is None
    assert c["dup_share_pct"] is None
    assert (
        c["weight_core"]
        == "row slots · 2 junk · hot · 66.7% · in rec · n=1 · vs 1 ok · thin · 33.3%"
    )
    assert c["weight_lean"] == "junk vs ok align · hot|thin"
    assert (
        c["weight"]
        == "row slots · 2 junk · hot · 66.7% · in rec · n=1 · vs 1 ok · thin · 33.3% · junk vs ok align · hot|thin"
    )
    assert c["tone"] == "warn"


def test_junk_share_quiet_band():
    """Quiet ≤25%: absolute junk ≠ sparse damage share."""
    recs = [{"symbol": f"S{i}"} for i in range(7)] + ["junk"]
    c = build_screener_opportunity_counts(
        {
            "recommendations": recs,
            "crypto_leaders": [],
            "stock_breakouts": [],
        }
    )
    assert c["n_total"] == 7
    assert c["n_junk"] == 1
    assert c["junk_lists"] == "rec"
    # 7 + 1 = 8 slots → 12.5% quiet · vs 7 ok · strong · 87.5%
    assert c["junk_share_pct"] == 12.5
    assert c["junk_share_severity"] == "quiet"
    assert c["ok_share_pct"] == 87.5
    assert c["ok_share_severity"] == "strong"
    assert c["junk_vs_ok"] == "align · quiet|strong"
    assert c["junk_vs_ok_warn"] is False
    assert c["junk_list_sample_gap"] == "n=1"
    assert (
        c["weight_core"]
        == "row slots · 1 junk · quiet · 12.5% · in rec · n=1 · vs 7 ok · strong · 87.5%"
    )
    assert c["weight_lean"] == "junk vs ok align · quiet|strong"
    assert (
        c["weight"]
        == "row slots · 1 junk · quiet · 12.5% · in rec · n=1 · vs 7 ok · strong · 87.5% · junk vs ok align · quiet|strong"
    )
    assert c["tone"] == "warn"


def test_junk_all_slots_speaks_zero_ok():
    """All-junk lists: junk% alone hid empty Total — speak vs 0 ok."""
    c = build_screener_opportunity_counts(
        {
            "recommendations": ["a", "b"],
            "crypto_leaders": [None],
            "stock_breakouts": [],
        }
    )
    assert c["n_total"] == 0
    assert c["n_junk"] == 3
    assert c["n_junk_rec"] == 2
    assert c["n_junk_crypto"] == 1
    assert c["n_junk_brk"] == 0
    assert c["junk_lists"] == "rec · crypto"
    # rec=2 · crypto=1 → lead rec · 67% · ahead thin · +1 · vs crypto · 1 · 33%
    assert c["junk_list_lead"] == "lead rec · 67%"
    assert c["junk_list_lead_name"] == "rec"
    assert c["junk_list_lead_share"] == 67
    assert c["junk_list_lead_margin"] == "ahead thin · +1"
    assert c["junk_list_lead_margin_gap"] == 1
    assert c["junk_list_lead_sides"] == "vs crypto · 1 · 33%"
    assert c["junk_list_lead_sides_name"] == "crypto"
    assert c["junk_list_lead_sides_n"] == 1
    assert c["junk_list_lead_sides_share"] == 33
    assert c["junk_list_sample_gap"] == ""
    assert c["junk_share_pct"] == 100.0
    assert c["junk_share_severity"] == "hot"
    assert c["ok_share_pct"] == 0.0
    assert c["ok_share_severity"] == "thin"
    assert c["junk_vs_ok"] == "align · hot|thin"
    assert (
        c["weight_core"]
        == "row slots · 3 junk · hot · 100% · in rec · crypto · lead rec · 67% · ahead thin · +1 · vs crypto · 1 · 33% · vs 0 ok · thin · 0%"
    )
    assert c["weight_lean"] == "junk vs ok align · hot|thin"
    assert (
        c["weight"]
        == "row slots · 3 junk · hot · 100% · in rec · crypto · lead rec · 67% · ahead thin · +1 · vs crypto · 1 · 33% · vs 0 ok · thin · 0% · junk vs ok align · hot|thin"
    )
    assert c["tone"] == "warn"


def test_junk_list_lead_strict():
    """≥2 damaged lists + strict max → lead; pointer ≠ ownership."""
    c = build_screener_opportunity_counts(
        {
            "recommendations": ["a", "b", "c"],
            "crypto_leaders": [None],
            "stock_breakouts": ["x"],
        }
    )
    assert c["n_junk"] == 5
    assert c["n_junk_rec"] == 3
    assert c["n_junk_crypto"] == 1
    assert c["n_junk_brk"] == 1
    assert c["junk_lists"] == "rec · crypto · brk"
    assert c["junk_list_lead"] == "lead rec · 60%"
    assert c["junk_list_lead_name"] == "rec"
    assert c["junk_list_lead_share"] == 60
    # ahead wide · +2; crypto=brk=1 → tied runners → sides silent
    assert c["junk_list_lead_margin"] == "ahead wide · +2"
    assert c["junk_list_lead_margin_gap"] == 2
    assert c["junk_list_lead_sides"] == ""
    assert c["junk_list_lead_sides_name"] == ""
    assert c["junk_list_lead_sides_n"] is None
    assert c["junk_list_lead_sides_share"] is None
    assert c["junk_list_sample_gap"] == ""
    assert "lead rec · 60%" in c["weight_core"]
    assert "ahead wide · +2" in c["weight_core"]
    assert "vs crypto" not in c["weight_core"]
    assert "tied" not in c["weight_core"]
    assert c["tone"] == "warn"


def test_junk_list_sample_gap_tied():
    """≥2 damaged lists with no strict lead → tied (silent tie hid ownership)."""
    c = build_screener_opportunity_counts(
        {
            "recommendations": ["a"],
            "crypto_leaders": [None],
            "stock_breakouts": [],
        }
    )
    assert c["n_junk"] == 2
    assert c["n_junk_rec"] == 1
    assert c["n_junk_crypto"] == 1
    assert c["junk_lists"] == "rec · crypto"
    assert c["junk_list_lead"] == ""
    assert c["junk_list_lead_margin"] == ""
    assert c["junk_list_lead_sides"] == ""
    assert c["junk_list_sample_gap"] == "tied"
    assert " · tied · " in c["weight_core"]
    assert c["tone"] == "warn"


def test_junk_list_sample_gap_n1():
    """Sole damaged sleeve → n=1 (in rec alone ≠ a thin multi-list sample)."""
    c = build_screener_opportunity_counts(
        {
            "recommendations": ["a", "b"],
            "crypto_leaders": [],
            "stock_breakouts": [],
        }
    )
    assert c["n_junk"] == 2
    assert c["junk_lists"] == "rec"
    assert c["junk_list_lead"] == ""
    assert c["junk_list_sample_gap"] == "n=1"
    assert " · n=1 · " in c["weight_core"]
    assert c["tone"] == "warn"


def test_junk_list_lead_margin_sides():
    """Lead % alone ≠ ahead / #2 — soft-allow gap symbol margin/sides parity."""
    c = build_screener_opportunity_counts(
        {
            "recommendations": ["a", "b", "c", "d"],
            "crypto_leaders": [None],
            "stock_breakouts": [],
        }
    )
    assert c["n_junk_rec"] == 4
    assert c["n_junk_crypto"] == 1
    assert c["junk_list_lead"] == "lead rec · 80%"
    assert c["junk_list_lead_margin"] == "ahead wide · +3"
    assert c["junk_list_lead_margin_gap"] == 3
    assert c["junk_list_lead_sides"] == "vs crypto · 1 · 20%"
    assert c["junk_list_lead_sides_name"] == "crypto"
    assert c["junk_list_lead_sides_n"] == 1
    assert c["junk_list_lead_sides_share"] == 20
    assert "ahead wide · +3" in c["weight_core"]
    assert "vs crypto · 1 · 20%" in c["weight_core"]
    assert c["tone"] == "warn"


def test_junk_vs_ok_clash_at_half():
    """50/50: junk hot + ok mid → exactly one lean (unique/dup half clash)."""
    c = build_screener_opportunity_counts(
        {
            "recommendations": [{"symbol": "AAPL"}, "junk"],
            "crypto_leaders": [],
            "stock_breakouts": [],
        }
    )
    assert c["n_total"] == 1
    assert c["n_junk"] == 1
    assert c["junk_lists"] == "rec"
    assert c["junk_share_pct"] == 50.0
    assert c["junk_share_severity"] == "hot"
    assert c["ok_share_pct"] == 50.0
    assert c["ok_share_severity"] == "ok"
    assert c["junk_vs_ok"] == "clash · junk hot · ok ok"
    assert c["junk_vs_ok_warn"] is True
    assert c["junk_list_sample_gap"] == "n=1"
    assert (
        c["weight_core"]
        == "row slots · 1 junk · hot · 50% · in rec · n=1 · vs 1 ok · 50%"
    )
    assert c["weight_lean"] == "junk vs ok clash · junk hot · ok ok"
    assert (
        c["weight"]
        == "row slots · 1 junk · hot · 50% · in rec · n=1 · vs 1 ok · 50% · junk vs ok clash · junk hot · ok ok"
    )
    assert c["tone"] == "warn"


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
    assert c["unique_vs_dup_delta_lead_size_louder_pct"] is None
    assert c["unique_vs_dup_delta_lead_size_quieter_pct"] is None
    assert c["weight_core"] == (
        "9 unique · thin · 45% · 11 dup · hot · 55%"
    )
    assert (
        c["weight_lean"]
        == "unique vs dup align · thin|hot · lean vs Δ clash · lean · Δ mid"
    )
    assert (
        c["weight"]
        == "9 unique · thin · 45% · 11 dup · hot · 55% · unique vs dup align · thin|hot · lean vs Δ clash · lean · Δ mid"
    )
    assert c["tone"] == "warn"
