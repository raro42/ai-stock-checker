"""Offline tests for gate soft-allow audit + desk memory."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from stock_checker.gate_audit import (
    enrich_soft_allows,
    format_aging_soft_allow_tally,
    format_expired_soft_allow_tally,
    format_fresh_soft_allow_tally,
    format_soft_allow_lead_bit,
    is_soft_allow_reason,
    load_soft_allows,
    log_soft_allow,
    recent_soft_allows,
    record_soft_allow,
    soft_allow_event_key,
    soft_allow_freshness,
    soft_allow_is_expired,
    soft_allow_lead_gate,
    soft_allow_lead_margin,
    soft_allow_lead_share,
    soft_allow_lead_sides,
    soft_allow_lead_sides_share,
    soft_allow_lead_sides_share_delta,
    soft_allow_lead_sides_share_vs_delta,
    soft_allow_sample_gap,
)


def test_is_soft_allow_reason_markers() -> None:
    assert is_soft_allow_reason("regime unknown — no SPY bars")
    assert is_soft_allow_reason("skip_no_bars")
    assert is_soft_allow_reason("insufficient history")
    assert is_soft_allow_reason("empty Yahoo earnings window · fail-open")
    assert is_soft_allow_reason("malformed Yahoo earnings · fail-open")
    assert is_soft_allow_reason("SPY RS unknown — anchor gap — allow")
    assert is_soft_allow_reason("IPO RS unknown — short history — allow")
    assert not is_soft_allow_reason("SPY above SMA200")
    assert not is_soft_allow_reason("")


def test_soft_allow_short_history_count() -> None:
    """xang1234 #668: short history ≠ anchor gap ≠ bare RS unknown."""
    from datetime import datetime, timezone

    from stock_checker.gate_audit import (
        format_soft_allow_short_history_bit,
        soft_allow_short_history_bench_count,
        soft_allow_short_history_bench_share,
        soft_allow_short_history_bench_vs_young,
        soft_allow_short_history_bench_vs_young_delta,
        soft_allow_short_history_bench_vs_young_delta_lead,
        soft_allow_short_history_bench_vs_young_lean,
        soft_allow_short_history_bench_vs_young_lean_vs_delta,
        soft_allow_short_history_count,
        soft_allow_short_history_last_freshness,
        soft_allow_short_history_last_vs_bench_young,
        soft_allow_short_history_last_lead_vs_bench_young,
        soft_allow_short_history_last_share_vs_bench_young,
        soft_allow_short_history_last_ring_vs_bench_young,
        soft_allow_short_history_last_lean_vs_bench_young,
        soft_allow_short_history_last_symbol,
        soft_allow_short_history_symbol_last_vs_lead,
        soft_allow_short_history_last_vs_lead_freshness,
        soft_allow_short_history_last_lead_vs_lean,
        soft_allow_short_history_last_lead_vs_share,
        soft_allow_short_history_last_lead_vs_ring,
        soft_allow_short_history_last_share_vs_ring,
        soft_allow_short_history_last_share_vs_lean,
        soft_allow_short_history_last_ring_vs_lean,
        soft_allow_short_history_symbol_lead,
        soft_allow_short_history_symbol_lead_margin,
        soft_allow_short_history_symbol_lead_sides,
        soft_allow_short_history_symbol_sample_gap,
        soft_allow_short_history_share,
        soft_allow_short_vs_gap,
        soft_allow_short_pair_share,
        soft_allow_short_vs_gap_lean,
        soft_allow_short_vs_gap_delta,
        soft_allow_short_vs_gap_lean_vs_delta,
        soft_allow_short_vs_gap_delta_lead,
        soft_allow_short_delta_moods,
        soft_allow_short_lean_moods,
        soft_allow_short_lean_vs_delta_moods,
        soft_allow_short_delta_lead_moods,
        soft_allow_short_history_last_vs_share,
        soft_allow_short_history_last_vs_ring_share,
        soft_allow_short_history_last_vs_lean,
        soft_allow_short_history_vs_scan_clash,
        soft_allow_short_history_vs_cash_clock_clash,
        soft_allow_short_history_vs_memory_clock_clash,
        soft_allow_short_history_vs_gap_clock_clash,
        soft_allow_vs_short_history_clock_clash,
    )

    assert soft_allow_short_history_count(None) == 0
    assert soft_allow_short_history_count([]) == 0
    assert soft_allow_short_history_bench_count(None) == 0
    assert soft_allow_short_history_bench_count([]) == 0
    assert soft_allow_short_history_bench_share(None) == (0, None, "")
    assert soft_allow_short_history_bench_share([]) == (0, None, "")
    assert soft_allow_short_history_bench_vs_young(None) == (0, None, "")
    assert soft_allow_short_history_bench_vs_young([]) == (0, None, "")
    assert soft_allow_short_history_bench_vs_young_lean(None) == ("", False)
    assert soft_allow_short_history_bench_vs_young_lean([]) == ("", False)
    assert soft_allow_short_history_bench_vs_young_delta(None) == (None, "")
    assert soft_allow_short_history_bench_vs_young_delta([]) == (None, "")
    assert soft_allow_short_history_bench_vs_young_lean_vs_delta(None) == (
        "",
        False,
    )
    assert soft_allow_short_history_bench_vs_young_lean_vs_delta([]) == (
        "",
        False,
    )
    assert soft_allow_short_history_bench_vs_young_delta_lead(None) == ""
    assert soft_allow_short_history_bench_vs_young_delta_lead([]) == ""
    assert soft_allow_short_history_last_vs_bench_young(None) == ("", False)
    assert soft_allow_short_history_last_vs_bench_young([]) == ("", False)
    assert soft_allow_short_history_last_lead_vs_bench_young(None) == (
        "",
        False,
    )
    assert soft_allow_short_history_last_lead_vs_bench_young([]) == (
        "",
        False,
    )
    assert soft_allow_short_history_last_share_vs_bench_young(None) == (
        "",
        False,
    )
    assert soft_allow_short_history_last_share_vs_bench_young([]) == (
        "",
        False,
    )
    assert soft_allow_short_history_last_ring_vs_bench_young(None) == (
        "",
        False,
    )
    assert soft_allow_short_history_last_ring_vs_bench_young([]) == (
        "",
        False,
    )
    assert soft_allow_short_history_last_lean_vs_bench_young(None) == (
        "",
        False,
    )
    assert soft_allow_short_history_last_lean_vs_bench_young([]) == (
        "",
        False,
    )
    assert soft_allow_short_history_last_symbol(None) == ""
    assert soft_allow_short_history_last_symbol([]) == ""
    assert soft_allow_short_history_last_freshness(None) == ""
    assert soft_allow_short_history_last_freshness([]) == ""
    assert soft_allow_short_history_symbol_lead(None) == ("", "", None)
    assert soft_allow_short_history_symbol_lead_margin(None) is None
    assert soft_allow_short_history_symbol_lead_sides(None) is None
    assert soft_allow_short_history_symbol_sample_gap(None) == ""
    assert soft_allow_short_history_symbol_last_vs_lead(None) == ""
    assert soft_allow_short_history_last_vs_lead_freshness(None) == (
        "",
        False,
    )
    assert soft_allow_short_history_last_lead_vs_lean(None) == ("", False)
    assert soft_allow_short_history_last_lead_vs_share(None) == ("", False)
    assert soft_allow_short_history_last_lead_vs_ring(None) == ("", False)
    assert soft_allow_short_history_last_share_vs_ring(None) == ("", False)
    assert soft_allow_short_history_last_share_vs_lean(None) == ("", False)
    assert soft_allow_short_history_last_ring_vs_lean(None) == ("", False)
    assert soft_allow_short_vs_gap(None) is None
    assert soft_allow_short_pair_share(None) is None
    assert soft_allow_short_vs_gap_lean(None) == ("", False)
    assert soft_allow_short_history_last_vs_share(None) == ("", False)
    assert soft_allow_short_history_last_vs_ring_share(None) == ("", False)
    assert soft_allow_short_history_last_vs_lean(None) == ("", False)
    assert soft_allow_short_history_vs_scan_clash(None) == ("", False)
    assert soft_allow_short_history_vs_gap_clock_clash(None) == ("", False)
    assert soft_allow_vs_short_history_clock_clash(None) == ("", False)
    assert soft_allow_short_history_vs_scan_clash(
        None, scan_freshness="fresh"
    ) == ("", False)
    assert soft_allow_short_history_vs_cash_clock_clash(None) == ("", False)
    assert soft_allow_short_history_vs_cash_clock_clash(
        None, cash_band="aging"
    ) == ("", False)
    assert soft_allow_short_history_vs_memory_clock_clash(None) == ("", False)
    assert soft_allow_short_history_vs_memory_clock_clash(
        None, laya_freshness="stale", debate_freshness="aging"
    ) == ("", False)
    assert format_soft_allow_short_history_bit(None) == ""
    assert (
        soft_allow_short_history_count(
            [{"gate": "rs", "reason": "AAPL RS unknown — allow"}]
        )
        == 0
    )
    assert (
        soft_allow_short_history_last_symbol(
            [{"gate": "rs", "reason": "AAPL RS unknown — allow"}]
        )
        == ""
    )
    assert (
        soft_allow_short_history_count(
            [{"gate": "rs", "reason": "AAPL RS unknown — anchor gap — allow"}]
        )
        == 0
    )
    assert (
        soft_allow_short_history_last_symbol(
            [{"gate": "rs", "reason": "AAPL RS unknown — anchor gap — allow"}]
        )
        == ""
    )
    mixed = [
        {"gate": "rs", "reason": "IPO RS unknown — short history — allow"},
        {"gate": "rs", "reason": "AAPL RS unknown — anchor gap — allow"},
        {"gate": "rs", "reason": "MSFT RS unknown — short history — allow"},
        "junk",
    ]
    assert soft_allow_short_history_count(mixed) == 2
    assert soft_allow_short_history_bench_count(mixed) == 0
    # Newest-first ring — IPO is the cursor (#546 after #668).
    assert soft_allow_short_history_last_symbol(mixed) == "IPO"
    # No at stamp → unknown silent (cursor name still speaks).
    assert soft_allow_short_history_last_freshness(mixed) == ""
    # Two distinct short names → tied (no strict lead).
    assert soft_allow_short_history_symbol_lead(mixed) == ("", "", None)
    assert soft_allow_short_history_symbol_lead_margin(mixed) is None
    assert soft_allow_short_history_symbol_lead_sides(mixed) is None
    assert soft_allow_short_history_symbol_sample_gap(mixed) == "tied"
    assert soft_allow_short_history_symbol_last_vs_lead(mixed) == ""
    # Absolute N short · N gap ≠ pair ownership (1 gap ÷ 3 = 33% thin).
    # Short owns 67% (hot) → align · hot|thin (junk vs ok / gap vs other).
    assert soft_allow_short_vs_gap(mixed) == (
        "vs gap · thin · 1 · 33%",
        1,
        33,
        "thin",
    )
    assert soft_allow_short_pair_share(mixed) == (2, 67, "hot")
    assert soft_allow_short_vs_gap_lean(mixed) == (
        "align · hot|thin",
        False,
    )
    # Lean alone hid how far short÷pair sits (67−33=+34pp wide).
    assert soft_allow_short_vs_gap_delta(None) == (None, "")
    assert soft_allow_short_vs_gap_delta([]) == (None, "")
    assert soft_allow_short_vs_gap_delta(mixed) == (34.0, "wide")
    assert soft_allow_short_vs_gap_lean_vs_delta(mixed) == (
        "align · wide",
        True,  # adverse hot|thin + wide
    )
    # Signed +34pp hid that short owns the pair spread (unique/Yahoo Δ lead).
    assert soft_allow_short_vs_gap_delta_lead(None) == ""
    assert soft_allow_short_vs_gap_delta_lead([]) == ""
    assert soft_allow_short_vs_gap_delta_lead(mixed) == "short"
    # No bench lean/Δ → cross-pair Δ moods / lean moods silent.
    assert soft_allow_short_delta_moods(None) == ("", False)
    assert soft_allow_short_delta_moods([]) == ("", False)
    assert soft_allow_short_delta_moods(mixed) == ("", False)
    assert soft_allow_short_lean_moods(None) == ("", False)
    assert soft_allow_short_lean_moods([]) == ("", False)
    assert soft_allow_short_lean_moods(mixed) == ("", False)
    assert soft_allow_short_lean_vs_delta_moods(None) == ("", False)
    assert soft_allow_short_lean_vs_delta_moods([]) == ("", False)
    assert soft_allow_short_lean_vs_delta_moods(mixed) == ("", False)
    # No freshness stamp → last/lean silent (age extremes required).
    assert soft_allow_short_history_last_vs_lean(mixed) == ("", False)
    # Absolute N short ≠ short÷ring (2/3 ≈ 66.7% hot; gap share parity).
    assert soft_allow_short_history_share(None) == (0, None, "")
    assert soft_allow_short_history_share([]) == (0, None, "")
    assert soft_allow_short_history_share(mixed) == (2, 66.7, "hot")
    assert format_soft_allow_short_history_bit(mixed) == (
        "2 short · last IPO · tied · hot · 66.7% · vs gap · thin · 1 · 33% · "
        "short vs gap align · hot|thin · short Δ wide · +34pp · "
        "short lean/Δ align · wide · short Δ lead · short"
    )
    lead_rows = [
        {"gate": "rs", "reason": "NEW RS unknown — short history — allow"},
        {"gate": "rs", "reason": "IPO RS unknown — short history — allow"},
        {"gate": "rs", "reason": "IPO RS unknown — short history — allow"},
    ]
    assert soft_allow_short_history_symbol_lead(lead_rows) == (
        "lead IPO · 2 · 67%",
        "IPO",
        67,
    )
    assert soft_allow_short_history_symbol_sample_gap(lead_rows) == ""
    assert soft_allow_short_history_symbol_last_vs_lead(lead_rows) == (
        "last vs lead · NEW"
    )
    # Lead % alone ≠ how far ahead ≠ who is #2 (gap margin/sides parity).
    assert soft_allow_short_history_symbol_lead_margin(lead_rows) == (
        "ahead thin · +1",
        1,
        "thin",
    )
    assert soft_allow_short_history_symbol_lead_sides(lead_rows) == (
        "vs NEW · 1 · 33%",
        "NEW",
        1,
        33,
    )
    # Short-only ring → no vs gap (gap silent); ring share still speaks.
    assert soft_allow_short_vs_gap(lead_rows) is None
    assert soft_allow_short_history_share(lead_rows) == (3, 100.0, "hot")
    assert format_soft_allow_short_history_bit(lead_rows) == (
        "3 short · last NEW · lead IPO · 2 · 67% · last vs lead · NEW · "
        "ahead thin · +1 · vs NEW · 1 · 33% · hot · 100%"
    )
    sole = [
        {"gate": "rs", "reason": "IPO RS unknown — short history — allow"},
    ]
    assert soft_allow_short_history_symbol_lead(sole) == ("", "", None)
    assert soft_allow_short_history_symbol_lead_margin(sole) is None
    assert soft_allow_short_history_symbol_sample_gap(sole) == "n=1"
    assert soft_allow_short_vs_gap(sole) is None
    assert soft_allow_short_history_share(sole) == (1, 100.0, "hot")
    assert format_soft_allow_short_history_bit(sole) == (
        "1 short · last IPO · n=1 · hot · 100%"
    )
    agree_rows = [
        {"gate": "rs", "reason": "IPO RS unknown — short history — allow"},
        {"gate": "rs", "reason": "IPO RS unknown — short history — allow"},
        {"gate": "rs", "reason": "NEW RS unknown — short history — allow"},
    ]
    assert soft_allow_short_history_symbol_last_vs_lead(agree_rows) == "agree"
    assert soft_allow_short_history_symbol_lead_margin(agree_rows) == (
        "ahead thin · +1",
        1,
        "thin",
    )
    assert soft_allow_short_history_symbol_lead_sides(agree_rows) == (
        "vs NEW · 1 · 33%",
        "NEW",
        1,
        33,
    )
    assert format_soft_allow_short_history_bit(agree_rows) == (
        "3 short · last IPO · lead IPO · 2 · 67% · agree · "
        "ahead thin · +1 · vs NEW · 1 · 33% · hot · 100%"
    )
    wide_rows = [
        {"gate": "rs", "reason": "NEW RS unknown — short history — allow"},
        {"gate": "rs", "reason": "IPO RS unknown — short history — allow"},
        {"gate": "rs", "reason": "IPO RS unknown — short history — allow"},
        {"gate": "rs", "reason": "IPO RS unknown — short history — allow"},
    ]
    assert soft_allow_short_history_symbol_lead_margin(wide_rows) == (
        "ahead wide · +2",
        2,
        "wide",
    )
    assert soft_allow_short_history_symbol_lead_sides(wide_rows) == (
        "vs NEW · 1 · 25%",
        "NEW",
        1,
        25,
    )
    assert format_soft_allow_short_history_bit(wide_rows) == (
        "4 short · last NEW · lead IPO · 3 · 75% · last vs lead · NEW · "
        "ahead wide · +2 · vs NEW · 1 · 25% · hot · 100%"
    )
    # xang1234 #679: primary-benchmark short ≠ young listing.
    bench_rows = [
        {"gate": "rs", "reason": "SPY RS unknown — short history — allow"},
        {"gate": "rs", "reason": "IPO RS unknown — short history — allow"},
        {"gate": "rs", "reason": "BTC RS unknown — short history — allow"},
        {"gate": "rs", "reason": "AAPL RS unknown — anchor gap — allow"},
    ]
    assert soft_allow_short_history_count(bench_rows) == 3
    assert soft_allow_short_history_bench_count(bench_rows) == 2
    assert soft_allow_short_history_bench_share(bench_rows) == (
        2,
        66.7,
        "hot",
    )
    assert soft_allow_short_history_bench_vs_young(bench_rows) == (
        1,
        33.3,
        "thin",
    )
    assert soft_allow_short_history_bench_vs_young_lean(bench_rows) == (
        "align · hot|thin",
        False,
    )
    # Lean alone hid how far bench÷short sits (66.7−33.3=+33.4pp wide).
    assert soft_allow_short_history_bench_vs_young_delta(bench_rows) == (
        33.4,
        "wide",
    )
    assert soft_allow_short_history_bench_vs_young_lean_vs_delta(
        bench_rows
    ) == (
        "align · wide",
        True,  # adverse hot|thin + wide
    )
    # Signed +pp → bench owns the spoken Δ (short vs gap Δ lead parity).
    assert soft_allow_short_history_bench_vs_young_delta_lead(bench_rows) == (
        "bench"
    )
    # Both lean/Δ wide → Δ moods align · both wide (Yahoo share vs gap warn).
    assert soft_allow_short_delta_moods(bench_rows) == (
        "align · both wide",
        True,
    )
    # Both lean verbs align → lean moods align · both align (no warn).
    assert soft_allow_short_lean_moods(bench_rows) == (
        "align · both align",
        False,
    )
    # Lean moods align + Δ moods align → lean vs Δ moods both align.
    assert soft_allow_short_lean_vs_delta_moods(bench_rows) == (
        "align · both align",
        False,
    )
    # short + bench leads → both adverse (Screener Δ lead moods parity).
    assert soft_allow_short_delta_lead_moods(bench_rows) == (
        "align · both adverse",
        True,
    )
    # Pair wide + bench/young thin → Δ moods clash (Yahoo share vs gap).
    mood_clash = (
        [{"gate": "rs", "reason": "SPY RS unknown — short history — allow"}]
        * 6
        + [{"gate": "rs", "reason": "IPO RS unknown — short history — allow"}]
        * 5
        + [{"gate": "rs", "reason": "AAPL RS unknown — anchor gap — allow"}]
    )
    assert soft_allow_short_vs_gap_lean_vs_delta(mood_clash) == (
        "align · wide",
        True,
    )
    assert soft_allow_short_history_bench_vs_young_lean_vs_delta(
        mood_clash
    ) == ("align · thin", False)
    assert soft_allow_short_delta_moods(mood_clash) == (
        "clash · short/gap wide · bench/young thin",
        True,
    )
    # Both lean verbs still align → lean moods calm even when Δ moods clash.
    assert soft_allow_short_lean_moods(mood_clash) == (
        "align · both align",
        False,
    )
    # Lean moods align + Δ moods clash → lean vs Δ moods clash (warns).
    assert soft_allow_short_lean_vs_delta_moods(mood_clash) == (
        "clash · lean align · Δ clash",
        True,
    )
    # mood_clash: short Δ lead · short + bench Δ lead · bench → both adverse.
    assert soft_allow_short_vs_gap_delta_lead(mood_clash) == "short"
    assert soft_allow_short_history_bench_vs_young_delta_lead(mood_clash) == (
        "bench"
    )
    assert soft_allow_short_delta_lead_moods(mood_clash) == (
        "align · both adverse",
        True,
    )
    # Pair one-sided lean clash + bench lean align → lean moods clash.
    # short=4 gap=4 → short 50% hot · gap 50% mid → clash · short hot · gap ok
    # bench=3/4=75% hot · young=1/4=25% thin → align hot|thin
    lean_mood_clash = (
        [{"gate": "rs", "reason": "SPY RS unknown — short history — allow"}]
        * 3
        + [{"gate": "rs", "reason": "IPO RS unknown — short history — allow"}]
        * 1
        + [{"gate": "rs", "reason": "AAPL RS unknown — anchor gap — allow"}]
        * 4
    )
    assert soft_allow_short_vs_gap_lean(lean_mood_clash)[0].startswith(
        "clash ·"
    )
    assert soft_allow_short_history_bench_vs_young_lean(lean_mood_clash)[
        0
    ].startswith("align ·")
    assert soft_allow_short_lean_moods(lean_mood_clash) == (
        "clash · short/gap clash · bench/young align",
        True,
    )
    # Mid-Δ clash → no Δ moods → lean vs Δ moods silent (need both).
    assert soft_allow_short_delta_moods(lean_mood_clash) == ("", False)
    assert soft_allow_short_lean_vs_delta_moods(lean_mood_clash) == (
        "",
        False,
    )
    # Mid-Δ → no pair Δ lead → Δ lead moods silent (need both leads).
    assert soft_allow_short_vs_gap_delta_lead(lean_mood_clash) == ""
    assert soft_allow_short_delta_lead_moods(lean_mood_clash) == ("", False)
    # short lead + young lead → polarity clash (adverse vs healthy).
    lead_mood_clash = (
        [{"gate": "rs", "reason": "IPO RS unknown — short history — allow"}]
        * 5
        + [{"gate": "rs", "reason": "SPY RS unknown — short history — allow"}]
        * 1
        + [{"gate": "rs", "reason": "AAPL RS unknown — anchor gap — allow"}]
    )
    assert soft_allow_short_vs_gap_delta_lead(lead_mood_clash) == "short"
    assert soft_allow_short_history_bench_vs_young_delta_lead(
        lead_mood_clash
    ) == "young"
    assert soft_allow_short_delta_lead_moods(lead_mood_clash) == (
        "clash · short/gap short · bench/young young",
        True,
    )
    # No stamp → last/bench silent (fresh|expired extremes only).
    assert soft_allow_short_history_last_vs_bench_young(bench_rows) == (
        "",
        False,
    )
    assert soft_allow_short_history_last_symbol(bench_rows) == "SPY"
    assert soft_allow_short_history_share(bench_rows) == (3, 75.0, "hot")
    assert format_soft_allow_short_history_bit(bench_rows) == (
        "3 short · 2 bench · hot · 66.7% · vs 1 young · thin · 33.3% · "
        "short bench vs young align · hot|thin · "
        "short bench Δ wide · +33.4pp · short bench lean/Δ align · wide · "
        "short bench Δ lead · bench · "
        "last SPY · tied · "
        "hot · 75% · vs gap · thin · 1 · 25% · short vs gap align · hot|thin · "
        "short Δ wide · +50pp · short lean/Δ align · wide · short Δ lead · short · "
        "short Δ moods align · both wide · short lean moods align · both align · "
        "short lean vs Δ moods align · both align · "
        "short Δ lead moods align · both adverse"
    )
    # Fresh cursor + align lean → last/bench align (gap last/lean parity).
    now_bench = datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)
    fresh_bench = [
        {
            "at": "2026-10-22T11:00:00Z",
            "gate": "rs",
            "reason": "SPY RS unknown — short history — allow",
        },
        {
            "at": "2026-10-22T10:30:00Z",
            "gate": "rs",
            "reason": "IPO RS unknown — short history — allow",
        },
        {
            "at": "2026-10-22T10:00:00Z",
            "gate": "rs",
            "reason": "BTC RS unknown — short history — allow",
        },
        {
            "at": "2026-10-22T09:30:00Z",
            "gate": "rs",
            "reason": "AAPL RS unknown — anchor gap — allow",
        },
    ]
    assert soft_allow_short_history_last_vs_bench_young(
        fresh_bench, now=now_bench
    ) == ("align · fresh · hot|thin", False)
    assert "short last/bench align · fresh · hot|thin" in (
        format_soft_allow_short_history_bit(fresh_bench, now=now_bench)
    )
    # last/share align + last/bench align → short share/bench both align.
    assert soft_allow_short_history_last_vs_share(
        fresh_bench, now=now_bench
    ) == ("align · fresh · hot", False)
    assert soft_allow_short_history_last_share_vs_bench_young(
        fresh_bench, now=now_bench
    ) == ("align · both align", False)
    assert "short share/bench align · both align" in (
        format_soft_allow_short_history_bit(fresh_bench, now=now_bench)
    )
    # last/ring align + last/bench align → short ring/bench both align.
    assert soft_allow_short_history_last_vs_ring_share(
        fresh_bench, now=now_bench
    ) == ("align · fresh · hot", False)
    assert soft_allow_short_history_last_ring_vs_bench_young(
        fresh_bench, now=now_bench
    ) == ("align · both align", False)
    assert "short ring/bench align · both align" in (
        format_soft_allow_short_history_bit(fresh_bench, now=now_bench)
    )
    # last/lean align + last/bench align → short lean/bench both align.
    assert soft_allow_short_history_last_vs_lean(
        fresh_bench, now=now_bench
    ) == ("align · fresh · hot|thin", False)
    assert soft_allow_short_history_last_lean_vs_bench_young(
        fresh_bench, now=now_bench
    ) == ("align · both align", False)
    assert "short lean/bench align · both align" in (
        format_soft_allow_short_history_bit(fresh_bench, now=now_bench)
    )
    # Fresh cursor + clash lean → last/bench clash (warn).
    clash_bench = [
        {
            "at": "2026-10-22T11:00:00Z",
            "gate": "rs",
            "reason": "SPY RS unknown — short history — allow",
        },
        {
            "at": "2026-10-22T10:30:00Z",
            "gate": "rs",
            "reason": "IPO RS unknown — short history — allow",
        },
    ]
    assert soft_allow_short_history_bench_vs_young_lean(clash_bench) == (
        "clash · bench hot · young ok",
        True,
    )
    assert soft_allow_short_history_last_vs_bench_young(
        clash_bench, now=now_bench
    ) == ("clash · fresh · bench hot · young ok", True)
    # Tied SPY/IPO → no last/lead → lead/bench silent.
    assert soft_allow_short_history_last_lead_vs_bench_young(
        clash_bench, now=now_bench
    ) == ("", False)
    # No gap → last/share silent → share/bench silent.
    assert soft_allow_short_history_last_share_vs_bench_young(
        clash_bench, now=now_bench
    ) == ("", False)
    # Short-only ring still speaks last/ring → ring/bench crossed.
    assert soft_allow_short_history_last_vs_ring_share(
        clash_bench, now=now_bench
    ) == ("align · fresh · hot", False)
    assert soft_allow_short_history_last_ring_vs_bench_young(
        clash_bench, now=now_bench
    ) == ("clash · ring align · bench clash", True)
    assert "short ring/bench clash · ring align · bench clash" in (
        format_soft_allow_short_history_bit(clash_bench, now=now_bench)
    )
    # No gap → last/lean silent → lean/bench silent.
    assert soft_allow_short_history_last_lean_vs_bench_young(
        clash_bench, now=now_bench
    ) == ("", False)
    # last/lead clash + last/bench align → short lead/bench clash.
    lead_clash_bench = [
        {
            "at": "2026-10-22T11:30:00Z",
            "gate": "rs",
            "reason": "NEW RS unknown — short history — allow",
        },
        {
            "at": "2026-10-22T11:00:00Z",
            "gate": "rs",
            "reason": "SPY RS unknown — short history — allow",
        },
        {
            "at": "2026-10-22T10:30:00Z",
            "gate": "rs",
            "reason": "SPY RS unknown — short history — allow",
        },
        {
            "at": "2026-10-22T10:00:00Z",
            "gate": "rs",
            "reason": "BTC RS unknown — short history — allow",
        },
    ]
    assert soft_allow_short_history_last_vs_lead_freshness(
        lead_clash_bench, now=now_bench
    ) == ("clash · fresh · vs NEW", True)
    assert soft_allow_short_history_last_vs_bench_young(
        lead_clash_bench, now=now_bench
    ) == ("align · fresh · hot|thin", False)
    assert soft_allow_short_history_last_lead_vs_bench_young(
        lead_clash_bench, now=now_bench
    ) == ("clash · lead clash · bench align", True)
    assert "short lead/bench clash · lead clash · bench align" in (
        format_soft_allow_short_history_bit(lead_clash_bench, now=now_bench)
    )
    # Same verb both clash → short lead/bench align · both clash (warn).
    expired_lead_clash_bench = [
        {
            "at": "2026-10-20T11:00:00Z",
            "gate": "rs",
            "reason": "SPY RS unknown — short history — allow",
        },
        {
            "at": "2026-10-20T10:30:00Z",
            "gate": "rs",
            "reason": "SPY RS unknown — short history — allow",
        },
        {
            "at": "2026-10-20T10:15:00Z",
            "gate": "rs",
            "reason": "BTC RS unknown — short history — allow",
        },
        {
            "at": "2026-10-20T10:00:00Z",
            "gate": "rs",
            "reason": "NEW RS unknown — short history — allow",
        },
    ]
    assert soft_allow_short_history_last_vs_lead_freshness(
        expired_lead_clash_bench, now=now_bench
    ) == ("clash · expired · agree", True)
    assert soft_allow_short_history_last_vs_bench_young(
        expired_lead_clash_bench, now=now_bench
    ) == ("clash · expired · hot|thin", True)
    assert soft_allow_short_history_last_lead_vs_bench_young(
        expired_lead_clash_bench, now=now_bench
    ) == ("align · both clash", True)
    assert "short lead/bench align · both clash" in (
        format_soft_allow_short_history_bit(
            expired_lead_clash_bench, now=now_bench
        )
    )
    # last/share clash + last/bench clash → short share/bench both clash.
    # 2 short + 6 gap → pair 25% quiet; fresh↔quiet → last/share clash;
    # SPY+IPO lean clash; fresh↔clash → last/bench clash.
    share_both_clash_bench = [
        {
            "at": "2026-10-22T11:00:00Z",
            "gate": "rs",
            "reason": "SPY RS unknown — short history — allow",
        },
        {
            "at": "2026-10-22T10:30:00Z",
            "gate": "rs",
            "reason": "IPO RS unknown — short history — allow",
        },
        {
            "at": "2026-10-22T10:00:00Z",
            "gate": "rs",
            "reason": "AAPL RS unknown — anchor gap — allow",
        },
        {
            "at": "2026-10-22T09:30:00Z",
            "gate": "rs",
            "reason": "MSFT RS unknown — anchor gap — allow",
        },
        {
            "at": "2026-10-22T09:00:00Z",
            "gate": "rs",
            "reason": "NVDA RS unknown — anchor gap — allow",
        },
        {
            "at": "2026-10-22T08:30:00Z",
            "gate": "rs",
            "reason": "AMD RS unknown — anchor gap — allow",
        },
        {
            "at": "2026-10-22T08:00:00Z",
            "gate": "rs",
            "reason": "META RS unknown — anchor gap — allow",
        },
        {
            "at": "2026-10-22T07:30:00Z",
            "gate": "rs",
            "reason": "GOOG RS unknown — anchor gap — allow",
        },
    ]
    assert soft_allow_short_history_last_vs_share(
        share_both_clash_bench, now=now_bench
    ) == ("clash · fresh · quiet", True)
    assert soft_allow_short_history_last_vs_bench_young(
        share_both_clash_bench, now=now_bench
    ) == ("clash · fresh · bench hot · young ok", True)
    assert soft_allow_short_history_last_share_vs_bench_young(
        share_both_clash_bench, now=now_bench
    ) == ("align · both clash", True)
    assert "short share/bench align · both clash" in (
        format_soft_allow_short_history_bit(
            share_both_clash_bench, now=now_bench
        )
    )
    # last/ring clash + last/bench clash → short ring/bench both clash.
    assert soft_allow_short_history_last_vs_ring_share(
        share_both_clash_bench, now=now_bench
    ) == ("clash · fresh · quiet", True)
    assert soft_allow_short_history_last_ring_vs_bench_young(
        share_both_clash_bench, now=now_bench
    ) == ("align · both clash", True)
    assert "short ring/bench align · both clash" in (
        format_soft_allow_short_history_bit(
            share_both_clash_bench, now=now_bench
        )
    )
    # last/lean align (fresh↔quiet|strong) + last/bench clash → crossed.
    assert soft_allow_short_history_last_vs_lean(
        share_both_clash_bench, now=now_bench
    ) == ("align · fresh · quiet|strong", False)
    assert soft_allow_short_history_last_lean_vs_bench_young(
        share_both_clash_bench, now=now_bench
    ) == ("clash · lean align · bench clash", True)
    assert "short lean/bench clash · lean align · bench clash" in (
        format_soft_allow_short_history_bit(
            share_both_clash_bench, now=now_bench
        )
    )
    # Fresh + hot pair (align share) + clash lean (clash bench) → crossed.
    share_cross_bench = [
        {
            "at": "2026-10-22T11:00:00Z",
            "gate": "rs",
            "reason": "SPY RS unknown — short history — allow",
        },
        {
            "at": "2026-10-22T10:30:00Z",
            "gate": "rs",
            "reason": "IPO RS unknown — short history — allow",
        },
        {
            "at": "2026-10-22T10:00:00Z",
            "gate": "rs",
            "reason": "AAPL RS unknown — anchor gap — allow",
        },
    ]
    assert soft_allow_short_history_last_vs_share(
        share_cross_bench, now=now_bench
    ) == ("align · fresh · hot", False)
    assert soft_allow_short_history_last_vs_bench_young(
        share_cross_bench, now=now_bench
    ) == ("clash · fresh · bench hot · young ok", True)
    assert soft_allow_short_history_last_share_vs_bench_young(
        share_cross_bench, now=now_bench
    ) == ("clash · share align · bench clash", True)
    assert "short share/bench clash · share align · bench clash" in (
        format_soft_allow_short_history_bit(
            share_cross_bench, now=now_bench
        )
    )
    # last/ring align + last/bench clash → short ring/bench crossed.
    assert soft_allow_short_history_last_vs_ring_share(
        share_cross_bench, now=now_bench
    ) == ("align · fresh · hot", False)
    assert soft_allow_short_history_last_ring_vs_bench_young(
        share_cross_bench, now=now_bench
    ) == ("clash · ring align · bench clash", True)
    assert "short ring/bench clash · ring align · bench clash" in (
        format_soft_allow_short_history_bit(
            share_cross_bench, now=now_bench
        )
    )
    # last/lean align + last/bench clash → short lean/bench crossed.
    assert soft_allow_short_history_last_vs_lean(
        share_cross_bench, now=now_bench
    ) == ("align · fresh · hot|thin", False)
    assert soft_allow_short_history_last_lean_vs_bench_young(
        share_cross_bench, now=now_bench
    ) == ("clash · lean align · bench clash", True)
    assert "short lean/bench clash · lean align · bench clash" in (
        format_soft_allow_short_history_bit(
            share_cross_bench, now=now_bench
        )
    )
    assert soft_allow_short_history_bench_count(
        [{"gate": "rs", "reason": "IPO RS unknown — short history — allow"}]
    ) == 0
    assert soft_allow_short_history_bench_count(
        [{"gate": "rs", "reason": "SPY RS unknown — allow"}]
    ) == 0
    # Gap last-freshness parity: last SYM ≠ live fail-open.
    # Aging is >12h and ≤24h; expired is >24h.
    now = datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)
    aged = [
        {
            "at": "2026-10-21T18:00:00Z",
            "gate": "rs",
            "reason": "IPO RS unknown — short history — allow",
        },
        {
            "at": "2026-10-22T11:00:00Z",
            "gate": "rs",
            "reason": "AAPL RS unknown — anchor gap — allow",
        },
    ]
    assert soft_allow_short_history_last_freshness(aged, now=now) == "aging"
    # Aging mid → last/lean silent (fresh|expired extremes only).
    assert soft_allow_short_history_last_vs_lean(aged, now=now) == (
        "",
        False,
    )
    assert format_soft_allow_short_history_bit(aged, now=now) == (
        "1 short · last IPO · aging · clash · short aging · gap fresh"
        " · n=1 · hot · 50% · vs gap · 1 · 50% · "
        "short vs gap clash · short hot · gap ok · "
        "short lean/Δ clash · lean · Δ mid"
    )
    expired = [
        {
            "at": "2026-10-20T11:00:00Z",
            "gate": "rs",
            "reason": "IPO RS unknown — short history — allow",
        },
    ]
    assert soft_allow_short_history_last_freshness(expired, now=now) == (
        "expired"
    )
    assert soft_allow_short_history_last_vs_ring_share(
        expired, now=now
    ) == ("clash · expired · hot", True)
    # Short-only ring: pair last/share silent; ring last/ring speaks.
    assert soft_allow_short_history_last_vs_share(expired, now=now) == (
        "",
        False,
    )
    assert format_soft_allow_short_history_bit(expired, now=now) == (
        "1 short · last IPO · expired · n=1 · hot · 100% · short last/ring clash · expired · hot"
    )
    # Short≠scan: expired cursor ≠ fresh scan; same band silent
    # (gap≠scan / xang1234 #549 parity).
    assert soft_allow_short_history_vs_scan_clash(
        expired, scan_freshness="fresh", now=now
    ) == ("clash · short expired · scan fresh", True)
    # Sole pins short-only · scan-only (gap≠scan / soft≠scan + #647 /
    # #531 / #668).
    assert soft_allow_short_history_vs_scan_clash(
        expired,
        scan_freshness="fresh",
        now=now,
        short_pin_size=" · short-only",
        scan_pin_size=" · scan-only",
    ) == (
        "clash · short expired · scan fresh · short-only · scan-only",
        True,
    )
    assert format_soft_allow_short_history_bit(
        expired, now=now, scan_freshness="fresh"
    ) == (
        "1 short · last IPO · expired · clash · short expired · scan fresh"
        " · n=1 · hot · 100% · short last/ring clash · expired · hot"
    )
    assert format_soft_allow_short_history_bit(
        expired,
        now=now,
        scan_freshness="fresh",
        short_pin_size=" · short-only",
        scan_pin_size=" · scan-only",
    ) == (
        "1 short · last IPO · expired · clash · short expired · scan fresh"
        " · short-only · scan-only · n=1 · hot · 100% · short last/ring clash · expired · hot"
    )
    assert soft_allow_short_history_vs_scan_clash(
        expired, scan_freshness="stale", now=now
    ) == ("", False)
    # Short≠cash: expired≡stale vs aging speaks; same band silent
    # (gap≠cash / short≠scan parity).
    assert soft_allow_short_history_vs_cash_clock_clash(
        expired, cash_band="aging", now=now
    ) == ("clash · short expired · cash aging", True)
    assert soft_allow_short_history_vs_cash_clock_clash(
        expired,
        cash_band="aging",
        now=now,
        short_pin_size=" · short-only",
        cash_pin_size=" · US-only",
    ) == (
        "clash · short expired · cash aging · short-only · US-only",
        True,
    )
    assert format_soft_allow_short_history_bit(
        expired, now=now, cash_band="aging"
    ) == (
        "1 short · last IPO · expired · clash · short expired · cash aging"
        " · n=1 · hot · 100% · short last/ring clash · expired · hot"
    )
    assert soft_allow_short_history_vs_cash_clock_clash(
        expired, cash_band="stale", now=now
    ) == ("", False)
    # Short≠memory: expired≡stale vs fresh laya speaks; same band silent
    # (gap≠memory / soft≠memory / short≠scan parity).
    assert soft_allow_short_history_vs_memory_clock_clash(
        expired,
        laya_freshness="fresh",
        debate_freshness="aging",
        now=now,
    ) == ("clash · short expired · laya fresh · debate aging", True)
    assert soft_allow_short_history_vs_memory_clock_clash(
        expired,
        laya_freshness="fresh",
        debate_freshness="aging",
        now=now,
        short_pin_size=" · short-only",
        memory_pin_size=" · ×2 · 100%",
    ) == (
        "clash · short expired · laya fresh · debate aging"
        " · short-only · ×2 · 100%",
        True,
    )
    # Keep-scan / keep-cash when short matches archive or cash (gap≠*
    # keep-pin parity + #660 / #647 / #531).
    assert soft_allow_short_history_vs_cash_clock_clash(
        expired,
        cash_band="aging",
        now=now,
        short_pin_size="short-only",
        cash_pin_size="US-only",
        keep_scan_pin_size=" · scan-only",
    ) == (
        "clash · short expired · cash aging · short-only · US-only"
        " · scan-only",
        True,
    )
    assert soft_allow_short_history_vs_memory_clock_clash(
        expired,
        laya_freshness="fresh",
        debate_freshness="aging",
        now=now,
        short_pin_size="short-only",
        memory_pin_size="×2 · 100%",
        keep_scan_pin_size="scan-only",
        keep_cash_pin_size="US-only",
    ) == (
        "clash · short expired · laya fresh · debate aging"
        " · short-only · ×2 · 100% · scan-only · US-only",
        True,
    )
    assert soft_allow_short_history_vs_scan_clash(
        expired,
        scan_freshness="fresh",
        now=now,
        short_pin_size="short-only",
        scan_pin_size="scan-only",
        keep_cash_pin_size="US-only",
        keep_memory_pin_size="laya-only",
    ) == (
        "clash · short expired · scan fresh · short-only · scan-only"
        " · US-only · laya-only",
        True,
    )
    # Keep-gap when short matches gap cursor (soft≠scan keep-gap +
    # #660 / #647 / #531).
    assert soft_allow_short_history_vs_scan_clash(
        expired,
        scan_freshness="fresh",
        now=now,
        short_pin_size="short-only",
        scan_pin_size="scan-only",
        keep_cash_pin_size="US-only",
        keep_memory_pin_size="laya-only",
        keep_gap_pin_size="gap-only",
    ) == (
        "clash · short expired · scan fresh · short-only · scan-only"
        " · US-only · laya-only · gap-only",
        True,
    )
    assert soft_allow_short_history_vs_cash_clock_clash(
        expired,
        cash_band="aging",
        now=now,
        short_pin_size="short-only",
        cash_pin_size="US-only",
        keep_scan_pin_size="scan-only",
        keep_gap_pin_size="gap-only",
    ) == (
        "clash · short expired · cash aging · short-only · US-only"
        " · scan-only · gap-only",
        True,
    )
    assert soft_allow_short_history_vs_memory_clock_clash(
        expired,
        laya_freshness="fresh",
        debate_freshness="aging",
        now=now,
        short_pin_size="short-only",
        memory_pin_size="×2 · 100%",
        keep_scan_pin_size="scan-only",
        keep_cash_pin_size="US-only",
        keep_gap_pin_size="gap-only",
    ) == (
        "clash · short expired · laya fresh · debate aging"
        " · short-only · ×2 · 100% · scan-only · US-only · gap-only",
        True,
    )
    assert format_soft_allow_short_history_bit(
        expired,
        now=now,
        scan_freshness="fresh",
        keep_gap_pin_size="gap-only",
    ) == (
        "1 short · last IPO · expired · clash · short expired · scan fresh"
        " · gap-only · n=1 · hot · 100% · short last/ring clash · expired · hot"
    )
    assert soft_allow_short_history_vs_memory_clock_clash(
        expired,
        laya_freshness="stale",
        debate_freshness="stale",
        now=now,
    ) == ("", False)
    assert format_soft_allow_short_history_bit(
        expired,
        now=now,
        laya_freshness="fresh",
        debate_freshness="",
    ) == (
        "1 short · last IPO · expired · clash · short expired · laya fresh"
        " · n=1 · hot · 100% · short last/ring clash · expired · hot"
    )
    # Short matching scan + cash aging — both clash bits on one line.
    assert format_soft_allow_short_history_bit(
        expired,
        now=now,
        scan_freshness="fresh",
        cash_band="aging",
    ) == (
        "1 short · last IPO · expired · clash · short expired · scan fresh"
        " · clash · short expired · cash aging · n=1 · hot · 100% · short last/ring clash · expired · hot"
    )
    # Short↔scan↔cash↔memory: all three generation clashes on one line.
    assert format_soft_allow_short_history_bit(
        expired,
        now=now,
        scan_freshness="fresh",
        cash_band="aging",
        laya_freshness="fresh",
        debate_freshness="",
    ) == (
        "1 short · last IPO · expired · clash · short expired · scan fresh"
        " · clash · short expired · cash aging"
        " · clash · short expired · laya fresh · n=1 · hot · 100% · short last/ring clash · expired · hot"
    )
    # Short≠gap: expired short vs fresh gap cursor (soft≠gap / short≠scan
    # parity; count lean ≠ clock). Same band silent.
    short_vs_gap_rows = [
        {
            "at": "2026-10-21T06:00:00Z",
            "gate": "rs",
            "reason": "IPO RS unknown — short history — allow",
        },
        {
            "at": "2026-10-22T11:30:00Z",
            "gate": "rs",
            "reason": "AAPL RS unknown — anchor gap — allow",
        },
    ]
    assert soft_allow_short_history_vs_gap_clock_clash(
        short_vs_gap_rows, now=now
    ) == ("clash · short expired · gap fresh", True)
    assert soft_allow_short_history_vs_gap_clock_clash(
        short_vs_gap_rows,
        now=now,
        short_pin_size="short-only",
        gap_pin_size="gap-only",
    ) == (
        "clash · short expired · gap fresh · short-only · gap-only",
        True,
    )
    assert format_soft_allow_short_history_bit(
        short_vs_gap_rows, now=now
    ) == (
        "1 short · last IPO · expired · clash · short expired · gap fresh"
        " · n=1 · hot · 50% · short last/ring clash · expired · hot · vs gap · 1 · 50%"
        " · short last/share clash · expired · hot"
        " · short share/ring align · both clash"
        " · short vs gap clash · short hot · gap ok"
        " · short lean/Δ clash · lean · Δ mid"
        " · short last/lean align · expired · short hot · gap ok"
        " · short share/lean clash · share clash · lean align"
        " · short ring/lean clash · ring clash · lean align"
    )
    assert soft_allow_short_history_vs_gap_clock_clash(
        short_vs_gap_rows,
        now=now,
        short_pin_size="short-only",
        gap_pin_size="gap-only",
        keep_scan_pin_size="scan-only",
        keep_cash_pin_size="US-only",
        keep_memory_pin_size="laya-only",
    ) == (
        "clash · short expired · gap fresh · short-only · gap-only"
        " · scan-only · US-only · laya-only",
        True,
    )
    same_gap_band = [
        {
            "at": "2026-10-22T11:30:00Z",
            "gate": "rs",
            "reason": "IPO RS unknown — short history — allow",
        },
        {
            "at": "2026-10-22T11:00:00Z",
            "gate": "rs",
            "reason": "AAPL RS unknown — anchor gap — allow",
        },
    ]
    assert soft_allow_short_history_vs_gap_clock_clash(
        same_gap_band, now=now
    ) == ("", False)
    fresh = [
        {
            "at": "2026-10-22T11:30:00Z",
            "gate": "rs",
            "reason": "IPO RS unknown — short history — allow",
        },
    ]
    assert soft_allow_short_history_last_freshness(fresh, now=now) == "fresh"
    # Fresh alone (no lean) → last/lean silent.
    assert soft_allow_short_history_last_vs_lean(fresh, now=now) == (
        "",
        False,
    )
    assert format_soft_allow_short_history_bit(fresh, now=now) == (
        "1 short · last IPO · fresh · n=1 · hot · 100% · short last/ring align · fresh · hot"
    )
    # Fresh + short/gap align → last/lean align (gap last/lean parity).
    fresh_align = [
        {
            "at": "2026-10-22T11:30:00Z",
            "gate": "rs",
            "reason": "IPO RS unknown — short history — allow",
        },
        {
            "at": "2026-10-22T11:00:00Z",
            "gate": "rs",
            "reason": "NEW RS unknown — short history — allow",
        },
        {
            "at": "2026-10-22T10:30:00Z",
            "gate": "rs",
            "reason": "AAPL RS unknown — anchor gap — allow",
        },
    ]
    assert soft_allow_short_vs_gap_lean(fresh_align) == (
        "align · hot|thin",
        False,
    )
    assert soft_allow_short_history_last_vs_share(
        fresh_align, now=now
    ) == ("align · fresh · hot", False)
    assert soft_allow_short_history_last_vs_ring_share(
        fresh_align, now=now
    ) == ("align · fresh · hot", False)
    assert soft_allow_short_history_last_vs_lean(
        fresh_align, now=now
    ) == ("align · fresh · hot|thin", False)
    assert soft_allow_short_history_last_share_vs_lean(
        fresh_align, now=now
    ) == ("align · both align", False)
    assert soft_allow_short_history_last_ring_vs_lean(
        fresh_align, now=now
    ) == ("align · both align", False)
    assert soft_allow_short_history_last_share_vs_ring(
        fresh_align, now=now
    ) == ("align · both align", False)
    assert format_soft_allow_short_history_bit(fresh_align, now=now) == (
        "2 short · last IPO · fresh · tied · hot · 66.7% · short last/ring align · fresh · hot · vs gap · thin · 1 · 33% · "
        "short last/share align · fresh · hot · "
        "short share/ring align · both align · "
        "short vs gap align · hot|thin · "
        "short Δ wide · +34pp · short lean/Δ align · wide · short Δ lead · short · "
        "short last/lean align · fresh · hot|thin · "
        "short share/lean align · both align · "
        "short ring/lean align · both align"
    )
    # Expired + short/gap align → last/lean clash (warn).
    expired_align = [
        {
            "at": "2026-10-20T11:00:00Z",
            "gate": "rs",
            "reason": "IPO RS unknown — short history — allow",
        },
        {
            "at": "2026-10-20T10:30:00Z",
            "gate": "rs",
            "reason": "NEW RS unknown — short history — allow",
        },
        {
            "at": "2026-10-20T10:00:00Z",
            "gate": "rs",
            "reason": "AAPL RS unknown — anchor gap — allow",
        },
    ]
    assert soft_allow_short_history_last_freshness(
        expired_align, now=now
    ) == "expired"
    assert soft_allow_short_history_last_vs_share(
        expired_align, now=now
    ) == ("clash · expired · hot", True)
    assert soft_allow_short_history_last_vs_ring_share(
        expired_align, now=now
    ) == ("clash · expired · hot", True)
    assert soft_allow_short_history_last_vs_lean(
        expired_align, now=now
    ) == ("clash · expired · hot|thin", True)
    assert soft_allow_short_history_last_share_vs_lean(
        expired_align, now=now
    ) == ("align · both clash", True)
    assert soft_allow_short_history_last_ring_vs_lean(
        expired_align, now=now
    ) == ("align · both clash", True)
    assert soft_allow_short_history_last_share_vs_ring(
        expired_align, now=now
    ) == ("align · both clash", True)
    assert format_soft_allow_short_history_bit(expired_align, now=now) == (
        "2 short · last IPO · expired · tied · hot · 66.7% · short last/ring clash · expired · hot · vs gap · thin · 1 · 33% · "
        "short last/share clash · expired · hot · "
        "short share/ring align · both clash · "
        "short vs gap align · hot|thin · "
        "short Δ wide · +34pp · short lean/Δ align · wide · short Δ lead · short · "
        "short last/lean clash · expired · hot|thin · "
        "short share/lean align · both clash · "
        "short ring/lean align · both clash"
    )
    # Gap last/lead freshness parity: bare agree ≠ live cursor match.
    # Fresh + agree → short last/lead align; expired + agree → clash warn.
    fresh_agree = [
        {
            "at": "2026-10-22T11:30:00Z",
            "gate": "rs",
            "reason": "IPO RS unknown — short history — allow",
        },
        {
            "at": "2026-10-22T11:00:00Z",
            "gate": "rs",
            "reason": "IPO RS unknown — short history — allow",
        },
        {
            "at": "2026-10-22T10:30:00Z",
            "gate": "rs",
            "reason": "NEW RS unknown — short history — allow",
        },
    ]
    assert soft_allow_short_history_symbol_last_vs_lead(fresh_agree) == (
        "agree"
    )
    assert soft_allow_short_history_last_freshness(
        fresh_agree, now=now
    ) == "fresh"
    assert soft_allow_short_history_last_vs_lead_freshness(
        fresh_agree, now=now
    ) == ("align · fresh · agree", False)
    assert format_soft_allow_short_history_bit(fresh_agree, now=now) == (
        "3 short · last IPO · fresh · lead IPO · 2 · 67% · agree · "
        "short last/lead align · fresh · agree · "
        "ahead thin · +1 · vs NEW · 1 · 33% · hot · 100% · short last/ring align · fresh · hot · "
        "short lead/ring align · both align"
    )
    expired_agree = [
        {
            "at": "2026-10-20T11:00:00Z",
            "gate": "rs",
            "reason": "IPO RS unknown — short history — allow",
        },
        {
            "at": "2026-10-20T10:30:00Z",
            "gate": "rs",
            "reason": "IPO RS unknown — short history — allow",
        },
        {
            "at": "2026-10-20T10:00:00Z",
            "gate": "rs",
            "reason": "NEW RS unknown — short history — allow",
        },
    ]
    assert soft_allow_short_history_last_vs_lead_freshness(
        expired_agree, now=now
    ) == ("clash · expired · agree", True)
    assert format_soft_allow_short_history_bit(expired_agree, now=now) == (
        "3 short · last IPO · expired · lead IPO · 2 · 67% · agree · "
        "short last/lead clash · expired · agree · "
        "ahead thin · +1 · vs NEW · 1 · 33% · hot · 100% · short last/ring clash · expired · hot · "
        "short lead/ring align · both clash"
    )
    # Fresh + name clash → short last/lead clash warn.
    fresh_clash = [
        {
            "at": "2026-10-22T11:30:00Z",
            "gate": "rs",
            "reason": "NEW RS unknown — short history — allow",
        },
        {
            "at": "2026-10-22T11:00:00Z",
            "gate": "rs",
            "reason": "IPO RS unknown — short history — allow",
        },
        {
            "at": "2026-10-22T10:30:00Z",
            "gate": "rs",
            "reason": "IPO RS unknown — short history — allow",
        },
    ]
    assert soft_allow_short_history_symbol_last_vs_lead(fresh_clash) == (
        "last vs lead · NEW"
    )
    assert soft_allow_short_history_last_vs_lead_freshness(
        fresh_clash, now=now
    ) == ("clash · fresh · vs NEW", True)
    assert format_soft_allow_short_history_bit(fresh_clash, now=now) == (
        "3 short · last NEW · fresh · lead IPO · 2 · 67% · "
        "last vs lead · NEW · short last/lead clash · fresh · vs NEW · "
        "ahead thin · +1 · vs NEW · 1 · 33% · hot · 100% · short last/ring align · fresh · hot · "
        "short lead/ring clash · lead clash · ring align"
    )
    # last/lead + last/lean together: crossed verbs → short lead/lean clash.
    fresh_clash_vs_gap = [
        {
            "at": "2026-10-22T11:30:00Z",
            "gate": "rs",
            "reason": "NEW RS unknown — short history — allow",
        },
        {
            "at": "2026-10-22T11:00:00Z",
            "gate": "rs",
            "reason": "IPO RS unknown — short history — allow",
        },
        {
            "at": "2026-10-22T10:30:00Z",
            "gate": "rs",
            "reason": "IPO RS unknown — short history — allow",
        },
        {
            "at": "2026-10-22T10:00:00Z",
            "gate": "rs",
            "reason": "AAPL RS unknown — anchor gap — allow",
        },
    ]
    assert soft_allow_short_history_last_vs_lead_freshness(
        fresh_clash_vs_gap, now=now
    ) == ("clash · fresh · vs NEW", True)
    assert soft_allow_short_history_last_vs_lean(
        fresh_clash_vs_gap, now=now
    ) == ("align · fresh · hot|thin", False)
    assert soft_allow_short_history_last_lead_vs_lean(
        fresh_clash_vs_gap, now=now
    ) == ("clash · lead clash · lean align", True)
    assert soft_allow_short_history_last_vs_share(
        fresh_clash_vs_gap, now=now
    ) == ("align · fresh · hot", False)
    assert soft_allow_short_history_last_lead_vs_share(
        fresh_clash_vs_gap, now=now
    ) == ("clash · lead clash · share align", True)
    assert soft_allow_short_history_last_lead_vs_ring(
        fresh_clash_vs_gap, now=now
    ) == ("clash · lead clash · ring align", True)
    assert soft_allow_short_history_last_share_vs_ring(
        fresh_clash_vs_gap, now=now
    ) == ("align · both align", False)
    assert soft_allow_short_history_last_share_vs_lean(
        fresh_clash_vs_gap, now=now
    ) == ("align · both align", False)
    assert soft_allow_short_history_last_ring_vs_lean(
        fresh_clash_vs_gap, now=now
    ) == ("align · both align", False)
    assert format_soft_allow_short_history_bit(
        fresh_clash_vs_gap, now=now
    ) == (
        "3 short · last NEW · fresh · lead IPO · 2 · 67% · "
        "last vs lead · NEW · short last/lead clash · fresh · vs NEW · "
        "ahead thin · +1 · vs NEW · 1 · 33% · hot · 75% · short last/ring align · fresh · hot · "
        "short lead/ring clash · lead clash · ring align · "
        "vs gap · thin · 1 · 25% · short last/share align · fresh · hot · "
        "short lead/share clash · lead clash · share align · "
        "short share/ring align · both align · "
        "short vs gap align · hot|thin · "
        "short Δ wide · +50pp · short lean/Δ align · wide · short Δ lead · short · "
        "short last/lean align · fresh · hot|thin · "
        "short lead/lean clash · lead clash · lean align · "
        "short share/lean align · both align · "
        "short ring/lean align · both align"
    )
    # Same verb both clash → short lead/lean align · both clash (warn).
    expired_agree_vs_gap = [
        {
            "at": "2026-10-20T11:00:00Z",
            "gate": "rs",
            "reason": "IPO RS unknown — short history — allow",
        },
        {
            "at": "2026-10-20T10:30:00Z",
            "gate": "rs",
            "reason": "IPO RS unknown — short history — allow",
        },
        {
            "at": "2026-10-20T10:15:00Z",
            "gate": "rs",
            "reason": "NEW RS unknown — short history — allow",
        },
        {
            "at": "2026-10-20T10:00:00Z",
            "gate": "rs",
            "reason": "AAPL RS unknown — anchor gap — allow",
        },
    ]
    assert soft_allow_short_history_last_vs_lead_freshness(
        expired_agree_vs_gap, now=now
    ) == ("clash · expired · agree", True)
    assert soft_allow_short_history_last_vs_lean(
        expired_agree_vs_gap, now=now
    ) == ("clash · expired · hot|thin", True)
    assert soft_allow_short_history_last_lead_vs_lean(
        expired_agree_vs_gap, now=now
    ) == ("align · both clash", True)
    assert soft_allow_short_history_last_vs_share(
        expired_agree_vs_gap, now=now
    ) == ("clash · expired · hot", True)
    assert soft_allow_short_history_last_lead_vs_share(
        expired_agree_vs_gap, now=now
    ) == ("align · both clash", True)
    assert soft_allow_short_history_last_lead_vs_ring(
        expired_agree_vs_gap, now=now
    ) == ("align · both clash", True)
    assert soft_allow_short_history_last_share_vs_ring(
        expired_agree_vs_gap, now=now
    ) == ("align · both clash", True)
    assert soft_allow_short_history_last_share_vs_lean(
        expired_agree_vs_gap, now=now
    ) == ("align · both clash", True)
    assert soft_allow_short_history_last_ring_vs_lean(
        expired_agree_vs_gap, now=now
    ) == ("align · both clash", True)
    assert format_soft_allow_short_history_bit(
        expired_agree_vs_gap, now=now
    ) == (
        "3 short · last IPO · expired · lead IPO · 2 · 67% · "
        "agree · short last/lead clash · expired · agree · "
        "ahead thin · +1 · vs NEW · 1 · 33% · hot · 75% · short last/ring clash · expired · hot · "
        "short lead/ring align · both clash · "
        "vs gap · thin · 1 · 25% · short last/share clash · expired · hot · "
        "short lead/share align · both clash · "
        "short share/ring align · both clash · "
        "short vs gap align · hot|thin · "
        "short Δ wide · +50pp · short lean/Δ align · wide · short Δ lead · short · "
        "short last/lean clash · expired · hot|thin · "
        "short lead/lean align · both clash · "
        "short share/lean align · both clash · "
        "short ring/lean align · both clash"
    )
    # Pair hot + ring quiet → last/share align vs last/ring clash → share/ring clash.
    fresh_share_ring_clash = [
        {
            "at": "2026-10-22T11:30:00Z",
            "gate": "rs",
            "reason": "IPO RS unknown — short history — allow",
        },
        {
            "at": "2026-10-22T11:00:00Z",
            "gate": "rs",
            "reason": "AAPL RS unknown — anchor gap — allow",
        },
        {
            "at": "2026-10-22T10:45:00Z",
            "gate": "breadth",
            "reason": "MSFT soft allow — breadth thin — allow",
        },
        {
            "at": "2026-10-22T10:30:00Z",
            "gate": "breadth",
            "reason": "NVDA soft allow — breadth thin — allow",
        },
        {
            "at": "2026-10-22T10:15:00Z",
            "gate": "regime",
            "reason": "AMD soft allow — regime skip — allow",
        },
    ]
    assert soft_allow_short_history_last_vs_share(
        fresh_share_ring_clash, now=now
    ) == ("align · fresh · hot", False)
    assert soft_allow_short_history_last_vs_ring_share(
        fresh_share_ring_clash, now=now
    ) == ("clash · fresh · quiet", True)
    assert soft_allow_short_history_last_share_vs_ring(
        fresh_share_ring_clash, now=now
    ) == ("clash · share align · ring clash", True)
    assert "short share/ring clash · share align · ring clash" in (
        format_soft_allow_short_history_bit(fresh_share_ring_clash, now=now)
    )


