"""Anti flip-flop rebuy cooldown glance (display only)."""

from __future__ import annotations

import json

from openbb_backend.charts import load_chart_payload
from openbb_backend.desk import (
    REBUY_COOLDOWN_GLANCE_BIT_CAP,
    REBUY_COOLDOWN_GLANCE_SYMBOLS_CAP,
    _coerce_rebuy_cooldown_name_cap,
    build_rebuy_cooldown_glance,
)


def test_rebuy_cooldown_glance_off() -> None:
    g = build_rebuy_cooldown_glance({}, cooldown_seconds=0)
    assert g["ready"] is True
    assert g["tone"] == "off"
    assert "off" in g["line"]


def test_rebuy_cooldown_glance_refuses_bool_knobs() -> None:
    """tradermonty #700/#655: True→1s lock / False→off / True→1970 exit invent."""
    now = 1_000_000.0
    # Bool cooldown → empty (not invent 1s lock or off).
    assert build_rebuy_cooldown_glance({}, cooldown_seconds=True)["ready"] is False  # type: ignore[arg-type]
    assert build_rebuy_cooldown_glance({}, cooldown_seconds=False)["ready"] is False  # type: ignore[arg-type]
    # Bool exit stamp → skip (not invent ~1970 cooling when now is also damaged).
    g = build_rebuy_cooldown_glance(
        {"SCHW": True},  # type: ignore[dict-item]
        cooldown_seconds=86400.0,
        now=True,  # type: ignore[arg-type]
    )
    assert g["ready"] is True
    assert g["cooling"] == 0
    assert g["tone"] == "clear"
    # Bool now falls back to wall clock — synthetic 1970-ish exit stays expired.
    g2 = build_rebuy_cooldown_glance(
        {"SCHW": now - 3600.0},
        cooldown_seconds=86400.0,
        now=True,  # type: ignore[arg-type]
    )
    assert g2["ready"] is True
    assert g2["cooling"] == 0


def test_rebuy_cooldown_glance_clear() -> None:
    g = build_rebuy_cooldown_glance({}, cooldown_seconds=86400, now=1_000_000.0)
    assert g["ready"] is True
    assert g["tone"] == "clear"
    assert g["cooling"] == 0
    assert "clear" in g["line"]
    assert "24h" in g["line"]


def test_rebuy_cooldown_glance_cooling() -> None:
    now = 1_000_000.0
    g = build_rebuy_cooldown_glance(
        {"schw": now - 3600.0},
        cooldown_seconds=86400.0,
        now=now,
    )
    assert g["ready"] is True
    assert g["tone"] == "cooling"
    assert g["cooling"] == 1
    assert "SCHW" in g["line"]
    assert "1 cooling" in g["line"]


def test_rebuy_cooldown_glance_flip_flop_pressure() -> None:
    now = 1_000_000.0
    exits = {
        "AAPL": now - 1000.0,
        "MSFT": now - 2000.0,
        "SCHW": now - 3000.0,
    }
    g = build_rebuy_cooldown_glance(exits, cooldown_seconds=86400.0, now=now)
    assert g["ready"] is True
    assert g["tone"] == "warn"
    assert g["cooling"] == 3
    assert "flip-flop pressure" in g["line"]


def test_rebuy_cooldown_glance_refuses_bool_name_cap() -> None:
    """True→1 must not invent a one-name flip-flop strip via cooling[:True]."""
    assert (
        _coerce_rebuy_cooldown_name_cap(True) == REBUY_COOLDOWN_GLANCE_BIT_CAP
    )
    assert (
        _coerce_rebuy_cooldown_name_cap(False) == REBUY_COOLDOWN_GLANCE_BIT_CAP
    )
    assert _coerce_rebuy_cooldown_name_cap(0) == REBUY_COOLDOWN_GLANCE_BIT_CAP
    assert _coerce_rebuy_cooldown_name_cap(None) == REBUY_COOLDOWN_GLANCE_BIT_CAP
    assert _coerce_rebuy_cooldown_name_cap(2) == 2
    assert (
        _coerce_rebuy_cooldown_name_cap(
            True, default=REBUY_COOLDOWN_GLANCE_SYMBOLS_CAP
        )
        == REBUY_COOLDOWN_GLANCE_SYMBOLS_CAP
    )

    now = 1_000_000.0
    exits = {f"S{i}": now - float(1000 * (i + 1)) for i in range(5)}
    g_true = build_rebuy_cooldown_glance(
        exits, cooldown_seconds=86400.0, now=now, bit_n=True, symbols_n=True
    )
    assert g_true["ready"] is True
    assert g_true["cooling"] == 5
    assert len(g_true["symbols"]) == REBUY_COOLDOWN_GLANCE_SYMBOLS_CAP
    # Soonest clear first → highest age first → S4, S3, S2 on the bit strip.
    assert "S4" in g_true["line"]
    assert "S3" in g_true["line"]
    assert "S2" in g_true["line"]
    assert "S1" not in g_true["line"]
    assert "S0" not in g_true["line"]
    assert "flip-flop pressure" in g_true["line"]
    # Without refuse, bit_n=True → cooling[:1] only (one name on the strip).
    assert g_true["line"].count("S") == REBUY_COOLDOWN_GLANCE_BIT_CAP

    g_false = build_rebuy_cooldown_glance(
        exits, cooldown_seconds=86400.0, now=now, bit_n=False, symbols_n=False
    )
    assert len(g_false["symbols"]) == REBUY_COOLDOWN_GLANCE_SYMBOLS_CAP
    assert "S4" in g_false["line"]
    assert "S2" in g_false["line"]
    assert g_false["line"].count("S") == REBUY_COOLDOWN_GLANCE_BIT_CAP

    g_short = build_rebuy_cooldown_glance(
        exits, cooldown_seconds=86400.0, now=now, bit_n=2, symbols_n=2
    )
    assert g_short["symbols"] == ["S4", "S3"]
    assert "S4" in g_short["line"]
    assert "S3" in g_short["line"]
    assert "S2" not in g_short["line"]
    assert g_short["line"].count("S") == 2
    # Absolute pressure floor still fires at 5 cooling even when bit_n=2.
    assert "flip-flop pressure" in g_short["line"]


def test_rebuy_cooldown_glance_ignores_expired() -> None:
    now = 1_000_000.0
    g = build_rebuy_cooldown_glance(
        {"OLD": now - 200_000.0, "NEW": now - 100.0},
        cooldown_seconds=86400.0,
        now=now,
    )
    assert g["cooling"] == 1
    assert g["symbols"] == ["NEW"]
    assert g["expiring_soon"] is False


def test_rebuy_cooldown_glance_expiring_soon() -> None:
    """tradermonty #398 — warn before lock clears (within one scan)."""
    now = 1_000_000.0
    # 24h cooldown; exited ~23h 50m ago → ~10m left
    g = build_rebuy_cooldown_glance(
        {"SCHW": now - (86400.0 - 600.0)},
        cooldown_seconds=86400.0,
        now=now,
    )
    assert g["ready"] is True
    assert g["cooling"] == 1
    assert g["expiring_soon"] is True
    assert g["tone"] == "expiring"
    assert "unlocks soon" in g["line"]


def test_rebuy_cooldown_glance_in_chart_payload(tmp_path) -> None:
    (tmp_path / "exit_times.json").write_text(
        json.dumps({"SCHW": 1.0}), encoding="utf-8"
    )
    payload = load_chart_payload(tmp_path)
    g = payload["rebuy_cooldown_glance"]
    assert g["ready"] is True
    assert "rebuy" in g["line"].lower() or "cooling" in g["line"] or "clear" in g["line"]
