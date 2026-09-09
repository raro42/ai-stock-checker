"""AI mode + multi-role policy glance (display only)."""

from __future__ import annotations

from openbb_backend.desk import build_ai_mode_glance, load_desk_snapshot


def test_ai_mode_glance_empty_input() -> None:
    assert build_ai_mode_glance(None)["ready"] is False
    assert build_ai_mode_glance("x")["ready"] is False  # type: ignore[arg-type]


def test_ai_mode_glance_off() -> None:
    g = build_ai_mode_glance(
        {"ai_mode": "off", "ai_model": "gemma4:latest", "ai_multi_role": True}
    )
    assert g["ready"] is True
    assert g["tone"] == "off"
    assert g["ai_mode"] == "off"
    assert "rules only" in g["line"]
    assert "multi-role on" in g["line"]


def test_ai_mode_glance_validate() -> None:
    g = build_ai_mode_glance(
        {
            "ai_mode": "validate",
            "ai_model": "qwen3.5:9b",
            "ai_multi_role": False,
        }
    )
    assert g["ready"] is True
    assert g["tone"] == "validate"
    assert "validate" in g["line"]
    assert "qwen3.5:9b" in g["line"]
    assert "multi-role off" in g["line"]


def test_ai_mode_glance_full() -> None:
    g = build_ai_mode_glance(
        {"ai_mode": "full", "ai_model": "gemma4:latest", "ai_multi_role": True}
    )
    assert g["ready"] is True
    assert g["tone"] == "full"
    assert "full" in g["line"]
    assert "gemma4:latest" in g["line"]
    assert g["ai_multi_role"] is True


def test_ai_mode_glance_in_snapshot(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    snap = load_desk_snapshot(tmp_path, live_marks=False)
    g = snap["ai_mode_glance"]
    assert g["ready"] is True
    assert g["ai_mode"] in {"off", "validate", "full"}
    assert "multi-role" in g["line"]