def test_soft_allow_anchor_gap_count() -> None:
    from stock_checker.gate_audit import (
        soft_allow_anchor_gap_count,
        soft_allow_anchor_gap_last_freshness,
        soft_allow_anchor_gap_last_symbol,
        soft_allow_anchor_gap_symbol_last_vs_lead,
        soft_allow_anchor_gap_symbol_lead,
        soft_allow_anchor_gap_symbol_lead_margin,
        soft_allow_anchor_gap_symbol_lead_sides,
        soft_allow_anchor_gap_symbol_sample_gap,
    )

    assert soft_allow_anchor_gap_count(None) == 0
    assert soft_allow_anchor_gap_count([]) == 0
    assert soft_allow_anchor_gap_last_symbol(None) == ""
    assert soft_allow_anchor_gap_last_symbol([]) == ""
    assert soft_allow_anchor_gap_last_freshness(None) == ""
    assert soft_allow_anchor_gap_last_freshness([]) == ""
    assert soft_allow_anchor_gap_symbol_lead(None) == ("", "", None)
    assert soft_allow_anchor_gap_symbol_lead_margin(None) is None
    assert soft_allow_anchor_gap_symbol_lead_sides(None) is None
    assert soft_allow_anchor_gap_symbol_last_vs_lead(None) == ""
    assert soft_allow_anchor_gap_symbol_sample_gap(None) == ""
    assert (
        soft_allow_anchor_gap_count(
            [{"gate": "rs", "reason": "SPY RS unknown — allow"}]
        )
        == 0
    )
    assert (
        soft_allow_anchor_gap_last_symbol(
            [{"gate": "rs", "reason": "SPY RS unknown — allow"}]
        )
        == ""
    )
    mixed = [
        {"gate": "rs", "reason": "AAPL RS unknown — anchor gap — allow"},
        {"gate": "rs", "reason": "MSFT RS unknown — allow"},
        {"gate": "regime", "reason": "unknown — no SPY bars"},
        "junk",
    ]
    assert soft_allow_anchor_gap_count(mixed) == 1
    assert soft_allow_anchor_gap_last_symbol(mixed) == "AAPL"
    # No at stamp → unknown silent (cursor name still speaks)
    assert soft_allow_anchor_gap_last_freshness(mixed) == ""
    assert soft_allow_anchor_gap_symbol_lead(mixed) == ("", "", None)
    assert soft_allow_anchor_gap_symbol_lead_margin(mixed) is None
    assert soft_allow_anchor_gap_symbol_lead_sides(mixed) is None
    assert soft_allow_anchor_gap_symbol_last_vs_lead(mixed) == ""
    assert soft_allow_anchor_gap_symbol_sample_gap(mixed) == "n=1"


