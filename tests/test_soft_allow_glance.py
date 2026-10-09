"""Fail-open soft-allow glance (display only)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from openbb_backend.desk import build_soft_allow_glance
from stock_checker.gate_audit import soft_allow_last_vs_lead


def test_soft_allow_last_vs_lead_helper() -> None:
    assert soft_allow_last_vs_lead("rs", "breadth") == "last vs lead · breadth"
    assert soft_allow_last_vs_lead("rs", "RS") == "agree"
    assert soft_allow_last_vs_lead("", "breadth") == ""
    assert soft_allow_last_vs_lead("rs", "") == ""


def test_soft_allow_glance_empty() -> None:
    assert build_soft_allow_glance(None)["ready"] is False
    assert build_soft_allow_glance([])["ready"] is False


def test_soft_allow_glance_one() -> None:
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    g = build_soft_allow_glance(
        [
            {
                "at": "2026-09-23T11:00:00Z",
                "gate": "regime",
                "reason": "unknown — no SPY bars",
            }
        ],
        now=now,
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["severity"] == "hot"
    assert g["count"] == 1
    assert g["fresh_count"] == 1
    assert g["aging_count"] == 0
    assert g["expired_count"] == 0
    assert g["aging_hours"] == 12.0
    assert g["last_gate"] == "regime"
    assert g["anchor_gap_count"] == 0
    assert g["anchor_gap_last"] == ""
    assert g["anchor_gap_symbol_lead"] == ""
    assert g["anchor_gap_symbol_lead_name"] == ""
    assert g["anchor_gap_symbol_lead_share"] is None
    assert g["anchor_gap_symbol_lead_margin"] is None
    assert g["anchor_gap_symbol_lead_margin_severity"] == ""
    assert g["anchor_gap_symbol_lead_margin_bit"] == ""
    assert g["anchor_gap_symbol_lead_runner"] == ""
    assert g["anchor_gap_symbol_lead_runner_count"] == 0
    assert g["anchor_gap_symbol_lead_runner_share"] is None
    assert g["anchor_gap_symbol_lead_sides"] == ""
    assert g["anchor_gap_symbol_last_vs_lead"] == ""
    assert g["anchor_gap_last_vs_lead_freshness"] == ""
    assert g["anchor_gap_last_vs_lead_freshness_warn"] is False
    assert g["anchor_gap_symbol_sample_gap"] == ""
    assert g["anchor_gap_share_pct"] is None
    assert g["anchor_gap_share_severity"] == ""
    assert g["anchor_gap_last_vs_share"] == ""
    assert g["anchor_gap_last_vs_share_warn"] is False
    assert g["anchor_gap_last_lead_vs_share"] == ""
    assert g["anchor_gap_last_lead_vs_share_warn"] is False
    assert g["anchor_gap_other_count"] == 0
    assert g["anchor_gap_other_share_pct"] is None
    assert g["anchor_gap_other_share_severity"] == ""
    assert g["anchor_gap_vs_other"] == ""
    assert g["anchor_gap_vs_other_warn"] is False
    assert g["anchor_gap_last_vs_lean"] == ""
    assert g["anchor_gap_last_vs_lean_warn"] is False
    assert g["anchor_gap_last_lead_vs_lean"] == ""
    assert g["anchor_gap_last_lead_vs_lean_warn"] is False
    assert g["anchor_gap_last_share_vs_lean"] == ""
    assert g["anchor_gap_last_share_vs_lean_warn"] is False
    assert g["anchor_gap_vs_scan_clash"] == ""
    assert g["anchor_gap_vs_scan_clash_warn"] is False
    assert g["soft_vs_gap_clock_clash"] == ""
    assert g["soft_vs_gap_clock_clash_warn"] is False
    assert g["soft_vs_cash_clock_clash"] == ""
    assert g["soft_vs_cash_clock_clash_warn"] is False
    assert g["anchor_gap_bit"] == ""
    assert g["last_freshness"] == "fresh"
    assert g["scan_freshness"] == ""
    assert g["scan_vs_soft_allow_clash"] == ""
    assert g["line"].startswith("hot · ")
    assert "1 recent soft-allow" in g["line"]
    assert "[regime]" in g["line"]
    assert "no SPY bars" in g["line"]
    assert " gap" not in g["line"]
    assert "clash" not in g["line"]


def test_soft_allow_glance_anchor_gap_count() -> None:
    """xang1234 #539: rs×N alone ≠ gappy-anchor fail-open count + share."""
    now = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
    g = build_soft_allow_glance(
        [
            {
                "at": "2026-10-08T11:00:00Z",
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            },
            {
                "at": "2026-10-08T10:30:00Z",
                "gate": "rs",
                "reason": "SPY RS unknown — allow",
            },
            {
                "at": "2026-10-08T10:00:00Z",
                "gate": "rs",
                "reason": "MSFT RS unknown — anchor gap — allow",
            },
        ],
        now=now,
    )
    assert g["ready"] is True
    assert g["anchor_gap_count"] == 2
    assert g["anchor_gap_last"] == "AAPL"
    assert g["anchor_gap_last_freshness"] == "fresh"
    assert g["anchor_gap_symbol_lead"] == ""
    assert g["anchor_gap_symbol_last_vs_lead"] == ""
    assert g["anchor_gap_symbol_sample_gap"] == "tied"
    assert g["anchor_gap_share_pct"] == 66.7
    assert g["anchor_gap_share_severity"] == "hot"
    assert g["anchor_gap_last_vs_share"] == "align · fresh · hot"
    assert g["anchor_gap_last_vs_share_warn"] is False
    assert g["anchor_gap_other_count"] == 1
    assert g["anchor_gap_other_share_pct"] == 33.3
    assert g["anchor_gap_other_share_severity"] == "thin"
    assert g["anchor_gap_vs_other"] == "align · hot|thin"
    assert g["anchor_gap_vs_other_warn"] is False
    assert g["anchor_gap_last_vs_lean"] == "align · fresh · hot|thin"
    assert g["anchor_gap_last_vs_lean_warn"] is False
    assert g["anchor_gap_last_share_vs_lean"] == "align · both align"
    assert g["anchor_gap_last_share_vs_lean_warn"] is False
    assert g["anchor_gap_bit"] == (
        "2 gap · last AAPL · fresh · tied · hot · 66.7% · "
        "last/share align · fresh · hot · vs 1 other · thin · "
        "33.3% · gap vs other align · hot|thin · "
        "last/lean align · fresh · hot|thin · "
        "share/lean align · both align"
    )
    assert (
        "2 gap · last AAPL · fresh · tied · hot · 66.7% · "
        "last/share align · fresh · hot · vs 1 other · thin · "
        "33.3% · gap vs other align · hot|thin · "
        "last/lean align · fresh · hot|thin · "
        "share/lean align · both align"
    ) in g["line"]
    assert "last [rs]" in g["line"]
    assert "anchor gap" in g["line"]


