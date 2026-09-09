"""Anti flip-flop rebuy cooldown glance (display only)."""

from __future__ import annotations

import json

from openbb_backend.charts import load_chart_payload
from openbb_backend.desk import build_rebuy_cooldown_glance


def test_rebuy_cooldown_glance_off() -> None:
    g = build_rebuy_cooldown_glance({}, cooldown_seconds=0)
    assert g["ready"] is True
    assert g["tone"] == "off"
    assert "off" in g["line"]


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


def test_rebuy_cooldown_glance_ignores_expired() -> None:
    now = 1_000_000.0
    g = build_rebuy_cooldown_glance(
        {"OLD": now - 200_000.0, "NEW": now - 100.0},
        cooldown_seconds=86400.0,
        now=now,
    )
    assert g["cooling"] == 1
    assert g["symbols"] == ["NEW"]


def test_rebuy_cooldown_glance_in_chart_payload(tmp_path) -> None:
    (tmp_path / "exit_times.json").write_text(
        json.dumps({"SCHW": 1.0}), encoding="utf-8"
    )
    payload = load_chart_payload(tmp_path)
    g = payload["rebuy_cooldown_glance"]
    assert g["ready"] is True
    assert "rebuy" in g["line"].lower() or "cooling" in g["line"] or "clear" in g["line"]