def test_soft_allow_anchor_gap_last_freshness() -> None:
    """last SYM ≠ live fail-open: speak fresh/aging/expired on gap cursor."""
    from stock_checker.gate_audit import (
        format_soft_allow_anchor_gap_bit,
        soft_allow_anchor_gap_last_freshness,
        soft_allow_anchor_gap_last_lead_vs_lean,
        soft_allow_anchor_gap_last_lead_vs_share,
        soft_allow_anchor_gap_last_share_vs_lean,
        soft_allow_anchor_gap_last_vs_lead_freshness,
        soft_allow_anchor_gap_last_vs_lean,
        soft_allow_anchor_gap_last_vs_share,
        soft_allow_anchor_gap_symbol_last_vs_lead,
        soft_allow_anchor_gap_vs_cash_clock_clash,
        soft_allow_anchor_gap_vs_memory_clock_clash,
        soft_allow_anchor_gap_vs_scan_clash,
        soft_allow_vs_gap_clock_clash,
        soft_allow_vs_short_history_clock_clash,
    )

    now = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
    fresh_at = "2026-10-08T11:00:00Z"  # 1h → fresh
    aging_at = "2026-10-07T18:00:00Z"  # 18h → aging
    expired_at = "2026-10-07T10:00:00Z"  # 26h → expired

    fresh_row = {
        "at": fresh_at,
        "gate": "rs",
        "reason": "AAPL RS unknown — anchor gap — allow",
    }
    aging_row = {
        "at": aging_at,
        "gate": "rs",
        "reason": "AAPL RS unknown — anchor gap — allow",
    }
    expired_row = {
        "at": expired_at,
        "gate": "rs",
        "reason": "AAPL RS unknown — anchor gap — allow",
    }
    other = {
        "at": fresh_at,
        "gate": "rs",
        "reason": "SPY RS unknown — allow",
    }
    assert soft_allow_anchor_gap_last_freshness(
        [fresh_row, other], now=now
    ) == "fresh"
    assert soft_allow_anchor_gap_last_freshness(
        [aging_row, other], now=now
    ) == "aging"
    assert soft_allow_anchor_gap_last_freshness(
        [expired_row, other], now=now
    ) == "expired"
    # Skip non-gap head; use newest gap stamp
    assert soft_allow_anchor_gap_last_freshness(
        [other, aging_row], now=now
    ) == "aging"
    # aging mid → last/share + last/lean + share/lean silent;
    # expired·hot → share clash vs lean align → share/lean clash warn
    assert soft_allow_anchor_gap_last_vs_share(
        [aging_row, other], now=now
    ) == ("", False)
    assert soft_allow_anchor_gap_last_vs_lean(
        [aging_row, other], now=now
    ) == ("", False)
    assert soft_allow_anchor_gap_last_share_vs_lean(
        [aging_row, other], now=now
    ) == ("", False)
    assert soft_allow_anchor_gap_last_lead_vs_share(
        [aging_row, other], now=now
    ) == ("", False)
    assert soft_allow_anchor_gap_last_lead_vs_lean(
        [aging_row, other], now=now
    ) == ("", False)
    assert soft_allow_anchor_gap_last_vs_share(
        [expired_row, other], now=now
    ) == ("clash · expired · hot · ×1 · 50%", True)
    assert soft_allow_anchor_gap_last_vs_lean(
        [expired_row, other], now=now
    ) == ("align · expired · gap hot · other ok · ×1 · 50%", False)
    assert soft_allow_anchor_gap_last_share_vs_lean(
        [expired_row, other], now=now
    ) == ("clash · share clash · lean align · ×1 · 50%", True)
    assert soft_allow_anchor_gap_last_vs_share(
        [fresh_row, other], now=now
    ) == ("align · fresh · hot · ×1 · 50%", False)
    assert soft_allow_anchor_gap_last_vs_lean(
        [fresh_row, other], now=now
    ) == ("clash · fresh · gap hot · other ok · ×1 · 50%", True)
    assert soft_allow_anchor_gap_last_share_vs_lean(
        [fresh_row, other], now=now
    ) == ("clash · share align · lean clash · ×1 · 50%", True)
    # expired·hot + lean align hot|thin → both relationships clash;
    # agreement on dual clash warns (not calm align).
    gap2 = {
        "at": expired_at,
        "gate": "rs",
        "reason": "MSFT RS unknown — anchor gap — allow",
    }
    other_expired = {**other, "at": expired_at}
    assert soft_allow_anchor_gap_last_vs_share(
        [expired_row, gap2, other_expired], now=now
    ) == ("clash · expired · hot · ×2 · 67%", True)
    assert soft_allow_anchor_gap_last_vs_lean(
        [expired_row, gap2, other_expired], now=now
    ) == ("clash · expired · hot|thin · ×2 · 67%", True)
    assert soft_allow_anchor_gap_last_share_vs_lean(
        [expired_row, gap2, other_expired], now=now
    ) == ("align · both clash · ×2 · 67%", True)
    # Sole-name lead + freshness: stale agree warns; live agree calm.
    agree_expired = [
        expired_row,
        {
            "at": expired_at,
            "gate": "rs",
            "reason": "AAPL RS unknown — anchor gap — allow",
        },
    ]
    assert soft_allow_anchor_gap_symbol_last_vs_lead(agree_expired) == "agree"
    assert soft_allow_anchor_gap_last_vs_lead_freshness(
        agree_expired, now=now
    ) == ("clash · expired · agree · ×2 · 100%", True)
    # stale agree + expired/hot share → both clash (warn)
    assert soft_allow_anchor_gap_last_vs_share(
        agree_expired, now=now
    ) == ("clash · expired · hot · ×2 · 100%", True)
    assert soft_allow_anchor_gap_last_lead_vs_share(
        agree_expired, now=now
    ) == ("align · both clash · ×2 · 100%", True)
    assert soft_allow_anchor_gap_last_vs_lean(
        agree_expired, now=now
    ) == ("clash · expired · hot|thin · ×2 · 100%", True)
    assert soft_allow_anchor_gap_last_lead_vs_lean(
        agree_expired, now=now
    ) == ("align · both clash · ×2 · 100%", True)
    agree_fresh = [
        fresh_row,
        {
            "at": fresh_at,
            "gate": "rs",
            "reason": "AAPL RS unknown — anchor gap — allow",
        },
    ]
    assert soft_allow_anchor_gap_last_vs_lead_freshness(
        agree_fresh, now=now
    ) == ("align · fresh · agree · ×2 · 100%", False)
    assert soft_allow_anchor_gap_last_vs_share(
        agree_fresh, now=now
    ) == ("align · fresh · hot · ×2 · 100%", False)
    assert soft_allow_anchor_gap_last_lead_vs_share(
        agree_fresh, now=now
    ) == ("align · both align · ×2 · 100%", False)
    assert soft_allow_anchor_gap_last_vs_lean(
        agree_fresh, now=now
    ) == ("align · fresh · hot|thin · ×2 · 100%", False)
    assert soft_allow_anchor_gap_last_lead_vs_lean(
        agree_fresh, now=now
    ) == ("align · both align · ×2 · 100%", False)
    # Live name clash warns (cursor ≠ owner while still fresh).
    lead_fresh = [
        {
            "at": fresh_at,
            "gate": "rs",
            "reason": "MSFT RS unknown — anchor gap — allow",
        },
        {
            "at": fresh_at,
            "gate": "rs",
            "reason": "AAPL RS unknown — anchor gap — allow",
        },
        {
            "at": fresh_at,
            "gate": "rs",
            "reason": "AAPL RS unknown — anchor gap — allow",
        },
    ]
    assert soft_allow_anchor_gap_symbol_last_vs_lead(lead_fresh) == (
        "last vs lead · MSFT"
    )
    assert soft_allow_anchor_gap_last_vs_lead_freshness(
        lead_fresh, now=now
    ) == ("clash · fresh · vs MSFT · ×3 · 100%", True)
    assert soft_allow_anchor_gap_last_vs_share(
        lead_fresh, now=now
    ) == ("align · fresh · hot · ×3 · 100%", False)
    assert soft_allow_anchor_gap_last_lead_vs_share(
        lead_fresh, now=now
    ) == ("clash · lead clash · share align · ×3 · 100%", True)
    assert soft_allow_anchor_gap_last_vs_lean(
        lead_fresh, now=now
    ) == ("align · fresh · hot|thin · ×3 · 100%", False)
    assert soft_allow_anchor_gap_last_lead_vs_lean(
        lead_fresh, now=now
    ) == ("clash · lead clash · lean align · ×3 · 100%", True)
    assert soft_allow_anchor_gap_last_vs_lead_freshness(
        [aging_row, other], now=now
    ) == ("", False)
    assert format_soft_allow_anchor_gap_bit(
        agree_expired, now=now
    ) == (
        "2 gap · last AAPL · expired · lead AAPL · 2 · 100% · agree · "
        "last/lead clash · expired · agree · ×2 · 100% · hot · 100% · "
        "last/share clash · expired · hot · ×2 · 100% · "
        "lead/share align · both clash · ×2 · 100% · "
        "vs 0 other · thin · 0% · "
        "gap vs other align · hot|thin · "
        "last/lean clash · expired · hot|thin · ×2 · 100% · "
        "lead/lean align · both clash · ×2 · 100% · "
        "share/lean align · both clash · ×2 · 100%"
    )
    assert format_soft_allow_anchor_gap_bit(
        [aging_row, other], now=now
    ) == (
        "1 gap · last AAPL · aging · n=1 · hot · 50% · vs 1 other · 50% · "
        "gap vs other clash · gap hot · other ok"
    )
    assert format_soft_allow_anchor_gap_bit(
        [expired_row, other], now=now
    ) == (
        "1 gap · last AAPL · expired · n=1 · hot · 50% · "
        "last/share clash · expired · hot · ×1 · 50% · vs 1 other · 50% · "
        "gap vs other clash · gap hot · other ok · "
        "last/lean align · expired · gap hot · other ok · ×1 · 50% · "
        "share/lean clash · share clash · lean align · ×1 · 50%"
    )
    assert format_soft_allow_anchor_gap_bit(
        [fresh_row, other], now=now
    ) == (
        "1 gap · last AAPL · fresh · n=1 · hot · 50% · "
        "last/share align · fresh · hot · ×1 · 50% · vs 1 other · 50% · "
        "gap vs other clash · gap hot · other ok · "
        "last/lean clash · fresh · gap hot · other ok · ×1 · 50% · "
        "share/lean clash · share align · lean clash · ×1 · 50%"
    )
    # Gap vs scan: expired cursor ≠ fresh scan; same band silent.
    assert soft_allow_anchor_gap_vs_scan_clash(
        [expired_row, other], scan_freshness="fresh", now=now
    ) == ("clash · gap expired · scan fresh", True)
    assert soft_allow_anchor_gap_vs_scan_clash(
        [expired_row, other],
        scan_freshness="fresh",
        now=now,
        gap_pin_size=" · gap-only",
        scan_pin_size=" · scan-only",
    ) == (
        "clash · gap expired · scan fresh · gap-only · scan-only",
        True,
    )
    assert soft_allow_anchor_gap_vs_scan_clash(
        [expired_row, other],
        scan_freshness="fresh",
        now=now,
        gap_pin_size=" · gap-only",
        scan_pin_size=" · scan-only",
        keep_soft_pin_size=" · soft-only",
    ) == (
        "clash · gap expired · scan fresh · gap-only · scan-only · soft-only",
        True,
    )
    assert soft_allow_anchor_gap_vs_scan_clash(
        [expired_row, other],
        scan_freshness="fresh",
        now=now,
        gap_pin_size=" · gap-only",
        scan_pin_size=" · scan-only",
        keep_soft_pin_size=" · soft-only",
        keep_memory_pin_size=" · ×2 · 100%",
    ) == (
        "clash · gap expired · scan fresh · gap-only · scan-only · "
        "soft-only · ×2 · 100%",
        True,
    )
    # Keep-short when gap matches short cursor (short keep-gap
    # speak-both-sides + #660 / #647 / #531 / #668).
    assert soft_allow_anchor_gap_vs_scan_clash(
        [expired_row, other],
        scan_freshness="fresh",
        now=now,
        gap_pin_size=" · gap-only",
        scan_pin_size=" · scan-only",
        keep_soft_pin_size=" · soft-only",
        keep_short_pin_size=" · short-only",
        keep_memory_pin_size=" · ×2 · 100%",
    ) == (
        "clash · gap expired · scan fresh · gap-only · scan-only · "
        "soft-only · short-only · ×2 · 100%",
        True,
    )
    assert soft_allow_anchor_gap_vs_cash_clock_clash(
        [expired_row, other],
        cash_band="aging",
        now=now,
        gap_pin_size=" · gap-only",
        cash_pin_size=" · US-only",
        keep_scan_pin_size=" · scan-only",
        keep_short_pin_size=" · short-only",
    ) == (
        "clash · gap expired · cash aging · gap-only · US-only · "
        "scan-only · short-only",
        True,
    )
    assert soft_allow_anchor_gap_vs_memory_clock_clash(
        [expired_row, other],
        laya_freshness="fresh",
        debate_freshness="aging",
        now=now,
        gap_pin_size=" · gap-only",
        keep_scan_pin_size=" · scan-only",
        keep_short_pin_size=" · short-only",
    ) == (
        "clash · gap expired · laya fresh · debate aging · gap-only · "
        "scan-only · short-only",
        True,
    )
    assert format_soft_allow_anchor_gap_bit(
        [expired_row, other],
        now=now,
        scan_freshness="fresh",
        gap_pin_size=" · gap-only",
        scan_pin_size=" · scan-only",
        keep_short_pin_size=" · short-only",
    ) == (
        "1 gap · last AAPL · expired · clash · gap expired · scan fresh · "
        "gap-only · scan-only · short-only · "
        "n=1 · hot · 50% · "
        "last/share clash · expired · hot · ×1 · 50% · vs 1 other · 50% · "
        "gap vs other clash · gap hot · other ok · "
        "last/lean align · expired · gap hot · other ok · ×1 · 50% · "
        "share/lean clash · share clash · lean align · ×1 · 50%"
    )
    assert soft_allow_anchor_gap_vs_scan_clash(
        [fresh_row, other], scan_freshness="fresh", now=now
    ) == ("", False)
    assert soft_allow_anchor_gap_vs_scan_clash(
        [aging_row, other],
        scan_freshness="fresh",
        now=now,
        gap_pin_size=" · gap-only",
    ) == ("clash · gap aging · scan fresh · gap-only", True)
    assert format_soft_allow_anchor_gap_bit(
        [expired_row, other],
        now=now,
        scan_freshness="fresh",
        gap_pin_size=" · gap-only",
        scan_pin_size=" · scan-only",
    ) == (
        "1 gap · last AAPL · expired · clash · gap expired · scan fresh · "
        "gap-only · scan-only · "
        "n=1 · hot · 50% · "
        "last/share clash · expired · hot · ×1 · 50% · vs 1 other · 50% · "
        "gap vs other clash · gap hot · other ok · "
        "last/lean align · expired · gap hot · other ok · ×1 · 50% · "
        "share/lean clash · share clash · lean align · ×1 · 50%"
    )
    # Soft last ≠ gap cursor closes the generation triangle.
    assert soft_allow_vs_gap_clock_clash(
        [other, expired_row], soft_last_freshness="fresh", now=now
    ) == ("clash · soft fresh · gap expired", True)
    assert soft_allow_vs_gap_clock_clash(
        [other, expired_row],
        soft_last_freshness="fresh",
        now=now,
        gap_pin_size=" · gap-only",
    ) == ("clash · soft fresh · gap expired · gap-only", True)
    assert soft_allow_vs_gap_clock_clash(
        [other, expired_row],
        soft_last_freshness="fresh",
        now=now,
        soft_pin_size=" · soft-only",
        gap_pin_size=" · gap-only",
    ) == (
        "clash · soft fresh · gap expired · soft-only · gap-only",
        True,
    )
    assert soft_allow_vs_gap_clock_clash(
        [expired_row, other], soft_last_freshness="stale", now=now
    ) == ("", False)
    assert soft_allow_vs_gap_clock_clash(
        [fresh_row, other], soft_last_freshness="fresh", now=now
    ) == ("", False)
    # Soft last ≠ short cursor closes soft↔short↔scan (soft≠gap parity).
    short_expired = {
        "at": expired_at,
        "gate": "rs",
        "reason": "IPO RS unknown — short history — allow",
    }
    short_fresh = {
        "at": fresh_at,
        "gate": "rs",
        "reason": "IPO RS unknown — short history — allow",
    }
    assert soft_allow_vs_short_history_clock_clash(
        [other, short_expired], soft_last_freshness="fresh", now=now
    ) == ("clash · soft fresh · short expired", True)
    assert soft_allow_vs_short_history_clock_clash(
        [other, short_expired],
        soft_last_freshness="fresh",
        now=now,
        soft_pin_size=" · soft-only",
        short_pin_size=" · short-only",
    ) == (
        "clash · soft fresh · short expired · soft-only · short-only",
        True,
    )
    assert soft_allow_vs_short_history_clock_clash(
        [short_expired, other], soft_last_freshness="stale", now=now
    ) == ("", False)
    assert soft_allow_vs_short_history_clock_clash(
        [other, short_fresh], soft_last_freshness="fresh", now=now
    ) == ("", False)
    # Gap ≠ cash: expired≡stale vs aging speaks; same band silent.
    assert soft_allow_anchor_gap_vs_cash_clock_clash(
        [expired_row, other], cash_band="aging", now=now
    ) == ("clash · gap expired · cash aging", True)
    assert soft_allow_anchor_gap_vs_cash_clock_clash(
        [expired_row, other],
        cash_band="aging",
        now=now,
        gap_pin_size=" · gap-only",
        cash_pin_size=" · US · 50%",
    ) == (
        "clash · gap expired · cash aging · gap-only · US · 50%",
        True,
    )
    assert soft_allow_anchor_gap_vs_cash_clock_clash(
        [expired_row, other], cash_band="stale", now=now
    ) == ("", False)
    assert soft_allow_anchor_gap_vs_cash_clock_clash(
        [fresh_row, other], cash_band="fresh", now=now
    ) == ("", False)
    assert soft_allow_anchor_gap_vs_cash_clock_clash(
        [fresh_row, other], cash_band="", now=now
    ) == ("", False)
    # Gap ≠ memory: soft matching memory can still hide gap≠laya/debate.
    assert soft_allow_anchor_gap_vs_memory_clock_clash(
        [expired_row, other],
        laya_freshness="fresh",
        debate_freshness="aging",
        now=now,
    ) == ("clash · gap expired · laya fresh · debate aging", True)
    assert soft_allow_anchor_gap_vs_memory_clock_clash(
        [expired_row, other],
        laya_freshness="fresh",
        debate_freshness="aging",
        now=now,
        gap_pin_size=" · gap-only",
        memory_pin_size=" · ×2 · 100%",
    ) == (
        "clash · gap expired · laya fresh · debate aging · gap-only · ×2 · 100%",
        True,
    )
    assert soft_allow_anchor_gap_vs_memory_clock_clash(
        [fresh_row, other],
        laya_freshness="fresh",
        debate_freshness="fresh",
        now=now,
    ) == ("", False)
    assert soft_allow_anchor_gap_vs_memory_clock_clash(
        [fresh_row, other],
        laya_freshness="fresh",
        debate_freshness="stale",
        now=now,
        gap_pin_size=" · gap-only",
        memory_pin_size=" · debate · 50%",
    ) == (
        "clash · gap fresh · debate stale · gap-only · debate · 50%",
        True,
    )
    assert soft_allow_anchor_gap_vs_memory_clock_clash(
        [expired_row, other],
        laya_freshness="stale",
        debate_freshness="",
        now=now,
    ) == ("", False)
    assert format_soft_allow_anchor_gap_bit(
        [expired_row, other],
        now=now,
        scan_freshness="fresh",
        gap_pin_size=" · gap-only",
        scan_pin_size=" · scan-only",
        cash_band="aging",
        laya_freshness="fresh",
        debate_freshness="aging",
        memory_pin_size=" · ×2 · 100%",
    ) == (
        "1 gap · last AAPL · expired · clash · gap expired · scan fresh · "
        "gap-only · scan-only · "
        "clash · gap expired · cash aging · gap-only · "
        "clash · gap expired · laya fresh · debate aging · gap-only · "
        "×2 · 100% · "
        "n=1 · hot · 50% · "
        "last/share clash · expired · hot · ×1 · 50% · vs 1 other · 50% · "
        "gap vs other clash · gap hot · other ok · "
        "last/lean align · expired · gap hot · other ok · ×1 · 50% · "
        "share/lean clash · share clash · lean align · ×1 · 50%"
    )