def test_soft_allow_glance_anchor_gap_symbol_lead() -> None:
    """last SYM ≠ ring ownership: strict gap-symbol lead speaks %."""
    now = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
    g = build_soft_allow_glance(
        [
            {
                "at": "2026-10-08T11:00:00Z",
                "gate": "rs",
                "reason": "MSFT RS unknown — anchor gap — allow",
            },
            {
                "at": "2026-10-08T10:45:00Z",
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            },
            {
                "at": "2026-10-08T10:30:00Z",
                "gate": "rs",
                "reason": "SPY RS unknown — allow",
            },
            {
                "at": "2026-10-08T10:00:00Z",
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            },
        ],
        now=now,
    )
    assert g["anchor_gap_count"] == 3
    assert g["anchor_gap_last"] == "MSFT"
    assert g["anchor_gap_last_freshness"] == "fresh"
    assert g["anchor_gap_symbol_lead"] == "lead AAPL · 67%"
    assert g["anchor_gap_symbol_lead_name"] == "AAPL"
    assert g["anchor_gap_symbol_lead_share"] == 67
    assert g["anchor_gap_symbol_lead_margin"] == 1
    assert g["anchor_gap_symbol_lead_margin_severity"] == "thin"
    assert g["anchor_gap_symbol_lead_margin_bit"] == "ahead thin · +1"
    assert g["anchor_gap_symbol_lead_runner"] == "MSFT"
    assert g["anchor_gap_symbol_lead_runner_count"] == 1
    assert g["anchor_gap_symbol_lead_runner_share"] == 33
    assert g["anchor_gap_symbol_lead_sides"] == "vs MSFT · 1 · 33%"
    assert g["anchor_gap_symbol_last_vs_lead"] == "last vs lead · MSFT"
    assert g["anchor_gap_last_vs_lead_freshness"] == (
        "clash · fresh · vs MSFT"
    )
    assert g["anchor_gap_last_vs_lead_freshness_warn"] is True
    assert g["anchor_gap_symbol_sample_gap"] == ""
    assert g["anchor_gap_last_vs_share"] == "align · fresh · hot"
    assert g["anchor_gap_last_vs_share_warn"] is False
    assert g["anchor_gap_last_lead_vs_share"] == (
        "clash · lead clash · share align"
    )
    assert g["anchor_gap_last_lead_vs_share_warn"] is True
    assert g["anchor_gap_last_vs_lean"] == "align · fresh · hot|thin"
    assert g["anchor_gap_last_vs_lean_warn"] is False
    assert g["anchor_gap_last_lead_vs_lean"] == (
        "clash · lead clash · lean align"
    )
    assert g["anchor_gap_last_lead_vs_lean_warn"] is True
    assert g["anchor_gap_last_share_vs_lean"] == "align · both align"
    assert g["anchor_gap_last_share_vs_lean_warn"] is False
    assert g["anchor_gap_bit"] == (
        "3 gap · last MSFT · fresh · lead AAPL · 67% · last vs lead · MSFT · "
        "last/lead clash · fresh · vs MSFT · "
        "ahead thin · +1 · vs MSFT · 1 · 33% · hot · 75% · "
        "last/share align · fresh · hot · "
        "lead/share clash · lead clash · share align · "
        "vs 1 other · thin · 25% · gap vs other align · hot|thin · "
        "last/lean align · fresh · hot|thin · "
        "lead/lean clash · lead clash · lean align · "
        "share/lean align · both align"
    )
    assert "lead AAPL · 67%" in g["line"]
    assert "last vs lead · MSFT" in g["line"]
    assert "last/lead clash · fresh · vs MSFT" in g["line"]
    assert "ahead thin · +1" in g["line"]
    assert "vs MSFT · 1 · 33%" in g["line"]
    assert "last/share align · fresh · hot" in g["line"]
    assert "lead/share clash · lead clash · share align" in g["line"]
    assert "last/lean align · fresh · hot|thin" in g["line"]
    assert "lead/lean clash · lead clash · lean align" in g["line"]
    assert "share/lean align · both align" in g["line"]


def test_soft_allow_glance_anchor_gap_last_vs_lead_freshness_stale_agree() -> None:
    """Bare agree ≠ live owner: expired + agree clashes and warns."""
    now = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
    stale = (now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {
                "at": stale,
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            },
            {
                "at": stale,
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            },
        ],
        now=now,
    )
    assert g["anchor_gap_symbol_last_vs_lead"] == "agree"
    assert g["anchor_gap_last_vs_lead_freshness"] == (
        "clash · expired · agree"
    )
    assert g["anchor_gap_last_vs_lead_freshness_warn"] is True
    assert g["anchor_gap_last_vs_share"] == "clash · expired · hot"
    assert g["anchor_gap_last_lead_vs_share"] == "align · both clash"
    assert g["anchor_gap_last_lead_vs_share_warn"] is True
    assert g["anchor_gap_last_vs_lean"] == "clash · expired · hot|thin"
    assert g["anchor_gap_last_lead_vs_lean"] == "align · both clash"
    assert g["anchor_gap_last_lead_vs_lean_warn"] is True
    assert g["tone"] == "warn"
    assert "last/lead clash · expired · agree" in g["anchor_gap_bit"]
    assert "lead/share align · both clash" in g["anchor_gap_bit"]
    assert "lead/lean align · both clash" in g["anchor_gap_bit"]
    assert "last/lead clash · expired · agree" in g["line"]
    assert "lead/share align · both clash" in g["line"]
    assert "lead/lean align · both clash" in g["line"]


