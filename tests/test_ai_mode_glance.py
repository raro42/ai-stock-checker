"""AI mode + multi-role policy glance (display only)."""

from __future__ import annotations

from openbb_backend.charts import load_chart_payload
from openbb_backend.desk import (
    AI_MODE_GLANCE_MODEL_MAX,
    AI_MODE_LINE_CHARS,
    _clip_ai_mode_glance_model,
    _clip_ai_mode_line,
    _coerce_ai_mode_line_chars,
    build_ai_mode_glance,
    load_desk_snapshot,
)


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


def test_ai_mode_glance_refuses_bool_model_ceiling() -> None:
    """True→1 must not invent a one-char model strip via model[:True]."""
    long = "org/ai_mode_model_" + ("m" * 40)
    basename = long.split("/")[-1]
    clipped = basename[: AI_MODE_GLANCE_MODEL_MAX - 1] + "…"
    assert _clip_ai_mode_glance_model(long, True) == clipped
    assert _clip_ai_mode_glance_model(long, False) == clipped
    assert clipped != "a…"
    assert _clip_ai_mode_glance_model(long, 8) == basename[:7] + "…"

    runtime = {
        "ai_mode": "validate",
        "ai_model": long,
        "ai_multi_role": True,
    }
    g_true = build_ai_mode_glance(runtime, model_n=True)
    assert g_true["ready"] is True
    assert g_true["model_short"] == clipped
    assert clipped in g_true["line"]
    g_false = build_ai_mode_glance(runtime, model_n=False)
    assert g_false["model_short"] == clipped
    g_short = build_ai_mode_glance(runtime, model_n=8)
    assert g_short["model_short"] == basename[:7] + "…"
    assert len(g_short["model_short"]) == 8


def test_coerce_ai_mode_line_chars_refuses_bool() -> None:
    """True→1 must not invent a one-char AI-mode strip; False must not wipe."""
    assert _coerce_ai_mode_line_chars(True) == AI_MODE_LINE_CHARS
    assert _coerce_ai_mode_line_chars(False) == AI_MODE_LINE_CHARS
    assert _coerce_ai_mode_line_chars(0) == AI_MODE_LINE_CHARS
    assert _coerce_ai_mode_line_chars(None) == AI_MODE_LINE_CHARS
    assert _coerce_ai_mode_line_chars(40) == 40


def test_clip_ai_mode_line_refuses_bool_ceiling() -> None:
    """True→1 must not invent line[:True]; False must not wipe via [:False]."""
    long = "x" * 120
    assert len(long) > AI_MODE_LINE_CHARS
    default = _clip_ai_mode_line(long)
    assert len(default) == AI_MODE_LINE_CHARS
    assert default.endswith("…")
    assert default == long[: AI_MODE_LINE_CHARS - 1] + "…"
    assert _clip_ai_mode_line(long, True) == default
    assert _clip_ai_mode_line(long, False) == default
    assert _clip_ai_mode_line(long, 0) == default
    thin = _clip_ai_mode_line(long, 12)
    assert thin == long[:11] + "…"
    assert len(thin) == 12


def test_ai_mode_glance_refuses_bool_line_ceiling() -> None:
    """line_n=True must not invent a one-char strip; False must not wipe."""
    runtime = {
        "ai_mode": "validate",
        "ai_model": "gemma4:latest",
        "ai_multi_role": True,
    }
    g = build_ai_mode_glance(runtime)
    g_bool = build_ai_mode_glance(runtime, line_n=True)
    g_false = build_ai_mode_glance(runtime, line_n=False)
    assert g_bool["line"] == g["line"]
    assert g_false["line"] == g["line"]
    assert len(g["line"]) <= AI_MODE_LINE_CHARS
    g_short = build_ai_mode_glance(runtime, line_n=12)
    assert len(g_short["line"]) == 12
    assert g_short["line"].endswith("…")


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


def test_ai_mode_glance_in_chart_payload(tmp_path) -> None:
    (tmp_path / "portfolio.json").write_text(
        '{"cash": 100000, "initial_cash": 100000, "holdings": {}, '
        '"total_fees_paid": 0}',
        encoding="utf-8",
    )
    (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")
    g = load_chart_payload(tmp_path)["ai_mode_glance"]
    assert g["ready"] is True
    assert g["ai_mode"] in {"off", "validate", "full"}
    assert "multi-role" in g["line"]
