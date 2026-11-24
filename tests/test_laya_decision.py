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
    assert "Price: 200.00" in text
    assert "PrevClose: 198.00" in text
    assert "Daily%: +1.01" in text
    assert "anti-churn" in text or "min hold" in text.lower() or "24h" in text


def test_build_state_daily_pct_unavailable_on_bool_or_missing() -> None:
    """tradermonty #798: bool/missing marks speak n/a — never invent flat +0.00."""
    for data in (
        {"symbol": "X", "current_price": True, "previous_close": 100},
        {"symbol": "X", "current_price": 100, "previous_close": True},
        {"symbol": "X", "current_price": None, "previous_close": 100},
        {"symbol": "X"},
    ):
        text = build_paper_entry_state(data)
        assert "Daily%: n/a" in text
        assert "Daily%: +0.00" not in text


def test_build_state_money_pe_volume_refuse_bool() -> None:
    """tradermonty #700/#655 + xang1234: raw Price/PE/Volume must not print True→$1."""
    text = build_paper_entry_state(
        {
            "symbol": "X",
            "current_price": True,
            "previous_close": False,
            "52_week_high": True,
            "52_week_low": False,
            "pe_ratio": True,
            "volume": False,
        }
    )
    assert "Price: n/a" in text
    assert "PrevClose: n/a" in text
    assert "52w High/Low: n/a / n/a" in text
    assert "P/E:" not in text
    assert "Volume:" not in text
    assert "True" not in text

    ok = build_paper_entry_state(
        {
            "symbol": "AAPL",
            "current_price": 150.0,
            "previous_close": 148.0,
            "52_week_high": 200.0,
            "52_week_low": 100.0,
            "pe_ratio": 22.5,
            "volume": 2_500_000,
        }
    )
    assert "Price: 150.00" in ok
    assert "PrevClose: 148.00" in ok
    assert "52w High/Low: 200.00 / 100.00" in ok
    assert "P/E: 22.50" in ok
    assert "Volume: 2,500,000" in ok


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


def test_parse_system_one_refuses_bool_edge_fee_probs() -> None:
    """tradermonty #700/#655: True must not invent edge 1 / fee 1 / prob 1."""
    parsed = parse_system_one_answers(
        {
            "answers": {
                "entry": {
                    "choice": "pass",
                    "probabilities": {"pass": True, "hold": 0.2, "reject": False},
                },
                "edge": {"score": True},
                "fee_churn": {"noul": True},
            }
        }
    )
    assert parsed["edge_score"] is None
    assert parsed["fee_churn"] is None
    assert "pass" not in parsed["probabilities"]
    assert "reject" not in parsed["probabilities"]
    assert parsed["probabilities"]["hold"] == 0.2


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


def test_laya_glance_refuses_bool_sample_counts(monkeypatch, tmp_path: Path) -> None:
    """tradermonty #700/#655 + FinRobot: True→1 must not invent pass/hold meters."""
    monkeypatch.setenv("LAYA_BASE_URL", "http://laya.test")
    monkeypatch.setenv("LAYA_ADVISORY", "1")

    def _fake_status(_root):
        return {
            "configured": True,
            "advisory": True,
            "model": "systemone",
            "stats": {
                "pass": True,
                "hold": False,
                "reject": True,
                "fail_open": True,
                "newest": None,
            },
        }

    monkeypatch.setattr(
        "stock_checker.laya_decision.laya_status", _fake_status
    )
    g = build_laya_glance(tmp_path)
    assert g["ready"] is True
    assert g["advisory"] is True
    assert "no sample" in g["line"]
    assert "1p/" not in g["line"]
    assert "1 fail-open" not in g["line"]


def test_laya_glance_refuses_bool_model_ceiling(monkeypatch, tmp_path: Path) -> None:
    """True→1 must not invent a one-char model strip via model[:True]."""
    from openbb_backend.desk import (
        LAYA_GLANCE_MODEL_MAX_ON,
        _clip_laya_glance_model,
    )

    long = "laya_model_" + ("m" * 40)
    clipped = long[: LAYA_GLANCE_MODEL_MAX_ON - 1] + "…"
    assert _clip_laya_glance_model(long, True) == clipped
    assert _clip_laya_glance_model(long, False) == clipped
    assert clipped != "l…"
    assert _clip_laya_glance_model(long, 8) == long[:7] + "…"

    monkeypatch.setenv("LAYA_BASE_URL", "http://laya.test")
    monkeypatch.setenv("LAYA_ADVISORY", "1")

    def _fake_status(_root):
        return {
            "configured": True,
            "advisory": True,
            "model": long,
            "stats": {
                "pass": 0,
                "hold": 0,
                "reject": 0,
                "fail_open": 0,
                "newest": None,
            },
        }

    monkeypatch.setattr(
        "stock_checker.laya_decision.laya_status", _fake_status
    )
    g_true = build_laya_glance(tmp_path, model_n=True)
    assert g_true["ready"] is True
    assert g_true["model_short"] == clipped
    assert clipped in g_true["line"]
    g_false = build_laya_glance(tmp_path, model_n=False)
    assert g_false["model_short"] == clipped
    g_short = build_laya_glance(tmp_path, model_n=8)
    assert g_short["model_short"] == long[:7] + "…"
    assert len(g_short["model_short"]) == 8


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
    assert g["fail_reason_class"] == ""
    assert g["fail_reason_warn"] is False


def test_laya_fail_reason_class_maps_provider_parse() -> None:
    """xang1234 #674 — typed System-1 fail reasons → compact why class."""
    from openbb_backend.desk import (
        laya_fail_reason_class,
        laya_fail_reason_detail,
    )

    assert laya_fail_reason_class("provider_error:TimeoutError") == "provider"
    assert laya_fail_reason_class("parse_error:JSONDecodeError") == "parse"
    assert laya_fail_reason_class("invalid_choice") == "invalid"
    assert laya_fail_reason_class("not_configured") == "config"
    assert laya_fail_reason_class("advisory_off") == "off"
    assert laya_fail_reason_class("unexpected_error") == "error"
    assert laya_fail_reason_class("ok") == ""
    assert laya_fail_reason_class("") == ""
    # Exception name after class (Timeout vs Auth; never the message).
    assert laya_fail_reason_detail("provider_error:TimeoutError") == "timeout"
    assert laya_fail_reason_detail("parse_error:JSONDecodeError") == "jsondecode"
    assert (
        laya_fail_reason_detail("provider_error:AuthenticationError") == "auth"
    )
    assert laya_fail_reason_detail("not_configured") == ""
    assert laya_fail_reason_detail("provider_error: bad msg") == ""
    assert laya_fail_reason_detail("ok") == ""


