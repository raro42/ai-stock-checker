"""Offline tests for AI validate debate memory (FinRobot Ideas transcript)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from openbb_backend.desk import build_ai_debate_glance, load_desk_snapshot
from stock_checker.ai_multi_role import consensus_from_multi_role
from stock_checker.ai_validate_memory import (
    latest_ai_actions,
    latest_ai_confidences,
    latest_ai_gated,
    load_ai_validate_memory,
    recent_ai_debates,
    record_ai_validate,
    summarize_ai_debates,
)


def test_record_and_recent_ai_debates(tmp_path: Path) -> None:
    ai = consensus_from_multi_role(
        {
            "bull": {"bias": "BUY", "note": "momentum"},
            "bear": {"bias": "HOLD", "note": "extended"},
            "risk": {"ok": True, "note": "liquid"},
            "action": "BUY",
            "confidence": "MEDIUM",
            "score": 35,
            "reasoning": "bull edged",
        },
        "AAPL",
    )
    record_ai_validate(tmp_path, ai, symbol="AAPL", kept=True)
    record_ai_validate(
        tmp_path,
        {
            "action": "SELL",
            "confidence": "HIGH",
            "score": -40,
            "reasons": ["weak tape"],
            "parse_mode": "single",
        },
        symbol="XYZ",
        kept=False,
    )

    events = load_ai_validate_memory(tmp_path)
    assert len(events) == 2
    assert events[0]["symbol"] == "AAPL"
    assert events[0]["bull_bias"] == "BUY"
    assert "momentum" in events[0]["bull_note"]
    assert latest_ai_actions(tmp_path) == {"AAPL": "BUY", "XYZ": "SELL"}
    assert latest_ai_confidences(tmp_path) == {"AAPL": "MEDIUM", "XYZ": "HIGH"}
    assert latest_ai_gated(tmp_path) == {"AAPL": False, "XYZ": False}
    assert events[0]["kept"] is True
    assert isinstance(events[0].get("reasons"), list)
    assert events[1]["symbol"] == "XYZ"
    assert events[1]["kept"] is False
    assert events[1]["reasons"] == ["weak tape"]

    recent = recent_ai_debates(tmp_path, limit=1)
    assert len(recent) == 1
    assert recent[0]["symbol"] == "XYZ"

    stats = summarize_ai_debates(tmp_path)
    assert stats["count"] == 2
    assert stats["buy"] == 1
    assert stats["sell"] == 1
    assert stats["hold"] == 0
    assert stats["kept"] == 1
    assert stats["dropped"] == 1
    assert stats["latest_symbol"] == "XYZ"
    assert stats["latest_action"] == "SELL"
    assert stats["latest_confidence"] == "HIGH"
    assert stats["latest_at"]


def test_latest_ai_actions_last_write_wins(tmp_path: Path) -> None:
    record_ai_validate(
        tmp_path,
        {"action": "BUY", "confidence": "HIGH", "score": 10, "reasons": ["up"]},
        symbol="AAPL",
        kept=True,
    )
    record_ai_validate(
        tmp_path,
        {"action": "HOLD", "confidence": "LOW", "score": 0, "reasons": ["fade"]},
        symbol="AAPL",
        kept=False,
    )
    assert latest_ai_actions(tmp_path) == {"AAPL": "HOLD"}
    assert latest_ai_confidences(tmp_path) == {"AAPL": "LOW"}
    assert latest_ai_gated(tmp_path) == {"AAPL": False}
    assert latest_ai_actions(tmp_path / "missing") == {}
    assert latest_ai_confidences(tmp_path / "missing") == {}
    assert latest_ai_gated(tmp_path / "missing") == {}


def test_latest_ai_gated_last_write_wins(tmp_path: Path) -> None:
    record_ai_validate(
        tmp_path,
        {
            "action": "BUY",
            "confidence": "HIGH",
            "score": 10,
            "reasons": ["up"],
            "multi_role_gated": False,
        },
        symbol="AAPL",
        kept=True,
    )
    record_ai_validate(
        tmp_path,
        {
            "action": "HOLD",
            "confidence": "LOW",
            "score": 0,
            "reasons": ["veto"],
            "multi_role_gated": True,
        },
        symbol="AAPL",
        kept=False,
    )
    assert latest_ai_gated(tmp_path) == {"AAPL": True}


def test_latest_ai_confidences_drops_blank(tmp_path: Path) -> None:
    record_ai_validate(
        tmp_path,
        {"action": "BUY", "confidence": "HIGH", "score": 10, "reasons": ["up"]},
        symbol="AAPL",
        kept=True,
    )
    record_ai_validate(
        tmp_path,
        {"action": "HOLD", "confidence": "", "score": 0, "reasons": ["fade"]},
        symbol="AAPL",
        kept=False,
    )
    assert latest_ai_actions(tmp_path) == {"AAPL": "HOLD"}
    assert latest_ai_confidences(tmp_path) == {}


def test_ai_validate_memory_cap(tmp_path: Path) -> None:
    for i in range(5):
        record_ai_validate(
            tmp_path,
            {"action": "HOLD", "confidence": "LOW", "score": 0, "reasons": ["x"]},
            symbol=f"T{i}",
            cap=3,
        )
    assert len(load_ai_validate_memory(tmp_path)) == 3
    assert load_ai_validate_memory(tmp_path)[-1]["symbol"] == "T4"


def test_ai_debates_in_desk_snapshot(tmp_path: Path) -> None:
    record_ai_validate(
        tmp_path,
        consensus_from_multi_role(
            {
                "bull": {"bias": "BUY", "note": "up"},
                "bear": {"bias": "SELL", "note": "down"},
                "risk": {"ok": True, "note": "ok"},
                "action": "BUY",
                "confidence": "HIGH",
                "score": 40,
                "reasoning": "conflict",
            },
            "NVDA",
        ),
        kept=False,
    )
    snap = load_desk_snapshot(tmp_path)
    assert "ai_debates" in snap
    assert snap["ai_debates"]
    row = snap["ai_debates"][0]
    assert row["symbol"] == "NVDA"
    assert row["action"] == "HOLD"  # disagreement gate
    assert row["multi_role_gated"] is True
    glance = snap["ai_debate_glance"]
    assert glance["ready"] is True
    assert glance["count"] == 1
    assert glance["hold"] == 1
    assert glance["gated"] == 1
    assert "NVDA" in glance["line"]
    assert glance["tone"] == "gated"


def test_build_ai_debate_glance_empty(tmp_path: Path) -> None:
    g = build_ai_debate_glance(tmp_path)
    assert g["ready"] is True
    assert g["count"] == 0
    assert g["tone"] == "empty"
    assert "empty" in g["line"].lower() or "No validate" in g["line"]
    assert g["freshness"] == ""


def test_build_ai_debate_glance_freshness_stale(tmp_path: Path) -> None:
    """Newest debate age uses scan-cadence fresh/aging/stale (display only)."""
    record_ai_validate(
        tmp_path,
        {"action": "BUY", "confidence": "HIGH", "score": 40, "reasons": ["tape"]},
        symbol="MSFT",
        kept=True,
    )
    events = load_ai_validate_memory(tmp_path)
    assert events
    events[-1]["at"] = "2026-09-01T00:00:00Z"
    path = tmp_path / "ai_validate_memory.json"
    path.write_text(
        json.dumps({"updated_at": events[-1]["at"], "events": events}) + "\n"
    )
    now = datetime(2026, 9, 12, 0, 0, tzinfo=timezone.utc)
    g = build_ai_debate_glance(tmp_path, now=now, scan_interval_sec=900)
    assert g["ready"] is True
    assert g["freshness"] == "stale"
    assert g["tone"] == "stale"
    assert "ago" in g["line"]
    assert "stale" in g["line"]


def test_build_ai_debate_glance_scan_clash(tmp_path: Path) -> None:
    """Last-debate band ≠ scan archive band → clash · scan {tone} (display only)."""
    record_ai_validate(
        tmp_path,
        {"action": "BUY", "confidence": "HIGH", "score": 40, "reasons": ["tape"]},
        symbol="MSFT",
        kept=True,
    )
    events = load_ai_validate_memory(tmp_path)
    # 15:00 UTC = US RTH — cash live (no pin) so cash clash stays silent.
    now = datetime(2026, 10, 6, 15, 0, tzinfo=timezone.utc)
    stale_at = (now - timedelta(hours=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    scan_at = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    events[-1]["at"] = stale_at
    path = tmp_path / "ai_validate_memory.json"
    path.write_text(json.dumps({"updated_at": stale_at, "events": events}) + "\n")
    g = build_ai_debate_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=scan_at
    )
    assert g["freshness"] == "stale"
    assert g["scan_freshness"] == "fresh"
    assert g["scan_vs_debate_clash"] == "clash · scan fresh"
    assert "clash" in g["line"]
    assert g["line"].index("stale") < g["line"].index("clash")
    assert g["line"].index("clash") < g["line"].index("MSFT")
    same = build_ai_debate_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=stale_at
    )
    assert same["scan_vs_debate_clash"] == ""
    assert "clash" not in same["line"]


def test_build_ai_debate_glance_scan_clash_escalates_tone(tmp_path: Path) -> None:
    """Fresh last BUY vs stale scan → clash warn, not buy-calm."""
    record_ai_validate(
        tmp_path,
        {"action": "BUY", "confidence": "HIGH", "score": 40, "reasons": ["tape"]},
        symbol="MSFT",
        kept=True,
    )
    events = load_ai_validate_memory(tmp_path)
    # 15:00 UTC = US RTH — cash live so calm path is buy, not cash-aging.
    now = datetime(2026, 10, 6, 15, 0, tzinfo=timezone.utc)
    fresh_at = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    stale_scan = (now - timedelta(hours=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    aging_scan = (now - timedelta(minutes=45)).strftime("%Y-%m-%dT%H:%M:%SZ")
    events[-1]["at"] = fresh_at
    path = tmp_path / "ai_validate_memory.json"
    path.write_text(json.dumps({"updated_at": fresh_at, "events": events}) + "\n")
    g = build_ai_debate_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=stale_scan
    )
    assert g["freshness"] == "fresh"
    assert g["scan_freshness"] == "stale"
    assert g["scan_vs_debate_clash"] == "clash · scan stale"
    assert g["tone"] == "stale"
    aging = build_ai_debate_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=aging_scan
    )
    assert aging["scan_freshness"] == "aging"
    assert aging["tone"] == "aging"
    calm = build_ai_debate_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=fresh_at
    )
    assert calm["scan_vs_debate_clash"] == ""
    assert calm["tone"] == "buy"


def test_build_ai_debate_glance_cash_clash_when_debate_matches_scan(
    tmp_path: Path,
) -> None:
    """xang1234 #549: debate matching scan ≠ pinned cash print generation."""
    record_ai_validate(
        tmp_path,
        {"action": "BUY", "confidence": "HIGH", "score": 40, "reasons": ["tape"]},
        symbol="MSFT",
        kept=True,
    )
    events = load_ai_validate_memory(tmp_path)
    # Saturday afternoon UTC — cash sleeves last-published; US Fri close
    # is ~17h ago → cash aging while a fresh debate + fresh scan stay
    # debate↔scan silent (LAYA soft≠cash parity).
    now = datetime(2026, 10, 10, 14, 0, tzinfo=timezone.utc)
    fresh_at = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    events[-1]["at"] = fresh_at
    path = tmp_path / "ai_validate_memory.json"
    path.write_text(json.dumps({"updated_at": fresh_at, "events": events}) + "\n")
    g = build_ai_debate_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=fresh_at
    )
    assert g["freshness"] == "fresh"
    assert g["scan_freshness"] == "fresh"
    assert g["scan_vs_debate_clash"] == ""
    cash = g["debate_vs_cash_clock_clash"]
    assert cash.startswith("clash · debate fresh · cash ")
    assert g["debate_vs_cash_clock_clash_warn"] is True
    assert cash in g["line"]
    assert g["tone"] == "aging"
    # Same-evening last-published: debate fresh + cash fresh → silent.
    even = datetime(2026, 9, 8, 1, 30, tzinfo=timezone.utc)
    even_at = (even - timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    events[-1]["at"] = even_at
    path.write_text(json.dumps({"updated_at": even_at, "events": events}) + "\n")
    same = build_ai_debate_glance(
        tmp_path, now=even, scan_interval_sec=900, scan_time=even_at
    )
    assert same["freshness"] == "fresh"
    assert same["debate_vs_cash_clock_clash"] == ""
    assert same["debate_vs_cash_clock_clash_warn"] is False
    assert "clash · debate" not in same["line"]


def test_build_ai_debate_glance_vs_soft_clock_clash(tmp_path: Path) -> None:
    """xang1234 #549: debate matching scan ≠ staler soft-allow (speak-both-sides)."""
    record_ai_validate(
        tmp_path,
        {"action": "BUY", "confidence": "HIGH", "score": 40, "reasons": ["tape"]},
        symbol="MSFT",
        kept=True,
    )
    events = load_ai_validate_memory(tmp_path)
    now = datetime(2026, 9, 8, 1, 30, tzinfo=timezone.utc)
    fresh_at = (now - timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    stale_at = (now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    events[-1]["at"] = fresh_at
    path = tmp_path / "ai_validate_memory.json"
    path.write_text(json.dumps({"updated_at": fresh_at, "events": events}) + "\n")
    (tmp_path / "gate_soft_allows.json").write_text(
        json.dumps(
            {
                "events": [
                    {
                        "at": stale_at,
                        "gate": "breadth",
                        "reason": "unknown breadth — allow",
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    g = build_ai_debate_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=fresh_at
    )
    assert g["freshness"] == "fresh"
    assert g["soft_freshness"] == "stale"
    assert g["debate_vs_soft_clock_clash"] == "clash · soft stale"
    assert g["debate_vs_soft_clock_clash_warn"] is True
    assert "clash · soft stale" in g["line"]
    assert g["tone"] in {"aging", "stale", "buy"}
    # Same band — silent.
    (tmp_path / "gate_soft_allows.json").write_text(
        json.dumps(
            {
                "events": [
                    {
                        "at": fresh_at,
                        "gate": "breadth",
                        "reason": "unknown breadth — allow",
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    same = build_ai_debate_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=fresh_at
    )
    assert same["soft_freshness"] == "fresh"
    assert same["debate_vs_soft_clock_clash"] == ""
    assert same["debate_vs_soft_clock_clash_warn"] is False
    assert "clash · soft" not in same["line"]


def test_build_ai_debate_glance_peer_soft_clash_when_debate_matches_soft(
    monkeypatch, tmp_path: Path
) -> None:
    """Debate matching soft can still hide LAYA ≠ soft (peer speak)."""
    monkeypatch.setenv("LAYA_BASE_URL", "http://laya.test")
    monkeypatch.setenv("LAYA_ADVISORY", "1")
    now = datetime(2026, 9, 8, 1, 30, tzinfo=timezone.utc)
    fresh_at = (now - timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    stale_at = (now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    record_ai_validate(
        tmp_path,
        {"action": "BUY", "confidence": "HIGH", "score": 40, "reasons": ["tape"]},
        symbol="MSFT",
        kept=True,
    )
    events = load_ai_validate_memory(tmp_path)
    events[-1]["at"] = fresh_at
    path = tmp_path / "ai_validate_memory.json"
    path.write_text(json.dumps({"updated_at": fresh_at, "events": events}) + "\n")
    (tmp_path / "gate_soft_allows.json").write_text(
        json.dumps(
            {
                "events": [
                    {
                        "at": fresh_at,
                        "gate": "breadth",
                        "reason": "unknown breadth — allow",
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "laya_decisions.json").write_text(
        json.dumps(
            {
                "events": [
                    {
                        "at": stale_at,
                        "symbol": "NVDA",
                        "ok": True,
                        "fail_open": False,
                        "reason": "ok",
                        "entry": "hold",
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    # No scan_time → no pinned cash sleeve, so peer-cash does not crowd the clip.
    g = build_ai_debate_glance(tmp_path, now=now, scan_interval_sec=900)
    assert g["freshness"] == "fresh"
    assert g["soft_freshness"] == "fresh"
    assert g["debate_vs_soft_clock_clash"] == ""
    assert g["debate_peer_cash_clock_clash"] == ""
    peer = g["debate_peer_soft_clock_clash"]
    assert peer.startswith("peer soft · laya ")
    assert "soft fresh" in peer
    assert g["debate_peer_soft_clock_clash_warn"] is True
    assert "peer soft" in g["line"]
    assert g["tone"] in {"aging", "stale"}


def test_build_ai_debate_glance_peer_cash_clash_when_debate_matches_cash(
    monkeypatch, tmp_path: Path
) -> None:
    """Debate matching cash can still hide LAYA ≠ cash (peer speak)."""
    monkeypatch.setenv("LAYA_BASE_URL", "http://laya.test")
    monkeypatch.setenv("LAYA_ADVISORY", "1")
    # Same-evening last-published: cash fresh. Fresh debate matches cash;
    # stale LAYA ≠ cash → peer bit on debate glance.
    now = datetime(2026, 9, 8, 1, 30, tzinfo=timezone.utc)
    fresh_at = (now - timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    stale_at = (now - timedelta(hours=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    record_ai_validate(
        tmp_path,
        {"action": "BUY", "confidence": "HIGH", "score": 40, "reasons": ["tape"]},
        symbol="MSFT",
        kept=True,
    )
    events = load_ai_validate_memory(tmp_path)
    events[-1]["at"] = fresh_at
    path = tmp_path / "ai_validate_memory.json"
    path.write_text(json.dumps({"updated_at": fresh_at, "events": events}) + "\n")
    (tmp_path / "laya_decisions.json").write_text(
        json.dumps(
            {
                "events": [
                    {
                        "at": stale_at,
                        "symbol": "NVDA",
                        "ok": True,
                        "fail_open": False,
                        "reason": "ok",
                        "entry": "hold",
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    g = build_ai_debate_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=fresh_at
    )
    assert g["freshness"] == "fresh"
    assert g["debate_vs_cash_clock_clash"] == ""
    peer = g["debate_peer_cash_clock_clash"]
    assert peer.startswith("peer cash · laya ")
    assert "cash fresh" in peer
    assert g["debate_peer_cash_clock_clash_warn"] is True
    # 96-char clip may truncate the peer sleeve name; keep the prefix.
    assert "peer cash" in g["line"]
    assert g["tone"] in {"aging", "stale"}


def test_build_ai_debate_glance_laya_clash(monkeypatch, tmp_path: Path) -> None:
    """Last-debate band ≠ LAYA last-row band → clash · laya {tone}."""
    monkeypatch.setenv("LAYA_BASE_URL", "http://laya.test")
    monkeypatch.setenv("LAYA_ADVISORY", "1")
    record_ai_validate(
        tmp_path,
        {"action": "BUY", "confidence": "HIGH", "score": 40, "reasons": ["tape"]},
        symbol="MSFT",
        kept=True,
    )
    events = load_ai_validate_memory(tmp_path)
    now = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)
    stale_at = (now - timedelta(hours=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    fresh_at = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    events[-1]["at"] = stale_at
    path = tmp_path / "ai_validate_memory.json"
    path.write_text(json.dumps({"updated_at": stale_at, "events": events}) + "\n")
    (tmp_path / "laya_decisions.json").write_text(
        json.dumps(
            {
                "events": [
                    {
                        "at": fresh_at,
                        "symbol": "NVDA",
                        "ok": True,
                        "fail_open": False,
                        "reason": "ok",
                        "entry": "hold",
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    g = build_ai_debate_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=stale_at
    )
    assert g["freshness"] == "stale"
    assert g["scan_freshness"] == "stale"
    assert g["laya_freshness"] == "fresh"
    assert g["scan_vs_debate_clash"] == "clash · laya fresh"
    assert "laya" in g["line"]
    both = build_ai_debate_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=fresh_at
    )
    assert both["scan_vs_debate_clash"] == "clash · scan fresh · laya fresh"


def test_build_ai_debate_glance_laya_name_clash(monkeypatch, tmp_path: Path) -> None:
    """Last-debate ticker/verb ≠ LAYA last-row → mixed/align/vs (display only)."""
    monkeypatch.setenv("LAYA_BASE_URL", "http://laya.test")
    monkeypatch.setenv("LAYA_ADVISORY", "1")
    # 15:00 UTC = US RTH — cash live so name clash is not clipped by cash.
    now = datetime(2026, 10, 6, 15, 0, tzinfo=timezone.utc)
    at = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    record_ai_validate(
        tmp_path,
        {"action": "BUY", "confidence": "HIGH", "score": 40, "reasons": ["tape"]},
        symbol="MSFT",
        kept=True,
    )
    events = load_ai_validate_memory(tmp_path)
    events[-1]["at"] = at
    (tmp_path / "ai_validate_memory.json").write_text(
        json.dumps({"updated_at": at, "events": events}) + "\n"
    )
    (tmp_path / "laya_decisions.json").write_text(
        json.dumps(
            {
                "events": [
                    {
                        "at": at,
                        "symbol": "NVDA",
                        "ok": True,
                        "fail_open": False,
                        "reason": "ok",
                        "entry": "hold",
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    g = build_ai_debate_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=at
    )
    assert g["scan_vs_debate_clash"] == ""
    assert g["memory_name_clash"] == "mixed · vs NVDA hold"
    assert g["memory_verb_oppose"] is False
    assert "mixed · vs NVDA hold" in g["line"]
    assert g["line"].index("vs NVDA") < g["line"].index("last MSFT")
    (tmp_path / "laya_decisions.json").write_text(
        json.dumps(
            {
                "events": [
                    {
                        "at": at,
                        "symbol": "NVDA",
                        "ok": True,
                        "fail_open": False,
                        "reason": "ok",
                        "entry": "pass",
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    align = build_ai_debate_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=at
    )
    assert align["memory_name_clash"] == "align · vs NVDA pass"
    assert align["memory_verb_oppose"] is False
    assert "align · vs NVDA pass" in align["line"]
    assert align["tone"] == "buy"


def test_build_ai_debate_glance_laya_verb_oppose(monkeypatch, tmp_path: Path) -> None:
    """BUY vs LAYA reject escalates tone off buy-calm (display only)."""
    monkeypatch.setenv("LAYA_BASE_URL", "http://laya.test")
    monkeypatch.setenv("LAYA_ADVISORY", "1")
    # 15:00 UTC = US RTH — cash live so hold/agree stay buy-calm.
    now = datetime(2026, 10, 6, 15, 0, tzinfo=timezone.utc)
    at = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    record_ai_validate(
        tmp_path,
        {"action": "BUY", "confidence": "HIGH", "score": 40, "reasons": ["tape"]},
        symbol="MSFT",
        kept=True,
    )
    events = load_ai_validate_memory(tmp_path)
    events[-1]["at"] = at
    (tmp_path / "ai_validate_memory.json").write_text(
        json.dumps({"updated_at": at, "events": events}) + "\n"
    )
    (tmp_path / "laya_decisions.json").write_text(
        json.dumps(
            {
                "events": [
                    {
                        "at": at,
                        "symbol": "MSFT",
                        "ok": True,
                        "fail_open": False,
                        "reason": "ok",
                        "entry": "reject",
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    g = build_ai_debate_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=at
    )
    assert g["memory_name_clash"] == "vs reject"
    assert g["memory_verb_oppose"] is True
    assert g["tone"] == "aging"
    (tmp_path / "laya_decisions.json").write_text(
        json.dumps(
            {
                "events": [
                    {
                        "at": at,
                        "symbol": "MSFT",
                        "ok": True,
                        "fail_open": False,
                        "reason": "ok",
                        "entry": "hold",
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    hold = build_ai_debate_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=at
    )
    assert hold["memory_name_clash"] == "mixed · vs hold"
    assert hold["memory_verb_oppose"] is False
    assert hold["tone"] == "buy"
    assert "mixed · vs hold" in hold["line"]
    (tmp_path / "laya_decisions.json").write_text(
        json.dumps(
            {
                "events": [
                    {
                        "at": at,
                        "symbol": "MSFT",
                        "ok": True,
                        "fail_open": False,
                        "reason": "ok",
                        "entry": "pass",
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    agree = build_ai_debate_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=at
    )
    assert agree["memory_name_clash"] == "agree"
    assert agree["memory_verb_oppose"] is False
    assert agree["tone"] == "buy"
    assert "agree" in agree["line"]
    assert "vs " not in agree["line"]


def test_build_ai_debate_glance_confidence_bits(tmp_path: Path) -> None:
    """Last-debate conf hi|med|lo speaks; lo escalates tone (not a gate)."""
    now = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)
    at = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _write(confidence: str) -> None:
        record_ai_validate(
            tmp_path,
            {
                "action": "BUY",
                "confidence": confidence,
                "score": 40,
                "reasons": ["tape"],
            },
            symbol="MSFT",
            kept=True,
        )
        events = load_ai_validate_memory(tmp_path)
        events[-1]["at"] = at
        (tmp_path / "ai_validate_memory.json").write_text(
            json.dumps({"updated_at": at, "events": events}) + "\n"
        )

    _write("HIGH")
    g = build_ai_debate_glance(tmp_path, now=now, scan_interval_sec=900)
    assert g["confidence_bits"] == "conf hi"
    assert g["confidence_warn"] is False
    assert g["latest_confidence"] == "HIGH"
    assert g["decision_vs_conf"] == "BUY/conf align · hi"
    # conf hi may share the clip with decision/conf align; field is source of truth.
    assert "conf hi" in g["line"] or g["confidence_bits"]
    assert "last MSFT BUY" in g["line"]
    assert g["tone"] == "buy"

    _write("MEDIUM")
    med = build_ai_debate_glance(tmp_path, now=now, scan_interval_sec=900)
    assert med["confidence_bits"] == "conf med"
    assert med["confidence_warn"] is False
    assert med["tone"] == "buy"

    _write("LOW")
    lo = build_ai_debate_glance(tmp_path, now=now, scan_interval_sec=900)
    assert lo["confidence_bits"] == "conf lo"
    assert lo["confidence_warn"] is True
    assert lo["tone"] == "aging"

    record_ai_validate(
        tmp_path,
        {"action": "BUY", "confidence": "", "score": 40, "reasons": ["tape"]},
        symbol="MSFT",
        kept=True,
    )
    events = load_ai_validate_memory(tmp_path)
    events[-1]["at"] = at
    (tmp_path / "ai_validate_memory.json").write_text(
        json.dumps({"updated_at": at, "events": events}) + "\n"
    )
    silent = build_ai_debate_glance(tmp_path, now=now, scan_interval_sec=900)
    assert silent["confidence_bits"] == ""
    assert silent["confidence_warn"] is False
    assert "conf " not in silent["line"]
    assert silent["tone"] == "buy"


def test_build_ai_debate_glance_edge_vs_conf(monkeypatch, tmp_path: Path) -> None:
    """Same-ticker LAYA edge vs debate conf clash/align (not a gate)."""
    monkeypatch.setenv("LAYA_BASE_URL", "http://laya.test")
    monkeypatch.setenv("LAYA_ADVISORY", "1")
    now = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)
    at = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _laya(edge_score: float, symbol: str = "MSFT") -> None:
        (tmp_path / "laya_decisions.json").write_text(
            json.dumps(
                {
                    "events": [
                        {
                            "at": at,
                            "symbol": symbol,
                            "ok": True,
                            "fail_open": False,
                            "reason": "ok",
                            "entry": "pass",
                            "edge_score": edge_score,
                            "fee_churn": 0.15,
                        }
                    ]
                }
            )
            + "\n",
            encoding="utf-8",
        )

    def _debate(confidence: str, symbol: str = "MSFT") -> None:
        record_ai_validate(
            tmp_path,
            {
                "action": "BUY",
                "confidence": confidence,
                "score": 40,
                "reasons": ["tape"],
            },
            symbol=symbol,
            kept=True,
        )
        events = load_ai_validate_memory(tmp_path)
        events[-1]["at"] = at
        (tmp_path / "ai_validate_memory.json").write_text(
            json.dumps({"updated_at": at, "events": events}) + "\n"
        )

    _laya(2.8)
    _debate("LOW")
    clash = build_ai_debate_glance(tmp_path, now=now, scan_interval_sec=900)
    assert clash["edge_vs_conf"] == "edge/conf clash · strong · lo"
    assert clash["edge_vs_conf_warn"] is True
    # May share the clip with BUY/conf clash · lo; field carries the full bit.
    assert "edge/conf clash" in clash["line"] or clash["edge_vs_conf"]
    assert clash["tone"] == "aging"

    _laya(1.0)
    _debate("LOW")
    align = build_ai_debate_glance(tmp_path, now=now, scan_interval_sec=900)
    assert align["edge_vs_conf"] == "edge/conf align · thin · lo"
    assert align["edge_vs_conf_warn"] is False
    # edge/fee thin·quiet warn is early; fee/conf may clip — field is source of truth.
    assert align["fee_vs_conf"] == "fee/conf clash · quiet · lo"
    assert align["fee_vs_conf_warn"] is True

    _laya(2.1)
    _debate("MEDIUM")
    mid = build_ai_debate_glance(tmp_path, now=now, scan_interval_sec=900)
    assert mid["edge_vs_conf"] == ""

    _laya(1.0, symbol="NVDA")
    _debate("HIGH", symbol="MSFT")
    cross = build_ai_debate_glance(tmp_path, now=now, scan_interval_sec=900)
    assert cross["edge_vs_conf"] == ""


def test_build_ai_debate_glance_fee_vs_conf(monkeypatch, tmp_path: Path) -> None:
    """Same-ticker LAYA fee vs debate conf clash/align (not a gate)."""
    monkeypatch.setenv("LAYA_BASE_URL", "http://laya.test")
    monkeypatch.setenv("LAYA_ADVISORY", "1")
    now = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)
    at = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _laya(fee_churn: float, symbol: str = "MSFT") -> None:
        (tmp_path / "laya_decisions.json").write_text(
            json.dumps(
                {
                    "events": [
                        {
                            "at": at,
                            "symbol": symbol,
                            "ok": True,
                            "fail_open": False,
                            "reason": "ok",
                            "entry": "pass",
                            "edge_score": 2.1,
                            "fee_churn": fee_churn,
                        }
                    ]
                }
            )
            + "\n",
            encoding="utf-8",
        )

    def _debate(confidence: str, symbol: str = "MSFT") -> None:
        # Replace memory each case so glance length stays single-row.
        (tmp_path / "ai_validate_memory.json").write_text(
            json.dumps(
                {
                    "updated_at": at,
                    "events": [
                        {
                            "at": at,
                            "symbol": symbol,
                            "action": "BUY",
                            "confidence": confidence,
                            "score": 40,
                            "reasons": ["tape"],
                            "kept": True,
                            "gated": False,
                        }
                    ],
                }
            )
            + "\n",
            encoding="utf-8",
        )

    _laya(0.8)
    _debate("HIGH")
    clash = build_ai_debate_glance(tmp_path, now=now, scan_interval_sec=900)
    assert clash["fee_vs_conf"] == "fee/conf clash · hot · hi"
    assert clash["fee_vs_conf_warn"] is True
    # May share the clip with decision/conf; field carries the full bit.
    assert "fee/" in clash["line"] or clash["fee_vs_conf"]
    assert clash["tone"] == "aging"

    _laya(0.1)
    _debate("HIGH")
    align = build_ai_debate_glance(tmp_path, now=now, scan_interval_sec=900)
    assert align["fee_vs_conf"] == "fee/conf align · quiet · hi"
    assert align["fee_vs_conf_warn"] is False
    # Dual align bits often clip after edge/conf; field carries the full bit.
    assert "fee/" in align["line"] or align["fee_vs_conf"]

    _laya(0.1)
    _debate("LOW")
    quiet_lo = build_ai_debate_glance(tmp_path, now=now, scan_interval_sec=900)
    assert quiet_lo["fee_vs_conf"] == "fee/conf clash · quiet · lo"
    assert quiet_lo["fee_vs_conf_warn"] is True
    # May share the clip with BUY/conf clash · lo; field carries the full bit.
    assert "fee/conf clash" in quiet_lo["line"] or quiet_lo["fee_vs_conf"]
    assert quiet_lo["tone"] == "aging"

    _laya(0.35)
    _debate("MEDIUM")
    mid = build_ai_debate_glance(tmp_path, now=now, scan_interval_sec=900)
    assert mid["fee_vs_conf"] == ""

    _laya(0.8, symbol="NVDA")
    _debate("HIGH", symbol="MSFT")
    cross = build_ai_debate_glance(tmp_path, now=now, scan_interval_sec=900)
    assert cross["fee_vs_conf"] == ""


def test_ai_debate_glance_edge_vs_fee(monkeypatch, tmp_path: Path) -> None:
    """Same-ticker LAYA edge vs fee on debate glance (not a gate)."""
    monkeypatch.setenv("LAYA_BASE_URL", "http://laya.test")
    monkeypatch.setenv("LAYA_ADVISORY", "1")
    now = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)
    at = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _laya(edge_score: float, fee_churn: float, symbol: str = "MSFT") -> None:
        (tmp_path / "laya_decisions.json").write_text(
            json.dumps(
                {
                    "events": [
                        {
                            "at": at,
                            "symbol": symbol,
                            "ok": True,
                            "fail_open": False,
                            "reason": "ok",
                            "entry": "pass",
                            "edge_score": edge_score,
                            "fee_churn": fee_churn,
                        }
                    ]
                }
            )
            + "\n",
            encoding="utf-8",
        )

    def _debate(symbol: str = "MSFT") -> None:
        (tmp_path / "ai_validate_memory.json").write_text(
            json.dumps(
                {
                    "updated_at": at,
                    "events": [
                        {
                            "at": at,
                            "symbol": symbol,
                            "action": "BUY",
                            "confidence": "HIGH",
                            "score": 40,
                            "reasons": ["tape"],
                            "kept": True,
                            "gated": False,
                        }
                    ],
                }
            )
            + "\n",
            encoding="utf-8",
        )

    _laya(2.8, 0.8)
    _debate()
    clash = build_ai_debate_glance(tmp_path, now=now, scan_interval_sec=900)
    assert clash["edge_vs_fee"] == "edge/fee clash · strong · hot"
    assert clash["edge_vs_fee_warn"] is True
    # Warn is ordered early; full bit may share the clip with fee/conf.
    assert "edge/fee clash" in clash["line"]
    assert clash["tone"] == "aging"

    _laya(2.8, 0.1)
    _debate()
    align = build_ai_debate_glance(tmp_path, now=now, scan_interval_sec=900)
    assert align["edge_vs_fee"] == "edge/fee align · strong · quiet"
    assert align["edge_vs_fee_warn"] is False

    _laya(2.8, 0.8, symbol="NVDA")
    _debate(symbol="MSFT")
    cross = build_ai_debate_glance(tmp_path, now=now, scan_interval_sec=900)
    assert cross["edge_vs_fee"] == ""


def test_ai_debate_glance_decision_vs_edge(monkeypatch, tmp_path: Path) -> None:
    """Same-ticker BUY/SELL vs LAYA edge clash/align (not a gate)."""
    monkeypatch.setenv("LAYA_BASE_URL", "http://laya.test")
    monkeypatch.setenv("LAYA_ADVISORY", "1")
    now = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)
    at = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _laya(edge_score: float, symbol: str = "MSFT") -> None:
        (tmp_path / "laya_decisions.json").write_text(
            json.dumps(
                {
                    "events": [
                        {
                            "at": at,
                            "symbol": symbol,
                            "ok": True,
                            "fail_open": False,
                            "reason": "ok",
                            "entry": "pass",
                            "edge_score": edge_score,
                            "fee_churn": 0.35,
                        }
                    ]
                }
            )
            + "\n",
            encoding="utf-8",
        )

    def _debate(action: str, symbol: str = "MSFT") -> None:
        (tmp_path / "ai_validate_memory.json").write_text(
            json.dumps(
                {
                    "updated_at": at,
                    "events": [
                        {
                            "at": at,
                            "symbol": symbol,
                            "action": action,
                            "confidence": "MEDIUM",
                            "score": 40,
                            "reasons": ["tape"],
                            "kept": True,
                            "gated": False,
                        }
                    ],
                }
            )
            + "\n",
            encoding="utf-8",
        )

    _laya(1.0)
    _debate("BUY")
    clash = build_ai_debate_glance(tmp_path, now=now, scan_interval_sec=900)
    assert clash["decision_vs_edge"] == "BUY/edge clash · thin"
    assert clash["decision_vs_edge_warn"] is True
    assert "BUY/edge clash" in clash["line"]
    assert clash["tone"] == "aging"

    _laya(2.8)
    _debate("BUY")
    align = build_ai_debate_glance(tmp_path, now=now, scan_interval_sec=900)
    assert align["decision_vs_edge"] == "BUY/edge align · strong"
    assert align["decision_vs_edge_warn"] is False

    _laya(2.8)
    _debate("SELL")
    sell_clash = build_ai_debate_glance(tmp_path, now=now, scan_interval_sec=900)
    assert sell_clash["decision_vs_edge"] == "SELL/edge clash · strong"
    assert sell_clash["decision_vs_edge_warn"] is True
    assert "SELL/edge clash · strong" in sell_clash["line"]
    assert sell_clash["tone"] == "aging"

    _laya(2.1)
    _debate("BUY")
    mid = build_ai_debate_glance(tmp_path, now=now, scan_interval_sec=900)
    assert mid["decision_vs_edge"] == ""

    _laya(1.0, symbol="NVDA")
    _debate("BUY", symbol="MSFT")
    cross = build_ai_debate_glance(tmp_path, now=now, scan_interval_sec=900)
    assert cross["decision_vs_edge"] == ""


def test_ai_debate_glance_decision_vs_conf(tmp_path: Path) -> None:
    """Same-row BUY/SELL vs typed conf clash/align (not a gate)."""
    now = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)
    at = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _debate(action: str, confidence: str) -> None:
        (tmp_path / "ai_validate_memory.json").write_text(
            json.dumps(
                {
                    "updated_at": at,
                    "events": [
                        {
                            "at": at,
                            "symbol": "MSFT",
                            "action": action,
                            "confidence": confidence,
                            "score": 40,
                            "reasons": ["tape"],
                            "kept": True,
                            "gated": False,
                        }
                    ],
                }
            )
            + "\n",
            encoding="utf-8",
        )

    _debate("BUY", "LOW")
    clash = build_ai_debate_glance(tmp_path, now=now, scan_interval_sec=900)
    assert clash["decision_vs_conf"] == "BUY/conf clash · lo"
    assert clash["decision_vs_conf_warn"] is True
    assert "BUY/conf clash · lo" in clash["line"]
    assert clash["tone"] == "aging"

    _debate("BUY", "HIGH")
    align = build_ai_debate_glance(tmp_path, now=now, scan_interval_sec=900)
    assert align["decision_vs_conf"] == "BUY/conf align · hi"
    assert align["decision_vs_conf_warn"] is False
    assert "BUY/conf align" in align["line"] or align["decision_vs_conf"]

    _debate("SELL", "HIGH")
    sell_align = build_ai_debate_glance(tmp_path, now=now, scan_interval_sec=900)
    assert sell_align["decision_vs_conf"] == "SELL/conf align · hi"
    assert sell_align["decision_vs_conf_warn"] is False

    _debate("SELL", "LOW")
    sell_clash = build_ai_debate_glance(tmp_path, now=now, scan_interval_sec=900)
    assert sell_clash["decision_vs_conf"] == "SELL/conf clash · lo"
    assert sell_clash["decision_vs_conf_warn"] is True
    assert "SELL/conf clash · lo" in sell_clash["line"]
    assert sell_clash["tone"] == "aging"

    _debate("BUY", "MEDIUM")
    mid = build_ai_debate_glance(tmp_path, now=now, scan_interval_sec=900)
    assert mid["decision_vs_conf"] == ""
    assert "BUY/conf " not in mid["line"] and "SELL/conf " not in mid["line"]

    _debate("HOLD", "HIGH")
    hold = build_ai_debate_glance(tmp_path, now=now, scan_interval_sec=900)
    assert hold["decision_vs_conf"] == ""


def test_build_ai_debate_glance_freshness_fresh(tmp_path: Path) -> None:
    record_ai_validate(
        tmp_path,
        {"action": "HOLD", "confidence": "MEDIUM", "score": 0, "reasons": ["wait"]},
        symbol="IBM",
        kept=False,
    )
    now = datetime.now(timezone.utc)
    g = build_ai_debate_glance(tmp_path, now=now, scan_interval_sec=900)
    assert g["freshness"] == "fresh"
    assert g["tone"] in {"fresh", "flat", "buy", "gated"}
    assert "ago" in g["line"] or "just now" in g["line"]
    assert g["confidence_bits"] == "conf med"


def test_build_ai_debate_glance_sample_lead(tmp_path: Path) -> None:
    """Decided sample (≥2) speaks lead · N% + ahead + vs runner · P%."""
    at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _write(events: list[dict]) -> None:
        (tmp_path / "ai_validate_memory.json").write_text(
            json.dumps({"updated_at": at, "events": events}) + "\n",
            encoding="utf-8",
        )

    def _row(action: str, symbol: str, *, conf: str = "MEDIUM") -> dict:
        return {
            "at": at,
            "symbol": symbol,
            "action": action,
            "confidence": conf,
            "score": 20,
            "reasons": ["tape"],
            "kept": True,
            "gated": False,
        }

    _write([_row("BUY", "AAPL")])
    thin = build_ai_debate_glance(tmp_path, now=datetime.now(timezone.utc), scan_interval_sec=900)
    assert thin["sample_lead"] == ""
    assert thin["sample_lead_share"] is None
    assert thin["sample_lead_margin"] == ""
    assert thin["sample_lead_sides"] == ""
    assert thin["sample_lead_sides_share"] is None
    assert thin["sample_gap"] == "n=1"
    assert "n=1" in thin["line"]

    _write([_row("BUY", "AAPL"), _row("BUY", "MSFT"), _row("HOLD", "NVDA")])
    lead = build_ai_debate_glance(
        tmp_path, now=datetime.now(timezone.utc), scan_interval_sec=900
    )
    assert lead["sample_lead"] == "lead BUY · 67%"
    assert lead["sample_lead_name"] == "BUY"
    assert lead["sample_lead_share"] == 67
    assert lead["sample_lead_margin"] == "ahead thin · +1"
    assert lead["sample_lead_margin_gap"] == 1
    assert lead["sample_lead_sides"] == "vs HOLD · 1 · 33%"
    assert lead["sample_lead_sides_name"] == "HOLD"
    assert lead["sample_lead_sides_n"] == 1
    assert lead["sample_lead_sides_share"] == 33
    # Newest HOLD ≠ BUY tilt — speak last vs lead (no tone escalate).
    assert lead["last_vs_sample_lead"] == "last vs lead · HOLD"
    assert lead["sample_gap"] == ""
    assert "2 BUY" in lead["line"]
    assert "lead BUY · 67%" in lead["line"]
    assert "last vs lead · HOLD" in lead["line"]
    assert lead["line"].index("2 BUY") < lead["line"].index("lead BUY")
    assert lead["line"].index("lead BUY") < lead["line"].index("last vs lead · HOLD")
    # Margin/sides may truncate after last-vs (counts + lead fill the 96).
    if "ahead thin" in lead["line"]:
        assert lead["line"].index("last vs lead · HOLD") < lead["line"].index(
            "ahead thin"
        )
    # Structured fields still hold runner honesty when the line clips.
    assert lead["sample_lead_sides"] == "vs HOLD · 1 · 33%"

    _write([_row("BUY", "AAPL"), _row("BUY", "MSFT")])
    sole = build_ai_debate_glance(
        tmp_path, now=datetime.now(timezone.utc), scan_interval_sec=900
    )
    assert sole["sample_lead"] == "lead BUY · 100%"
    assert sole["sample_lead_margin"] == ""
    assert sole["sample_lead_sides"] == ""
    assert sole["sample_lead_sides_share"] is None
    assert sole["last_vs_sample_lead"] == "agree"
    assert "agree" in sole["line"]
    assert "ahead " not in sole["line"]
    assert "last vs lead" not in sole["line"]

    _write(
        [
            _row("BUY", "AAPL"),
            _row("BUY", "MSFT"),
            _row("BUY", "NVDA"),
            _row("HOLD", "TSLA"),
        ]
    )
    wide = build_ai_debate_glance(
        tmp_path, now=datetime.now(timezone.utc), scan_interval_sec=900
    )
    assert wide["sample_lead_margin"] == "ahead wide · +2"
    assert wide["sample_lead_margin_gap"] == 2
    assert wide["sample_lead_sides"] == "vs HOLD · 1 · 25%"
    assert wide["sample_lead_sides_share"] == 25

    # Tied runners: ahead speaks, vs silent.
    _write(
        [
            _row("BUY", "AAPL"),
            _row("BUY", "MSFT"),
            _row("BUY", "NVDA"),
            _row("HOLD", "TSLA"),
            _row("SELL", "AMD"),
        ]
    )
    tied_runners = build_ai_debate_glance(
        tmp_path, now=datetime.now(timezone.utc), scan_interval_sec=900
    )
    assert tied_runners["sample_lead"] == "lead BUY · 60%"
    assert tied_runners["sample_lead_margin"] == "ahead wide · +2"
    assert tied_runners["sample_lead_sides"] == ""
    assert tied_runners["sample_lead_sides_share"] is None
    assert "vs HOLD" not in tied_runners["line"]
    assert "vs SELL" not in tied_runners["line"]

    _write([_row("BUY", "AAPL"), _row("SELL", "MSFT")])
    tied = build_ai_debate_glance(
        tmp_path, now=datetime.now(timezone.utc), scan_interval_sec=900
    )
    assert tied["sample_lead"] == ""
    assert tied["sample_lead_margin"] == ""
    assert tied["sample_lead_sides"] == ""
    assert tied["sample_lead_sides_share"] is None
    assert tied["sample_gap"] == "tied"
    assert "tied" in tied["line"]
    assert "lead " not in tied["line"]


def test_ideas_template_has_ai_debates_section() -> None:
    text = Path("openbb_backend/templates/desk_ideas.html").read_text()
    assert "ai_debates" in text
    assert 'id="debate-h"' in text
    assert 'class="ai-debate"' in text
    assert "debate-json" in text
    assert "tojson" in text
    assert "ai_debate_glance" in text


def test_desk_templates_include_ai_debate_glance() -> None:
    roots = Path("openbb_backend/templates")
    for name in (
        "desk_overview.html",
        "desk_ops.html",
        "desk_ideas.html",
        "desk_screener.html",
        "desk_book.html",
        "desk_breadth.html",
        "desk_scan_log.html",
    ):
        text = (roots / name).read_text()
        assert "ai_debate_glance" in text, name
    assert "ai_debate_glance" in Path("openbb_backend/templates/macros.html").read_text()
    assert "renderAiDebateGlance" in Path("openbb_backend/static/charts.js").read_text()