def test_soft_allow_glance_anchor_gap_share_lean_both_clash_warns() -> None:
    """Dual-clash agreement ≠ calm: align · both clash warns + tone."""
    now = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
    stale = (now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {
                "at": stale,
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            },
            {
                "at": stale,
                "gate": "rs",
                "reason": "MSFT RS unknown — anchor gap — allow",
            },
            {
                "at": stale,
                "gate": "rs",
                "reason": "SPY RS unknown — allow",
            },
        ],
        now=now,
    )
    assert g["anchor_gap_last_freshness"] == "expired"
    assert g["anchor_gap_share_severity"] == "hot"
    assert g["anchor_gap_last_vs_share"] == "clash · expired · hot"
    assert g["anchor_gap_last_vs_share_warn"] is True
    assert g["anchor_gap_vs_other"] == "align · hot|thin"
    assert g["anchor_gap_vs_other_warn"] is False
    assert g["anchor_gap_last_vs_lean"] == "clash · expired · hot|thin"
    assert g["anchor_gap_last_vs_lean_warn"] is True
    assert g["anchor_gap_last_share_vs_lean"] == "align · both clash"
    assert g["anchor_gap_last_share_vs_lean_warn"] is True
    assert g["severity"] == "cool"
    assert g["tone"] == "warn"
    assert "share/lean align · both clash" in g["anchor_gap_bit"]
    assert "share/lean align · both clash" in g["line"]


def test_soft_allow_glance_anchor_gap_share_quiet() -> None:
    """portfolio AI: low gap ownership speaks quiet · % + vs other strong."""
    now = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
    g = build_soft_allow_glance(
        [
            {
                "at": "2026-10-08T11:00:00Z",
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            },
            {
                "at": "2026-10-08T10:45:00Z",
                "gate": "rs",
                "reason": "MSFT RS unknown — allow",
            },
            {
                "at": "2026-10-08T10:30:00Z",
                "gate": "regime",
                "reason": "unknown — no SPY bars",
            },
            {
                "at": "2026-10-08T10:00:00Z",
                "gate": "breadth",
                "reason": "unknown scan",
            },
        ],
        now=now,
    )
    assert g["anchor_gap_count"] == 1
    assert g["anchor_gap_last"] == "AAPL"
    assert g["anchor_gap_last_freshness"] == "fresh"
    assert g["anchor_gap_symbol_lead"] == ""
    assert g["anchor_gap_symbol_sample_gap"] == "n=1"
    assert g["anchor_gap_share_pct"] == 25.0
    assert g["anchor_gap_share_severity"] == "quiet"
    assert g["anchor_gap_last_vs_share"] == "clash · fresh · quiet"
    assert g["anchor_gap_last_vs_share_warn"] is True
    assert g["anchor_gap_other_count"] == 3
    assert g["anchor_gap_other_share_pct"] == 75.0
    assert g["anchor_gap_other_share_severity"] == "strong"
    assert g["anchor_gap_vs_other"] == "align · quiet|strong"
    assert g["anchor_gap_vs_other_warn"] is False
    assert g["anchor_gap_last_vs_lean"] == "align · fresh · quiet|strong"
    assert g["anchor_gap_last_vs_lean_warn"] is False
    assert g["anchor_gap_last_share_vs_lean"] == (
        "clash · share clash · lean align"
    )
    assert g["anchor_gap_last_share_vs_lean_warn"] is True
    assert g["anchor_gap_bit"] == (
        "1 gap · last AAPL · fresh · n=1 · quiet · 25% · "
        "last/share clash · fresh · quiet · vs 3 other · strong · "
        "75% · gap vs other align · quiet|strong · "
        "last/lean align · fresh · quiet|strong · "
        "share/lean clash · share clash · lean align"
    )
    assert (
        "1 gap · last AAPL · fresh · n=1 · quiet · 25% · "
        "last/share clash · fresh · quiet · vs 3 other · strong · "
        "75% · gap vs other align · quiet|strong · "
        "last/lean align · fresh · quiet|strong · "
        "share/lean clash · share clash · lean align"
    ) in g["line"]


def test_soft_allow_glance_anchor_gap_vs_other_clash() -> None:
    """Sides alone ≠ lean: gap hot + other mid speaks clash (junk_vs_ok)."""
    now = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
    g = build_soft_allow_glance(
        [
            {
                "at": "2026-10-08T11:00:00Z",
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            },
            {
                "at": "2026-10-08T10:30:00Z",
                "gate": "rs",
                "reason": "SPY RS unknown — allow",
            },
        ],
        now=now,
    )
    assert g["anchor_gap_share_severity"] == "hot"
    assert g["anchor_gap_last"] == "AAPL"
    assert g["anchor_gap_last_freshness"] == "fresh"
    assert g["anchor_gap_last_vs_share"] == "align · fresh · hot"
    assert g["anchor_gap_last_vs_share_warn"] is False
    assert g["anchor_gap_symbol_lead"] == ""
    assert g["anchor_gap_symbol_sample_gap"] == "n=1"
    assert g["anchor_gap_other_share_severity"] == "ok"
    assert g["anchor_gap_vs_other"] == "clash · gap hot · other ok"
    assert g["anchor_gap_vs_other_warn"] is True
    assert g["anchor_gap_last_vs_lean"] == "clash · fresh · gap hot · other ok"
    assert g["anchor_gap_last_vs_lean_warn"] is True
    assert g["anchor_gap_last_share_vs_lean"] == (
        "clash · share align · lean clash"
    )
    assert g["anchor_gap_last_share_vs_lean_warn"] is True
    assert "1 gap · last AAPL · fresh · n=1 · hot · 50%" in g["anchor_gap_bit"]
    assert "last/share align · fresh · hot" in g["anchor_gap_bit"]
    assert "gap vs other clash · gap hot · other ok" in g["anchor_gap_bit"]
    assert "last/lean clash · fresh · gap hot · other ok" in g["anchor_gap_bit"]
    assert (
        "share/lean clash · share align · lean clash" in g["anchor_gap_bit"]
    )
    assert "gap vs other clash · gap hot · other ok" in g["line"]


def test_soft_allow_glance_anchor_gap_last_freshness_aging() -> None:
    """Cursor name ≠ live fail-open: aging/expired speak after last SYM."""
    now = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
    aging = (now - timedelta(hours=18)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {
                "at": aging,
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            },
            {
                "at": aging,
                "gate": "rs",
                "reason": "SPY RS unknown — allow",
            },
        ],
        now=now,
    )
    assert g["anchor_gap_last"] == "AAPL"
    assert g["anchor_gap_last_freshness"] == "aging"
    assert g["anchor_gap_share_severity"] == "hot"
    assert g["anchor_gap_last_vs_share"] == ""
    assert g["anchor_gap_last_vs_share_warn"] is False
    assert g["anchor_gap_vs_other_warn"] is True
    assert g["anchor_gap_last_vs_lean"] == ""
    assert g["anchor_gap_last_vs_lean_warn"] is False
    assert g["anchor_gap_last_share_vs_lean"] == ""
    assert g["anchor_gap_last_share_vs_lean_warn"] is False
    # Hot share / lean clash escalate tone; severity stays aging (not hot).
    assert g["severity"] == "aging"
    assert g["tone"] == "warn"
    assert g["anchor_gap_bit"].startswith("1 gap · last AAPL · aging · n=1")
    assert "last AAPL · aging" in g["line"]
    assert "last/share" not in g["anchor_gap_bit"]
    assert "last/lean" not in g["anchor_gap_bit"]
    assert "share/lean" not in g["anchor_gap_bit"]


