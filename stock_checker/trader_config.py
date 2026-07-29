"""
Desk/trader runtime knobs persisted under data/trader_config.json.

Ops can edit these without editing compose. Env (.env) is the fallback when
the file is missing. Secrets never live here.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

from stock_checker.fees import (
    DEFAULT_FEE_PRESET,
    FEE_PRESETS,
    rates_for_preset,
)
from stock_checker.promoted_strategy import promote_enabled_from_env

ALLOWED_AI_MODES = frozenset({"off", "validate", "full"})
ALLOWED_FEE_PRESETS = frozenset(FEE_PRESETS.keys()) | frozenset({"custom"})

# Instruct/general defaults — never suggest coder models for trade gates.
DEFAULT_AI_MODEL = "gemma4:latest"

DEFAULTS: dict[str, Any] = {
    "ai_mode": "off",
    "ai_model": DEFAULT_AI_MODEL,
    "ai_multi_role": True,
    "regime_gate": True,
    "fee_preset": DEFAULT_FEE_PRESET,
    # Anti-churn paper defaults (tighter than old compose 8×4h).
    "max_positions": 5,
    "min_hold_hours": 24,
    # Champion entry filter (experiment_strategy). Off until calm paper stretch.
    "promote_experiment_strategy": False,
}


def config_path(data_dir: Path | str) -> Path:
    return Path(data_dir) / "trader_config.json"


def _as_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in {"0", "false", "no", "off", ""}


def _env_defaults() -> dict[str, Any]:
    mode = (os.getenv("AI_MODE") or DEFAULTS["ai_mode"]).strip().lower() or "off"
    if mode not in ALLOWED_AI_MODES:
        mode = "off"
    model = (os.getenv("AI_MODEL") or DEFAULT_AI_MODEL).strip() or DEFAULT_AI_MODEL
    fee_preset = (
        os.getenv("FEE_PRESET") or DEFAULT_FEE_PRESET
    ).strip().lower() or DEFAULT_FEE_PRESET
    if fee_preset not in ALLOWED_FEE_PRESETS:
        fee_preset = DEFAULT_FEE_PRESET
    rate, min_eur = rates_for_preset(fee_preset)
    try:
        max_pos = int(os.getenv("MAX_POSITIONS") or DEFAULTS["max_positions"])
    except (TypeError, ValueError):
        max_pos = int(DEFAULTS["max_positions"])
    try:
        min_hold_h = float(os.getenv("MIN_HOLD_HOURS") or DEFAULTS["min_hold_hours"])
    except (TypeError, ValueError):
        min_hold_h = float(DEFAULTS["min_hold_hours"])
    return {
        "ai_mode": mode,
        "ai_model": model,
        "ai_multi_role": _as_bool(os.getenv("AI_MULTI_ROLE"), True),
        "regime_gate": _as_bool(os.getenv("REGIME_GATE"), True),
        "fee_preset": fee_preset,
        "commission_rate": rate,
        "commission_min_eur": min_eur,
        "max_positions": max(1, min(12, max_pos)),
        "min_hold_hours": max(4.0, min(168.0, min_hold_h)),
        "promote_experiment_strategy": promote_enabled_from_env(
            bool(DEFAULTS["promote_experiment_strategy"])
        ),
    }


def normalize_config(raw: dict[str, Any] | None, *, base: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """Merge raw over base (or env defaults) and clamp to allowed values."""
    out = dict(base if base is not None else _env_defaults())
    if not isinstance(raw, dict):
        rate, min_eur = rates_for_preset(str(out.get("fee_preset") or DEFAULT_FEE_PRESET))
        out["commission_rate"] = rate
        out["commission_min_eur"] = min_eur
        return out

    if "ai_mode" in raw:
        mode = str(raw.get("ai_mode") or "").strip().lower()
        if mode in ALLOWED_AI_MODES:
            out["ai_mode"] = mode

    if "ai_model" in raw:
        model = str(raw.get("ai_model") or "").strip()
        # Block obvious coder defaults for trade decisions.
        lowered = model.lower()
        if model and "coder" not in lowered:
            out["ai_model"] = model[:80]

    if "ai_multi_role" in raw:
        out["ai_multi_role"] = _as_bool(raw.get("ai_multi_role"), out["ai_multi_role"])

    if "regime_gate" in raw:
        out["regime_gate"] = _as_bool(raw.get("regime_gate"), out["regime_gate"])

    if "fee_preset" in raw:
        preset = str(raw.get("fee_preset") or "").strip().lower()
        if preset in ALLOWED_FEE_PRESETS:
            out["fee_preset"] = preset

    # Custom numeric overrides only when preset is custom.
    if out.get("fee_preset") == "custom":
        if "commission_rate" in raw:
            try:
                r = float(raw.get("commission_rate"))
                if 0 <= r <= 0.05:
                    out["commission_rate"] = r
            except (TypeError, ValueError):
                pass
        if "commission_min_eur" in raw:
            try:
                m = float(raw.get("commission_min_eur"))
                if 0 <= m <= 50:
                    out["commission_min_eur"] = m
            except (TypeError, ValueError):
                pass
    else:
        rate, min_eur = rates_for_preset(str(out.get("fee_preset") or DEFAULT_FEE_PRESET))
        out["commission_rate"] = rate
        out["commission_min_eur"] = min_eur

    if "max_positions" in raw:
        try:
            mp = int(raw.get("max_positions"))
            if 1 <= mp <= 12:
                out["max_positions"] = mp
        except (TypeError, ValueError):
            pass

    if "min_hold_hours" in raw:
        try:
            mh = float(raw.get("min_hold_hours"))
            if 4.0 <= mh <= 168.0:
                out["min_hold_hours"] = mh
        except (TypeError, ValueError):
            pass

    if "promote_experiment_strategy" in raw:
        out["promote_experiment_strategy"] = _as_bool(
            raw.get("promote_experiment_strategy"),
            bool(out.get("promote_experiment_strategy", False)),
        )

    # Ensure sizing keys always present after merge.
    if "max_positions" not in out:
        out["max_positions"] = int(DEFAULTS["max_positions"])
    if "min_hold_hours" not in out:
        out["min_hold_hours"] = float(DEFAULTS["min_hold_hours"])
    if "promote_experiment_strategy" not in out:
        out["promote_experiment_strategy"] = bool(
            DEFAULTS["promote_experiment_strategy"]
        )

    return out


def load_trader_config(data_dir: Path | str) -> dict[str, Any]:
    path = config_path(data_dir)
    base = _env_defaults()
    if not path.is_file():
        return base
    try:
        raw = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return base
    return normalize_config(raw if isinstance(raw, dict) else {}, base=base)


def save_trader_config(data_dir: Path | str, updates: dict[str, Any]) -> dict[str, Any]:
    """Validate, merge with current, write JSON. Returns the saved config."""
    current = load_trader_config(data_dir)
    merged = normalize_config(updates, base=current)
    path = config_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "ai_mode": merged["ai_mode"],
        "ai_model": merged["ai_model"],
        "ai_multi_role": bool(merged["ai_multi_role"]),
        "regime_gate": bool(merged["regime_gate"]),
        "fee_preset": merged["fee_preset"],
        "commission_rate": float(merged["commission_rate"]),
        "commission_min_eur": float(merged["commission_min_eur"]),
        "max_positions": int(merged["max_positions"]),
        "min_hold_hours": float(merged["min_hold_hours"]),
        "promote_experiment_strategy": bool(
            merged.get("promote_experiment_strategy", False)
        ),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return payload
