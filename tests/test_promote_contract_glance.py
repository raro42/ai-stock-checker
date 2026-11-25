"""Promote entry-veto contract glance (A18; display only)."""

from __future__ import annotations

from openbb_backend.charts import load_chart_payload
from openbb_backend.desk import (
    PROMOTE_CONTRACT_LINE_CHARS,
    _clip_promote_contract_line,
    _coerce_promote_contract_line_chars,
    build_promote_contract_glance,
    load_desk_snapshot,
)


def test_coerce_promote_contract_line_chars_refuses_bool() -> None:
    """True→1 must not invent a one-char promote strip; False must not wipe."""
    assert (
        _coerce_promote_contract_line_chars(True) == PROMOTE_CONTRACT_LINE_CHARS
    )
    assert (
        _coerce_promote_contract_line_chars(False) == PROMOTE_CONTRACT_LINE_CHARS
    )
    assert (
        _coerce_promote_contract_line_chars(0) == PROMOTE_CONTRACT_LINE_CHARS
    )
    assert (
        _coerce_promote_contract_line_chars(None) == PROMOTE_CONTRACT_LINE_CHARS
    )
    assert _coerce_promote_contract_line_chars(40) == 40


def test_clip_promote_contract_line_refuses_bool_ceiling() -> None:
    """True→1 must not invent line[:True]; False must not wipe via [:False]."""
    long = "x" * 120
    assert len(long) > PROMOTE_CONTRACT_LINE_CHARS
    default = _clip_promote_contract_line(long)
    assert len(default) == PROMOTE_CONTRACT_LINE_CHARS
    assert default.endswith("…")
    assert default == long[: PROMOTE_CONTRACT_LINE_CHARS - 1] + "…"
    assert _clip_promote_contract_line(long, True) == default
    assert _clip_promote_contract_line(long, False) == default
    assert _clip_promote_contract_line(long, 0) == default
    thin = _clip_promote_contract_line(long, 12)
    assert thin == long[:11] + "…"
    assert len(thin) == 12


def test_promote_contract_glance_refuses_bool_line_ceiling() -> None:
    """line_n=True must not invent a one-char strip; False must not wipe."""
    rt = {"promote_experiment_strategy": True}
    g = build_promote_contract_glance(rt)
    g_bool = build_promote_contract_glance(rt, line_n=True)
    g_false = build_promote_contract_glance(rt, line_n=False)
    assert g_bool["line"] == g["line"]
    assert g_false["line"] == g["line"]
    assert len(g["line"]) <= PROMOTE_CONTRACT_LINE_CHARS
    g_short = build_promote_contract_glance(rt, line_n=12)
    assert len(g_short["line"]) == 12
    assert g_short["line"].endswith("…")


def test_promote_contract_glance_off() -> None:
    g = build_promote_contract_glance({"promote_experiment_strategy": False})
    assert g["ready"] is True
    assert g["tone"] == "off"
    assert g["promote_on"] is False
    assert g["entry_veto_only"] is True
    assert g["exits_via_champion"] is False
    assert "entry veto only" in g["line"]
    assert "exit_policy" in g["line"]
    assert g["source"] == "experiment_strategy"


def test_promote_contract_glance_on() -> None:
    g = build_promote_contract_glance({"promote_experiment_strategy": True})
    assert g["ready"] is True
    assert g["tone"] == "on"
    assert g["promote_on"] is True
    assert g["entry_veto_only"] is True
    assert g["exits_via_champion"] is False
    assert "SELL ≠ buy" in g["line"]
    assert "exit_policy" in g["line"]


def test_promote_contract_glance_empty_runtime() -> None:
    g = build_promote_contract_glance(None)
    assert g["ready"] is False
    assert g["line"] == ""


def test_promote_contract_glance_in_snapshot(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    snap = load_desk_snapshot(tmp_path, live_marks=False)
    g = snap["promote_contract_glance"]
    assert g["ready"] is True
    assert g["entry_veto_only"] is True
    assert "entry veto" in g["line"]


def test_promote_contract_glance_in_chart_payload(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    g = load_chart_payload(tmp_path)["promote_contract_glance"]
    assert g["ready"] is True
    assert g["exits_via_champion"] is False
    assert "exit_policy" in g["line"]