def test_soft_allow_glance_anchor_gap_expired_tone_warn() -> None:
    """RyanJHamby age≠severity: expired gap cursor warns; cool-off stays cool."""
    now = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
    stale = (now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    other = {
        "at": stale,
        "gate": "rs",
        "reason": "SPY RS unknown — allow",
    }
    g = build_soft_allow_glance(
        [
            {
                "at": stale,
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            },
            other,
            {**other, "reason": "MSFT RS unknown — allow"},
            {**other, "reason": "NVDA RS unknown — allow"},
        ],
        now=now,
    )
    assert g["anchor_gap_last_freshness"] == "expired"
    assert g["anchor_gap_share_severity"] == "quiet"
    assert g["anchor_gap_last_vs_share"] == "align · expired · quiet"
    assert g["anchor_gap_last_vs_share_warn"] is False
    assert g["anchor_gap_vs_other_warn"] is False
    assert g["anchor_gap_last_vs_lean"] == "clash · expired · quiet|strong"
    assert g["anchor_gap_last_vs_lean_warn"] is True
    assert g["anchor_gap_last_share_vs_lean"] == (
        "clash · share align · lean clash"
    )
    assert g["anchor_gap_last_share_vs_lean_warn"] is True
    assert g["severity"] == "cool"
    assert g["tone"] == "warn"
    assert "last AAPL · expired" in g["anchor_gap_bit"]
    assert "last/share align · expired · quiet" in g["anchor_gap_bit"]
    assert "last/lean clash · expired · quiet|strong" in g["anchor_gap_bit"]
    assert (
        "share/lean clash · share align · lean clash" in g["anchor_gap_bit"]
    )


def test_soft_allow_glance_anchor_gap_last_vs_share_clash_tone() -> None:
    """Cursor age ≠ ownership heat: expired·hot clash warns (cool-off cool)."""
    now = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
    stale = (now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {
                "at": stale,
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            },
            {
                "at": stale,
                "gate": "rs",
                "reason": "SPY RS unknown — allow",
            },
        ],
        now=now,
    )
    assert g["anchor_gap_last_freshness"] == "expired"
    assert g["anchor_gap_share_severity"] == "hot"
    assert g["anchor_gap_last_vs_share"] == "clash · expired · hot"
    assert g["anchor_gap_last_vs_share_warn"] is True
    assert g["anchor_gap_last_vs_lean"] == (
        "align · expired · gap hot · other ok"
    )
    assert g["anchor_gap_last_vs_lean_warn"] is False
    assert g["anchor_gap_last_share_vs_lean"] == (
        "clash · share clash · lean align"
    )
    assert g["anchor_gap_last_share_vs_lean_warn"] is True
    assert g["severity"] == "cool"
    assert g["tone"] == "warn"
    assert "last/share clash · expired · hot" in g["anchor_gap_bit"]
    assert "last/share clash · expired · hot" in g["line"]
    assert "last/lean align · expired · gap hot · other ok" in g["line"]
    assert "share/lean clash · share clash · lean align" in g["line"]


def test_soft_allow_glance_anchor_gap_aging_quiet_stays_flat() -> None:
    """Aging quiet gap label alone does not escalate (expired/hot/clash do)."""
    now = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
    aging = (now - timedelta(hours=18)).strftime("%Y-%m-%dT%H:%M:%SZ")
    other = {
        "at": aging,
        "gate": "rs",
        "reason": "SPY RS unknown — allow",
    }
    g = build_soft_allow_glance(
        [
            {
                "at": aging,
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            },
            other,
            {**other, "reason": "MSFT RS unknown — allow"},
            {**other, "reason": "NVDA RS unknown — allow"},
        ],
        now=now,
    )
    assert g["anchor_gap_last_freshness"] == "aging"
    assert g["anchor_gap_share_severity"] == "quiet"
    assert g["anchor_gap_last_vs_share"] == ""
    assert g["anchor_gap_last_vs_share_warn"] is False
    assert g["anchor_gap_vs_other_warn"] is False
    assert g["anchor_gap_last_vs_lean"] == ""
    assert g["anchor_gap_last_vs_lean_warn"] is False
    assert g["anchor_gap_last_share_vs_lean"] == ""
    assert g["anchor_gap_last_share_vs_lean_warn"] is False
    assert g["severity"] == "aging"
    assert g["tone"] == "flat"


def test_soft_allow_glance_truncates_reason() -> None:
    long = "x" * 100
    g = build_soft_allow_glance([{"at": "t", "gate": "rs", "reason": long}])
    assert g["ready"] is True
    assert g["last_reason"].endswith("…")
    assert len(g["last_reason"]) <= 72


def test_soft_allow_glance_speaks_aging() -> None:
    """xang1234 / RyanJHamby: aging (>12h) speaks before expired."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    aging = (now - timedelta(hours=18)).strftime("%Y-%m-%dT%H:%M:%SZ")
    fresh = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {"at": fresh, "gate": "rs", "reason": "insufficient history"},
            {"at": aging, "gate": "breadth", "reason": "unknown scan"},
        ],
        now=now,
    )
    assert g["count"] == 2
    assert g["fresh_count"] == 1
    assert g["aging_count"] == 1
    assert g["expired_count"] == 0
    assert g["fresh_tally"] == "rs×1"
    assert g["aging_tally"] == "breadth×1"
    assert g["expired_tally"] == ""
    assert g["severity"] == "hot"
    assert g["tone"] == "warn"
    assert g["line"].startswith("hot · ")
    assert "2 soft-allows" in g["line"]
    assert "1 fresh" in g["line"]
    assert "rs×1" in g["line"]
    assert "1 aging" in g["line"]
    assert "breadth×1" in g["line"]
    assert "expired" not in g["line"]
    assert "[rs]" in g["line"]


def test_soft_allow_glance_consolidates_expired() -> None:
    """tradermonty #437: expired soft-allows speak count + gate tally."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    stale = (now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    aging = (now - timedelta(hours=18)).strftime("%Y-%m-%dT%H:%M:%SZ")
    fresh = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {"at": fresh, "gate": "rs", "reason": "insufficient history"},
            {"at": aging, "gate": "breadth", "reason": "unknown scan"},
            {"at": stale, "gate": "regime", "reason": "unknown — no SPY bars"},
            {"at": stale, "gate": "regime", "reason": "unknown — no BTC bars"},
        ],
        now=now,
        fresh_hours=24.0,
    )
    assert g["count"] == 4
    assert g["fresh_count"] == 1
    assert g["aging_count"] == 1
    assert g["expired_count"] == 2
    assert g["fresh_tally"] == "rs×1"
    assert g["aging_tally"] == "breadth×1"
    assert g["expired_tally"] == "regime×2"
    assert g["severity"] == "hot"
    assert g["tone"] == "warn"
    assert g["line"].startswith("hot · ")
    assert "4 soft-allows" in g["line"]
    assert "1 fresh" in g["line"]
    assert "rs×1" in g["line"]
    assert "1 aging" in g["line"]
    assert "breadth×1" in g["line"]
    assert "2 expired" in g["line"]
    assert "regime×2" in g["line"]
    assert "[rs]" in g["line"]


