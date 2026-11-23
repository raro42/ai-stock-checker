"""LAYA advisory ring / reason·model clips must refuse bool invents."""

from __future__ import annotations

from pathlib import Path

from stock_checker.laya_decision import (
    DECISION_CAP,
    _DEFAULT_MODEL_CHARS,
    _DEFAULT_REASON_CHARS,
    _clip,
    _coerce_clip_chars,
    _coerce_decision_cap,
    load_laya_decisions,
    record_laya_decision,
)


def test_coerce_decision_cap_refuses_bool() -> None:
    """True→1 must not invent a one-row FinRobot/JEV advisory ring."""
    assert _coerce_decision_cap(True) == DECISION_CAP
    assert _coerce_decision_cap(False) == DECISION_CAP
    assert _coerce_decision_cap(None) == DECISION_CAP
    assert _coerce_decision_cap(5) == 5
    assert _coerce_decision_cap(0) == 0


def test_coerce_clip_chars_refuses_bool() -> None:
    """True→1 must not invent a one-char reason/model; False must not wipe."""
    assert _coerce_clip_chars(True, _DEFAULT_REASON_CHARS) == _DEFAULT_REASON_CHARS
    assert _coerce_clip_chars(False, _DEFAULT_MODEL_CHARS) == _DEFAULT_MODEL_CHARS
    assert _coerce_clip_chars(0, _DEFAULT_REASON_CHARS) == _DEFAULT_REASON_CHARS
    assert _coerce_clip_chars(None, _DEFAULT_MODEL_CHARS) == _DEFAULT_MODEL_CHARS
    assert _coerce_clip_chars(40, _DEFAULT_REASON_CHARS) == 40


def test_clip_refuses_bool_char_ceiling() -> None:
    """True→1 must not invent ``o…``; False must not wipe via s[:-1]."""
    note = "provider_error:Timeout"
    assert _clip(note, True, default=_DEFAULT_REASON_CHARS) == note
    assert _clip(note, False, default=_DEFAULT_REASON_CHARS) == note
    assert _clip(note, 0, default=_DEFAULT_REASON_CHARS) == note
    assert _clip(note, 8, default=_DEFAULT_REASON_CHARS) == "provide…"


def test_record_laya_decision_refuses_bool_cap(tmp_path: Path) -> None:
    """True→1 must not shrink the advisory ring to a single row."""
    base = {
        "ok": True,
        "fail_open": False,
        "reason": "ok",
        "entry": "hold",
        "edge_score": 1.0,
        "fee_churn": 0.2,
        "model": "systemone",
    }
    for i in range(5):
        record_laya_decision(tmp_path, base, symbol=f"T{i}", cap=True)
    # Without refuse, int(True)→1 would keep only the newest event.
    assert len(load_laya_decisions(tmp_path)) == 5

    for i in range(3):
        record_laya_decision(tmp_path, base, symbol=f"F{i}", cap=False)
    # False→0 via int() then max(1,0)→1 would also invent a 1-row ring.
    assert len(load_laya_decisions(tmp_path)) == 8

    for i, letter in enumerate("abc"):
        record_laya_decision(tmp_path, base, symbol=letter, cap=2)
    assert len(load_laya_decisions(tmp_path)) == 2


def test_record_laya_decision_refuses_bool_clip_ceilings(tmp_path: Path) -> None:
    """True→1 must not invent a one-char Ops reason/model strip."""
    long_reason = "provider_error:Timeout while calling systemone upstream"
    long_model = "gemma4:latest-via-tunnel"
    record_laya_decision(
        tmp_path,
        {
            "ok": False,
            "fail_open": True,
            "reason": long_reason,
            "entry": None,
            "model": long_model,
        },
        symbol="MSFT",
        reason_n=True,
        model_n=True,
    )
    row = load_laya_decisions(tmp_path)[-1]
    assert row["reason"] == long_reason
    assert row["model"] == long_model
    assert "…" not in row["reason"]
    assert "…" not in row["model"]

    record_laya_decision(
        tmp_path,
        {
            "ok": False,
            "fail_open": True,
            "reason": long_reason,
            "entry": None,
            "model": long_model,
        },
        symbol="AAPL",
        reason_n=12,
        model_n=8,
    )
    clipped = load_laya_decisions(tmp_path)[-1]
    assert clipped["reason"] == "provider_er…"
    assert clipped["model"] == "gemma4:…"
