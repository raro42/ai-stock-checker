"""Min-hold lock glance + holding annotation (display only)."""

from __future__ import annotations

from openbb_backend.desk import (
    MIN_HOLD_LOCK_LINE_CHARS,
    _clip_min_hold_lock_line,
    _coerce_min_hold_lock_line_chars,
    _cooldown_expiring_soon,
    _fmt_cooldown_left,
    _fmt_hold,
    apply_min_hold_lock_fields,
    build_min_hold_lock_glance,
)


def test_min_hold_lock_glance_empty() -> None:
    assert build_min_hold_lock_glance(None)["ready"] is False
    assert build_min_hold_lock_glance([])["ready"] is False


def test_min_hold_lock_glance_all_ghost_no_entry() -> None:
    """mphinance order-lifecycle UNKNOWN — open lots without entry stamp speak."""
    g = build_min_hold_lock_glance([{"symbol": "AAPL"}, {"symbol": "MSFT"}])
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["ghost"] == 2
    assert g["timed"] == 0
    assert "2 no entry" in g["line"]
    assert "hold age unknown" in g["line"]


def test_min_hold_lock_glance_all_unlocked() -> None:
    g = build_min_hold_lock_glance(
        [
            {"symbol": "AAPL", "held_seconds": 90_000},
            {"symbol": "MSFT", "held_seconds": 100_000},
        ],
        min_hold_hours=24,
    )
    assert g["ready"] is True
    assert g["tone"] == "quiet"
    assert g["locked"] == 0
    assert g["timed"] == 2
    assert g["ghost"] == 0
    assert "all 2 past min-hold" in g["line"]
    assert "rotate/trim OK" in g["line"]


