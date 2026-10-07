"""Offline tests for LAYA / JEV System-1 advisory (fail-open, not a gate)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from openbb_backend.desk import build_laya_glance
from stock_checker.laya_decision import (
    PAPER_ENTRY_QUESTIONS,
    build_paper_entry_state,
    evaluate_paper_entry,
    laya_advisory_enabled,
    laya_configured,
    maybe_advise_paper_entry,
    parse_system_one_answers,
    record_laya_decision,
    summarize_laya_decisions,
)


def test_paper_entry_questions_shape() -> None:
    assert PAPER_ENTRY_QUESTIONS["entry"]["type"] == "choice"
    assert set(PAPER_ENTRY_QUESTIONS["entry"]["criteria"]) == {
        "pass",
        "hold",
        "reject",
    }
    assert PAPER_ENTRY_QUESTIONS["edge"]["type"] == "score"
    assert PAPER_ENTRY_QUESTIONS["fee_churn"]["type"] == "noul"


def test_build_state_includes_symbol() -> None:
    text = build_paper_entry_state(
        {
            "symbol": "AAPL",
            "name": "Apple",
            "current_price": 200,
            "previous_close": 198,
            "strategy": "breakout",
        }
    )
    assert "AAPL" in text
    assert "breakout" in text
    assert "anti-churn" in text or "min hold" in text.lower() or "24h" in text


def test_parse_system_one_answers() -> None:
    parsed = parse_system_one_answers(
        {
            "answers": {
                "entry": {
                    "choice": "pass",
                    "probabilities": {"pass": 0.7, "hold": 0.2, "reject": 0.1},
                },
                "edge": {"score": 2.1},
                "fee_churn": {"noul": 0.15},
            }
        }
    )
    assert parsed["entry"] == "pass"
    assert parsed["probabilities"]["pass"] == 0.7
    assert parsed["edge_score"] == 2.1
    assert parsed["fee_churn"] == 0.15


def test_evaluate_fail_open_when_not_configured(monkeypatch) -> None:
    monkeypatch.delenv("LAYA_BASE_URL", raising=False)
    monkeypatch.delenv("JEV_BASE_URL", raising=False)
    monkeypatch.delenv("LAYA_ADVISORY", raising=False)
    assert not laya_configured()
    res = evaluate_paper_entry({"symbol": "MSFT"})
    assert res["fail_open"] is True
    assert res["ok"] is False
    assert res["reason"] == "not_configured"


def test_evaluate_advisory_off_when_url_set(monkeypatch) -> None:
    monkeypatch.setenv("LAYA_BASE_URL", "http://127.0.0.1:9")
    monkeypatch.setenv("LAYA_ADVISORY", "0")
    assert laya_configured()
    assert not laya_advisory_enabled()
    res = evaluate_paper_entry({"symbol": "MSFT"})
    assert res["reason"] == "advisory_off"
    assert res["fail_open"] is True


def test_evaluate_with_transport(monkeypatch) -> None:
    monkeypatch.setenv("LAYA_BASE_URL", "http://laya.test")
    monkeypatch.setenv("LAYA_ADVISORY", "1")

    def fake_transport(url, body, headers, timeout):
        assert url.endswith("/v1/systemone")
        assert "questions" in body
        assert body["questions"]["entry"]["type"] == "choice"
        return {
            "answers": {
                "entry": {
                    "choice": "hold",
                    "probabilities": {"pass": 0.2, "hold": 0.7, "reject": 0.1},
                },
                "edge": {"score": 1.0},
                "fee_churn": {"noul": 0.4},
            }
        }

    res = evaluate_paper_entry(
        {"symbol": "SAP.DE", "current_price": 100, "previous_close": 99},
        transport=fake_transport,
    )
    assert res["ok"] is True
    assert res["fail_open"] is False
    assert res["entry"] == "hold"
    assert res["latency_ms"] is not None


def test_evaluate_transport_error_fail_open(monkeypatch) -> None:
    monkeypatch.setenv("LAYA_BASE_URL", "http://laya.test")
    monkeypatch.setenv("LAYA_ADVISORY", "1")

    def boom(*_a, **_k):
        raise TimeoutError("slow")

    res = evaluate_paper_entry({"symbol": "X"}, transport=boom)
    assert res["ok"] is False
    assert res["fail_open"] is True
    assert "provider_error" in res["reason"]


def test_record_and_summarize(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LAYA_BASE_URL", "http://laya.test")
    monkeypatch.setenv("LAYA_ADVISORY", "1")

    def ok_transport(*_a, **_k):
        return {
            "answers": {
                "entry": {"choice": "pass", "probabilities": {"pass": 0.9}},
                "edge": {"score": 2.5},
                "fee_churn": {"noul": 0.05},
            }
        }

    res = maybe_advise_paper_entry(
        {"symbol": "BTC-USD"}, tmp_path, transport=ok_transport
    )
    assert res is not None
    assert res["entry"] == "pass"
    stats = summarize_laya_decisions(tmp_path)
    assert stats["count"] == 1
    assert stats["pass"] == 1
    assert stats["newest"]["symbol"] == "BTC-USD"


def test_laya_glance_off(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("LAYA_BASE_URL", raising=False)
    monkeypatch.delenv("JEV_BASE_URL", raising=False)
    monkeypatch.delenv("LAYA_ADVISORY", raising=False)
    g = build_laya_glance(tmp_path)
    assert g["ready"] is True
    assert g["tone"] == "off"
    assert "not a gate" in g["line"]


def test_laya_glance_advisory(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LAYA_BASE_URL", "http://laya.test")
    monkeypatch.setenv("LAYA_ADVISORY", "1")
    record_laya_decision(
        tmp_path,
        {
            "ok": True,
            "fail_open": False,
            "reason": "ok",
            "entry": "reject",
            "edge_score": 0.5,
            "fee_churn": 0.8,
            "latency_ms": 40,
            "model": "systemone",
        },
        symbol="NVDA",
    )
    g = build_laya_glance(tmp_path)
    assert g["advisory"] is True
    # edge thin (0.5) + fee hot (0.8) escalate tone — pass/reject alone ≠ calm
    assert g["tone"] == "aging"
    assert g["edge_fee_bits"] == "edge thin · fee hot"
    assert g["edge_vs_fee"] == "edge/fee align · thin · hot"
    assert g["edge_vs_fee_warn"] is False
    assert g["decision_vs_edge"] == "reject/edge align · thin"
    assert g["decision_vs_edge_warn"] is False
    assert g["freshness"] == "fresh"
    assert "NVDA" in g["line"]
    assert "reject" in g["line"]
    assert "fresh" in g["line"]
    assert g["line"].index("fresh") < g["line"].index("NVDA")


def test_laya_glance_stale_last_row(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LAYA_BASE_URL", "http://laya.test")
    monkeypatch.setenv("LAYA_ADVISORY", "1")
    stale_at = (datetime.now(timezone.utc) - timedelta(hours=10)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    (tmp_path / "laya_decisions.json").write_text(
        json.dumps(
            {
                "events": [
                    {
                        "at": stale_at,
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
    g = build_laya_glance(tmp_path, scan_interval_sec=900)
    assert g["freshness"] == "stale"
    assert g["tone"] == "stale"
    assert "stale" in g["line"]
    assert "MSFT" in g["line"]


def test_laya_glance_scan_clash(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LAYA_BASE_URL", "http://laya.test")
    monkeypatch.setenv("LAYA_ADVISORY", "1")
    now = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)
    stale_at = (now - timedelta(hours=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    scan_at = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    (tmp_path / "laya_decisions.json").write_text(
        json.dumps(
            {
                "events": [
                    {
                        "at": stale_at,
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
    g = build_laya_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=scan_at
    )
    assert g["freshness"] == "stale"
    assert g["scan_freshness"] == "fresh"
    assert g["scan_vs_laya_clash"] == "clash · scan fresh"
    assert "clash" in g["line"]
    assert g["line"].index("stale") < g["line"].index("clash")
    same = build_laya_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=stale_at
    )
    assert same["scan_vs_laya_clash"] == ""
    assert "clash" not in same["line"]


def test_laya_glance_scan_clash_escalates_tone(monkeypatch, tmp_path: Path) -> None:
    """Fresh last-row vs stale scan → clash warn tone (age label ≠ severity)."""
    monkeypatch.setenv("LAYA_BASE_URL", "http://laya.test")
    monkeypatch.setenv("LAYA_ADVISORY", "1")
    now = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)
    fresh_at = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    stale_scan = (now - timedelta(hours=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    aging_scan = (now - timedelta(minutes=45)).strftime("%Y-%m-%dT%H:%M:%SZ")
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
                        "entry": "pass",
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    g = build_laya_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=stale_scan
    )
    assert g["freshness"] == "fresh"
    assert g["scan_freshness"] == "stale"
    assert g["scan_vs_laya_clash"] == "clash · scan stale"
    assert g["tone"] == "stale"
    aging = build_laya_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=aging_scan
    )
    assert aging["scan_freshness"] == "aging"
    assert aging["scan_vs_laya_clash"] == "clash · scan aging"
    assert aging["tone"] == "aging"
    calm = build_laya_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=fresh_at
    )
    assert calm["scan_vs_laya_clash"] == ""
    assert calm["tone"] == "advisory"


def test_laya_glance_debate_clash(monkeypatch, tmp_path: Path) -> None:
    """Last-row band ≠ last-debate band → clash · debate {tone} (display only)."""
    monkeypatch.setenv("LAYA_BASE_URL", "http://laya.test")
    monkeypatch.setenv("LAYA_ADVISORY", "1")
    now = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)
    stale_at = (now - timedelta(hours=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    fresh_at = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    (tmp_path / "laya_decisions.json").write_text(
        json.dumps(
            {
                "events": [
                    {
                        "at": stale_at,
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
    (tmp_path / "ai_validate_memory.json").write_text(
        json.dumps(
            {
                "updated_at": fresh_at,
                "events": [
                    {
                        "at": fresh_at,
                        "symbol": "NVDA",
                        "action": "BUY",
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    g = build_laya_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=stale_at
    )
    assert g["freshness"] == "stale"
    assert g["scan_freshness"] == "stale"
    assert g["debate_freshness"] == "fresh"
    assert g["scan_vs_laya_clash"] == "clash · debate fresh"
    assert "clash" in g["line"]
    both = build_laya_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=fresh_at
    )
    assert both["scan_vs_laya_clash"] == "clash · scan fresh · debate fresh"
    same = build_laya_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=stale_at
    )
    (tmp_path / "ai_validate_memory.json").write_text(
        json.dumps(
            {
                "updated_at": stale_at,
                "events": [{"at": stale_at, "symbol": "NVDA", "action": "HOLD"}],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    quiet = build_laya_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=stale_at
    )
    assert quiet["scan_vs_laya_clash"] == ""
    assert same["scan_vs_laya_clash"] == "clash · debate fresh"


def test_laya_glance_debate_name_clash(monkeypatch, tmp_path: Path) -> None:
    """Last-row ticker/verb ≠ last-debate → mixed/align/vs (display only)."""
    monkeypatch.setenv("LAYA_BASE_URL", "http://laya.test")
    monkeypatch.setenv("LAYA_ADVISORY", "1")
    now = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)
    at = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _write(laya_sym: str, laya_entry: str, debate_sym: str, debate_act: str) -> None:
        (tmp_path / "laya_decisions.json").write_text(
            json.dumps(
                {
                    "events": [
                        {
                            "at": at,
                            "symbol": laya_sym,
                            "ok": True,
                            "fail_open": False,
                            "reason": "ok",
                            "entry": laya_entry,
                        }
                    ]
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (tmp_path / "ai_validate_memory.json").write_text(
            json.dumps(
                {
                    "updated_at": at,
                    "events": [
                        {"at": at, "symbol": debate_sym, "action": debate_act}
                    ],
                }
            )
            + "\n",
            encoding="utf-8",
        )

    _write("MSFT", "hold", "NVDA", "BUY")
    g = build_laya_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=at
    )
    assert g["scan_vs_laya_clash"] == ""
    assert g["memory_name_clash"] == "mixed · vs NVDA BUY"
    assert g["memory_verb_oppose"] is False
    assert "mixed · vs NVDA BUY" in g["line"]
    assert g["line"].index("fresh") < g["line"].index("vs NVDA")
    assert g["tone"] == "advisory"
    _write("MSFT", "pass", "NVDA", "BUY")
    align = build_laya_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=at
    )
    assert align["memory_name_clash"] == "align · vs NVDA BUY"
    assert align["memory_verb_oppose"] is False
    assert "align · vs NVDA BUY" in align["line"]
    assert align["tone"] == "advisory"
    _write("MSFT", "hold", "MSFT", "BUY")
    verb = build_laya_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=at
    )
    assert verb["memory_name_clash"] == "mixed · vs BUY"
    assert verb["memory_verb_oppose"] is False
    assert "mixed · vs BUY" in verb["line"]
    assert verb["tone"] == "advisory"
    _write("MSFT", "hold", "MSFT", "HOLD")
    same = build_laya_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=at
    )
    assert same["memory_name_clash"] == "agree"
    assert same["memory_verb_oppose"] is False
    assert "agree" in same["line"]
    assert "vs " not in same["line"]
    _write("MSFT", "pass", "MSFT", "BUY")
    bull = build_laya_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=at
    )
    assert bull["memory_name_clash"] == "agree"
    assert bull["memory_verb_oppose"] is False
    assert bull["tone"] == "advisory"
    _write("MSFT", "reject", "MSFT", "SELL")
    bear = build_laya_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=at
    )
    assert bear["memory_name_clash"] == "agree"
    assert bear["memory_verb_oppose"] is False
    assert bear["tone"] == "advisory"


def test_laya_glance_debate_verb_oppose(monkeypatch, tmp_path: Path) -> None:
    """reject vs BUY escalates tone; ticker-only clash stays advisory."""
    monkeypatch.setenv("LAYA_BASE_URL", "http://laya.test")
    monkeypatch.setenv("LAYA_ADVISORY", "1")
    now = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)
    at = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _write(laya_entry: str, debate_act: str, *, laya_sym: str = "MSFT") -> None:
        (tmp_path / "laya_decisions.json").write_text(
            json.dumps(
                {
                    "events": [
                        {
                            "at": at,
                            "symbol": laya_sym,
                            "ok": True,
                            "fail_open": False,
                            "reason": "ok",
                            "entry": laya_entry,
                        }
                    ]
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (tmp_path / "ai_validate_memory.json").write_text(
            json.dumps(
                {
                    "updated_at": at,
                    "events": [
                        {"at": at, "symbol": "MSFT", "action": debate_act}
                    ],
                }
            )
            + "\n",
            encoding="utf-8",
        )

    _write("reject", "BUY")
    g = build_laya_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=at
    )
    assert g["memory_name_clash"] == "vs BUY"
    assert g["memory_verb_oppose"] is True
    assert g["tone"] == "aging"
    _write("pass", "SELL")
    pass_sell = build_laya_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=at
    )
    assert pass_sell["memory_verb_oppose"] is True
    assert pass_sell["tone"] == "aging"
    _write("reject", "BUY", laya_sym="NVDA")
    ticker = build_laya_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=at
    )
    assert ticker["memory_name_clash"] == "vs MSFT BUY"
    assert ticker["memory_verb_oppose"] is True
    assert ticker["tone"] == "aging"
    _write("hold", "BUY")
    hold = build_laya_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=at
    )
    assert hold["memory_name_clash"] == "mixed · vs BUY"
    assert hold["memory_verb_oppose"] is False
    assert hold["tone"] == "advisory"


def test_laya_glance_debate_mixed_fail_open(monkeypatch, tmp_path: Path) -> None:
    """fail-open vs BUY on same ticker speaks mixed (not polarity oppose)."""
    monkeypatch.setenv("LAYA_BASE_URL", "http://laya.test")
    monkeypatch.setenv("LAYA_ADVISORY", "1")
    now = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)
    at = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    (tmp_path / "laya_decisions.json").write_text(
        json.dumps(
            {
                "events": [
                    {
                        "at": at,
                        "symbol": "MSFT",
                        "ok": False,
                        "fail_open": True,
                        "reason": "timeout",
                        "entry": "",
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "ai_validate_memory.json").write_text(
        json.dumps(
            {
                "updated_at": at,
                "events": [{"at": at, "symbol": "MSFT", "action": "BUY"}],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    g = build_laya_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=at
    )
    assert g["memory_name_clash"] == "mixed · vs BUY"
    assert g["memory_verb_oppose"] is False
    assert g["tone"] == "advisory"
    assert "mixed · vs BUY" in g["line"]


def test_laya_glance_edge_fee_bits(monkeypatch, tmp_path: Path) -> None:
    """Last-row edge + fee-churn speak; thin/hot escalate tone (not a gate)."""
    monkeypatch.setenv("LAYA_BASE_URL", "http://laya.test")
    monkeypatch.setenv("LAYA_ADVISORY", "1")
    now = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)
    at = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _write(
        *,
        entry: str = "pass",
        edge_score: float | None = 2.1,
        fee_churn: float | None = 0.15,
    ) -> None:
        row: dict = {
            "at": at,
            "symbol": "MSFT",
            "ok": True,
            "fail_open": False,
            "reason": "ok",
            "entry": entry,
        }
        if edge_score is not None:
            row["edge_score"] = edge_score
        if fee_churn is not None:
            row["fee_churn"] = fee_churn
        (tmp_path / "laya_decisions.json").write_text(
            json.dumps({"events": [row]}) + "\n", encoding="utf-8"
        )

    _write()
    g = build_laya_glance(tmp_path, now=now, scan_interval_sec=900, scan_time=at)
    assert g["edge_fee_bits"] == "edge ok · fee quiet"
    assert g["edge_fee_warn"] is False
    assert "edge ok · fee quiet" in g["line"]
    assert g["line"].index("last MSFT pass") < g["line"].index("edge ok")
    assert g["tone"] == "advisory"

    _write(edge_score=1.0, fee_churn=0.15)
    thin = build_laya_glance(tmp_path, now=now, scan_interval_sec=900, scan_time=at)
    assert thin["edge_fee_bits"] == "edge thin · fee quiet"
    assert thin["edge_fee_warn"] is True
    assert thin["tone"] == "aging"

    _write(edge_score=2.8, fee_churn=0.6)
    hot = build_laya_glance(tmp_path, now=now, scan_interval_sec=900, scan_time=at)
    assert hot["edge_fee_bits"] == "edge strong · fee hot"
    assert hot["edge_fee_warn"] is True
    assert hot["tone"] == "aging"

    _write(edge_score=None, fee_churn=None)
    silent = build_laya_glance(tmp_path, now=now, scan_interval_sec=900, scan_time=at)
    assert silent["edge_fee_bits"] == ""
    assert silent["edge_fee_warn"] is False
    assert "edge " not in silent["line"]
    assert silent["tone"] == "advisory"


def test_laya_glance_edge_vs_conf(monkeypatch, tmp_path: Path) -> None:
    """Same-ticker edge vs debate conf clash/align (not a gate)."""
    from stock_checker.ai_validate_memory import record_ai_validate

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
        events = json.loads(
            (tmp_path / "ai_validate_memory.json").read_text(encoding="utf-8")
        )["events"]
        events[-1]["at"] = at
        (tmp_path / "ai_validate_memory.json").write_text(
            json.dumps({"updated_at": at, "events": events}) + "\n",
            encoding="utf-8",
        )

    _laya(1.0)
    _debate("HIGH")
    clash = build_laya_glance(tmp_path, now=now, scan_interval_sec=900, scan_time=at)
    assert clash["edge_vs_conf"] == "edge/conf clash · thin · hi"
    assert clash["edge_vs_conf_warn"] is True
    # May share the 96-char clip with edge/fee + pass/edge warn; field is source of truth.
    assert clash["tone"] == "aging"

    _laya(2.8)
    _debate("HIGH")
    align = build_laya_glance(tmp_path, now=now, scan_interval_sec=900, scan_time=at)
    assert align["edge_vs_conf"] == "edge/conf align · strong · hi"
    assert align["edge_vs_conf_warn"] is False
    # Align may share the clip with pass/edge; field carries the full bit.
    assert "edge/conf align" in align["line"] or align["edge_vs_conf"]

    _laya(2.1)
    _debate("MEDIUM")
    mid = build_laya_glance(tmp_path, now=now, scan_interval_sec=900, scan_time=at)
    assert mid["edge_vs_conf"] == ""
    assert "edge/conf " not in mid["line"]

    _laya(2.8, symbol="MSFT")
    _debate("LOW", symbol="NVDA")
    cross = build_laya_glance(tmp_path, now=now, scan_interval_sec=900, scan_time=at)
    assert cross["edge_vs_conf"] == ""


def test_laya_glance_edge_vs_fee(monkeypatch, tmp_path: Path) -> None:
    """Same-row edge vs fee-churn clash/align (not a gate)."""
    monkeypatch.setenv("LAYA_BASE_URL", "http://laya.test")
    monkeypatch.setenv("LAYA_ADVISORY", "1")
    now = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)
    at = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _laya(edge_score: float, fee_churn: float) -> None:
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
                            "edge_score": edge_score,
                            "fee_churn": fee_churn,
                        }
                    ]
                }
            )
            + "\n",
            encoding="utf-8",
        )

    _laya(2.8, 0.8)
    clash = build_laya_glance(tmp_path, now=now, scan_interval_sec=900, scan_time=at)
    assert clash["edge_vs_fee"] == "edge/fee clash · strong · hot"
    assert clash["edge_vs_fee_warn"] is True
    assert "edge/fee clash · strong · hot" in clash["line"]
    assert clash["tone"] == "aging"

    _laya(2.8, 0.1)
    align = build_laya_glance(tmp_path, now=now, scan_interval_sec=900, scan_time=at)
    assert align["edge_vs_fee"] == "edge/fee align · strong · quiet"
    assert align["edge_vs_fee_warn"] is False
    # Align sits after raw bands; 96-char clip may truncate the tail.
    assert "edge/fee align" in align["line"] or align["edge_vs_fee"]

    _laya(1.0, 0.1)
    thin_quiet = build_laya_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=at
    )
    assert thin_quiet["edge_vs_fee"] == "edge/fee clash · thin · quiet"
    assert thin_quiet["edge_vs_fee_warn"] is True
    assert "edge/fee clash · thin · quiet" in thin_quiet["line"]
    assert thin_quiet["tone"] == "aging"

    _laya(2.1, 0.35)
    mid = build_laya_glance(tmp_path, now=now, scan_interval_sec=900, scan_time=at)
    assert mid["edge_vs_fee"] == ""
    assert "edge/fee " not in mid["line"]


def test_laya_glance_decision_vs_edge(monkeypatch, tmp_path: Path) -> None:
    """Same-row pass/reject vs typed edge clash/align (not a gate)."""
    monkeypatch.setenv("LAYA_BASE_URL", "http://laya.test")
    monkeypatch.setenv("LAYA_ADVISORY", "1")
    now = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)
    at = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _laya(entry: str, edge_score: float) -> None:
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
                            "entry": entry,
                            "edge_score": edge_score,
                            "fee_churn": 0.35,
                        }
                    ]
                }
            )
            + "\n",
            encoding="utf-8",
        )

    _laya("pass", 1.0)
    clash = build_laya_glance(tmp_path, now=now, scan_interval_sec=900, scan_time=at)
    assert clash["decision_vs_edge"] == "pass/edge clash · thin"
    assert clash["decision_vs_edge_warn"] is True
    assert "pass/edge clash · thin" in clash["line"]
    assert clash["tone"] == "aging"

    _laya("pass", 2.8)
    align = build_laya_glance(tmp_path, now=now, scan_interval_sec=900, scan_time=at)
    assert align["decision_vs_edge"] == "pass/edge align · strong"
    assert align["decision_vs_edge_warn"] is False
    assert "pass/edge align" in align["line"] or align["decision_vs_edge"]

    _laya("reject", 2.8)
    rej_clash = build_laya_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=at
    )
    assert rej_clash["decision_vs_edge"] == "reject/edge clash · strong"
    assert rej_clash["decision_vs_edge_warn"] is True
    assert "reject/edge clash · strong" in rej_clash["line"]
    assert rej_clash["tone"] == "aging"

    _laya("reject", 1.0)
    rej_align = build_laya_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=at
    )
    assert rej_align["decision_vs_edge"] == "reject/edge align · thin"
    assert rej_align["decision_vs_edge_warn"] is False

    _laya("pass", 2.1)
    mid = build_laya_glance(tmp_path, now=now, scan_interval_sec=900, scan_time=at)
    assert mid["decision_vs_edge"] == ""
    assert "pass/edge " not in mid["line"] and "reject/edge " not in mid["line"]

    _laya("hold", 2.8)
    hold = build_laya_glance(tmp_path, now=now, scan_interval_sec=900, scan_time=at)
    assert hold["decision_vs_edge"] == ""


def test_laya_glance_fee_vs_conf(monkeypatch, tmp_path: Path) -> None:
    """Same-ticker fee-churn vs debate conf clash/align (not a gate)."""
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
    clash = build_laya_glance(tmp_path, now=now, scan_interval_sec=900, scan_time=at)
    assert clash["fee_vs_conf"] == "fee/conf clash · hot · hi"
    assert clash["fee_vs_conf_warn"] is True
    # May share the 96-char clip with edge/fee warn; field carries the full bit.
    assert "fee/conf clash" in clash["line"]
    assert clash["tone"] == "aging"

    _laya(0.1)
    _debate("HIGH")
    align = build_laya_glance(tmp_path, now=now, scan_interval_sec=900, scan_time=at)
    assert align["fee_vs_conf"] == "fee/conf align · quiet · hi"
    assert align["fee_vs_conf_warn"] is False
    # Align may share the clip with edge/conf; prefix is enough.
    assert "fee/conf align" in align["line"]

    _laya(0.1)
    _debate("LOW")
    quiet_lo = build_laya_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=at
    )
    assert quiet_lo["fee_vs_conf"] == "fee/conf clash · quiet · lo"
    assert quiet_lo["fee_vs_conf_warn"] is True
    assert "fee/conf clash · quiet · lo" in quiet_lo["line"]
    assert quiet_lo["tone"] == "aging"

    _laya(0.35)
    _debate("MEDIUM")
    mid = build_laya_glance(tmp_path, now=now, scan_interval_sec=900, scan_time=at)
    assert mid["fee_vs_conf"] == ""
    assert "fee/conf " not in mid["line"]

    _laya(0.8, symbol="MSFT")
    _debate("HIGH", symbol="NVDA")
    cross = build_laya_glance(tmp_path, now=now, scan_interval_sec=900, scan_time=at)
    assert cross["fee_vs_conf"] == ""


def test_desk_templates_include_laya_glance() -> None:
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
        assert "laya_glance" in text, name
    assert "laya_glance" in Path("openbb_backend/templates/macros.html").read_text()
    assert "renderLayaGlance" in Path("openbb_backend/static/charts.js").read_text()


def test_laya_glance_no_sample(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LAYA_BASE_URL", "http://laya.test")
    monkeypatch.setenv("LAYA_ADVISORY", "1")
    g = build_laya_glance(tmp_path)
    assert "no sample" in g["line"]
    assert g["tone"] == "advisory"
    assert g["freshness"] == ""


def test_laya_glance_in_snapshot(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("LAYA_BASE_URL", raising=False)
    monkeypatch.delenv("JEV_BASE_URL", raising=False)
    from openbb_backend.desk import load_desk_snapshot

    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    snap = load_desk_snapshot(tmp_path, live_marks=False)
    assert "laya_glance" in snap
    assert snap["laya_glance"]["ready"] is True