def test_soft_allow_glance_aging_tally_only() -> None:
    """Aging-only ledger consolidates gates like the expired all-expired path."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    aging = (now - timedelta(hours=18)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {"at": aging, "gate": "breadth", "reason": "unknown scan a"},
            {"at": aging, "gate": "breadth", "reason": "unknown scan b"},
            {"at": aging, "gate": "rs", "reason": "insufficient history"},
        ],
        now=now,
    )
    assert g["aging_count"] == 3
    assert g["expired_count"] == 0
    assert g["fresh_tally"] == ""
    assert g["aging_tally"] == "breadth×2 · rs×1"
    assert g["severity"] == "aging"
    assert g["tone"] == "flat"
    assert g["lead_bit"] == (
        "breadth leads · aging · ×2 · 67% · ahead thin · +1 · vs rs ×1 · 33% · share Δ wide · +33pp"
    )
    assert g["lead_runner_gate"] == "rs"
    assert g["lead_runner_count"] == 1
    assert g["lead_runner_share_pct"] == 33.3
    assert g["lead_share_delta_pp"] == 33.4
    assert g["lead_share_delta_severity"] == "wide"
    assert g["lead_share_vs_delta"] == ""
    assert g["line"].startswith(
        "aging · breadth leads · aging · ×2 · 67% · ahead thin · +1 · vs rs ×1 · 33% · "
        "share Δ wide · +33pp · "
    )
    assert "3 soft-allows" in g["line"]
    assert "3 aging" in g["line"]
    assert "breadth×2" in g["line"]
    assert "rs×1" in g["line"]
    assert "fresh" not in g["line"]
    assert "expired" not in g["line"]


def test_soft_allow_glance_fresh_tally_mixed() -> None:
    """portfolio AI + xang1234: fresh gate tally beside aging/expired."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    aging = (now - timedelta(hours=18)).strftime("%Y-%m-%dT%H:%M:%SZ")
    fresh = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {"at": fresh, "gate": "rs", "reason": "insufficient a"},
            {"at": fresh, "gate": "regime", "reason": "no SPY bars"},
            {"at": aging, "gate": "breadth", "reason": "unknown scan"},
        ],
        now=now,
    )
    assert g["fresh_count"] == 2
    assert g["aging_count"] == 1
    assert g["fresh_tally"] == "regime×1 · rs×1"
    assert "2 fresh" in g["line"]
    assert "regime×1" in g["line"]
    assert "rs×1" in g["line"]
    assert "1 aging" in g["line"]


def test_soft_allow_glance_fresh_tally_multi_recent() -> None:
    """All-fresh multi-gate ledger consolidates without aging noise."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    fresh = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {"at": fresh, "gate": "rs", "reason": "insufficient a"},
            {"at": fresh, "gate": "rs", "reason": "insufficient b"},
            {"at": fresh, "gate": "breadth", "reason": "unknown scan"},
        ],
        now=now,
    )
    assert g["fresh_count"] == 3
    assert g["aging_count"] == 0
    assert g["expired_count"] == 0
    assert g["fresh_tally"] == "rs×2 · breadth×1"
    assert g["lead_bit"] == (
        "rs leads · fresh · ×2 · 67% · ahead thin · +1 · vs breadth ×1 · 33% · "
        "share Δ wide · +33pp"
    )
    assert g["lead_runner_gate"] == "breadth"
    assert g["lead_runner_count"] == 1
    assert g["lead_share_delta_pp"] == 33.4
    assert g["lead_share_delta_severity"] == "wide"
    assert "3 recent soft-allows" in g["line"]
    assert "rs×2" in g["line"]
    assert "breadth×1" in g["line"]
    assert "aging" not in g["line"]
    assert "expired" not in g["line"]


def test_soft_allow_glance_all_expired() -> None:
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    stale = (now - timedelta(hours=48)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {"at": stale, "gate": "promote", "reason": "ABC: skip_no_bars"},
            {"at": stale, "gate": "breadth", "reason": "unknown scan"},
        ],
        now=now,
    )
    assert g["expired_count"] == 2
    assert g["fresh_count"] == 0
    assert g["aging_count"] == 0
    assert g["severity"] == "cool"
    assert g["tone"] == "flat"
    assert g["line"].startswith("cool · ")
    assert "2 expired soft-allows" in g["line"]
    assert "breadth×1" in g["line"]
    assert "promote×1" in g["line"]


def test_soft_allow_glance_cool_off_severity_triad() -> None:
    """portfolio AI + xang1234: hot / aging / cool — expired is not warn."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    fresh = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    aging = (now - timedelta(hours=18)).strftime("%Y-%m-%dT%H:%M:%SZ")
    stale = (now - timedelta(hours=48)).strftime("%Y-%m-%dT%H:%M:%SZ")
    hot = build_soft_allow_glance(
        [{"at": fresh, "gate": "rs", "reason": "insufficient"}],
        now=now,
    )
    cooling = build_soft_allow_glance(
        [{"at": aging, "gate": "breadth", "reason": "unknown scan"}],
        now=now,
    )
    cool = build_soft_allow_glance(
        [{"at": stale, "gate": "regime", "reason": "no SPY bars"}],
        now=now,
    )
    assert (hot["severity"], hot["tone"]) == ("hot", "warn")
    assert (cooling["severity"], cooling["tone"]) == ("aging", "flat")
    assert (cool["severity"], cool["tone"]) == ("cool", "flat")
    assert hot["lead_bit"] == ""
    assert cooling["lead_bit"] == ""
    assert cool["lead_bit"] == ""


