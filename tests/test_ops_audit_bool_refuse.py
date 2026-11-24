"""Ops audit refuse window / retention / age bands must refuse bool invents."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from stock_checker.ops_audit import (
    OPS_ACTIONS_CAP,
    OPS_DETAIL_CHANGED_ITEMS_MAX,
    OPS_DETAIL_CHANGED_ITEM_CHARS,
    OPS_DETAIL_KEYS_MAX,
    OPS_DETAIL_OPEN_CASH_ITEMS_MAX,
    OPS_DETAIL_OPEN_CASH_ITEM_CHARS,
    OPS_DETAIL_STRING_CHARS,
    OPS_OUTCOME_AGING_HOURS,
    OPS_OUTCOME_FRESH_HOURS,
    OPS_PENDING_REFUSE_SECONDS,
    _coerce_ops_actions_cap,
    _coerce_ops_age_sec,
    _coerce_ops_detail_ceiling,
    _coerce_ops_outcome_hours,
    _coerce_ops_refuse_seconds,
    _ops_age_short,
    _ops_vs_file_age_delta_lean,
    _ops_vs_file_clash_sides_delta,
    _ops_vs_file_clash_sides_share,
    _ops_vs_file_clash_sides_share_pcts,
    _safe_detail,
    append_ops_action,
    ops_save_body_detail,
    load_ops_actions,
    ops_outcome_age_band,
    ops_pending_freshness_band,
)


def test_coerce_ops_refuse_seconds_refuses_bool() -> None:
    """True→1s must not invent a thin double-click refuse window."""
    assert (
        _coerce_ops_refuse_seconds(True) == OPS_PENDING_REFUSE_SECONDS
    )
    assert (
        _coerce_ops_refuse_seconds(False) == OPS_PENDING_REFUSE_SECONDS
    )
    assert _coerce_ops_refuse_seconds(0) == OPS_PENDING_REFUSE_SECONDS
    assert _coerce_ops_refuse_seconds(30) == 30


def test_coerce_ops_actions_cap_refuses_bool() -> None:
    """True→1 must not invent a one-row Ops audit ring."""
    assert _coerce_ops_actions_cap(True) == OPS_ACTIONS_CAP
    assert _coerce_ops_actions_cap(False) == OPS_ACTIONS_CAP
    assert _coerce_ops_actions_cap(5) == 5
    assert _coerce_ops_actions_cap(0) == 0


def test_coerce_ops_outcome_hours_refuses_bool() -> None:
    """True→1h must not invent a thin audit age band."""
    assert (
        _coerce_ops_outcome_hours(True, OPS_OUTCOME_FRESH_HOURS)
        == OPS_OUTCOME_FRESH_HOURS
    )
    assert (
        _coerce_ops_outcome_hours(False, OPS_OUTCOME_AGING_HOURS)
        == OPS_OUTCOME_AGING_HOURS
    )
    assert _coerce_ops_outcome_hours(-3.0, 24.0) == 24.0
    assert _coerce_ops_outcome_hours(6.0, 24.0) == 6.0


def test_ops_pending_freshness_refuses_bool_window() -> None:
    """Bool refuse_seconds falls back to 120s (not True→1s)."""
    now = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)
    stamp = (now - timedelta(seconds=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    row = {"outcome": "requested", "at": stamp}
    # Without refuse, True→1 would mark 30s as stale.
    assert (
        ops_pending_freshness_band(row, now=now, refuse_seconds=True) == "fresh"
    )
    assert (
        ops_pending_freshness_band(row, now=now, refuse_seconds=False) == "fresh"
    )


def test_ops_outcome_age_refuses_bool_hours() -> None:
    """Bool fresh/aging knobs fall back to 24h/7d (not True→1h)."""
    now = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)
    aging = (now - timedelta(hours=48)).strftime("%Y-%m-%dT%H:%M:%SZ")
    row = {"at": aging}
    assert (
        ops_outcome_age_band(row, now=now, fresh_hours=True, aging_hours=True)
        == "aging"
    )


def test_ops_age_short_refuses_bool() -> None:
    """True→1s must not invent ``now`` / ``1s`` on Ops audit age clips."""
    assert _coerce_ops_age_sec(True) is None
    assert _coerce_ops_age_sec(False) is None
    assert _coerce_ops_age_sec(-1) is None
    assert _coerce_ops_age_sec(45) == 45.0
    assert _ops_age_short(True) == "n/a"
    assert _ops_age_short(False) == "n/a"
    assert _ops_age_short(3) == "now"
    assert _ops_age_short(45) == "45s"
    assert _ops_age_short(120) == "2m"


def test_ops_vs_file_age_helpers_refuse_bool() -> None:
    """True→1s must not invent sides Δ thin / 50-50 share from bool ages."""
    assert _ops_vs_file_clash_sides_delta(True, False) == ""
    assert _ops_vs_file_clash_sides_delta(True, 3600) == ""
    assert _ops_vs_file_clash_sides_share_pcts(True, False) is None
    assert _ops_vs_file_clash_sides_share(True, False) == ""
    assert _ops_vs_file_age_delta_lean(True, False) == "mid"
    # Real near-equal ages still speak thin Δ (|200−100|=100s → 1m).
    assert _ops_vs_file_clash_sides_delta(100.0, 200.0) == "sides Δ thin · 1m"
    pcts = _ops_vs_file_clash_sides_share_pcts(100.0, 100.0)
    assert pcts == (50, 50)


def test_coerce_ops_detail_ceiling_refuses_bool() -> None:
    """True→1 / [:True] must not invent a one-key / one-char Save Δ strip."""
    assert _coerce_ops_detail_ceiling(True, OPS_DETAIL_KEYS_MAX) == OPS_DETAIL_KEYS_MAX
    assert (
        _coerce_ops_detail_ceiling(False, OPS_DETAIL_STRING_CHARS)
        == OPS_DETAIL_STRING_CHARS
    )
    assert _coerce_ops_detail_ceiling(0, OPS_DETAIL_CHANGED_ITEM_CHARS) == (
        OPS_DETAIL_CHANGED_ITEM_CHARS
    )
    assert _coerce_ops_detail_ceiling(None, OPS_DETAIL_OPEN_CASH_ITEM_CHARS) == (
        OPS_DETAIL_OPEN_CASH_ITEM_CHARS
    )
    assert _coerce_ops_detail_ceiling(12, OPS_DETAIL_KEYS_MAX) == 12


def test_ops_save_body_detail_refuses_bool_key_strip() -> None:
    """True→1 must not invent a one-key Ops Save audit strip via body[:True]."""
    body = {f"knob_{i:02d}": i for i in range(20)}
    default = ops_save_body_detail(body)
    assert len(default) == OPS_DETAIL_CHANGED_ITEMS_MAX
    assert list(default) == sorted(body)[:OPS_DETAIL_CHANGED_ITEMS_MAX]
    # Bool ceilings fall back to the changed-items default (not True→1).
    assert ops_save_body_detail(body, True) == default
    assert ops_save_body_detail(body, False) == default
    assert ops_save_body_detail(body, 0) == default
    thin = ops_save_body_detail(body, 3)
    assert list(thin) == sorted(body)[:3]
    assert ops_save_body_detail(None) == {}
    assert ops_save_body_detail("nope") == {}  # type: ignore[arg-type]


def test_safe_detail_refuses_bool_clip_ceilings() -> None:
    """Bool ceilings fall back to defaults; False must not wipe via [:False]."""
    note = "n" * 120
    changed = [f"knob_{i}_" + ("x" * 50) for i in range(20)]
    cash = [("sleeve_" + str(i) + "_" + ("y" * 40)) for i in range(6)]
    detail = {
        "note": note,
        "changed": changed,
        "open_cash": cash,
        "ai_mode": "validate",
    }
    out = _safe_detail(
        detail,
        keys_n=True,
        changed_n=True,
        changed_chars=True,
        open_cash_n=True,
        open_cash_chars=True,
        string_chars=True,
    )
    # Without refuse, keys_n=True → items[:True] would keep only note.
    assert "changed" in out
    assert "open_cash" in out
    assert "ai_mode" in out
    assert len(out["note"]) == OPS_DETAIL_STRING_CHARS
    assert len(out["changed"]) == OPS_DETAIL_CHANGED_ITEMS_MAX
    assert all(
        len(item) == OPS_DETAIL_CHANGED_ITEM_CHARS for item in out["changed"]
    )
    assert len(out["open_cash"]) == OPS_DETAIL_OPEN_CASH_ITEMS_MAX
    assert all(
        len(item) == OPS_DETAIL_OPEN_CASH_ITEM_CHARS for item in out["open_cash"]
    )

    wiped = _safe_detail(
        detail,
        keys_n=False,
        changed_n=False,
        changed_chars=False,
        open_cash_n=False,
        open_cash_chars=False,
        string_chars=False,
    )
    assert len(wiped["note"]) == OPS_DETAIL_STRING_CHARS
    assert len(wiped["changed"]) == OPS_DETAIL_CHANGED_ITEMS_MAX
    assert len(wiped["open_cash"]) == OPS_DETAIL_OPEN_CASH_ITEMS_MAX

    tight = _safe_detail(
        detail,
        keys_n=2,
        changed_n=3,
        changed_chars=8,
        open_cash_n=2,
        open_cash_chars=5,
        string_chars=10,
    )
    assert set(tight) <= {"note", "changed"}
    assert len(tight) == 2
    assert len(tight["note"]) == 10
    assert len(tight["changed"]) == 3
    assert all(len(item) == 8 for item in tight["changed"])


def test_append_ops_action_refuses_bool_cap(tmp_path: Path) -> None:
    """True→1 must not shrink the Ops audit ring to a single row."""
    for i in range(5):
        assert append_ops_action(
            tmp_path,
            {
                "at": f"2026-11-20T12:0{i}:00Z",
                "kind": "save",
                "outcome": "accepted",
                "id": f"r{i}",
            },
            cap=True,
        )
    # Without refuse, int(True)→1 would keep only the newest event.
    assert len(load_ops_actions(tmp_path)) == 5

    for i in range(3):
        assert append_ops_action(
            tmp_path,
            {
                "at": f"2026-11-20T13:0{i}:00Z",
                "kind": "save",
                "outcome": "accepted",
                "id": f"f{i}",
            },
            cap=False,
        )
    # False→0 via int() then max(1,0)→1 would also invent a 1-row ring.
    assert len(load_ops_actions(tmp_path)) == 8

    for i, letter in enumerate("abc"):
        assert append_ops_action(
            tmp_path,
            {
                "at": f"2026-11-20T14:0{i}:00Z",
                "kind": "save",
                "outcome": "accepted",
                "id": letter,
            },
            cap=2,
        )
    assert len(load_ops_actions(tmp_path)) == 2