def test_soft_allow_anchor_gap_share() -> None:
    """portfolio AI count≠share: gap÷ring with hot/quiet floors + vs other."""
    from stock_checker.gate_audit import (
        format_soft_allow_anchor_gap_bit,
        soft_allow_anchor_gap_last_symbol,
        soft_allow_anchor_gap_share,
        soft_allow_anchor_gap_symbol_last_vs_lead,
        soft_allow_anchor_gap_symbol_lead,
        soft_allow_anchor_gap_symbol_lead_margin,
        soft_allow_anchor_gap_symbol_lead_sides,
        soft_allow_anchor_gap_symbol_sample_gap,
        soft_allow_anchor_gap_vs_other,
        soft_allow_anchor_gap_vs_other_lean,
    )

    assert soft_allow_anchor_gap_share(None) == (0, None, "")
    assert soft_allow_anchor_gap_share([]) == (0, None, "")
    assert soft_allow_anchor_gap_vs_other(None) == (0, None, "")
    assert soft_allow_anchor_gap_vs_other_lean(None) == ("", False)
    assert format_soft_allow_anchor_gap_bit(None) == ""

    # 1/4 = 25% gap quiet · 75% other strong → align
    quiet_rows = [
        {"gate": "rs", "reason": "AAPL RS unknown — anchor gap — allow"},
        {"gate": "rs", "reason": "MSFT RS unknown — allow"},
        {"gate": "regime", "reason": "unknown — no SPY bars"},
        {"gate": "breadth", "reason": "unknown scan"},
    ]
    assert soft_allow_anchor_gap_share(quiet_rows) == (1, 25.0, "quiet")
    assert soft_allow_anchor_gap_last_symbol(quiet_rows) == "AAPL"
    assert soft_allow_anchor_gap_symbol_lead(quiet_rows) == ("", "", None)
    assert soft_allow_anchor_gap_symbol_lead_margin(quiet_rows) is None
    assert soft_allow_anchor_gap_symbol_last_vs_lead(quiet_rows) == ""
    assert soft_allow_anchor_gap_symbol_sample_gap(quiet_rows) == "n=1"
    assert soft_allow_anchor_gap_vs_other(quiet_rows) == (3, 75.0, "strong")
    assert soft_allow_anchor_gap_vs_other_lean(quiet_rows) == (
        "align · quiet|strong",
        False,
    )
    assert format_soft_allow_anchor_gap_bit(quiet_rows) == (
        "1 gap · last AAPL · n=1 · quiet · 25% · vs 3 other · strong · 75% · "
        "gap vs other align · quiet|strong"
    )

    # 2/3 ≈ 66.7% gap hot · 33.3% other thin → align; newest gap cursor
    # + two distinct gap names → tied (last ≠ ownership)
    hot_rows = [
        {"gate": "rs", "reason": "AAPL RS unknown — anchor gap — allow"},
        {"gate": "rs", "reason": "SPY RS unknown — allow"},
        {"gate": "rs", "reason": "MSFT RS unknown — anchor gap — allow"},
    ]
    assert soft_allow_anchor_gap_share(hot_rows) == (2, 66.7, "hot")
    assert soft_allow_anchor_gap_last_symbol(hot_rows) == "AAPL"
    assert soft_allow_anchor_gap_symbol_lead(hot_rows) == ("", "", None)
    assert soft_allow_anchor_gap_symbol_lead_margin(hot_rows) is None
    assert soft_allow_anchor_gap_symbol_last_vs_lead(hot_rows) == ""
    assert soft_allow_anchor_gap_symbol_sample_gap(hot_rows) == "tied"
    assert soft_allow_anchor_gap_vs_other(hot_rows) == (1, 33.3, "thin")
    assert soft_allow_anchor_gap_vs_other_lean(hot_rows) == (
        "align · hot|thin",
        False,
    )
    assert format_soft_allow_anchor_gap_bit(hot_rows) == (
        "2 gap · last AAPL · tied · hot · 66.7% · vs 1 other · thin · 33.3% · "
        "gap vs other align · hot|thin"
    )

    # Strict lead: 2×AAPL + 1×MSFT gap (last MSFT ≠ lead AAPL)
    # margin thin +1 · vs MSFT · 1 · 33%
    lead_rows = [
        {"gate": "rs", "reason": "MSFT RS unknown — anchor gap — allow"},
        {"gate": "rs", "reason": "AAPL RS unknown — anchor gap — allow"},
        {"gate": "rs", "reason": "SPY RS unknown — allow"},
        {"gate": "rs", "reason": "AAPL RS unknown — anchor gap — allow"},
    ]
    assert soft_allow_anchor_gap_symbol_lead(lead_rows) == (
        "lead AAPL · 2 · 67%",
        "AAPL",
        67,
    )
    assert soft_allow_anchor_gap_symbol_lead_margin(lead_rows) == (
        "ahead thin · +1",
        1,
        "thin",
    )
    assert soft_allow_anchor_gap_symbol_lead_sides(lead_rows) == (
        "vs MSFT · 1 · 33%",
        "MSFT",
        1,
        33,
    )
    assert soft_allow_anchor_gap_symbol_sample_gap(lead_rows) == ""
    assert soft_allow_anchor_gap_last_symbol(lead_rows) == "MSFT"
    assert soft_allow_anchor_gap_symbol_last_vs_lead(lead_rows) == (
        "last vs lead · MSFT"
    )
    assert format_soft_allow_anchor_gap_bit(lead_rows) == (
        "3 gap · last MSFT · lead AAPL · 2 · 67% · last vs lead · MSFT · "
        "ahead thin · +1 · vs MSFT · 1 · 33% · hot · 75% · "
        "vs 1 other · thin · 25% · gap vs other align · hot|thin"
    )

    # Wide margin: 3×AAPL + 1×MSFT (ahead ≥2)
    wide_rows = lead_rows + [
        {"gate": "rs", "reason": "AAPL RS unknown — anchor gap — allow"},
    ]
    assert soft_allow_anchor_gap_symbol_lead(wide_rows) == (
        "lead AAPL · 3 · 75%",
        "AAPL",
        75,
    )
    assert soft_allow_anchor_gap_symbol_lead_margin(wide_rows) == (
        "ahead wide · +2",
        2,
        "wide",
    )
    assert soft_allow_anchor_gap_symbol_lead_sides(wide_rows) == (
        "vs MSFT · 1 · 25%",
        "MSFT",
        1,
        25,
    )
    assert format_soft_allow_anchor_gap_bit(wide_rows) == (
        "4 gap · last MSFT · lead AAPL · 3 · 75% · last vs lead · MSFT · "
        "ahead wide · +2 · vs MSFT · 1 · 25% · hot · 80% · "
        "vs 1 other · thin · 20% · gap vs other align · hot|thin"
    )

    # 2/5 = 40% gap mid · 60% other mid (leans silent); gap names tied
    mid_rows = hot_rows + [
        {"gate": "regime", "reason": "unknown — no SPY bars"},
        {"gate": "breadth", "reason": "unknown scan"},
    ]
    assert soft_allow_anchor_gap_share(mid_rows) == (2, 40.0, "ok")
    assert soft_allow_anchor_gap_vs_other(mid_rows) == (3, 60.0, "ok")
    assert soft_allow_anchor_gap_vs_other_lean(mid_rows) == ("", False)
    assert soft_allow_anchor_gap_symbol_sample_gap(mid_rows) == "tied"
    assert format_soft_allow_anchor_gap_bit(mid_rows) == (
        "2 gap · last AAPL · tied · 40% · vs 3 other · 60%"
    )

    # All-gap → vs 0 other · thin · 0% · align hot|thin; names tied
    all_gap = [
        {"gate": "rs", "reason": "AAPL RS unknown — anchor gap — allow"},
        {"gate": "rs", "reason": "MSFT RS unknown — anchor gap — allow"},
    ]
    assert soft_allow_anchor_gap_vs_other(all_gap) == (0, 0.0, "thin")
    assert soft_allow_anchor_gap_vs_other_lean(all_gap) == (
        "align · hot|thin",
        False,
    )
    assert soft_allow_anchor_gap_symbol_sample_gap(all_gap) == "tied"
    assert format_soft_allow_anchor_gap_bit(all_gap) == (
        "2 gap · last AAPL · tied · hot · 100% · vs 0 other · thin · 0% · "
        "gap vs other align · hot|thin"
    )

    # Same symbol twice → lead · 100% (sole-name with n≥2); no ahead
    same_sym = [
        {"gate": "rs", "reason": "AAPL RS unknown — anchor gap — allow"},
        {"gate": "rs", "reason": "AAPL RS unknown — anchor gap — allow"},
    ]
    assert soft_allow_anchor_gap_symbol_lead(same_sym) == (
        "lead AAPL · 2 · 100%",
        "AAPL",
        100,
    )
    assert soft_allow_anchor_gap_symbol_lead_margin(same_sym) is None
    assert soft_allow_anchor_gap_symbol_lead_sides(same_sym) is None
    assert soft_allow_anchor_gap_symbol_sample_gap(same_sym) == ""
    assert soft_allow_anchor_gap_symbol_last_vs_lead(same_sym) == "agree"
    assert format_soft_allow_anchor_gap_bit(same_sym) == (
        "2 gap · last AAPL · lead AAPL · 2 · 100% · agree · hot · 100% · "
        "vs 0 other · thin · 0% · gap vs other align · hot|thin"
    )

    # 1/2 = 50% gap hot · 50% other ok → one-lean clash (warn)
    half_rows = [
        {"gate": "rs", "reason": "AAPL RS unknown — anchor gap — allow"},
        {"gate": "rs", "reason": "SPY RS unknown — allow"},
    ]
    assert soft_allow_anchor_gap_share(half_rows) == (1, 50.0, "hot")
    assert soft_allow_anchor_gap_vs_other(half_rows) == (1, 50.0, "ok")
    assert soft_allow_anchor_gap_vs_other_lean(half_rows) == (
        "clash · gap hot · other ok",
        True,
    )
    assert soft_allow_anchor_gap_symbol_sample_gap(half_rows) == "n=1"
    assert format_soft_allow_anchor_gap_bit(half_rows) == (
        "1 gap · last AAPL · n=1 · hot · 50% · vs 1 other · 50% · "
        "gap vs other clash · gap hot · other ok"
    )

    # Bench-label gap cursor (SPY window hole) + skip non-gap head
    bench_gap = [
        {"gate": "rs", "reason": "NVDA RS unknown — allow"},
        {"gate": "rs", "reason": "SPY RS unknown — anchor gap — allow"},
    ]
    assert soft_allow_anchor_gap_last_symbol(bench_gap) == "SPY"
    assert soft_allow_anchor_gap_symbol_sample_gap(bench_gap) == "n=1"
    assert format_soft_allow_anchor_gap_bit(bench_gap) == (
        "1 gap · last SPY · n=1 · hot · 50% · vs 1 other · 50% · "
        "gap vs other clash · gap hot · other ok"
    )

