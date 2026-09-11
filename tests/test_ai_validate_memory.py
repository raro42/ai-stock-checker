"""Offline tests for AI validate debate memory (FinRobot Ideas transcript)."""

from __future__ import annotations

from pathlib import Path

from openbb_backend.desk import load_desk_snapshot
from stock_checker.ai_multi_role import consensus_from_multi_role
from stock_checker.ai_validate_memory import (
    load_ai_validate_memory,
    recent_ai_debates,
    record_ai_validate,
)


def test_record_and_recent_ai_debates(tmp_path: Path) -> None:
    ai = consensus_from_multi_role(
        {
            "bull": {"bias": "BUY", "note": "momentum"},
            "bear": {"bias": "HOLD", "note": "extended"},
            "risk": {"ok": True, "note": "liquid"},
            "action": "BUY",
            "confidence": "MEDIUM",
            "score": 35,
            "reasoning": "bull edged",
        },
        "AAPL",
    )
    record_ai_validate(tmp_path, ai, symbol="AAPL", kept=True)
    record_ai_validate(
        tmp_path,
        {
            "action": "SELL",
            "confidence": "HIGH",
            "score": -40,
            "reasons": ["weak tape"],
            "parse_mode": "single",
        },
        symbol="XYZ",
        kept=False,
    )

    events = load_ai_validate_memory(tmp_path)
    assert len(events) == 2
    assert events[0]["symbol"] == "AAPL"
    assert events[0]["bull_bias"] == "BUY"
    assert "momentum" in events[0]["bull_note"]
    assert events[0]["kept"] is True
    assert isinstance(events[0].get("reasons"), list)
    assert events[1]["symbol"] == "XYZ"
    assert events[1]["kept"] is False
    assert events[1]["reasons"] == ["weak tape"]

    recent = recent_ai_debates(tmp_path, limit=1)
    assert len(recent) == 1
    assert recent[0]["symbol"] == "XYZ"


def test_ai_validate_memory_cap(tmp_path: Path) -> None:
    for i in range(5):
        record_ai_validate(
            tmp_path,
            {"action": "HOLD", "confidence": "LOW", "score": 0, "reasons": ["x"]},
            symbol=f"T{i}",
            cap=3,
        )
    assert len(load_ai_validate_memory(tmp_path)) == 3
    assert load_ai_validate_memory(tmp_path)[-1]["symbol"] == "T4"


def test_ai_debates_in_desk_snapshot(tmp_path: Path) -> None:
    record_ai_validate(
        tmp_path,
        consensus_from_multi_role(
            {
                "bull": {"bias": "BUY", "note": "up"},
                "bear": {"bias": "SELL", "note": "down"},
                "risk": {"ok": True, "note": "ok"},
                "action": "BUY",
                "confidence": "HIGH",
                "score": 40,
                "reasoning": "conflict",
            },
            "NVDA",
        ),
        kept=False,
    )
    snap = load_desk_snapshot(tmp_path)
    assert "ai_debates" in snap
    assert snap["ai_debates"]
    row = snap["ai_debates"][0]
    assert row["symbol"] == "NVDA"
    assert row["action"] == "HOLD"  # disagreement gate
    assert row["multi_role_gated"] is True


def test_ideas_template_has_ai_debates_section() -> None:
    text = Path("openbb_backend/templates/desk_ideas.html").read_text()
    assert "ai_debates" in text
    assert 'id="debate-h"' in text
    assert 'class="ai-debate"' in text
    assert "debate-json" in text
    assert "tojson" in text
