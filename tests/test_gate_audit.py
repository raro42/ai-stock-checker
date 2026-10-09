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
    assert not is_soft_allow_reason("SPY above SMA200")
    assert not is_soft_allow_reason("")


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
        soft_allow_anchor_gap_last_lead_vs_share,
        soft_allow_anchor_gap_last_share_vs_lean,
        soft_allow_anchor_gap_last_vs_lead_freshness,
        soft_allow_anchor_gap_last_vs_lean,
        soft_allow_anchor_gap_last_vs_share,
        soft_allow_anchor_gap_symbol_last_vs_lead,
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
    assert soft_allow_anchor_gap_last_vs_share(
        [expired_row, other], now=now
    ) == ("clash · expired · hot", True)
    assert soft_allow_anchor_gap_last_vs_lean(
        [expired_row, other], now=now
    ) == ("align · expired · gap hot · other ok", False)
    assert soft_allow_anchor_gap_last_share_vs_lean(
        [expired_row, other], now=now
    ) == ("clash · share clash · lean align", True)
    assert soft_allow_anchor_gap_last_vs_share(
        [fresh_row, other], now=now
    ) == ("align · fresh · hot", False)
    assert soft_allow_anchor_gap_last_vs_lean(
        [fresh_row, other], now=now
    ) == ("clash · fresh · gap hot · other ok", True)
    assert soft_allow_anchor_gap_last_share_vs_lean(
        [fresh_row, other], now=now
    ) == ("clash · share align · lean clash", True)
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
    ) == ("clash · expired · hot", True)
    assert soft_allow_anchor_gap_last_vs_lean(
        [expired_row, gap2, other_expired], now=now
    ) == ("clash · expired · hot|thin", True)
    assert soft_allow_anchor_gap_last_share_vs_lean(
        [expired_row, gap2, other_expired], now=now
    ) == ("align · both clash", True)
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
    ) == ("clash · expired · agree", True)
    # stale agree + expired/hot share → both clash (warn)
    assert soft_allow_anchor_gap_last_vs_share(
        agree_expired, now=now
    ) == ("clash · expired · hot", True)
    assert soft_allow_anchor_gap_last_lead_vs_share(
        agree_expired, now=now
    ) == ("align · both clash", True)
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
    ) == ("align · fresh · agree", False)
    assert soft_allow_anchor_gap_last_vs_share(
        agree_fresh, now=now
    ) == ("align · fresh · hot", False)
    assert soft_allow_anchor_gap_last_lead_vs_share(
        agree_fresh, now=now
    ) == ("align · both align", False)
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
    ) == ("clash · fresh · vs MSFT", True)
    assert soft_allow_anchor_gap_last_vs_share(
        lead_fresh, now=now
    ) == ("align · fresh · hot", False)
    assert soft_allow_anchor_gap_last_lead_vs_share(
        lead_fresh, now=now
    ) == ("clash · lead clash · share align", True)
    assert soft_allow_anchor_gap_last_vs_lead_freshness(
        [aging_row, other], now=now
    ) == ("", False)
    assert format_soft_allow_anchor_gap_bit(
        agree_expired, now=now
    ) == (
        "2 gap · last AAPL · expired · lead AAPL · 100% · agree · "
        "last/lead clash · expired · agree · hot · 100% · "
        "last/share clash · expired · hot · "
        "lead/share align · both clash · "
        "vs 0 other · thin · 0% · "
        "gap vs other align · hot|thin · "
        "last/lean clash · expired · hot|thin · "
        "share/lean align · both clash"
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
        "last/share clash · expired · hot · vs 1 other · 50% · "
        "gap vs other clash · gap hot · other ok · "
        "last/lean align · expired · gap hot · other ok · "
        "share/lean clash · share clash · lean align"
    )
    assert format_soft_allow_anchor_gap_bit(
        [fresh_row, other], now=now
    ) == (
        "1 gap · last AAPL · fresh · n=1 · hot · 50% · "
        "last/share align · fresh · hot · vs 1 other · 50% · "
        "gap vs other clash · gap hot · other ok · "
        "last/lean clash · fresh · gap hot · other ok · "
        "share/lean clash · share align · lean clash"
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
        "lead AAPL · 67%",
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
        "3 gap · last MSFT · lead AAPL · 67% · last vs lead · MSFT · "
        "ahead thin · +1 · vs MSFT · 1 · 33% · hot · 75% · "
        "vs 1 other · thin · 25% · gap vs other align · hot|thin"
    )

    # Wide margin: 3×AAPL + 1×MSFT (ahead ≥2)
    wide_rows = lead_rows + [
        {"gate": "rs", "reason": "AAPL RS unknown — anchor gap — allow"},
    ]
    assert soft_allow_anchor_gap_symbol_lead(wide_rows) == (
        "lead AAPL · 75%",
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
        "4 gap · last MSFT · lead AAPL · 75% · last vs lead · MSFT · "
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
        "lead AAPL · 100%",
        "AAPL",
        100,
    )
    assert soft_allow_anchor_gap_symbol_lead_margin(same_sym) is None
    assert soft_allow_anchor_gap_symbol_lead_sides(same_sym) is None
    assert soft_allow_anchor_gap_symbol_sample_gap(same_sym) == ""
    assert soft_allow_anchor_gap_symbol_last_vs_lead(same_sym) == "agree"
    assert format_soft_allow_anchor_gap_bit(same_sym) == (
        "2 gap · last AAPL · lead AAPL · 100% · agree · hot · 100% · "
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