def test_record_and_recent_soft_allows(tmp_path: Path) -> None:
    record_soft_allow(tmp_path, "regime", "unknown — no bars")
    record_soft_allow(tmp_path, "rs", "hard pass — should not store")
    record_soft_allow(tmp_path, "promote", "ABC: skip_no_bars")

    events = load_soft_allows(tmp_path)
    assert len(events) == 2
    assert events[0]["gate"] == "regime"
    assert events[1]["gate"] == "promote"

    recent = recent_soft_allows(tmp_path, limit=1)
    assert len(recent) == 1
    assert recent[0]["gate"] == "promote"
    assert "skip_no_bars" in recent[0]["reason"]


def test_soft_allow_cap(tmp_path: Path) -> None:
    for i in range(5):
        record_soft_allow(tmp_path, "breadth", f"unknown #{i}", cap=3)
    events = load_soft_allows(tmp_path)
    assert len(events) == 3
    assert events[-1]["reason"] == "unknown #4"


def test_soft_allow_rejects_duplicate_gate_reason(tmp_path: Path) -> None:
    """tradermonty #447: same gate+reason refreshes stamp; no duplicate rows."""
    assert soft_allow_event_key("Regime", "Unknown — no bars") == soft_allow_event_key(
        "regime", "unknown — no bars"
    )
    record_soft_allow(tmp_path, "regime", "unknown — no bars")
    record_soft_allow(tmp_path, "rs", "insufficient history")
    first = load_soft_allows(tmp_path)
    assert len(first) == 2
    stamp0 = first[0]["at"]
    record_soft_allow(tmp_path, "REGIME", "Unknown — no bars")
    events = load_soft_allows(tmp_path)
    assert len(events) == 2
    assert events[0]["gate"] == "rs"
    assert events[1]["gate"] == "REGIME"
    assert events[1]["reason"] == "Unknown — no bars"
    assert events[1]["at"] >= stamp0
    # Distinct reason still accumulates under the same gate.
    record_soft_allow(tmp_path, "regime", "unknown — empty Yahoo earnings window")
    assert len(load_soft_allows(tmp_path)) == 3