def test_soft_allow_glance_lead_gate_hot() -> None:
    """portfolio AI concentration: dominant fresh gate after severity."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    fresh = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {"at": fresh, "gate": "rs", "reason": "insufficient a"},
            {"at": fresh, "gate": "rs", "reason": "insufficient b"},
            {"at": fresh, "gate": "breadth", "reason": "unknown scan"},
        ],
        now=now,
    )
    assert g["severity"] == "hot"
    assert g["lead_gate"] == "rs"
    assert g["lead_count"] == 2
    assert g["lead_share_pct"] == 66.7
    assert g["lead_margin"] == 1
    assert g["lead_margin_severity"] == "thin"
    assert g["lead_runner_gate"] == "breadth"
    assert g["lead_runner_count"] == 1
    assert g["lead_band"] == "fresh"
    assert g["lead_bit"] == (
        "rs leads · fresh · ×2 · 67% · ahead thin · +1 · vs breadth ×1 · 33% · share Δ wide · +33pp"
    )
    assert g["lead_share_delta_pp"] == 33.4
    assert g["lead_share_delta_severity"] == "wide"
    assert g["lead_share_vs_delta"] == ""
    assert g["line"].startswith(
        "hot · rs leads · fresh · ×2 · 67% · ahead thin · +1 · vs breadth ×1 · 33% · "
        "share Δ wide · +33pp · "
    )
    assert "rs×2" in g["line"]


def test_soft_allow_glance_lead_gate_aging() -> None:
    """Aging severity drives lead from the aging band (not expired)."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    aging = (now - timedelta(hours=18)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {"at": aging, "gate": "breadth", "reason": "unknown scan a"},
            {"at": aging, "gate": "breadth", "reason": "unknown scan b"},
            {"at": aging, "gate": "rs", "reason": "insufficient history"},
        ],
        now=now,
    )
    assert g["severity"] == "aging"
    assert g["lead_gate"] == "breadth"
    assert g["lead_count"] == 2
    assert g["lead_share_pct"] == 66.7
    assert g["lead_margin"] == 1
    assert g["lead_margin_severity"] == "thin"
    assert g["lead_runner_gate"] == "rs"
    assert g["lead_runner_count"] == 1
    assert g["lead_band"] == "aging"
    assert g["lead_bit"] == (
        "breadth leads · aging · ×2 · 67% · ahead thin · +1 · vs rs ×1 · 33% · share Δ wide · +33pp"
    )
    assert g["lead_share_delta_pp"] == 33.4
    assert g["lead_share_delta_severity"] == "wide"
    assert g["line"].startswith(
        "aging · breadth leads · aging · ×2 · 67% · ahead thin · +1 · vs rs ×1 · 33% · "
        "share Δ wide · +33pp · "
    )


def test_soft_allow_glance_lead_gate_tie_silent() -> None:
    """Tied top gates stay silent — no false concentration."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    fresh = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {"at": fresh, "gate": "rs", "reason": "insufficient a"},
            {"at": fresh, "gate": "rs", "reason": "insufficient b"},
            {"at": fresh, "gate": "regime", "reason": "no SPY a"},
            {"at": fresh, "gate": "regime", "reason": "no SPY b"},
        ],
        now=now,
    )
    assert g["fresh_tally"] == "regime×2 · rs×2"
    assert g["lead_bit"] == ""
    assert g["lead_gate"] == ""
    assert g["lead_share_pct"] is None
    assert g["lead_margin"] is None
    assert g["lead_margin_severity"] == ""
    assert g["lead_runner_gate"] == ""
    assert g["lead_runner_count"] == 0
    assert g["lead_share_delta_pp"] is None
    assert g["lead_share_delta_severity"] == ""
    assert "leads" not in g["line"]


def test_soft_allow_glance_lead_gate_cool_expired() -> None:
    """Cool severity drives lead from the expired band."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    stale = (now - timedelta(hours=48)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {"at": stale, "gate": "regime", "reason": "no SPY bars"},
            {"at": stale, "gate": "regime", "reason": "no BTC bars"},
            {"at": stale, "gate": "promote", "reason": "ABC: skip_no_bars"},
        ],
        now=now,
    )
    assert g["severity"] == "cool"
    assert g["lead_gate"] == "regime"
    assert g["lead_count"] == 2
    assert g["lead_share_pct"] == 66.7
    assert g["lead_margin"] == 1
    assert g["lead_margin_severity"] == "thin"
    assert g["lead_runner_gate"] == "promote"
    assert g["lead_runner_count"] == 1
    assert g["lead_band"] == "expired"
    assert g["lead_bit"] == (
        "regime leads · expired · ×2 · 67% · ahead thin · +1 · vs promote ×1 · 33% · "
        "share Δ wide · +33pp"
    )
    assert g["lead_share_delta_pp"] == 33.4
    assert g["lead_share_delta_severity"] == "wide"
    assert g["line"].startswith(
        "cool · regime leads · expired · ×2 · 67% · ahead thin · +1 · vs promote ×1 · 33% · "
        "share Δ wide · +33pp · "
    )


def test_soft_allow_glance_lead_margin_wide() -> None:
    """Wide ahead when lead clears #2 by ≥2 (share ≠ margin)."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    fresh = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {"at": fresh, "gate": "rs", "reason": "insufficient a"},
            {"at": fresh, "gate": "rs", "reason": "insufficient b"},
            {"at": fresh, "gate": "rs", "reason": "insufficient c"},
            {"at": fresh, "gate": "breadth", "reason": "unknown scan"},
        ],
        now=now,
    )
    assert g["lead_margin"] == 2
    assert g["lead_margin_severity"] == "wide"
    assert g["lead_runner_gate"] == "breadth"
    assert g["lead_runner_count"] == 1
    assert g["lead_runner_share_pct"] == 25.0
    assert g["lead_share_delta_pp"] == 50.0
    assert g["lead_share_delta_severity"] == "wide"
    assert g["lead_share_vs_delta"] == "align"
    assert g["lead_share_vs_delta_ahead"] == "wide"
    assert g["lead_share_vs_delta_share"] == "wide"
    assert g["lead_bit"] == (
        "rs leads · fresh · ×3 · 75% · ahead wide · +2 · vs breadth ×1 · 25% · "
        "share Δ wide · +50pp · share vs Δ align · wide"
    )
    assert g["line"].startswith(
        "hot · rs leads · fresh · ×3 · 75% · ahead wide · +2 · vs breadth ×1 · 25% · "
        "share Δ wide · +50pp · share vs Δ align · wide · "
    )


def test_soft_allow_glance_lead_sole_no_ahead() -> None:
    """Sole-gate 100% share still omits ahead (no runner-up)."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    fresh = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {"at": fresh, "gate": "rs", "reason": "insufficient a"},
            {"at": fresh, "gate": "rs", "reason": "insufficient b"},
        ],
        now=now,
    )
    assert g["lead_share_pct"] == 100.0
    assert g["lead_margin"] is None
    assert g["lead_margin_severity"] == ""
    assert g["lead_runner_gate"] == ""
    assert g["lead_runner_count"] == 0
    assert g["lead_bit"] == "rs leads · fresh · ×2 · 100%"
    assert "ahead" not in g["lead_bit"]
    assert "vs " not in g["lead_bit"]
    assert g["lead_runner_share_pct"] is None
    assert g["lead_share_delta_pp"] is None
    assert g["lead_share_delta_severity"] == ""
    assert g["lead_share_vs_delta"] == ""
    assert "share Δ" not in g["lead_bit"]


