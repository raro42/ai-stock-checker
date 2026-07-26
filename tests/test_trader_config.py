"""Offline tests for Ops trader_config persistence."""

import json
from pathlib import Path

from stock_checker.trader_config import (
    load_trader_config,
    normalize_config,
    save_trader_config,
)


def test_normalize_rejects_coder_model_and_bad_mode():
    base = {
        "ai_mode": "off",
        "ai_model": "gemma4:latest",
        "ai_multi_role": True,
        "regime_gate": True,
    }
    out = normalize_config(
        {"ai_mode": "nope", "ai_model": "qwen2.5-coder:latest", "regime_gate": "0"},
        base=base,
    )
    assert out["ai_mode"] == "off"
    assert out["ai_model"] == "gemma4:latest"
    assert out["regime_gate"] is False


def test_save_load_roundtrip(tmp_path: Path):
    saved = save_trader_config(
        tmp_path,
        {
            "ai_mode": "validate",
            "ai_model": "gemma4:latest",
            "ai_multi_role": False,
            "regime_gate": True,
        },
    )
    assert saved["ai_mode"] == "validate"
    assert (tmp_path / "trader_config.json").is_file()
    loaded = load_trader_config(tmp_path)
    assert loaded["ai_mode"] == "validate"
    assert loaded["ai_multi_role"] is False
    raw = json.loads((tmp_path / "trader_config.json").read_text())
    assert "api_key" not in raw
