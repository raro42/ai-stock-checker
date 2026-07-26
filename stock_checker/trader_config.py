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

ALLOWED_AI_MODES = frozenset({"off", "validate", "full"})

# Instruct/general defaults — never suggest coder models for trade gates.
DEFAULT_AI_MODEL = "gemma4:latest"

DEFAULTS: dict[str, Any] = {
    "ai_mode": "off",
    "ai_model": DEFAULT_AI_MODEL,
    "ai_multi_role": True,
    "regime_gate": True,
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
    return {
        "ai_mode": mode,
        "ai_model": model,
        "ai_multi_role": _as_bool(os.getenv("AI_MULTI_ROLE"), True),
        "regime_gate": _as_bool(os.getenv("REGIME_GATE"), True),
    }


def normalize_config(raw: dict[str, Any] | None, *, base: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """Merge raw over base (or env defaults) and clamp to allowed values."""
    out = dict(base if base is not None else _env_defaults())
    if not isinstance(raw, dict):
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
    }
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return payload
