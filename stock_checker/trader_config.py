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
    free_legs_for_preset,
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
    "rs_gate": True,
    "breadth_gate": True,
    "fee_preset": DEFAULT_FEE_PRESET,
    # Anti-churn paper defaults — single source of truth with compose + IntelligentTrader.
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
        "rs_gate": _as_bool(os.getenv("RS_GATE"), True),
        "breadth_gate": _as_bool(os.getenv("BREADTH_GATE"), True),
        "fee_preset": fee_preset,
        "commission_rate": rate,
        "commission_min_eur": min_eur,
        "free_legs_per_month": free_legs_for_preset(fee_preset),
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
        preset = str(out.get("fee_preset") or DEFAULT_FEE_PRESET)
        rate, min_eur = rates_for_preset(preset)
        out["commission_rate"] = rate
        out["commission_min_eur"] = min_eur
        out["free_legs_per_month"] = free_legs_for_preset(preset)
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

    if "rs_gate" in raw:
        out["rs_gate"] = _as_bool(raw.get("rs_gate"), out.get("rs_gate", True))

    if "breadth_gate" in raw:
        out["breadth_gate"] = _as_bool(
            raw.get("breadth_gate"), out.get("breadth_gate", True)
        )

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
        preset = str(out.get("fee_preset") or DEFAULT_FEE_PRESET)
        rate, min_eur = rates_for_preset(preset)
        out["commission_rate"] = rate
        out["commission_min_eur"] = min_eur
        out["free_legs_per_month"] = free_legs_for_preset(preset)

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
    if "rs_gate" not in out:
        out["rs_gate"] = bool(DEFAULTS["rs_gate"])
    if "breadth_gate" not in out:
        out["breadth_gate"] = bool(DEFAULTS["breadth_gate"])

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


# Knobs compared for Ops precedence honesty (xang1234 saved-row > env).
PRECEDENCE_KEYS: tuple[str, ...] = (
    "ai_mode",
    "ai_model",
    "ai_multi_role",
    "regime_gate",
    "rs_gate",
    "breadth_gate",
    "fee_preset",
    "max_positions",
    "min_hold_hours",
    "promote_experiment_strategy",
)

_PRECEDENCE_SHORT: dict[str, str] = {
    "ai_mode": "AI",
    "ai_model": "model",
    "ai_multi_role": "multi-role",
    "regime_gate": "regime",
    "rs_gate": "RS",
    "breadth_gate": "breadth",
    "fee_preset": "fees",
    "max_positions": "max pos",
    "min_hold_hours": "hold",
    "promote_experiment_strategy": "promote",
}


def _values_differ(a: Any, b: Any) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return bool(a) != bool(b)
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) > 1e-9
    return str(a).strip() != str(b).strip()


def _format_key_list(keys: list[str], *, limit: int = 4) -> str:
    short = [_PRECEDENCE_SHORT.get(k, k) for k in keys[:limit]]
    bits = " · ".join(short)
    extra = len(keys) - len(short)
    if extra > 0:
        bits = f"{bits} +{extra}" if bits else f"+{extra}"
    return bits


def config_precedence_status(data_dir: Path | str) -> dict[str, Any]:
    """Report Ops file vs env/compose precedence (display / API honesty).

    Resolve order matches load_trader_config:
      1. saved trader_config.json keys (Ops)
      2. process environment / compose
      3. DEFAULTS

    Adapted from xang1234/stock-screener #394 (saved row over environment).
    Not a gate — friends see whether a redeploy's env can still shadow knobs
    missing from a partial Ops file. When Ops overrides some keys and leaves
    others to env, the line speaks both sides (override keys + env gaps).
    Keys present in the Ops file that still match env speak as confirms
    (portfolio AI speak-both-sides — override ≠ silent agreement).
    """
    path = config_path(data_dir)
    env = _env_defaults()
    empty = {
        "overrides": [],
        "confirms": [],
        "env_fallbacks": list(PRECEDENCE_KEYS),
        "override_n": 0,
        "confirm_n": 0,
        "env_fallback_n": len(PRECEDENCE_KEYS),
        "ready": True,
    }
    if not path.is_file():
        return {
            **empty,
            "source": "env",
            "tone": "env",
            "line": "env · no Ops file",
        }

    try:
        raw = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {
            **empty,
            "source": "env",
            "tone": "warn",
            "line": "env · Ops file unreadable",
        }

    if not isinstance(raw, dict):
        raw = {}

    effective = normalize_config(raw, base=env)
    overrides: list[str] = []
    confirms: list[str] = []
    env_fallbacks: list[str] = []
    for key in PRECEDENCE_KEYS:
        if key not in raw:
            env_fallbacks.append(key)
            continue
        if _values_differ(effective.get(key), env.get(key)):
            overrides.append(key)
        else:
            confirms.append(key)

    if overrides:
        bits = _format_key_list(overrides)
        line = f"file · Ops wins · {bits}"
        # Speak-both-sides: Ops override ≠ silent confirms / env gaps
        # (portfolio AI + xang1234 #394 after saved-row precedence).
        if confirms:
            conf = _format_key_list(confirms, limit=2)
            line = f"{line} · confirms {conf}"
        if env_fallbacks:
            gap = _format_key_list(env_fallbacks, limit=2)
            line = f"{line} · env for {gap}"
        tone = "override"
    elif env_fallbacks:
        bits = _format_key_list(env_fallbacks, limit=3)
        line = f"file · partial · env for {bits}"
        if confirms:
            conf = _format_key_list(confirms, limit=2)
            line = f"{line} · confirms {conf}"
        tone = "partial"
    else:
        line = "file · Ops wins · matches env"
        tone = "file"

    if len(line) > 96:
        line = line[:95] + "…"

    return {
        "source": "file",
        "overrides": overrides,
        "confirms": confirms,
        "env_fallbacks": env_fallbacks,
        "override_n": len(overrides),
        "confirm_n": len(confirms),
        "env_fallback_n": len(env_fallbacks),
        "tone": tone,
        "line": line,
        "ready": True,
    }


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
        "rs_gate": bool(merged.get("rs_gate", True)),
        "breadth_gate": bool(merged.get("breadth_gate", True)),
        "fee_preset": merged["fee_preset"],
        "commission_rate": float(merged["commission_rate"]),
        "commission_min_eur": float(merged["commission_min_eur"]),
        "free_legs_per_month": int(
            merged.get("free_legs_per_month")
            or free_legs_for_preset(str(merged.get("fee_preset") or DEFAULT_FEE_PRESET))
        ),
        "max_positions": int(merged["max_positions"]),
        "min_hold_hours": float(merged["min_hold_hours"]),
        "promote_experiment_strategy": bool(
            merged.get("promote_experiment_strategy", False)
        ),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return payload