def test_soft_allow_glance_lead_share_delta_mid_clash() -> None:
    """Mid ownership spread: share Δ silent; share vs Δ clash speaks."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    fresh = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
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
    assert g["lead_share_pct"] == 57.1
    assert g["lead_runner_share_pct"] == 42.9
    assert g["lead_share_delta_pp"] is None
    assert g["lead_share_delta_severity"] == ""
    assert g["lead_share_vs_delta"] == "clash"
    assert g["lead_share_vs_delta_ahead"] == "thin"
    assert g["lead_share_vs_delta_share"] == "mid"
    assert g["lead_bit"] == (
        "rs leads · fresh · ×4 · 57% · ahead thin · +1 · vs regime ×3 · 43% · "
        "share vs Δ clash · ahead thin · share mid"
    )
    assert "share Δ" not in g["lead_bit"]


def test_soft_allow_glance_lead_share_delta_thin() -> None:
    """Thin ownership spread speaks when |Δ| < 10pp; align when ahead thin."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    fresh = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
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
    assert g["lead_share_delta_pp"] == 9.0
    assert g["lead_share_delta_severity"] == "thin"
    assert g["lead_share_vs_delta"] == "align"
    assert g["lead_share_vs_delta_ahead"] == "thin"
    assert g["lead_share_vs_delta_share"] == "thin"
    assert g["lead_bit"] == (
        "rs leads · fresh · ×6 · 54% · ahead thin · +1 · vs regime ×5 · 46% · "
        "share Δ thin · +9pp · share vs Δ align · thin"
    )


def test_soft_allow_glance_last_vs_lead() -> None:
    """Newest gate vs band lead — FinRobot last ≠ ring tilt (LAYA parity)."""
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    fresh = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    # Newest print is breadth; fresh band still led by rs.
    clash = build_soft_allow_glance(
        [
            {"at": fresh, "gate": "breadth", "reason": "unknown scan"},
            {"at": fresh, "gate": "rs", "reason": "insufficient a"},
            {"at": fresh, "gate": "rs", "reason": "insufficient b"},
        ],
        now=now,
    )
    assert clash["lead_gate"] == "rs"
    assert clash["last_gate"] == "breadth"
    assert clash["last_vs_lead"] == "last vs lead · breadth"
    assert "last vs lead · breadth" in clash["line"]
    assert clash["line"].startswith(
        "hot · rs leads · fresh · ×2 · 67% · ahead thin · +1 · vs breadth ×1 · 33% · "
        "share Δ wide · +33pp · last vs lead · breadth · "
    )

    # Newest matches lead — speak agree (silent confirm hid match).
    match = build_soft_allow_glance(
        [
            {"at": fresh, "gate": "rs", "reason": "insufficient a"},
            {"at": fresh, "gate": "rs", "reason": "insufficient b"},
            {"at": fresh, "gate": "breadth", "reason": "unknown scan"},
        ],
        now=now,
    )
    assert match["lead_gate"] == "rs"
    assert match["last_gate"] == "rs"
    assert match["last_vs_lead"] == "agree"
    assert " · agree · " in match["line"]
    assert "last vs lead" not in match["line"]

    # No lead (thin) — speak n=1 (last-row ≠ ring tilt; LAYA sample-gap parity).
    thin = build_soft_allow_glance(
        [{"at": fresh, "gate": "breadth", "reason": "unknown scan"}],
        now=now,
    )
    assert thin["lead_gate"] == ""
    assert thin["last_vs_lead"] == ""
    assert thin["sample_gap"] == "n=1"
    assert "n=1" in thin["line"]
    assert thin["line"].startswith("hot · n=1 · ")
    assert "last vs lead" not in thin["line"]
    assert "agree" not in thin["line"]

    # No lead (ties) — speak tied (≥2 in band, no strict winner).
    tied = build_soft_allow_glance(
        [
            {"at": fresh, "gate": "rs", "reason": "insufficient a"},
            {"at": fresh, "gate": "breadth", "reason": "unknown scan"},
        ],
        now=now,
    )
    assert tied["lead_gate"] == ""
    assert tied["sample_gap"] == "tied"
    assert "tied" in tied["line"]
    assert tied["line"].startswith("hot · tied · ")
    assert "leads" not in tied["line"]

    # Lead cases stay silent on sample_gap.
    assert match["sample_gap"] == ""
    assert "n=1" not in match["line"]
    assert "tied" not in match["line"]


def test_soft_allow_glance_scan_clash_expired_vs_fresh() -> None:
    """xang1234 #549: expired soft-allow ≠ fresh scan → clash · scan fresh."""
    now = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)
    expired_at = (now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    scan_at = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {
                "at": expired_at,
                "gate": "rs",
                "reason": "AAPL RS unknown — allow",
            }
        ],
        now=now,
        scan_time=scan_at,
        scan_interval_sec=900,
    )
    assert g["ready"] is True
    assert g["last_freshness"] == "stale"
    assert g["scan_freshness"] == "fresh"
    assert g["scan_vs_soft_allow_clash"] == "clash · scan fresh"
    assert g["tone"] == "warn"
    assert g["severity"] == "cool"
    assert g["line"].startswith("cool · clash · scan fresh · ")
    assert "clash" in g["line"]
    same = build_soft_allow_glance(
        [
            {
                "at": expired_at,
                "gate": "rs",
                "reason": "AAPL RS unknown — allow",
            }
        ],
        now=now,
        scan_time=expired_at,
        scan_interval_sec=900,
    )
    assert same["scan_freshness"] == "stale"
    assert same["scan_vs_soft_allow_clash"] == ""
    # Soft↔scan same band — soft≠cash may still speak (pinned print age).
    assert "clash · scan" not in same["line"]
    if same["soft_vs_cash_clock_clash"]:
        assert same["tone"] == "warn"
        assert same["soft_vs_cash_clock_clash"] in same["line"]
    else:
        assert same["tone"] == "flat"