def test_min_hold_lock_glance_past_plus_ghost() -> None:
    """Past-unlock strip must not claim rotate/trim OK when ghosts remain."""
    g = build_min_hold_lock_glance(
        [
            {"symbol": "AAPL", "held_seconds": 90_000},
            {"symbol": "MSFT"},  # no entry
        ],
        min_hold_hours=24,
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["ghost"] == 1
    assert g["timed"] == 1
    assert "1 no entry" in g["line"]
    assert "rotate/trim OK" not in g["line"]


def test_min_hold_lock_glance_partial_lock() -> None:
    g = build_min_hold_lock_glance(
        [
            {"symbol": "AAPL", "held_seconds": 3_600},
            {"symbol": "MSFT", "held_seconds": 100_000},
            {"symbol": "BTC-USD", "held_seconds": 7_200},
        ],
        min_hold_hours=24,
    )
    assert g["ready"] is True
    assert g["tone"] == "flat"
    assert g["locked"] == 2
    assert g["timed"] == 3
    assert g["earliest_symbol"] == "BTC-USD"
    assert "2/3 in min-hold lock" in g["line"]
    assert "BTC-USD" in g["line"]


def test_min_hold_lock_glance_lock_plus_ghost() -> None:
    g = build_min_hold_lock_glance(
        [
            {"symbol": "AAPL", "held_seconds": 3_600},
            {"symbol": "GHOST"},
        ],
        min_hold_hours=24,
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["ghost"] == 1
    assert g["locked"] == 1
    assert "1 no entry" in g["line"]


def test_min_hold_lock_glance_all_locked() -> None:
    g = build_min_hold_lock_glance(
        [{"symbol": "AAPL", "held_seconds": 600}],
        min_hold_hours=24,
    )
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["locked"] == 1
    assert g["earliest_symbol"] == "AAPL"
    assert g["expiring_soon"] is False


def test_min_hold_lock_glance_expiring_soon() -> None:
    """tradermonty #398 — warn before earliest lot unlocks."""
    # 24h hold; held 23h 50m → ~10m left
    g = build_min_hold_lock_glance(
        [{"symbol": "AAPL", "held_seconds": 24 * 3600 - 600}],
        min_hold_hours=24,
    )
    assert g["ready"] is True
    assert g["locked"] == 1
    assert g["expiring_soon"] is True
    assert g["tone"] == "expiring"
    assert "unlocks soon" in g["line"]


def test_apply_min_hold_lock_fields_locked() -> None:
    row = {"symbol": "AAPL", "held_seconds": 3600.0}
    out = apply_min_hold_lock_fields(row, 24 * 3600)
    assert out["past_min_hold"] is False
    assert out["min_hold_left_seconds"] == 23 * 3600
    assert out["min_hold_note"].startswith("unlock")


def test_apply_min_hold_lock_fields_past() -> None:
    row = {"symbol": "AAPL", "held_seconds": 100_000.0}
    out = apply_min_hold_lock_fields(row, 24 * 3600)
    assert out["past_min_hold"] is True
    assert out["min_hold_left_seconds"] == 0.0
    assert out["min_hold_note"] == "past min-hold"
    assert out["min_hold_left"] == ""


def test_apply_min_hold_lock_fields_missing_entry() -> None:
    row = {"symbol": "AAPL", "held_seconds": None}
    out = apply_min_hold_lock_fields(row, 24 * 3600)
    assert out["past_min_hold"] is False
    assert out["min_hold_note"] == "no entry"


def test_min_hold_refuses_bool_hours() -> None:
    """tradermonty #700/#655: True→1h must not invent unlock window."""
    g = build_min_hold_lock_glance(
        [{"symbol": "AAPL", "held_seconds": 3_600}],
        min_hold_hours=True,  # type: ignore[arg-type]
    )
    # Falls back to 0 → no lock window spoken as 0h (not invent 1h).
    assert g["min_hold_hours"] == 0.0
    row = apply_min_hold_lock_fields(
        {"symbol": "AAPL", "held_seconds": 3_600.0},
        True,  # type: ignore[arg-type]
    )
    # Bool lock seconds → 0 → past unlock (fail-open display; not invent 1s).
    assert row["past_min_hold"] is True
    assert row["min_hold_note"] == "past min-hold"


def test_cooldown_expiry_refuses_bool() -> None:
    """tradermonty #700/#655: True→1s left / True→1s warn must not invent soon."""
    assert _cooldown_expiring_soon(True, warn_seconds=900) is False  # type: ignore[arg-type]
    assert _cooldown_expiring_soon(100, warn_seconds=True) is False  # type: ignore[arg-type]
    assert _cooldown_expiring_soon(False, warn_seconds=900) is False  # type: ignore[arg-type]
    assert _cooldown_expiring_soon(600, warn_seconds=900) is True
    assert _fmt_cooldown_left(True) == "—"  # type: ignore[arg-type]
    assert _fmt_hold(True) == "—"  # type: ignore[arg-type]


def test_min_hold_lock_glance_refuses_bool_expiry_warn() -> None:
    """Bool expiry warn falls back to 15m default — not invent True→1s window."""
    # 24h hold; held 23h 50m → ~10m left (inside default 15m warn).
    g = build_min_hold_lock_glance(
        [{"symbol": "AAPL", "held_seconds": 24 * 3600 - 600}],
        min_hold_hours=24,
        expiry_warn_seconds=True,  # type: ignore[arg-type]
    )
    assert g["ready"] is True
    assert g["expiring_soon"] is True
    assert g["tone"] == "expiring"
    assert "unlocks soon" in g["line"]

    g2 = build_min_hold_lock_glance(
        [{"symbol": "AAPL", "held_seconds": 24 * 3600 - 600}],
        min_hold_hours=24,
        expiry_warn_seconds=False,  # type: ignore[arg-type]
    )
    assert g2["expiring_soon"] is True  # default 15m, not False→0 off


def test_clip_min_hold_lock_line_refuses_bool_ceiling() -> None:
    """True→1 must not invent line[:True]; False must not wipe via [:False]."""
    long = "x" * 120
    assert len(long) > MIN_HOLD_LOCK_LINE_CHARS
    default = _clip_min_hold_lock_line(long)
    assert len(default) == MIN_HOLD_LOCK_LINE_CHARS
    assert default.endswith("…")
    assert default == long[: MIN_HOLD_LOCK_LINE_CHARS - 1] + "…"
    assert _clip_min_hold_lock_line(long, True) == default
    assert _clip_min_hold_lock_line(long, False) == default
    assert _clip_min_hold_lock_line(long, 0) == default
    assert _coerce_min_hold_lock_line_chars(True) == MIN_HOLD_LOCK_LINE_CHARS
    assert _coerce_min_hold_lock_line_chars(False) == MIN_HOLD_LOCK_LINE_CHARS
    thin = _clip_min_hold_lock_line(long, 12)
    assert thin == long[:11] + "…"
    assert len(thin) == 12


def test_min_hold_lock_glance_refuses_bool_line_ceiling() -> None:
    """line_n=True must not invent a one-char strip; False must not wipe."""
    holdings = [
        {"symbol": "VERYLONGSYMBOLNAME", "held_seconds": 600},
        {"symbol": "ANOTHERLONGNAME", "held_seconds": 1_200},
        {"symbol": "GHOSTLOT"},
    ]
    g = build_min_hold_lock_glance(holdings, min_hold_hours=24)
    g_bool = build_min_hold_lock_glance(holdings, min_hold_hours=24, line_n=True)
    g_false = build_min_hold_lock_glance(holdings, min_hold_hours=24, line_n=False)
    assert g_bool["line"] == g["line"]
    assert g_false["line"] == g["line"]
    assert len(g["line"]) <= MIN_HOLD_LOCK_LINE_CHARS
    assert "min-hold lock" in g["line"]
    thin = build_min_hold_lock_glance(holdings, min_hold_hours=24, line_n=12)
    assert len(thin["line"]) == 12
    assert thin["line"].endswith("…")
