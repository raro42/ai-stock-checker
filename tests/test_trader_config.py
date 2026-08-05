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
        "rs_gate": True,
        "fee_preset": "revolut_standard",
        "commission_rate": 0.0025,
        "commission_min_eur": 1.0,
    }
    out = normalize_config(
        {
            "ai_mode": "nope",
            "ai_model": "qwen2.5-coder:latest",
            "regime_gate": "0",
            "rs_gate": "0",
        },
        base=base,
    )
    assert out["ai_mode"] == "off"
    assert out["ai_model"] == "gemma4:latest"
    assert out["regime_gate"] is False
    assert out["rs_gate"] is False


def test_rs_gate_roundtrip(tmp_path: Path):
    saved = save_trader_config(tmp_path, {"rs_gate": False})
    assert saved["rs_gate"] is False
    loaded = load_trader_config(tmp_path)
    assert loaded["rs_gate"] is False
    saved2 = save_trader_config(tmp_path, {"rs_gate": True})
    assert saved2["rs_gate"] is True


def test_save_load_roundtrip(tmp_path: Path):
    saved = save_trader_config(
        tmp_path,
        {
            "ai_mode": "validate",
            "ai_model": "gemma4:latest",
            "ai_multi_role": False,
            "regime_gate": True,
            "rs_gate": False,
            "fee_preset": "revolut_ultra",
        },
    )
    assert saved["ai_mode"] == "validate"
    assert saved["fee_preset"] == "revolut_ultra"
    assert saved["rs_gate"] is False
    assert abs(saved["commission_rate"] - 0.0012) < 1e-9
    assert (tmp_path / "trader_config.json").is_file()
    loaded = load_trader_config(tmp_path)
    assert loaded["ai_mode"] == "validate"
    assert loaded["ai_multi_role"] is False
    assert loaded["fee_preset"] == "revolut_ultra"
    assert loaded["rs_gate"] is False
    raw = json.loads((tmp_path / "trader_config.json").read_text())
    assert "api_key" not in raw
    assert "rs_gate" in raw


def test_fee_preset_revolut_standard_default(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("FEE_PRESET", raising=False)
    monkeypatch.delenv("MAX_POSITIONS", raising=False)
    monkeypatch.delenv("MIN_HOLD_HOURS", raising=False)
    monkeypatch.delenv("PROMOTE_EXPERIMENT_STRATEGY", raising=False)
    monkeypatch.delenv("RS_GATE", raising=False)
    cfg = load_trader_config(tmp_path)
    assert cfg["fee_preset"] == "revolut_standard"
    assert abs(cfg["commission_rate"] - 0.0025) < 1e-9
    assert abs(cfg["commission_min_eur"] - 1.0) < 1e-9
    assert cfg["max_positions"] == 5
    assert cfg["min_hold_hours"] == 24
    assert cfg["promote_experiment_strategy"] is False
    assert cfg["rs_gate"] is True
    assert cfg["breadth_gate"] is True


def test_breadth_gate_roundtrip(tmp_path: Path):
    saved = save_trader_config(tmp_path, {"breadth_gate": False})
    assert saved["breadth_gate"] is False
    loaded = load_trader_config(tmp_path)
    assert loaded["breadth_gate"] is False


def test_promote_flag_roundtrip(tmp_path: Path):
    saved = save_trader_config(tmp_path, {"promote_experiment_strategy": True})
    assert saved["promote_experiment_strategy"] is True
    loaded = load_trader_config(tmp_path)
    assert loaded["promote_experiment_strategy"] is True


def test_book_limits_clamp(tmp_path: Path):
    saved = save_trader_config(
        tmp_path, {"max_positions": 99, "min_hold_hours": 1}
    )
    # Invalid values ignored → defaults from base
    assert saved["max_positions"] == 5
    assert saved["min_hold_hours"] == 24.0
    saved2 = save_trader_config(
        tmp_path, {"max_positions": 4, "min_hold_hours": 48}
    )
    assert saved2["max_positions"] == 4
    assert saved2["min_hold_hours"] == 48.0