def test_log_soft_allow_persists(tmp_path: Path, capsys) -> None:
    log_soft_allow("rs", "insufficient bars", data_dir=tmp_path)
    out = capsys.readouterr().out
    assert "Soft-allow [rs]" in out
    assert recent_soft_allows(tmp_path)


def test_soft_allow_expired_and_tally() -> None:
    """tradermonty #437: age >24h is expired; tally consolidates by gate."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    stale = (now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    fresh = (now - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert soft_allow_is_expired(stale, now=now) is True
    assert soft_allow_is_expired(fresh, now=now) is False
    assert soft_allow_is_expired("not-a-stamp", now=now) is False

    rows = enrich_soft_allows(
        [
            {"at": fresh, "gate": "rs", "reason": "insufficient"},
            {"at": stale, "gate": "regime", "reason": "unknown a"},
            {"at": stale, "gate": "regime", "reason": "unknown b"},
        ],
        now=now,
    )
    assert rows[0]["expired"] is False
    assert rows[0]["freshness"] == "fresh"
    assert rows[1]["expired"] is True
    assert rows[1]["freshness"] == "expired"
    assert rows[2]["expired"] is True
    assert format_expired_soft_allow_tally(rows) == "regime×2"


def test_soft_allow_freshness_aging_band() -> None:
    """xang1234 / RyanJHamby: aging between 12h and 24h before expired."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    fresh = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    aging = (now - timedelta(hours=18)).strftime("%Y-%m-%dT%H:%M:%SZ")
    stale = (now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert soft_allow_freshness(fresh, now=now) == "fresh"
    assert soft_allow_freshness(aging, now=now) == "aging"
    assert soft_allow_freshness(stale, now=now) == "expired"
    assert soft_allow_freshness("bad", now=now) == "unknown"
    rows = enrich_soft_allows(
        [
            {"at": fresh, "gate": "rs", "reason": "insufficient"},
            {"at": aging, "gate": "breadth", "reason": "unknown scan"},
            {"at": stale, "gate": "regime", "reason": "unknown"},
        ],
        now=now,
    )
    assert [r["freshness"] for r in rows] == ["fresh", "aging", "expired"]
    assert rows[1]["expired"] is False
    assert rows[2]["expired"] is True
    assert format_aging_soft_allow_tally(rows) == "breadth×1"


def test_soft_allow_aging_tally_consolidates() -> None:
    """portfolio AI + xang1234: aging gate tally mirrors expired speak-both-sides."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    aging = (now - timedelta(hours=18)).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = enrich_soft_allows(
        [
            {"at": aging, "gate": "breadth", "reason": "unknown scan a"},
            {"at": aging, "gate": "breadth", "reason": "unknown scan b"},
            {"at": aging, "gate": "rs", "reason": "insufficient history"},
        ],
        now=now,
    )
    assert all(r["freshness"] == "aging" for r in rows)
    assert format_aging_soft_allow_tally(rows) == "breadth×2 · rs×1"
    assert format_expired_soft_allow_tally(rows) == ""


def test_soft_allow_fresh_tally_consolidates() -> None:
    """portfolio AI + xang1234: fresh gate tally completes the triad."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    fresh = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    aging = (now - timedelta(hours=18)).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = enrich_soft_allows(
        [
            {"at": fresh, "gate": "rs", "reason": "insufficient a"},
            {"at": fresh, "gate": "rs", "reason": "insufficient b"},
            {"at": fresh, "gate": "regime", "reason": "no SPY bars"},
            {"at": aging, "gate": "breadth", "reason": "unknown scan"},
        ],
        now=now,
    )
    assert format_fresh_soft_allow_tally(rows) == "rs×2 · regime×1"
    assert format_aging_soft_allow_tally(rows) == "breadth×1"
    assert format_expired_soft_allow_tally(rows) == ""