def test_soft_allow_glance_scan_clash_fresh_vs_stale() -> None:
    """Fresh fail-open vs stale scan → clash · scan stale (mixed generation)."""
    now = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)
    fresh_at = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    stale_scan = (now - timedelta(hours=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {
                "at": fresh_at,
                "gate": "breadth",
                "reason": "unknown breadth — allow",
            }
        ],
        now=now,
        scan_time=stale_scan,
        scan_interval_sec=900,
    )
    assert g["last_freshness"] == "fresh"
    assert g["scan_freshness"] == "stale"
    assert g["scan_vs_soft_allow_clash"] == "clash · scan stale"
    assert g["tone"] == "warn"
    assert g["line"].startswith("hot · clash · scan stale · ")


def test_soft_allow_glance_gap_vs_scan_when_last_matches_scan() -> None:
    """xang1234 #549/e3c84e1: soft-allow last matching scan ≠ live gap cursor."""
    now = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)
    fresh_at = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    expired_at = (now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    scan_at = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {
                "at": fresh_at,
                "gate": "regime",
                "reason": "no SPY bars — allow",
            },
            {
                "at": expired_at,
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            },
        ],
        now=now,
        scan_time=scan_at,
        scan_interval_sec=900,
    )
    assert g["last_freshness"] == "fresh"
    assert g["scan_freshness"] == "fresh"
    # Soft-allow last matches scan — no ring-level clash.
    assert g["scan_vs_soft_allow_clash"] == ""
    # Soft last ≠ gap cursor — close the generation triangle.
    assert g["soft_vs_gap_clock_clash"] == (
        "clash · soft fresh · gap expired"
    )
    assert g["soft_vs_gap_clock_clash_warn"] is True
    assert "clash · soft fresh · gap expired" in g["line"]
    # Gap cursor is a different generation — speak both sides.
    assert g["anchor_gap_vs_scan_clash"] == (
        "clash · gap expired · scan fresh"
    )
    assert g["anchor_gap_vs_scan_clash_warn"] is True
    assert g["tone"] == "warn"
    assert "clash · gap expired · scan fresh" in g["anchor_gap_bit"]
    assert "last AAPL · expired · clash · gap expired · scan fresh" in (
        g["anchor_gap_bit"]
    )
    same = build_soft_allow_glance(
        [
            {
                "at": fresh_at,
                "gate": "regime",
                "reason": "no SPY bars — allow",
            },
            {
                "at": fresh_at,
                "gate": "rs",
                "reason": "AAPL RS unknown — anchor gap — allow",
            },
        ],
        now=now,
        scan_time=scan_at,
        scan_interval_sec=900,
    )
    assert same["soft_vs_gap_clock_clash"] == ""
    assert same["soft_vs_gap_clock_clash_warn"] is False
    assert "clash · soft fresh · gap" not in same["line"]
    assert "clash · soft stale · gap" not in same["line"]
    assert same["anchor_gap_vs_scan_clash"] == ""
    assert same["anchor_gap_vs_scan_clash_warn"] is False
    assert "clash · gap expired" not in same["anchor_gap_bit"]
    assert "clash · gap fresh" not in same["anchor_gap_bit"]
    assert "clash · gap aging" not in same["anchor_gap_bit"]
    # Soft↔gap silent; soft≠cash may still speak on the clip.
    if same["soft_vs_cash_clock_clash"]:
        assert same["soft_vs_cash_clock_clash"] in same["line"]


def test_soft_allow_glance_soft_vs_gap_same_when_last_is_gap() -> None:
    """When soft last *is* the gap row, soft≠gap stays silent."""
    now = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)
    expired_at = (now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {
                "at": expired_at,
                "gate": "rs",
                "reason": "MSFT RS unknown — anchor gap — allow",
            }
        ],
        now=now,
    )
    assert g["last_freshness"] == "stale"
    assert g["anchor_gap_last_freshness"] == "expired"
    assert g["soft_vs_gap_clock_clash"] == ""
    assert g["soft_vs_gap_clock_clash_warn"] is False
    assert "clash · soft" not in g["line"]


def test_soft_allow_glance_soft_vs_cash_when_soft_matches_scan() -> None:
    """xang1234 #549: soft matching scan ≠ pinned cash print generation."""
    # Saturday afternoon UTC — both cash sleeves last-published; US Fri
    # close is ~17h ago → cash aging while a fresh soft-allow + fresh
    # scan archive stay soft↔scan silent.
    now = datetime(2026, 10, 10, 14, 0, tzinfo=timezone.utc)
    fresh_at = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    g = build_soft_allow_glance(
        [
            {
                "at": fresh_at,
                "gate": "regime",
                "reason": "no SPY bars — allow",
            }
        ],
        now=now,
        scan_time=fresh_at,
        scan_interval_sec=900,
    )
    assert g["last_freshness"] == "fresh"
    assert g["scan_freshness"] == "fresh"
    assert g["scan_vs_soft_allow_clash"] == ""
    cash = g["soft_vs_cash_clock_clash"]
    assert cash.startswith("clash · soft fresh · cash ")
    assert g["soft_vs_cash_clock_clash_warn"] is True
    assert cash in g["line"]
    assert g["tone"] == "warn"
    # Same-evening last-published: soft fresh + cash fresh → silent.
    even = datetime(2026, 9, 8, 1, 30, tzinfo=timezone.utc)
    even_at = (even - timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    same = build_soft_allow_glance(
        [
            {
                "at": even_at,
                "gate": "regime",
                "reason": "no SPY bars — allow",
            }
        ],
        now=even,
        scan_time=even_at,
        scan_interval_sec=900,
    )
    assert same["last_freshness"] == "fresh"
    assert same["soft_vs_cash_clock_clash"] == ""
    assert same["soft_vs_cash_clock_clash_warn"] is False
    assert "cash" not in same["line"] or "clash · soft" not in same["line"]