def test_laya_glance_fail_open_speaks_reason_class(
    monkeypatch, tmp_path: Path
) -> None:
    """Bare fail-open hid provider vs parse (#674 / Yahoo last-error parity)."""
    monkeypatch.setenv("LAYA_BASE_URL", "http://laya.test")
    monkeypatch.setenv("LAYA_ADVISORY", "1")
    now = datetime(2026, 10, 21, 15, 0, tzinfo=timezone.utc)
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
                        "reason": "provider_error:TimeoutError",
                        "entry": None,
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    g = build_laya_glance(tmp_path, now=now, scan_interval_sec=900)
    assert g["fail_reason_class"] == "provider"
    assert g["fail_reason_detail"] == "timeout"
    assert g["fail_reason_warn"] is True
    assert "fail · provider · timeout" in g["line"]
    assert "last MSFT" in g["line"]
    # Why sits before last so the 96-char clip keeps it.
    assert g["line"].index("fail · provider · timeout") < g["line"].index(
        "last MSFT"
    )
    assert g["tone"] == "aging"
    # Config/off stay calm (no warn escalate) but still speak the class.
    (tmp_path / "laya_decisions.json").write_text(
        json.dumps(
            {
                "events": [
                    {
                        "at": at,
                        "symbol": "AAPL",
                        "ok": False,
                        "fail_open": True,
                        "reason": "not_configured",
                        "entry": None,
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    calm = build_laya_glance(tmp_path, now=now, scan_interval_sec=900)
    assert calm["fail_reason_class"] == "config"
    assert calm["fail_reason_detail"] == ""
    assert calm["fail_reason_warn"] is False
    assert "fail · config" in calm["line"]
    assert "last AAPL" in calm["line"]


def test_laya_glance_fail_open_sample_class_lead(
    monkeypatch, tmp_path: Path
) -> None:
    """Absolute N fail-open hid which why owns the ring (#674 / junk lead)."""
    monkeypatch.setenv("LAYA_BASE_URL", "http://laya.test")
    monkeypatch.setenv("LAYA_ADVISORY", "1")
    now = datetime(2026, 10, 21, 15, 0, tzinfo=timezone.utc)
    at = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    at2 = (now - timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    at3 = (now - timedelta(minutes=15)).strftime("%Y-%m-%dT%H:%M:%SZ")
    (tmp_path / "laya_decisions.json").write_text(
        json.dumps(
            {
                "events": [
                    {
                        "at": at3,
                        "symbol": "AAA",
                        "ok": False,
                        "fail_open": True,
                        "reason": "provider_error:TimeoutError",
                        "entry": None,
                    },
                    {
                        "at": at2,
                        "symbol": "BBB",
                        "ok": False,
                        "fail_open": True,
                        "reason": "parse_error:JSONDecodeError",
                        "entry": None,
                    },
                    {
                        "at": at,
                        "symbol": "MSFT",
                        "ok": False,
                        "fail_open": True,
                        "reason": "provider_error:TimeoutError",
                        "entry": None,
                    },
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    g = build_laya_glance(tmp_path, now=now, scan_interval_sec=900)
    assert g["fail_reason_class"] == "provider"
    assert "3 fail-open" in g["line"] or g["line"].endswith("…")
    assert g["fail_sample_lead_name"] == "provider"
    assert g["fail_sample_lead_share"] == 67
    # Compact when newest matches lead (class already on the why bit).
    assert g["fail_sample_lead"] == "fail lead · 2 · 67%"
    assert "fail lead · 2 · 67%" in g["line"]
    assert g["last_vs_fail_sample_lead"] == "fail agree"
    # Tied classes: no strict lead — speak fail tied (not a fake owner).
    (tmp_path / "laya_decisions.json").write_text(
        json.dumps(
            {
                "events": [
                    {
                        "at": at2,
                        "symbol": "AAA",
                        "ok": False,
                        "fail_open": True,
                        "reason": "provider_error:TimeoutError",
                        "entry": None,
                    },
                    {
                        "at": at,
                        "symbol": "MSFT",
                        "ok": False,
                        "fail_open": True,
                        "reason": "parse_error:JSONDecodeError",
                        "entry": None,
                    },
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    tied = build_laya_glance(tmp_path, now=now, scan_interval_sec=900)
    assert tied["fail_sample_gap"] == "fail tied"
    assert "fail tied" in tied["line"]
    assert tied["fail_sample_lead"] == ""
    assert tied["last_vs_fail_sample_lead"] == ""
    # Count may clip after fail tied; gap owns the early strip.


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
    now = datetime(2026, 10, 6, 15, 0, tzinfo=timezone.utc)
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
    assert g["scan_vs_laya_clash"] == (
        "clash · scan fresh · laya-only · scan-only"
    )
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
    now = datetime(2026, 10, 6, 15, 0, tzinfo=timezone.utc)
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
    assert g["scan_vs_laya_clash"] == (
        "clash · scan stale · laya-only · scan-only"
    )
    assert g["tone"] == "stale"
    aging = build_laya_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=aging_scan
    )
    assert aging["scan_freshness"] == "aging"
    assert aging["scan_vs_laya_clash"] == (
        "clash · scan aging · laya-only · scan-only"
    )
    assert aging["tone"] == "aging"
    calm = build_laya_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=fresh_at
    )
    assert calm["scan_vs_laya_clash"] == ""
    assert calm["tone"] == "advisory"


def test_laya_glance_cash_clash_when_laya_matches_scan(
    monkeypatch, tmp_path: Path
) -> None:
    """xang1234 #549: LAYA matching scan ≠ pinned cash print generation."""
    monkeypatch.setenv("LAYA_BASE_URL", "http://laya.test")
    monkeypatch.setenv("LAYA_ADVISORY", "1")
    # Saturday afternoon UTC — cash sleeves last-published; US Fri close
    # is ~17h ago → cash aging while a fresh LAYA + fresh scan stay
    # LAYA↔scan silent (soft-allow soft≠cash parity).
    now = datetime(2026, 10, 10, 14, 0, tzinfo=timezone.utc)
    fresh_at = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    (tmp_path / "laya_decisions.json").write_text(
        json.dumps(
            {
                "events": [
                    {
                        "at": fresh_at,
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
    (tmp_path / "gate_soft_allows.json").write_text(
        json.dumps(
            {
                "events": [
                    {
                        "at": fresh_at,
                        "gate": "rs",
                        "reason": "AAPL RS unknown — anchor gap — allow",
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    g = build_laya_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=fresh_at
    )
    assert g["freshness"] == "fresh"
    assert g["scan_freshness"] == "fresh"
    assert g["soft_freshness"] == "fresh"
    assert g["gap_freshness"] == "fresh"
    assert g["scan_vs_laya_clash"] == ""
    assert g["laya_vs_soft_clock_clash"] == ""
    assert g["laya_vs_gap_clock_clash"] == ""
    cash = g["laya_vs_cash_clock_clash"]
    assert cash.startswith("clash · laya fresh · cash ")
    assert " · laya-only · " in cash
    # Own matches scan + soft + gap → keep all three so cash alone cannot
    # hide any match (keep-scan + soft + gap / #660 / #647 / #531).
    assert cash.endswith(
        "· ×2 · 100% · scan-only · soft-only · gap-only"
    )
    assert g["laya_vs_cash_clock_clash_warn"] is True
    # 96-char clip may truncate ×N · P%; keep the cash clash + own pin.
    assert "clash · laya fresh · cash" in g["line"]
    assert "laya-only" in g["line"]
    assert g["tone"] == "aging"
    # Same-evening last-published: LAYA fresh + cash fresh → silent.
    even = datetime(2026, 9, 8, 1, 30, tzinfo=timezone.utc)
    even_at = (even - timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    (tmp_path / "laya_decisions.json").write_text(
        json.dumps(
            {
                "events": [
                    {
                        "at": even_at,
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
    (tmp_path / "gate_soft_allows.json").write_text(
        json.dumps(
            {
                "events": [
                    {
                        "at": even_at,
                        "gate": "rs",
                        "reason": "AAPL RS unknown — anchor gap — allow",
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    same = build_laya_glance(
        tmp_path, now=even, scan_interval_sec=900, scan_time=even_at
    )
    assert same["freshness"] == "fresh"
    assert same["laya_vs_cash_clock_clash"] == ""
    assert same["laya_vs_cash_clock_clash_warn"] is False
    assert "clash · laya" not in same["line"]


def test_laya_glance_vs_soft_clock_clash(monkeypatch, tmp_path: Path) -> None:
    """xang1234 #549: LAYA matching scan ≠ staler soft-allow (speak-both-sides)."""
    monkeypatch.setenv("LAYA_BASE_URL", "http://laya.test")
    monkeypatch.setenv("LAYA_ADVISORY", "1")
    now = datetime(2026, 9, 8, 1, 30, tzinfo=timezone.utc)
    fresh_at = (now - timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    stale_at = (now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    (tmp_path / "laya_decisions.json").write_text(
        json.dumps(
            {
                "events": [
                    {
                        "at": fresh_at,
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
    (tmp_path / "gate_soft_allows.json").write_text(
        json.dumps(
            {
                "events": [
                    {
                        "at": stale_at,
                        "gate": "rs",
                        "reason": "AAPL RS unknown — allow",
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    g = build_laya_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=fresh_at
    )
    assert g["freshness"] == "fresh"
    assert g["scan_freshness"] == "fresh"
    assert g["soft_freshness"] == "stale"
    # Own matches cash (evening last-published) → keep cash pin so soft
    # alone cannot hide the cash match (soft≠* keep-cash / #660 / #647).
    assert g["laya_vs_cash_clock_clash"] == ""
    assert g["laya_vs_soft_clock_clash"] == (
        "clash · soft stale · laya-only · soft-only · scan-only · ×2 · 100%"
    )
    assert g["laya_vs_soft_clock_clash_warn"] is True
    assert "clash · soft stale · laya-only · soft-only" in g["line"]
    assert g["tone"] in {"aging", "stale"}
    # Same band — silent.
    (tmp_path / "gate_soft_allows.json").write_text(
        json.dumps(
            {
                "events": [
                    {
                        "at": fresh_at,
                        "gate": "rs",
                        "reason": "AAPL RS unknown — allow",
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    same = build_laya_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=fresh_at
    )
    assert same["soft_freshness"] == "fresh"
    assert same["laya_vs_soft_clock_clash"] == ""
    assert same["laya_vs_soft_clock_clash_warn"] is False
    assert "clash · soft" not in same["line"]


def test_laya_glance_peer_soft_clash_when_laya_matches_soft(
    monkeypatch, tmp_path: Path
) -> None:
    """LAYA matching soft can still hide debate ≠ soft (peer speak)."""
    from stock_checker.ai_validate_memory import record_ai_validate

    monkeypatch.setenv("LAYA_BASE_URL", "http://laya.test")
    monkeypatch.setenv("LAYA_ADVISORY", "1")
    now = datetime(2026, 9, 8, 1, 30, tzinfo=timezone.utc)
    fresh_at = (now - timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    stale_at = (now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    (tmp_path / "laya_decisions.json").write_text(
        json.dumps(
            {
                "events": [
                    {
                        "at": fresh_at,
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
    (tmp_path / "gate_soft_allows.json").write_text(
        json.dumps(
            {
                "events": [
                    {
                        "at": fresh_at,
                        "gate": "rs",
                        "reason": "AAPL RS unknown — allow",
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    record_ai_validate(
        tmp_path,
        {"action": "BUY", "confidence": "HIGH", "score": 40, "reasons": ["tape"]},
        symbol="NVDA",
        kept=True,
    )
    events = json.loads(
        (tmp_path / "ai_validate_memory.json").read_text(encoding="utf-8")
    )
    events["events"][-1]["at"] = stale_at
    events["updated_at"] = stale_at
    (tmp_path / "ai_validate_memory.json").write_text(
        json.dumps(events) + "\n", encoding="utf-8"
    )
    # No scan_time → no pinned cash sleeve, so peer-cash does not crowd the clip.
    g = build_laya_glance(tmp_path, now=now, scan_interval_sec=900)
    assert g["freshness"] == "fresh"
    assert g["soft_freshness"] == "fresh"
    assert g["laya_vs_soft_clock_clash"] == ""
    assert g["laya_peer_cash_clock_clash"] == ""
    peer = g["laya_peer_soft_clock_clash"]
    assert peer.startswith("peer soft · debate ")
    assert "soft fresh" in peer
    assert " · debate-only · " in peer
    assert peer.endswith("· soft-only")
    assert g["laya_peer_soft_clock_clash_warn"] is True
    assert "peer soft" in g["line"]
    assert g["tone"] in {"aging", "stale"}


def test_laya_glance_peer_soft_keeps_scan_only_when_own_matches_scan(
    monkeypatch, tmp_path: Path
) -> None:
    """Peer soft crowding peer_ring must not drop scan-only (own≈archive)."""
    from stock_checker.ai_validate_memory import record_ai_validate

    monkeypatch.setenv("LAYA_BASE_URL", "http://laya.test")
    monkeypatch.setenv("LAYA_ADVISORY", "1")
    now = datetime(2026, 9, 8, 1, 30, tzinfo=timezone.utc)
    fresh_at = (now - timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    stale_at = (now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    (tmp_path / "laya_decisions.json").write_text(
        json.dumps(
            {
                "events": [
                    {
                        "at": fresh_at,
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
    (tmp_path / "gate_soft_allows.json").write_text(
        json.dumps(
            {
                "events": [
                    {
                        "at": fresh_at,
                        "gate": "rs",
                        "reason": "AAPL RS unknown — allow",
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    record_ai_validate(
        tmp_path,
        {"action": "BUY", "confidence": "HIGH", "score": 40, "reasons": ["tape"]},
        symbol="NVDA",
        kept=True,
    )
    events = json.loads(
        (tmp_path / "ai_validate_memory.json").read_text(encoding="utf-8")
    )
    events["events"][-1]["at"] = stale_at
    events["updated_at"] = stale_at
    (tmp_path / "ai_validate_memory.json").write_text(
        json.dumps(events) + "\n", encoding="utf-8"
    )
    g = build_laya_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=fresh_at
    )
    assert g["freshness"] == "fresh"
    assert g["scan_freshness"] == "fresh"
    assert g["soft_freshness"] == "fresh"
    peer = g["laya_peer_soft_clock_clash"]
    assert peer.startswith("peer soft · debate ")
    assert " · debate-only · " in peer
    assert " · soft-only" in peer
    # Peer soft crowded the full peer_ring off the clash; scan-only
    # rides the peer bit so matching the archive is not silent.
    # Own matching cash also keeps the cash pin (soft≠* keep-cash
    # speak-both-sides on peer soft).
    assert peer.endswith("· soft-only · scan-only · ×2 · 100%")
    assert g["scan_vs_laya_clash"] == "clash · debate stale"
    assert "scan-only" not in g["scan_vs_laya_clash"]


def test_laya_glance_peer_soft_and_gap_both_keep_scan_only(
    monkeypatch, tmp_path: Path
) -> None:
    """Two peer bits that crowd peer_ring each keep scan-only (#660)."""
    from stock_checker.ai_validate_memory import record_ai_validate

    monkeypatch.setenv("LAYA_BASE_URL", "http://laya.test")
    monkeypatch.setenv("LAYA_ADVISORY", "1")
    now = datetime(2026, 9, 8, 1, 30, tzinfo=timezone.utc)
    fresh_at = (now - timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    stale_at = (now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    (tmp_path / "laya_decisions.json").write_text(
        json.dumps(
            {
                "events": [
                    {
                        "at": fresh_at,
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
    # One gap row is also soft last — own matches soft+gap; stale debate
    # peers both; elif used to keep scan-only only on soft.
    (tmp_path / "gate_soft_allows.json").write_text(
        json.dumps(
            {
                "events": [
                    {
                        "at": fresh_at,
                        "gate": "rs",
                        "reason": "AAPL RS unknown — anchor gap — allow",
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    record_ai_validate(
        tmp_path,
        {"action": "BUY", "confidence": "HIGH", "score": 40, "reasons": ["tape"]},
        symbol="NVDA",
        kept=True,
    )
    events = json.loads(
        (tmp_path / "ai_validate_memory.json").read_text(encoding="utf-8")
    )
    events["events"][-1]["at"] = stale_at
    events["updated_at"] = stale_at
    (tmp_path / "ai_validate_memory.json").write_text(
        json.dumps(events) + "\n", encoding="utf-8"
    )
    g = build_laya_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=fresh_at
    )
    assert g["freshness"] == "fresh"
    assert g["scan_freshness"] == "fresh"
    assert g["soft_freshness"] == "fresh"
    assert g["gap_freshness"] == "fresh"
    soft = g["laya_peer_soft_clock_clash"]
    gap = g["laya_peer_gap_clock_clash"]
    assert soft.startswith("peer soft · debate ")
    assert gap.startswith("peer gap · debate ")
    # Own matches cash+gap → cash pin + gap-only on peer soft; soft+cash
    # on peer gap (peer keep soft/cash/gap after scan-only).
    assert soft.endswith("· soft-only · scan-only · ×2 · 100% · gap-only")
    assert gap.endswith("· gap-only · scan-only · soft-only · ×2 · 100%")
    assert g["scan_vs_laya_clash"] == "clash · debate stale"
    assert "scan-only" not in g["scan_vs_laya_clash"]


def test_laya_glance_vs_short_clock_clash(monkeypatch, tmp_path: Path) -> None:
    """Soft last matching LAYA can still hide a staler short-history cursor."""
    monkeypatch.setenv("LAYA_BASE_URL", "http://laya.test")
    monkeypatch.setenv("LAYA_ADVISORY", "1")
    now = datetime(2026, 9, 8, 1, 30, tzinfo=timezone.utc)
    fresh_at = (now - timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    stale_at = (now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    (tmp_path / "laya_decisions.json").write_text(
        json.dumps(
            {
                "events": [
                    {
                        "at": fresh_at,
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
    (tmp_path / "gate_soft_allows.json").write_text(
        json.dumps(
            {
                "events": [
                    {
                        "at": stale_at,
                        "gate": "rs",
                        "reason": "IPO RS unknown — short history — allow",
                    },
                    {
                        "at": fresh_at,
                        "gate": "breadth",
                        "reason": "unknown breadth — allow",
                    },
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    g = build_laya_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=fresh_at
    )
    assert g["freshness"] == "fresh"
    assert g["soft_freshness"] == "fresh"
    assert g["short_freshness"] == "stale"
    assert g["scan_freshness"] == "fresh"
    assert g["laya_vs_soft_clock_clash"] == ""
    assert g["laya_vs_cash_clock_clash"] == ""
    assert g["laya_vs_short_clock_clash"] == (
        "clash · short stale · laya-only · short-only · scan-only · "
        "soft-only · ×2 · 100%"
    )
    assert g["laya_vs_short_clock_clash_warn"] is True
    assert "clash · short stale · laya-only · short-only" in g["line"]
    assert g["tone"] in {"aging", "stale"}
    # Same band — silent.
    (tmp_path / "gate_soft_allows.json").write_text(
        json.dumps(
            {
                "events": [
                    {
                        "at": fresh_at,
                        "gate": "rs",
                        "reason": "IPO RS unknown — short history — allow",
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    same = build_laya_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=fresh_at
    )
    assert same["short_freshness"] == "fresh"
    assert same["laya_vs_short_clock_clash"] == ""
    assert same["laya_vs_short_clock_clash_warn"] is False
    assert "clash · short" not in same["line"]


def test_laya_glance_peer_short_clash_when_laya_matches_short(
    monkeypatch, tmp_path: Path
) -> None:
    """LAYA matching short can still hide debate ≠ short (peer speak)."""
    from stock_checker.ai_validate_memory import record_ai_validate

    monkeypatch.setenv("LAYA_BASE_URL", "http://laya.test")
    monkeypatch.setenv("LAYA_ADVISORY", "1")
    now = datetime(2026, 9, 8, 1, 30, tzinfo=timezone.utc)
    fresh_at = (now - timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    stale_at = (now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    (tmp_path / "laya_decisions.json").write_text(
        json.dumps(
            {
                "events": [
                    {
                        "at": fresh_at,
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
    (tmp_path / "gate_soft_allows.json").write_text(
        json.dumps(
            {
                "events": [
                    {
                        "at": fresh_at,
                        "gate": "rs",
                        "reason": "IPO RS unknown — short history — allow",
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    record_ai_validate(
        tmp_path,
        {"action": "BUY", "confidence": "HIGH", "score": 40, "reasons": ["tape"]},
        symbol="NVDA",
        kept=True,
    )
    events = json.loads(
        (tmp_path / "ai_validate_memory.json").read_text(encoding="utf-8")
    )
    events["events"][-1]["at"] = stale_at
    events["updated_at"] = stale_at
    (tmp_path / "ai_validate_memory.json").write_text(
        json.dumps(events) + "\n", encoding="utf-8"
    )
    g = build_laya_glance(tmp_path, now=now, scan_interval_sec=900)
    assert g["freshness"] == "fresh"
    assert g["short_freshness"] == "fresh"
    assert g["laya_vs_short_clock_clash"] == ""
    peer = g["laya_peer_short_clock_clash"]
    assert peer.startswith("peer short · debate ")
    assert "short fresh" in peer
    assert " · debate-only · " in peer
    assert peer.endswith("· short-only · soft-only")
    assert g["laya_peer_short_clock_clash_warn"] is True
    assert "peer short" in g["line"]
    assert g["tone"] in {"aging", "stale"}


def test_laya_glance_vs_gap_clock_clash(monkeypatch, tmp_path: Path) -> None:
    """Soft last matching LAYA can still hide a staler gap cursor."""
    monkeypatch.setenv("LAYA_BASE_URL", "http://laya.test")
    monkeypatch.setenv("LAYA_ADVISORY", "1")
    now = datetime(2026, 9, 8, 1, 30, tzinfo=timezone.utc)
    fresh_at = (now - timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    stale_at = (now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    (tmp_path / "laya_decisions.json").write_text(
        json.dumps(
            {
                "events": [
                    {
                        "at": fresh_at,
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
    (tmp_path / "gate_soft_allows.json").write_text(
        json.dumps(
            {
                "events": [
                    {
                        "at": stale_at,
                        "gate": "rs",
                        "reason": "AAPL RS unknown — anchor gap — allow",
                    },
                    {
                        "at": fresh_at,
                        "gate": "breadth",
                        "reason": "unknown breadth — allow",
                    },
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    g = build_laya_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=fresh_at
    )
    assert g["freshness"] == "fresh"
    assert g["soft_freshness"] == "fresh"
    assert g["gap_freshness"] == "stale"
    assert g["scan_freshness"] == "fresh"
    assert g["laya_vs_soft_clock_clash"] == ""
    # Own matches soft + cash → keep soft-only · cash so gap alone cannot
    # hide either match (gap≠scan keep-cash / #660 / #647 / #531).
    assert g["laya_vs_cash_clock_clash"] == ""
    assert g["laya_vs_gap_clock_clash"] == (
        "clash · gap stale · laya-only · gap-only · scan-only · "
        "soft-only · ×2 · 100%"
    )
    assert g["laya_vs_gap_clock_clash_warn"] is True
    assert "clash · gap stale · laya-only · gap-only" in g["line"]
    assert g["tone"] in {"aging", "stale"}
    # Same band — silent.
    (tmp_path / "gate_soft_allows.json").write_text(
        json.dumps(
            {
                "events": [
                    {
                        "at": fresh_at,
                        "gate": "rs",
                        "reason": "AAPL RS unknown — anchor gap — allow",
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    same = build_laya_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=fresh_at
    )
    assert same["gap_freshness"] == "fresh"
    assert same["laya_vs_gap_clock_clash"] == ""
    assert same["laya_vs_gap_clock_clash_warn"] is False
    assert "clash · gap" not in same["line"]


def test_laya_glance_keep_peer_when_own_matches_debate(
    monkeypatch, tmp_path: Path
) -> None:
    """Own matching debate → keep debate-only on ≠gap (soft keep-memory parity)."""
    from stock_checker.ai_validate_memory import record_ai_validate

    monkeypatch.setenv("LAYA_BASE_URL", "http://laya.test")
    monkeypatch.setenv("LAYA_ADVISORY", "1")
    now = datetime(2026, 9, 8, 1, 30, tzinfo=timezone.utc)
    fresh_at = (now - timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    stale_at = (now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    (tmp_path / "laya_decisions.json").write_text(
        json.dumps(
            {
                "events": [
                    {
                        "at": fresh_at,
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
    record_ai_validate(
        tmp_path,
        {"action": "BUY", "confidence": "HIGH", "score": 40, "reasons": ["tape"]},
        symbol="NVDA",
        kept=True,
    )
    events = json.loads(
        (tmp_path / "ai_validate_memory.json").read_text(encoding="utf-8")
    )
    events["events"][-1]["at"] = fresh_at
    events["updated_at"] = fresh_at
    (tmp_path / "ai_validate_memory.json").write_text(
        json.dumps(events) + "\n", encoding="utf-8"
    )
    (tmp_path / "gate_soft_allows.json").write_text(
        json.dumps(
            {
                "events": [
                    {
                        "at": stale_at,
                        "gate": "rs",
                        "reason": "AAPL RS unknown — anchor gap — allow",
                    },
                    {
                        "at": fresh_at,
                        "gate": "breadth",
                        "reason": "unknown breadth — allow",
                    },
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    g = build_laya_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=fresh_at
    )
    assert g["freshness"] == "fresh"
    assert g["debate_freshness"] == "fresh"
    assert g["gap_freshness"] == "stale"
    assert g["laya_vs_gap_clock_clash"] == (
        "clash · gap stale · laya-only · gap-only · scan-only · "
        "soft-only · ×2 · 100% · debate-only"
    )
    assert g["laya_vs_gap_clock_clash_warn"] is True
    # Same band peer — no peer-gap speak (keep rides own ≠gap instead).
    assert g["laya_peer_gap_clock_clash"] == ""


def test_laya_glance_peer_gap_clash_when_laya_matches_gap(
    monkeypatch, tmp_path: Path
) -> None:
    """LAYA matching gap can still hide debate ≠ gap (peer speak)."""
    from stock_checker.ai_validate_memory import record_ai_validate

    monkeypatch.setenv("LAYA_BASE_URL", "http://laya.test")
    monkeypatch.setenv("LAYA_ADVISORY", "1")
    now = datetime(2026, 9, 8, 1, 30, tzinfo=timezone.utc)
    fresh_at = (now - timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    stale_at = (now - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    (tmp_path / "laya_decisions.json").write_text(
        json.dumps(
            {
                "events": [
                    {
                        "at": fresh_at,
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
    (tmp_path / "gate_soft_allows.json").write_text(
        json.dumps(
            {
                "events": [
                    {
                        "at": fresh_at,
                        "gate": "rs",
                        "reason": "AAPL RS unknown — anchor gap — allow",
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    record_ai_validate(
        tmp_path,
        {"action": "BUY", "confidence": "HIGH", "score": 40, "reasons": ["tape"]},
        symbol="NVDA",
        kept=True,
    )
    events = json.loads(
        (tmp_path / "ai_validate_memory.json").read_text(encoding="utf-8")
    )
    events["events"][-1]["at"] = stale_at
    events["updated_at"] = stale_at
    (tmp_path / "ai_validate_memory.json").write_text(
        json.dumps(events) + "\n", encoding="utf-8"
    )
    g = build_laya_glance(tmp_path, now=now, scan_interval_sec=900)
    assert g["freshness"] == "fresh"
    assert g["gap_freshness"] == "fresh"
    assert g["laya_vs_gap_clock_clash"] == ""
    peer = g["laya_peer_gap_clock_clash"]
    assert peer.startswith("peer gap · debate ")
    assert "gap fresh" in peer
    assert " · debate-only · " in peer
    # Gap row is also soft last — own matches soft → soft-only rides
    # peer gap (peer keep soft/cash/gap).
    assert peer.endswith("· gap-only · soft-only")
    assert g["laya_peer_gap_clock_clash_warn"] is True
    assert "peer gap" in g["line"]
    assert g["tone"] in {"aging", "stale"}


def test_laya_glance_peer_cash_clash_when_laya_matches_cash(
    monkeypatch, tmp_path: Path
) -> None:
    """LAYA matching cash can still hide debate ≠ cash (peer speak)."""
    from stock_checker.ai_validate_memory import record_ai_validate

    monkeypatch.setenv("LAYA_BASE_URL", "http://laya.test")
    monkeypatch.setenv("LAYA_ADVISORY", "1")
    # Same-evening last-published: cash fresh. Fresh LAYA matches cash;
    # stale debate ≠ cash → peer bit on LAYA glance.
    now = datetime(2026, 9, 8, 1, 30, tzinfo=timezone.utc)
    fresh_at = (now - timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    stale_at = (now - timedelta(hours=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    (tmp_path / "laya_decisions.json").write_text(
        json.dumps(
            {
                "events": [
                    {
                        "at": fresh_at,
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
    record_ai_validate(
        tmp_path,
        {"action": "BUY", "confidence": "HIGH", "score": 40, "reasons": ["tape"]},
        symbol="NVDA",
        kept=True,
    )
    events = json.loads(
        (tmp_path / "ai_validate_memory.json").read_text(encoding="utf-8")
    )
    events["events"][-1]["at"] = stale_at
    events["updated_at"] = stale_at
    (tmp_path / "ai_validate_memory.json").write_text(
        json.dumps(events) + "\n", encoding="utf-8"
    )
    g = build_laya_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=fresh_at
    )
    assert g["freshness"] == "fresh"
    assert g["laya_vs_cash_clock_clash"] == ""
    peer = g["laya_peer_cash_clock_clash"]
    assert peer.startswith("peer cash · debate ")
    assert "cash fresh" in peer
    assert " · debate-only · " in peer
    # Peer cash crowded peer_ring off the clash; scan-only rides here.
    assert peer.endswith("· ×2 · 100% · scan-only")
    assert g["laya_peer_cash_clock_clash_warn"] is True
    assert "peer cash" in g["line"]
    # Stale peer clock clash escalates tone above aging warn.
    assert g["tone"] in {"aging", "stale"}


def test_laya_glance_debate_clash(monkeypatch, tmp_path: Path) -> None:
    """Last-row band ≠ last-debate band → clash · debate {tone} (display only)."""
    monkeypatch.setenv("LAYA_BASE_URL", "http://laya.test")
    monkeypatch.setenv("LAYA_ADVISORY", "1")
    now = datetime(2026, 10, 6, 15, 0, tzinfo=timezone.utc)
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
    assert g["scan_vs_laya_clash"] == (
        "clash · debate fresh · scan-only · debate-only"
    )
    assert "clash" in g["line"]
    both = build_laya_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=fresh_at
    )
    assert both["scan_vs_laya_clash"] == (
        "clash · scan fresh · debate fresh · laya-only · scan-only"
    )
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
    assert same["scan_vs_laya_clash"] == (
        "clash · debate fresh · scan-only · debate-only"
    )


def test_laya_glance_debate_name_clash(monkeypatch, tmp_path: Path) -> None:
    """Last-row ticker/verb ≠ last-debate → mixed/align/vs (display only)."""
    monkeypatch.setenv("LAYA_BASE_URL", "http://laya.test")
    monkeypatch.setenv("LAYA_ADVISORY", "1")
    now = datetime(2026, 10, 6, 15, 0, tzinfo=timezone.utc)
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
    now = datetime(2026, 10, 6, 15, 0, tzinfo=timezone.utc)
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
    now = datetime(2026, 10, 6, 15, 0, tzinfo=timezone.utc)
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
    now = datetime(2026, 10, 6, 15, 0, tzinfo=timezone.utc)
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
    now = datetime(2026, 10, 6, 15, 0, tzinfo=timezone.utc)
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
    now = datetime(2026, 10, 6, 15, 0, tzinfo=timezone.utc)
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
    now = datetime(2026, 10, 6, 15, 0, tzinfo=timezone.utc)
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


def test_laya_glance_decision_vs_conf(monkeypatch, tmp_path: Path) -> None:
    """Same-ticker pass/reject vs debate conf clash/align (not a gate)."""
    monkeypatch.setenv("LAYA_BASE_URL", "http://laya.test")
    monkeypatch.setenv("LAYA_ADVISORY", "1")
    now = datetime(2026, 10, 6, 15, 0, tzinfo=timezone.utc)
    at = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _laya(entry: str, symbol: str = "MSFT") -> None:
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
                            "entry": entry,
                            "edge_score": 2.1,
                            "fee_churn": 0.35,
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

    _laya("pass")
    _debate("LOW")
    clash = build_laya_glance(tmp_path, now=now, scan_interval_sec=900, scan_time=at)
    assert clash["decision_vs_conf"] == "pass/conf clash · lo"
    assert clash["decision_vs_conf_warn"] is True
    assert "pass/conf clash · lo" in clash["line"]
    assert clash["tone"] == "aging"

    _laya("pass")
    _debate("HIGH")
    align = build_laya_glance(tmp_path, now=now, scan_interval_sec=900, scan_time=at)
    assert align["decision_vs_conf"] == "pass/conf align · hi"
    assert align["decision_vs_conf_warn"] is False
    assert "pass/conf align" in align["line"] or align["decision_vs_conf"]

    _laya("reject")
    _debate("HIGH")
    rej_align = build_laya_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=at
    )
    assert rej_align["decision_vs_conf"] == "reject/conf align · hi"
    assert rej_align["decision_vs_conf_warn"] is False

    _laya("reject")
    _debate("LOW")
    rej_clash = build_laya_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=at
    )
    assert rej_clash["decision_vs_conf"] == "reject/conf clash · lo"
    assert rej_clash["decision_vs_conf_warn"] is True
    assert "reject/conf clash · lo" in rej_clash["line"]
    assert rej_clash["tone"] == "aging"

    _laya("pass")
    _debate("MEDIUM")
    mid = build_laya_glance(tmp_path, now=now, scan_interval_sec=900, scan_time=at)
    assert mid["decision_vs_conf"] == ""
    assert "pass/conf " not in mid["line"] and "reject/conf " not in mid["line"]

    _laya("hold")
    _debate("HIGH")
    hold = build_laya_glance(tmp_path, now=now, scan_interval_sec=900, scan_time=at)
    assert hold["decision_vs_conf"] == ""

    _laya("pass", symbol="NVDA")
    _debate("LOW", symbol="MSFT")
    cross = build_laya_glance(tmp_path, now=now, scan_interval_sec=900, scan_time=at)
    assert cross["decision_vs_conf"] == ""


def test_laya_glance_fee_vs_conf(monkeypatch, tmp_path: Path) -> None:
    """Same-ticker fee-churn vs debate conf clash/align (not a gate)."""
    monkeypatch.setenv("LAYA_BASE_URL", "http://laya.test")
    monkeypatch.setenv("LAYA_ADVISORY", "1")
    now = datetime(2026, 10, 6, 15, 0, tzinfo=timezone.utc)
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
    # Align may share the clip with decision/conf; field is source of truth.
    assert "fee/conf align" in align["line"] or align["fee_vs_conf"]

    _laya(0.1)
    _debate("LOW")
    quiet_lo = build_laya_glance(
        tmp_path, now=now, scan_interval_sec=900, scan_time=at
    )
    assert quiet_lo["fee_vs_conf"] == "fee/conf clash · quiet · lo"
    assert quiet_lo["fee_vs_conf_warn"] is True
    # May share the clip with pass/conf clash · lo; field carries the full bit.
    assert "fee/conf clash" in quiet_lo["line"] or quiet_lo["fee_vs_conf"]
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


def test_laya_glance_sample_lead(monkeypatch, tmp_path: Path) -> None:
    """Decided sample (≥2) speaks lead · N% + ahead + vs runner · P%."""
    monkeypatch.setenv("LAYA_BASE_URL", "http://laya.test")
    monkeypatch.setenv("LAYA_ADVISORY", "1")
    at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _write(events: list[dict]) -> None:
        (tmp_path / "laya_decisions.json").write_text(
            json.dumps({"events": events}) + "\n", encoding="utf-8"
        )

    def _row(entry: str, symbol: str = "NVDA") -> dict:
        # Mid edge/fee so clash warns do not eat the 96-char clip before meter.
        return {
            "at": at,
            "symbol": symbol,
            "ok": True,
            "fail_open": False,
            "reason": "ok",
            "entry": entry,
            "edge_score": 2.0,
            "fee_churn": 0.35,
            "latency_ms": 40,
            "model": "systemone",
        }

    # Thin sample (1 decided) speaks n=1 — last-row ≠ ring tilt.
    _write([_row("reject")])
    thin = build_laya_glance(tmp_path, now=datetime.now(timezone.utc), scan_interval_sec=900)
    assert thin["sample_lead"] == ""
    assert thin["sample_lead_share"] is None
    assert thin["sample_lead_margin"] == ""
    assert thin["sample_lead_sides"] == ""
    assert thin["sample_lead_sides_share"] is None
    assert thin["sample_gap"] == "n=1"
    assert "n=1" in thin["line"]
    assert "lead " not in thin["line"]

    # Strict reject lead · 2 · 67% + ahead thin · +1 · vs pass · 1 · 33%.
    # Newest reject matches tilt — speak agree (silent confirm hid match).
    _write([_row("pass", "AAPL"), _row("reject", "MSFT"), _row("reject", "NVDA")])
    lead = build_laya_glance(tmp_path, now=datetime.now(timezone.utc), scan_interval_sec=900)
    assert lead["sample_lead"] == "lead reject · 2 · 67%"
    assert lead["sample_lead_name"] == "reject"
    assert lead["sample_lead_share"] == 67
    assert lead["sample_lead_margin"] == "ahead thin · +1"
    assert lead["sample_lead_margin_gap"] == 1
    assert lead["sample_lead_sides"] == "vs pass · 1 · 33%"
    assert lead["sample_lead_sides_name"] == "pass"
    assert lead["sample_lead_sides_n"] == 1
    assert lead["sample_lead_sides_share"] == 33
    assert lead["last_vs_sample_lead"] == "agree"
    assert lead["sample_gap"] == ""
    assert "1p/0h/2r" in lead["line"]
    assert "lead reject · 2 · 67%" in lead["line"]
    assert "agree" in lead["line"]
    # Meter before lead so the 96-char clip keeps ownership after counts.
    assert lead["line"].index("1p/0h/2r") < lead["line"].index("lead reject")
    assert lead["line"].index("lead reject") < lead["line"].index("agree")
    # Ahead/runner may truncate after agree (age + meter already fill the 96).
    if "ahead thin" in lead["line"]:
        assert lead["line"].index("agree") < lead["line"].index("ahead thin")
    assert "last vs lead" not in lead["line"]

    # Newest pass ≠ reject tilt — speak last vs lead (no tone escalate).
    _write([_row("reject", "AAPL"), _row("reject", "MSFT"), _row("pass", "NVDA")])
    clash = build_laya_glance(tmp_path, now=datetime.now(timezone.utc), scan_interval_sec=900)
    assert clash["sample_lead"] == "lead reject · 2 · 67%"
    assert clash["last_vs_sample_lead"] == "last vs lead · pass"
    # Count on lead may clip the runner verb on the 96-char line.
    assert "last vs lead · pa" in clash["line"]
    assert clash["line"].index("lead reject") < clash["line"].index(
        "last vs lead · pa"
    )
    # Margin/sides may truncate after last-vs (age + meter fill the 96).
    if "ahead thin" in clash["line"]:
        assert clash["line"].index("last vs lead · pa") < clash["line"].index(
            "ahead thin"
        )
    assert clash["tone"] == "advisory"  # last vs lead does not escalate tone

    # Sole-bucket lead omits ahead + vs (ownership % ≠ margin ≠ who is #2).
    _write([_row("reject", "AAPL"), _row("reject", "MSFT")])
    sole = build_laya_glance(tmp_path, now=datetime.now(timezone.utc), scan_interval_sec=900)
    assert sole["sample_lead"] == "lead reject · 2 · 100%"
    assert sole["sample_lead_margin"] == ""
    assert sole["sample_lead_sides"] == ""
    assert sole["sample_lead_sides_share"] is None
    assert sole["last_vs_sample_lead"] == "agree"
    assert "agree" in sole["line"]
    assert "ahead " not in sole["line"]
    assert "vs pass" not in sole["line"]
    assert "vs hold" not in sole["line"]
    assert "vs reject" not in sole["line"]
    assert "last vs lead" not in sole["line"]

    # Wide margin (≥2) when lead is further ahead; clear runner still speaks.
    _write(
        [
            _row("pass", "AAPL"),
            _row("reject", "MSFT"),
            _row("reject", "NVDA"),
            _row("reject", "TSLA"),
        ]
    )
    wide = build_laya_glance(tmp_path, now=datetime.now(timezone.utc), scan_interval_sec=900)
    assert wide["sample_lead_margin"] == "ahead wide · +2"
    assert wide["sample_lead_margin_gap"] == 2
    assert wide["sample_lead_sides"] == "vs pass · 1 · 25%"
    assert wide["sample_lead_sides_share"] == 25
    assert wide["last_vs_sample_lead"] == "agree"
    assert "agree" in wide["line"]
    # Ahead/runner may truncate after agree (age + meter fill the 96).
    assert "ahead wide" in wide["line"] or wide["line"].endswith("…")
    assert "vs pass · 1" in wide["line"] or "vs …" in wide["line"] or wide[
        "line"
    ].endswith("…")

    # Tied runners: ahead speaks, vs silent (ahead ≠ who is #2).
    # Newest reject matches tilt — agree speaks; ahead may still fit.
    _write(
        [
            _row("pass", "TSLA"),
            _row("hold", "AMD"),
            _row("reject", "AAPL"),
            _row("reject", "MSFT"),
            _row("reject", "NVDA"),
        ]
    )
    tied_runners = build_laya_glance(
        tmp_path, now=datetime.now(timezone.utc), scan_interval_sec=900
    )
    assert tied_runners["sample_lead"] == "lead reject · 3 · 60%"
    assert tied_runners["sample_lead_margin"] == "ahead wide · +2"
    assert tied_runners["sample_lead_sides"] == ""
    assert tied_runners["sample_lead_sides_share"] is None
    assert tied_runners["last_vs_sample_lead"] == "agree"
    assert "agree" in tied_runners["line"]
    if "ahead wide" in tied_runners["line"]:
        assert tied_runners["line"].index("agree") < tied_runners["line"].index(
            "ahead wide"
        )
    assert "vs pass" not in tied_runners["line"]
    assert "vs hold" not in tied_runners["line"]
    assert "last vs lead" not in tied_runners["line"]

    # Tie speaks tied (counts without a winner).
    _write([_row("pass", "AAPL"), _row("reject", "MSFT")])
    tied = build_laya_glance(tmp_path, now=datetime.now(timezone.utc), scan_interval_sec=900)
    assert tied["sample_lead"] == ""
    assert tied["sample_lead_margin"] == ""
    assert tied["sample_lead_sides"] == ""
    assert tied["sample_lead_sides_share"] is None
    assert tied["sample_gap"] == "tied"
    assert "tied" in tied["line"]
    assert "lead " not in tied["line"]


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