def test_soft_allow_lead_gate_concentration() -> None:
    """portfolio AI + xang1234: dominant gate needs ≥2 and a clear lead."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    fresh = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = enrich_soft_allows(
        [
            {"at": fresh, "gate": "rs", "reason": "insufficient a"},
            {"at": fresh, "gate": "rs", "reason": "insufficient b"},
            {"at": fresh, "gate": "regime", "reason": "no SPY bars"},
        ],
        now=now,
    )
    assert soft_allow_lead_gate(rows, band="fresh") == ("rs", 2)
    assert soft_allow_lead_share(rows, band="fresh") == ("rs", 2, 66.7)
    assert soft_allow_lead_margin(rows, band="fresh") == (
        "rs",
        2,
        66.7,
        1,
        "thin",
    )
    assert soft_allow_lead_sides(rows, band="fresh") == (
        "rs",
        2,
        66.7,
        1,
        "thin",
        "regime",
        1,
    )
    assert soft_allow_lead_sides_share(rows, band="fresh") == (
        "rs",
        2,
        66.7,
        1,
        "thin",
        "regime",
        1,
        33.3,
    )
    assert soft_allow_lead_sides_share_delta(rows, band="fresh") == (
        "rs",
        2,
        66.7,
        1,
        "thin",
        "regime",
        1,
        33.3,
        33.4,
        "wide",
    )
    # ahead thin ≠ share wide → different lean silent on vs Δ
    assert soft_allow_lead_sides_share_vs_delta(rows, band="fresh") is None
    assert (
        format_soft_allow_lead_bit(rows, band="fresh")
        == "rs leads · fresh · ×2 · 67% · ahead thin · +1 · vs regime ×1 · 33% · share Δ wide · +33pp"
    )
    # Single row stays silent.
    one = enrich_soft_allows(
        [{"at": fresh, "gate": "rs", "reason": "insufficient"}],
        now=now,
    )
    assert soft_allow_lead_gate(one, band="fresh") is None
    assert soft_allow_lead_share(one, band="fresh") is None
    assert soft_allow_lead_margin(one, band="fresh") is None
    assert soft_allow_lead_sides(one, band="fresh") is None
    assert soft_allow_lead_sides_share(one, band="fresh") is None
    assert soft_allow_lead_sides_share_delta(one, band="fresh") is None
    assert soft_allow_lead_sides_share_vs_delta(one, band="fresh") is None
    assert format_soft_allow_lead_bit(one, band="fresh") == ""
    assert soft_allow_sample_gap(one, band="fresh") == "n=1"
    assert soft_allow_sample_gap(one, band="fresh", lead_gate="rs") == ""
    # Tie stays silent on lead; sample gap speaks tied.
    tied = enrich_soft_allows(
        [
            {"at": fresh, "gate": "rs", "reason": "a"},
            {"at": fresh, "gate": "rs", "reason": "b"},
            {"at": fresh, "gate": "regime", "reason": "c"},
            {"at": fresh, "gate": "regime", "reason": "d"},
        ],
        now=now,
    )
    assert soft_allow_lead_gate(tied, band="fresh") is None
    assert soft_allow_lead_share(tied, band="fresh") is None
    assert soft_allow_lead_margin(tied, band="fresh") is None
    assert soft_allow_lead_sides(tied, band="fresh") is None
    assert soft_allow_lead_sides_share(tied, band="fresh") is None
    assert soft_allow_lead_sides_share_delta(tied, band="fresh") is None
    assert soft_allow_lead_sides_share_vs_delta(tied, band="fresh") is None
    assert soft_allow_sample_gap(tied, band="fresh") == "tied"
    # Sole-gate lead still speaks ownership; ahead stays silent (no #2).
    sole = enrich_soft_allows(
        [
            {"at": fresh, "gate": "rs", "reason": "a"},
            {"at": fresh, "gate": "rs", "reason": "b"},
        ],
        now=now,
    )
    assert soft_allow_lead_share(sole, band="fresh") == ("rs", 2, 100.0)
    assert soft_allow_sample_gap(sole, band="fresh", lead_gate="rs") == ""
    assert soft_allow_lead_margin(sole, band="fresh") is None
    assert soft_allow_lead_sides(sole, band="fresh") is None
    assert soft_allow_lead_sides_share(sole, band="fresh") is None
    assert soft_allow_lead_sides_share_delta(sole, band="fresh") is None
    assert soft_allow_lead_sides_share_vs_delta(sole, band="fresh") is None
    assert format_soft_allow_lead_bit(sole, band="fresh") == "rs leads · fresh · ×2 · 100%"
    # Wide margin when lead clears #2 by ≥2.
    wide = enrich_soft_allows(
        [
            {"at": fresh, "gate": "rs", "reason": "a"},
            {"at": fresh, "gate": "rs", "reason": "b"},
            {"at": fresh, "gate": "rs", "reason": "c"},
            {"at": fresh, "gate": "regime", "reason": "d"},
        ],
        now=now,
    )
    assert soft_allow_lead_margin(wide, band="fresh") == (
        "rs",
        3,
        75.0,
        2,
        "wide",
    )
    assert soft_allow_lead_sides(wide, band="fresh") == (
        "rs",
        3,
        75.0,
        2,
        "wide",
        "regime",
        1,
    )
    assert soft_allow_lead_sides_share(wide, band="fresh") == (
        "rs",
        3,
        75.0,
        2,
        "wide",
        "regime",
        1,
        25.0,
    )
    assert soft_allow_lead_sides_share_delta(wide, band="fresh") == (
        "rs",
        3,
        75.0,
        2,
        "wide",
        "regime",
        1,
        25.0,
        50.0,
        "wide",
    )
    assert soft_allow_lead_sides_share_vs_delta(wide, band="fresh") == (
        "align",
        "wide",
        "wide",
    )
    assert (
        format_soft_allow_lead_bit(wide, band="fresh")
        == "rs leads · fresh · ×3 · 75% · ahead wide · +2 · vs regime ×1 · 25% · "
        "share Δ wide · +50pp · share vs Δ align · wide"
    )
    # Mid ownership spread → clash (ahead spoke · share mid).
    mid = enrich_soft_allows(
        [
            {"at": fresh, "gate": "rs", "reason": "a"},
            {"at": fresh, "gate": "rs", "reason": "b"},
            {"at": fresh, "gate": "rs", "reason": "c"},
            {"at": fresh, "gate": "rs", "reason": "d"},
            {"at": fresh, "gate": "regime", "reason": "e"},
            {"at": fresh, "gate": "regime", "reason": "f"},
            {"at": fresh, "gate": "regime", "reason": "g"},
        ],
        now=now,
    )
    assert soft_allow_lead_sides_share(mid, band="fresh") == (
        "rs",
        4,
        57.1,
        1,
        "thin",
        "regime",
        3,
        42.9,
    )
    assert soft_allow_lead_sides_share_delta(mid, band="fresh") is None
    assert soft_allow_lead_sides_share_vs_delta(mid, band="fresh") == (
        "clash",
        "thin",
        "mid",
    )
    assert (
        format_soft_allow_lead_bit(mid, band="fresh")
        == "rs leads · fresh · ×4 · 57% · ahead thin · +1 · vs regime ×3 · 43% · "
        "share vs Δ clash · ahead thin · share mid"
    )
    # Thin ownership spread speaks when |Δ| < 10pp; align when ahead thin.
    thin_pp = enrich_soft_allows(
        [
            {"at": fresh, "gate": "rs", "reason": f"a{i}"}
            for i in range(6)
        ]
        + [
            {"at": fresh, "gate": "regime", "reason": f"b{i}"}
            for i in range(5)
        ],
        now=now,
    )
    assert soft_allow_lead_sides_share(thin_pp, band="fresh") == (
        "rs",
        6,
        54.5,
        1,
        "thin",
        "regime",
        5,
        45.5,
    )
    assert soft_allow_lead_sides_share_delta(thin_pp, band="fresh") == (
        "rs",
        6,
        54.5,
        1,
        "thin",
        "regime",
        5,
        45.5,
        9.0,
        "thin",
    )
    assert soft_allow_lead_sides_share_vs_delta(thin_pp, band="fresh") == (
        "align",
        "thin",
        "thin",
    )
    assert (
        format_soft_allow_lead_bit(thin_pp, band="fresh")
        == "rs leads · fresh · ×6 · 54% · ahead thin · +1 · vs regime ×5 · 46% · "
        "share Δ thin · +9pp · share vs Δ align · thin"
    )


def test_soft_allow_row_is_lead_matches_band() -> None:
    """Ops list lead tag: same gate×band as glance; fresh includes unknown."""
    from stock_checker.gate_audit import (
        mark_soft_allow_lead_rows,
        soft_allow_row_is_lead,
        soft_allow_row_is_runner,
    )

    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    fresh = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    aging = (now - timedelta(hours=14)).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = enrich_soft_allows(
        [
            {"at": fresh, "gate": "rs", "reason": "a"},
            {"at": fresh, "gate": "rs", "reason": "b"},
            {"at": fresh, "gate": "regime", "reason": "c"},
            {"at": aging, "gate": "rs", "reason": "d"},
            {"at": None, "gate": "rs", "reason": "e"},
        ],
        now=now,
    )
    assert soft_allow_row_is_lead(rows[0], lead_gate="rs", lead_band="fresh")
    assert soft_allow_row_is_lead(rows[1], lead_gate="rs", lead_band="fresh")
    assert not soft_allow_row_is_lead(
        rows[2], lead_gate="rs", lead_band="fresh"
    )
    assert not soft_allow_row_is_lead(
        rows[3], lead_gate="rs", lead_band="fresh"
    )
    assert soft_allow_row_is_lead(rows[4], lead_gate="rs", lead_band="fresh")
    assert not soft_allow_row_is_lead(rows[0], lead_gate="", lead_band="fresh")
    assert soft_allow_row_is_runner(
        rows[2], runner_gate="regime", lead_band="fresh"
    )
    assert not soft_allow_row_is_runner(
        rows[0], runner_gate="regime", lead_band="fresh"
    )
    marked = mark_soft_allow_lead_rows(
        rows,
        lead_gate="rs",
        lead_band="fresh",
        runner_gate="regime",
    )
    assert [r["is_lead"] for r in marked] == [
        True,
        True,
        False,
        False,
        True,
    ]
    assert [r["is_runner"] for r in marked] == [
        False,
        False,
        True,
        False,
        False,
    ]
    # xang1234 identity: lead/runner band is glance severity, not row cool-off.
    assert [r.get("lead_band") for r in marked] == [
        "fresh",
        "fresh",
        "",
        "",
        "fresh",
    ]
    assert [r.get("runner_band") for r in marked] == [
        "",
        "",
        "fresh",
        "",
        "",
    ]
