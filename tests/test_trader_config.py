"""Offline tests for Ops trader_config persistence."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from stock_checker.trader_config import (
    config_precedence_status,
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


def test_saved_row_beats_env(tmp_path: Path, monkeypatch):
    """xang1234 #394: Ops file wins over process environment when both set."""
    monkeypatch.setenv("AI_MODE", "full")
    monkeypatch.setenv("RS_GATE", "1")
    monkeypatch.setenv("BREADTH_GATE", "1")
    save_trader_config(
        tmp_path, {"ai_mode": "validate", "rs_gate": False, "breadth_gate": False}
    )
    cfg = load_trader_config(tmp_path)
    assert cfg["ai_mode"] == "validate"
    assert cfg["rs_gate"] is False
    assert cfg["breadth_gate"] is False
    st = config_precedence_status(tmp_path)
    assert st["source"] == "file"
    assert st["tone"] == "override"
    assert "ai_mode" in st["overrides"]
    assert "rs_gate" in st["overrides"]
    assert "Ops wins" in st["line"]


def test_config_precedence_env_when_no_file(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("AI_MODE", raising=False)
    st = config_precedence_status(tmp_path)
    assert st["source"] == "env"
    assert st["tone"] == "env"
    assert "no Ops file" in st["line"]
    assert st["env_fallback_n"] > 0
    assert st["meter"] == f"0 win · 0 ok · {st['env_fallback_n']} env"
    assert st["meter"] in st["line"]
    assert st["lead"] == "lead env"
    assert st["lead_share"] == "100%"
    assert st["lead_margin"] == ""  # sole-bucket: share ≠ ahead
    assert st["lead_sides"] == ""  # sole-bucket: ahead ≠ vs
    assert st["lead_sides_share"] == ""  # no vs → no runner %
    assert st["lead_sides_share_delta"] == ""  # no runner % → no share Δ
    assert st["sample_gap"] == ""  # lead present → gap silent
    assert "lead env · 100%" in st["line"]
    assert "ahead " not in st["line"]
    assert "vs " not in st["line"]
    assert "share Δ" not in st["line"]
    assert "tied" not in st["line"]
    assert st["file_freshness"] == ""
    assert "saved " not in st["line"]


def test_config_precedence_partial_file(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("AI_MODE", "full")
    monkeypatch.setenv("RS_GATE", "0")
    (tmp_path / "trader_config.json").write_text(
        json.dumps({"rs_gate": False}) + "\n"
    )
    cfg = load_trader_config(tmp_path)
    assert cfg["rs_gate"] is False
    assert cfg["ai_mode"] == "full"  # missing from file → env
    st = config_precedence_status(tmp_path)
    assert st["source"] == "file"
    assert "ai_mode" in st["env_fallbacks"]
    assert "rs_gate" not in st["env_fallbacks"]
    # rs_gate matches env (both false) → not an override; partial speaks env gaps
    assert st["tone"] in {"partial", "file"}
    assert "partial" in st["line"] or "matches env" in st["line"]
    assert st["meter"] in st["line"]
    assert st["lead"] == "lead env"
    assert "lead env" in st["line"]


def test_config_precedence_override_speaks_env_gaps(tmp_path: Path, monkeypatch):
    """Partial Ops file: overrides + missing keys both speak (portfolio AI both-sides)."""
    monkeypatch.setenv("AI_MODE", "full")
    monkeypatch.setenv("RS_GATE", "1")
    monkeypatch.setenv("BREADTH_GATE", "1")
    (tmp_path / "trader_config.json").write_text(
        json.dumps({"ai_mode": "validate"}) + "\n"
    )
    cfg = load_trader_config(tmp_path)
    assert cfg["ai_mode"] == "validate"
    assert cfg["rs_gate"] is True  # missing → env
    st = config_precedence_status(tmp_path)
    assert st["tone"] == "override"
    assert "ai_mode" in st["overrides"]
    assert "rs_gate" in st["env_fallbacks"]
    assert st["env_fallback_n"] >= 1  # both-sides payload (line may truncate)
    assert "Ops wins" in st["line"]
    assert st["override_n"] == 1
    assert st["meter"].startswith("1 win ·")
    assert st["meter"] in st["line"]
    assert st["lead"] == "lead env"
    assert "lead env" in st["line"]
    assert st["lead_sides"] == "vs win · 1"
    assert st["lead_sides_share"] == "10%"  # 1÷10
    assert st["lead_sides_share_delta"] == "share Δ wide · +80pp"  # 90−10
    assert "vs win · 1 · Δ+80=W" in st["line"]
    assert st["line"].index(st["meter"]) < st["line"].index("lead env")


def test_config_precedence_override_speaks_confirms(tmp_path: Path, monkeypatch):
    """Ops keys that match env speak as confirms (not silent agreement)."""
    monkeypatch.setenv("AI_MODE", "full")
    monkeypatch.setenv("RS_GATE", "1")
    monkeypatch.setenv("BREADTH_GATE", "1")
    monkeypatch.setenv("MIN_HOLD_HOURS", "24")
    (tmp_path / "trader_config.json").write_text(
        json.dumps(
            {
                "ai_mode": "validate",
                "rs_gate": True,
                "min_hold_hours": 24,
            }
        )
        + "\n"
    )
    st = config_precedence_status(tmp_path)
    assert st["tone"] == "override"
    assert "ai_mode" in st["overrides"]
    assert "rs_gate" in st["confirms"]
    assert "min_hold_hours" in st["confirms"]
    assert "breadth_gate" in st["env_fallbacks"]
    assert "Ops wins" in st["line"]
    assert st["override_n"] == 1
    assert st["confirm_n"] == 2
    assert st["env_fallback_n"] == 7
    # confirms/env-for key names may truncate; meter+lead+ahead+vs stay early.
    assert st["meter"] == f"1 win · 2 ok · {st['env_fallback_n']} env"
    assert st["meter"] in st["line"]
    assert st["lead"] == "lead env"
    assert st["lead_share"] == "70%"
    assert st["lead_margin"] == "ahead wide · +5"  # 7 − 2
    assert st["lead_sides"] == "vs ok · 2"  # ahead ≠ who is #2
    assert st["lead_sides_share"] == "20%"  # 2÷10; absolute ≠ ownership
    assert st["lead_sides_share_delta"] == "share Δ wide · +50pp"  # 70−20
    assert "lead env" in st["line"]
    assert "ahead wide · +5" in st["line"]
    assert "vs ok · 2 · Δ+50=W" in st["line"]
    assert st["line"].index("ahead wide") < st["line"].index("vs ok")
    assert st["line"].index("vs ok") < st["line"].index("Δ+50=W")
    assert st["line"].index(st["meter"]) < st["line"].index("vs ok")


def test_config_precedence_meter_survives_truncate(tmp_path: Path, monkeypatch):
    """Multi-meter stays ahead of key names when the line hits 120 chars."""
    monkeypatch.setenv("AI_MODE", "full")
    monkeypatch.setenv("AI_MODEL", "gemma4:latest")
    monkeypatch.setenv("AI_MULTI_ROLE", "1")
    monkeypatch.setenv("REGIME_GATE", "1")
    monkeypatch.setenv("RS_GATE", "1")
    monkeypatch.setenv("BREADTH_GATE", "1")
    monkeypatch.setenv("FEE_PRESET", "revolut_standard")
    monkeypatch.setenv("MAX_POSITIONS", "5")
    monkeypatch.setenv("MIN_HOLD_HOURS", "24")
    monkeypatch.setenv("PROMOTE_EXPERIMENT_STRATEGY", "0")
    (tmp_path / "trader_config.json").write_text(
        json.dumps(
            {
                "ai_mode": "validate",
                "ai_model": "qwen3.5:9b",
                "ai_multi_role": False,
                "regime_gate": False,
                "rs_gate": False,
                "breadth_gate": False,
                "fee_preset": "revolut_ultra",
                "max_positions": 3,
                "min_hold_hours": 48,
                "promote_experiment_strategy": True,
            }
        )
        + "\n"
    )
    st = config_precedence_status(tmp_path)
    assert st["tone"] == "override"
    assert st["override_n"] == 10
    assert st["confirm_n"] == 0
    assert st["env_fallback_n"] == 0
    assert st["meter"] == "10 win · 0 ok · 0 env"
    assert st["meter"] in st["line"]
    assert st["lead"] == "lead win"
    assert st["lead_share"] == "100%"
    assert st["lead_margin"] == ""  # sole-bucket omits ahead
    assert st["lead_sides"] == ""
    assert st["lead_sides_share"] == ""
    assert st["lead_sides_share_delta"] == ""
    assert st["sample_gap"] == ""
    assert "lead win" in st["line"]
    assert "100%" in st["line"]
    assert "ahead " not in st["line"]
    assert "vs " not in st["line"]
    assert "share Δ" not in st["line"]
    assert "tied" not in st["line"]
    assert st["line"].index(st["meter"]) < st["line"].index("lead win")
    assert st["line"].index("lead win") < st["line"].index("100%")
    assert len(st["line"]) <= 120


def test_config_precedence_sample_gap_helper():
    from stock_checker.trader_config import _precedence_sample_gap

    # Sole bucket always leads → gap silent (unlike soft-allow min_count=2).
    assert _precedence_sample_gap(0, 0, 1) == ""
    assert _precedence_sample_gap(3, 0, 0) == ""
    assert _precedence_sample_gap(0, 0, 0) == ""
    # ≥2 with no strict lead → tied (soft-allow / LAYA sample_gap parity).
    assert _precedence_sample_gap(2, 2, 0) == "tied"
    assert _precedence_sample_gap(1, 1, 1) == "tied"
    # Thin branch kept for API parity (unreachable while sole buckets lead).
    assert _precedence_sample_gap(0, 0, 0) == ""


def test_config_precedence_lead_silent_on_tie(tmp_path: Path, monkeypatch):
    """Equal top buckets speak tied (no ambiguous lead)."""
    monkeypatch.setenv("AI_MODE", "full")
    monkeypatch.setenv("AI_MODEL", "gemma4:latest")
    monkeypatch.setenv("AI_MULTI_ROLE", "1")
    monkeypatch.setenv("REGIME_GATE", "1")
    monkeypatch.setenv("RS_GATE", "1")
    monkeypatch.setenv("BREADTH_GATE", "1")
    monkeypatch.setenv("FEE_PRESET", "revolut_standard")
    monkeypatch.setenv("MAX_POSITIONS", "5")
    monkeypatch.setenv("MIN_HOLD_HOURS", "24")
    monkeypatch.setenv("PROMOTE_EXPERIMENT_STRATEGY", "0")
    # 5 overrides + 5 confirms + 0 env → tie win/ok → lead silent · tied.
    (tmp_path / "trader_config.json").write_text(
        json.dumps(
            {
                "ai_mode": "validate",
                "ai_model": "qwen3.5:9b",
                "ai_multi_role": False,
                "regime_gate": False,
                "promote_experiment_strategy": True,
                "rs_gate": True,
                "breadth_gate": True,
                "fee_preset": "revolut_standard",
                "max_positions": 5,
                "min_hold_hours": 24,
            }
        )
        + "\n"
    )
    st = config_precedence_status(tmp_path)
    assert st["override_n"] == 5
    assert st["confirm_n"] == 5
    assert st["env_fallback_n"] == 0
    assert st["lead"] == ""
    assert st["lead_share"] == ""
    assert st["lead_margin"] == ""
    assert st["lead_sides"] == ""
    assert st["lead_sides_share"] == ""
    assert st["lead_sides_share_delta"] == ""
    assert st["sample_gap"] == "tied"
    assert "lead " not in st["line"]
    assert "ahead " not in st["line"]
    assert "vs " not in st["line"]
    assert "share Δ" not in st["line"]
    assert st["meter"] in st["line"]
    assert " · tied" in st["line"]
    assert st["line"].index(st["meter"]) < st["line"].index("tied")


def test_config_precedence_lead_ok(tmp_path: Path, monkeypatch):
    """Confirms strictly ahead → lead ok + ownership % + ahead + vs."""
    monkeypatch.setenv("AI_MODE", "validate")
    monkeypatch.setenv("AI_MODEL", "gemma4:latest")
    monkeypatch.setenv("AI_MULTI_ROLE", "1")
    monkeypatch.setenv("REGIME_GATE", "1")
    monkeypatch.setenv("RS_GATE", "1")
    monkeypatch.setenv("BREADTH_GATE", "1")
    monkeypatch.setenv("FEE_PRESET", "revolut_standard")
    monkeypatch.setenv("MAX_POSITIONS", "5")
    monkeypatch.setenv("MIN_HOLD_HOURS", "24")
    monkeypatch.setenv("PROMOTE_EXPERIMENT_STRATEGY", "0")
    (tmp_path / "trader_config.json").write_text(
        json.dumps(
            {
                "ai_mode": "validate",
                "ai_model": "gemma4:latest",
                "ai_multi_role": True,
                "regime_gate": True,
                "rs_gate": True,
                "breadth_gate": True,
                "fee_preset": "revolut_standard",
                "max_positions": 5,
                "min_hold_hours": 24,
                # promote missing → env gap; rest confirm
            }
        )
        + "\n"
    )
    st = config_precedence_status(tmp_path)
    assert st["confirm_n"] == 9
    assert st["override_n"] == 0
    assert st["env_fallback_n"] == 1
    assert st["lead"] == "lead ok"
    assert st["lead_share"] == "90%"
    assert st["lead_margin"] == "ahead wide · +8"  # 9 − 1
    assert st["lead_sides"] == "vs env · 1"
    assert st["lead_sides_share"] == "10%"  # 1÷10
    assert st["lead_sides_share_delta"] == "share Δ wide · +80pp"  # 90−10
    assert "lead ok" in st["line"]
    assert "90%" in st["line"]
    assert "ahead wide · +8" in st["line"]
    assert "vs env · 1 · Δ+80=W" in st["line"]
    assert st["tone"] == "partial"


def test_config_precedence_lead_share_partial_win(tmp_path: Path, monkeypatch):
    """Lead win with env gaps speaks ownership + ahead + vs under 100%."""
    monkeypatch.setenv("AI_MODE", "full")
    monkeypatch.setenv("AI_MODEL", "gemma4:latest")
    monkeypatch.setenv("AI_MULTI_ROLE", "1")
    monkeypatch.setenv("REGIME_GATE", "1")
    monkeypatch.setenv("RS_GATE", "1")
    monkeypatch.setenv("BREADTH_GATE", "1")
    monkeypatch.setenv("FEE_PRESET", "revolut_standard")
    monkeypatch.setenv("MAX_POSITIONS", "5")
    monkeypatch.setenv("MIN_HOLD_HOURS", "24")
    monkeypatch.setenv("PROMOTE_EXPERIMENT_STRATEGY", "0")
    # 6 overrides + 0 confirms + 4 env → lead win · 60% · ahead wide · +2
    (tmp_path / "trader_config.json").write_text(
        json.dumps(
            {
                "ai_mode": "validate",
                "ai_model": "qwen3.5:9b",
                "ai_multi_role": False,
                "regime_gate": False,
                "rs_gate": False,
                "breadth_gate": False,
            }
        )
        + "\n"
    )
    st = config_precedence_status(tmp_path)
    assert st["override_n"] == 6
    assert st["confirm_n"] == 0
    assert st["env_fallback_n"] == 4
    assert st["lead"] == "lead win"
    assert st["lead_share"] == "60%"
    assert st["lead_margin"] == "ahead wide · +2"  # 6 − 4
    assert st["lead_sides"] == "vs env · 4"
    assert st["lead_sides_share"] == "40%"  # 4÷10
    assert st["lead_sides_share_delta"] == "share Δ wide · +20pp"  # 60−40
    assert st["lead_sides_share_vs_delta"] == "share vs Δ align · wide"
    assert "lead win · 60%" in st["line"]
    assert "ahead wide · +2" in st["line"]
    assert "vs env · 4 · Δ+20=W" in st["line"]
    assert st["line"].index("lead win") < st["line"].index("60%")
    assert st["line"].index("60%") < st["line"].index("ahead wide")
    assert st["line"].index("ahead wide") < st["line"].index("vs env")
    assert st["line"].index("vs env") < st["line"].index("Δ+20=W")


def test_config_precedence_lead_margin_thin(tmp_path: Path, monkeypatch):
    """Lead−runner = 1 → ahead thin · +1 (not wide) + vs runner."""
    monkeypatch.setenv("AI_MODE", "full")
    monkeypatch.setenv("AI_MODEL", "gemma4:latest")
    monkeypatch.setenv("AI_MULTI_ROLE", "1")
    monkeypatch.setenv("REGIME_GATE", "1")
    monkeypatch.setenv("RS_GATE", "1")
    monkeypatch.setenv("BREADTH_GATE", "1")
    monkeypatch.setenv("FEE_PRESET", "revolut_standard")
    monkeypatch.setenv("MAX_POSITIONS", "5")
    monkeypatch.setenv("MIN_HOLD_HOURS", "24")
    monkeypatch.setenv("PROMOTE_EXPERIMENT_STRATEGY", "0")
    # 5 win + 1 ok + 4 env → lead win · 50% · ahead thin · +1 · vs env · 4
    (tmp_path / "trader_config.json").write_text(
        json.dumps(
            {
                "ai_mode": "validate",
                "ai_model": "qwen3.5:9b",
                "ai_multi_role": False,
                "regime_gate": False,
                "rs_gate": False,
                "breadth_gate": True,  # confirm
            }
        )
        + "\n"
    )
    st = config_precedence_status(tmp_path)
    assert st["override_n"] == 5
    assert st["confirm_n"] == 1
    assert st["env_fallback_n"] == 4
    assert st["lead"] == "lead win"
    assert st["lead_share"] == "50%"
    assert st["lead_margin"] == "ahead thin · +1"  # 5 − 4
    assert st["lead_sides"] == "vs env · 4"
    assert st["lead_sides_share"] == "40%"  # 4÷10
    assert st["lead_sides_share_delta"] == ""  # 50−40 = 10pp mid silent
    assert st["lead_sides_share_vs_delta"] == "share vs Δ clash · ×thin · %mid"
    assert "ahead thin · +1" in st["line"]
    assert "vs env · 4 · ×T/%m" in st["line"]
    assert "share Δ" not in st["line"]
    assert "40%" in st["lead_sides_share"]


def test_config_precedence_lead_sides_tied_runner_silent(tmp_path: Path, monkeypatch):
    """Tied #2 buckets keep ahead but omit vs (ambiguous runner)."""
    monkeypatch.setenv("AI_MODE", "full")
    monkeypatch.setenv("AI_MODEL", "gemma4:latest")
    monkeypatch.setenv("AI_MULTI_ROLE", "1")
    monkeypatch.setenv("REGIME_GATE", "1")
    monkeypatch.setenv("RS_GATE", "1")
    monkeypatch.setenv("BREADTH_GATE", "1")
    monkeypatch.setenv("FEE_PRESET", "revolut_standard")
    monkeypatch.setenv("MAX_POSITIONS", "5")
    monkeypatch.setenv("MIN_HOLD_HOURS", "24")
    monkeypatch.setenv("PROMOTE_EXPERIMENT_STRATEGY", "0")
    # 6 win + 2 ok + 2 env → ahead wide · +4; ok/env tie → vs silent
    (tmp_path / "trader_config.json").write_text(
        json.dumps(
            {
                "ai_mode": "validate",
                "ai_model": "qwen3.5:9b",
                "ai_multi_role": False,
                "regime_gate": False,
                "rs_gate": False,
                "breadth_gate": False,
                "fee_preset": "revolut_standard",  # confirm
                "max_positions": 5,  # confirm
            }
        )
        + "\n"
    )
    st = config_precedence_status(tmp_path)
    assert st["override_n"] == 6
    assert st["confirm_n"] == 2
    assert st["env_fallback_n"] == 2
    assert st["lead"] == "lead win"
    assert st["lead_margin"] == "ahead wide · +4"  # 6 − 2
    assert st["lead_sides"] == ""
    assert st["lead_sides_share"] == ""  # no vs → no runner %
    assert st["lead_sides_share_delta"] == ""
    assert st["lead_sides_share_vs_delta"] == ""
    assert "ahead wide · +4" in st["line"]
    assert "vs " not in st["line"]
    assert "share Δ" not in st["line"]
    assert "align·" not in st["line"]
    assert "×" not in st["line"]


def test_config_precedence_lead_sides_share(tmp_path: Path, monkeypatch):
    """Clear runner speaks ownership % after vs (count ≠ share)."""
    monkeypatch.setenv("AI_MODE", "full")
    monkeypatch.setenv("AI_MODEL", "gemma4:latest")
    monkeypatch.setenv("AI_MULTI_ROLE", "1")
    monkeypatch.setenv("REGIME_GATE", "1")
    monkeypatch.setenv("RS_GATE", "1")
    monkeypatch.setenv("BREADTH_GATE", "1")
    monkeypatch.setenv("FEE_PRESET", "revolut_standard")
    monkeypatch.setenv("MAX_POSITIONS", "5")
    monkeypatch.setenv("MIN_HOLD_HOURS", "24")
    monkeypatch.setenv("PROMOTE_EXPERIMENT_STRATEGY", "0")
    # 7 win + 0 ok + 3 env → vs env · 3 · Δ+40=W
    (tmp_path / "trader_config.json").write_text(
        json.dumps(
            {
                "ai_mode": "validate",
                "ai_model": "qwen3.5:9b",
                "ai_multi_role": False,
                "regime_gate": False,
                "rs_gate": False,
                "breadth_gate": False,
                "fee_preset": "revolut_ultra",
            }
        )
        + "\n"
    )
    st = config_precedence_status(tmp_path)
    assert st["override_n"] == 7
    assert st["confirm_n"] == 0
    assert st["env_fallback_n"] == 3
    assert st["lead"] == "lead win"
    assert st["lead_sides"] == "vs env · 3"
    assert st["lead_sides_share"] == "30%"
    assert st["lead_sides_share_delta"] == "share Δ wide · +40pp"  # 70−30
    assert st["lead_sides_share_vs_delta"] == "share vs Δ align · wide"
    assert "vs env · 3 · Δ+40=W" in st["line"]
    assert st["line"].index("vs env") < st["line"].index("Δ+40=W")


def test_config_precedence_lead_sides_share_delta_mid_silent(
    tmp_path: Path, monkeypatch
):
    """10pp ownership spread stays silent (mid band; count ahead ≠ pp)."""
    monkeypatch.setenv("AI_MODE", "full")
    monkeypatch.setenv("AI_MODEL", "gemma4:latest")
    monkeypatch.setenv("AI_MULTI_ROLE", "1")
    monkeypatch.setenv("REGIME_GATE", "1")
    monkeypatch.setenv("RS_GATE", "1")
    monkeypatch.setenv("BREADTH_GATE", "1")
    monkeypatch.setenv("FEE_PRESET", "revolut_standard")
    monkeypatch.setenv("MAX_POSITIONS", "5")
    monkeypatch.setenv("MIN_HOLD_HOURS", "24")
    monkeypatch.setenv("PROMOTE_EXPERIMENT_STRATEGY", "0")
    # 5 win + 1 ok + 4 env → 50% vs 40% = 10pp mid
    (tmp_path / "trader_config.json").write_text(
        json.dumps(
            {
                "ai_mode": "validate",
                "ai_model": "qwen3.5:9b",
                "ai_multi_role": False,
                "regime_gate": False,
                "rs_gate": False,
                "breadth_gate": True,
            }
        )
        + "\n"
    )
    st = config_precedence_status(tmp_path)
    assert st["lead_share"] == "50%"
    assert st["lead_sides_share"] == "40%"
    assert st["lead_sides_share_delta"] == ""
    assert st["lead_sides_share_vs_delta"] == "share vs Δ clash · ×thin · %mid"
    assert "share Δ" not in st["line"]
    assert "×T/%m" in st["line"]


def _stamp_config_mtime(path: Path, clock: datetime, age_sec: float) -> None:
    ts = clock.timestamp() - age_sec
    os.utime(path, (ts, ts))


def test_config_precedence_saved_age_fresh(tmp_path: Path, monkeypatch):
    """Ops file mtime fresh <24h (RyanJHamby triad + xang1234 seed-age)."""
    monkeypatch.setenv("AI_MODE", "full")
    (tmp_path / "trader_config.json").write_text(
        json.dumps({"ai_mode": "validate"}) + "\n"
    )
    now = datetime(2026, 10, 6, 8, 0, tzinfo=timezone.utc)
    _stamp_config_mtime(tmp_path / "trader_config.json", now, 6 * 3600)
    st = config_precedence_status(tmp_path, now=now)
    assert st["file_freshness"] == "fresh"
    assert st["file_age_label"] == "6h ago"
    assert st["file_age_bit"] == "saved 6h ago · fresh"
    assert st["file_age_line"] == "6h fresh"
    assert "6h fresh" in st["line"]
    assert st["line"].index("6h fresh") < st["line"].index(st["meter"])
    assert st["meter"] in st["line"]
    assert st["tone"] == "override"
    assert st["source"] == "file"


def test_config_precedence_saved_age_aging(tmp_path: Path, monkeypatch):
    """Ops file mtime aging between 24h and 7d."""
    monkeypatch.setenv("AI_MODE", "full")
    (tmp_path / "trader_config.json").write_text(
        json.dumps({"ai_mode": "validate"}) + "\n"
    )
    now = datetime(2026, 10, 6, 8, 0, tzinfo=timezone.utc)
    _stamp_config_mtime(tmp_path / "trader_config.json", now, 48 * 3600)
    st = config_precedence_status(tmp_path, now=now)
    assert st["file_freshness"] == "aging"
    assert st["file_age_label"] == "2d ago"
    assert "2d aging" in st["line"]
    assert st["tone"] == "override"  # aging keeps source tone
    assert st["source"] == "file"


def test_config_precedence_saved_age_stale(tmp_path: Path, monkeypatch):
    """Ops file mtime stale ≥7d — file exists ≠ recently intended."""
    monkeypatch.setenv("AI_MODE", "full")
    (tmp_path / "trader_config.json").write_text(
        json.dumps({"ai_mode": "validate"}) + "\n"
    )
    now = datetime(2026, 10, 6, 8, 0, tzinfo=timezone.utc)
    _stamp_config_mtime(tmp_path / "trader_config.json", now, 10 * 86400)
    st = config_precedence_status(tmp_path, now=now)
    assert st["file_freshness"] == "stale"
    assert st["file_age_label"] == "10d ago"
    assert "10d stale" in st["line"]
    assert st["meter"] in st["line"]
    assert len(st["line"]) <= 120
    assert st["source"] == "file"
    assert st["tone"] == "warn"  # age label ≠ warn; stale escalates
