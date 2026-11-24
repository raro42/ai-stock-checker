"""
Desk/trader runtime knobs persisted under data/trader_config.json.

Ops can edit these without editing compose. Env (.env) is the fallback when
the file is missing. Secrets never live here.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
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
# Ops Persist / env model tag ceiling — bare ``model[:80]`` lied when bool
# (LAYA / AI-mode glance model clip peers).
AI_MODEL_CHARS = 80

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


def _coerce_ai_model_chars(
    value: object, default: int = AI_MODEL_CHARS
) -> int:
    """Positive Ops ai_model char ceiling, or ``default`` when bool/gap/≤0.

    FinRobot + tradermonty #700/#655 + xang1234/portfolio AI: ``True→1`` must
    not invent a one-char persisted model tag via ``model[:True]``;
    ``False→0`` must not wipe (LAYA / AI-mode glance model clip peers —
    Ops normalize/env still sliced bare ``[:80]``).
    """
    from stock_checker.technical_indicators import coerce_nonneg_int

    n = coerce_nonneg_int(value)
    if n is None or n <= 0:
        return int(default)
    return n


def _clip_ai_model(text: object, n: object = None) -> str:
    """Hard-truncate model tag (no ellipsis — Ollama tags must stay runnable)."""
    ceiling = _coerce_ai_model_chars(
        AI_MODEL_CHARS if n is None else n
    )
    return str(text or "").strip()[:ceiling]


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
        "ai_model": _clip_ai_model(model),
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


def normalize_config(
    raw: dict[str, Any] | None,
    *,
    base: Optional[dict[str, Any]] = None,
    ai_model_n: object = None,
) -> dict[str, Any]:
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
        # True→1 must not invent a one-char tag via model[:True]
        # (LAYA / AI-mode glance peers — Ops persist was still bare [:80]).
        lowered = model.lower()
        if model and "coder" not in lowered:
            out["ai_model"] = _clip_ai_model(model, ai_model_n)

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
    # tradermonty #700/#655: refuse bool — float(True)→1.0 / float(False)→0.0
    # invents 100% fees, free legs, or €1 min (xang1234/portfolio AI claim honesty).
    from stock_checker.technical_indicators import _finite_signed

    if out.get("fee_preset") == "custom":
        if "commission_rate" in raw:
            raw_rate = raw.get("commission_rate")
            if _finite_signed(raw_rate):
                r = float(raw_rate)  # type: ignore[arg-type]
                if 0 <= r <= 0.05:
                    out["commission_rate"] = r
        if "commission_min_eur" in raw:
            raw_min = raw.get("commission_min_eur")
            if _finite_signed(raw_min):
                m = float(raw_min)  # type: ignore[arg-type]
                if 0 <= m <= 50:
                    out["commission_min_eur"] = m
    else:
        preset = str(out.get("fee_preset") or DEFAULT_FEE_PRESET)
        rate, min_eur = rates_for_preset(preset)
        out["commission_rate"] = rate
        out["commission_min_eur"] = min_eur
        out["free_legs_per_month"] = free_legs_for_preset(preset)

    if "max_positions" in raw:
        raw_mp = raw.get("max_positions")
        # bool is an int subclass — int(True)==1 must not invent a 1-slot book.
        if not isinstance(raw_mp, bool):
            try:
                mp = int(raw_mp)  # type: ignore[arg-type]
                if 1 <= mp <= 12:
                    out["max_positions"] = mp
            except (TypeError, ValueError):
                pass

    if "min_hold_hours" in raw:
        raw_mh = raw.get("min_hold_hours")
        if _finite_signed(raw_mh):
            mh = float(raw_mh)  # type: ignore[arg-type]
            if 4.0 <= mh <= 168.0:
                out["min_hold_hours"] = mh

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
        raw = json.loads(path.read_text(encoding="utf-8"))
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

# Save-impact short labels (disk_config_payload keys; xang1234 #636).
_CHANGE_SHORT: dict[str, str] = {
    **_PRECEDENCE_SHORT,
    "commission_rate": "fee%",
    "commission_min_eur": "fee min",
    "free_legs_per_month": "free legs",
}

# Book / fee / promote knobs move live paper risk (xang1234 #636 advanced Run).
# Advisory AI + soft gates stay quiet — labels alone hid hot vs calm Saves.
_CHANGE_HOT_KEYS: frozenset[str] = frozenset(
    {
        "fee_preset",
        "commission_rate",
        "commission_min_eur",
        "free_legs_per_month",
        "max_positions",
        "min_hold_hours",
        "promote_experiment_strategy",
    }
)


def _values_differ(a: Any, b: Any) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return bool(a) != bool(b)
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) > 1e-9
    return str(a).strip() != str(b).strip()


_PRECEDENCE_KEY_LIST_LIMIT = 4
# Ops precedence glance line ceiling — bare ``line[:119]+…`` lied when bool
# (ai_model / key-list clip peers).
PRECEDENCE_LINE_CHARS = 120


def _coerce_key_list_limit(
    value: object, default: int = _PRECEDENCE_KEY_LIST_LIMIT
) -> int:
    """Positive Ops precedence key-strip ceiling, or ``default`` when bool/gap/≤0.

    tradermonty #700/#655 + xang1234/portfolio AI: ``True→1`` must not invent
    a one-key override/confirm/env clip via ``keys[:True]``; ``False→0`` must
    not wipe (Close honesty / quiet inventory name-cap peer — precedence
    counts already refused; key-strip ceilings were still open).
    """
    from stock_checker.technical_indicators import coerce_nonneg_int

    n = coerce_nonneg_int(value)
    if n is None or n <= 0:
        return int(default)
    return n


def _coerce_precedence_line_chars(
    value: object, default: int = PRECEDENCE_LINE_CHARS
) -> int:
    """Positive Ops precedence line ceiling, or ``default`` when bool/gap/≤0.

    FinRobot + tradermonty #700/#655 + xang1234/portfolio AI: ``True→1`` must
    not invent a one-char Ops precedence strip via ``line[:True]``;
    ``False→0`` must not wipe (ai_model / key-list clip peers — line truncate
    was still bare ``[:119]+…``).
    """
    from stock_checker.technical_indicators import coerce_nonneg_int

    n = coerce_nonneg_int(value)
    if n is None or n <= 0:
        return int(default)
    return n


def _clip_precedence_line(text: object, n: object = None) -> str:
    """Ellipsis-truncate Ops precedence glance line to a safe ceiling."""
    ceiling = _coerce_precedence_line_chars(
        PRECEDENCE_LINE_CHARS if n is None else n
    )
    s = str(text or "")
    if len(s) <= ceiling:
        return s
    if ceiling <= 1:
        return "…"[:ceiling]
    return s[: ceiling - 1] + "…"


def _format_key_list(
    keys: list[str], *, limit: object = _PRECEDENCE_KEY_LIST_LIMIT
) -> str:
    ceiling = _coerce_key_list_limit(limit)
    short = [_PRECEDENCE_SHORT.get(k, k) for k in keys[:ceiling]]
    bits = " · ".join(short)
    extra = len(keys) - len(short)
    if extra > 0:
        bits = f"{bits} +{extra}" if bits else f"+{extra}"
    return bits


def _coerce_precedence_count(value: object) -> int:
    """Non-neg Ops precedence meter count; bool/gap → 0 (never ``True→1``).

    tradermonty #700/#655 + xang1234/portfolio AI claim honesty — damaged
    bool must not invent a one-key win/ok/env bucket or ``n=1`` sample gap.
    """
    from stock_checker.technical_indicators import coerce_nonneg_int

    n = coerce_nonneg_int(value)
    return 0 if n is None else n


def _precedence_counts(
    override_n: object, confirm_n: object, env_n: object
) -> tuple[int, int, int]:
    return (
        _coerce_precedence_count(override_n),
        _coerce_precedence_count(confirm_n),
        _coerce_precedence_count(env_n),
    )


def _precedence_meter(override_n: object, confirm_n: object, env_n: object) -> str:
    """Compact win/ok/env counts (xang1234 multi-meter + portfolio AI)."""
    override_n, confirm_n, env_n = _precedence_counts(override_n, confirm_n, env_n)
    return f"{override_n} win · {confirm_n} ok · {env_n} env"


def _precedence_lead(override_n: object, confirm_n: object, env_n: object) -> str:
    """Name the strictly largest meter bucket; ties stay silent.

    Counts alone hide which side owns the Ops/env story (xang1234 multi-meter
    lead + portfolio AI speak-both-sides after win/ok/env). Thin/tied samples
    use ``_precedence_sample_gap`` instead of a fake lead.
    """
    override_n, confirm_n, env_n = _precedence_counts(override_n, confirm_n, env_n)
    buckets = (("win", override_n), ("ok", confirm_n), ("env", env_n))
    name, top = max(buckets, key=lambda item: item[1])
    if top <= 0:
        return ""
    if sum(1 for _, n in buckets if n == top) > 1:
        return ""
    return f"lead {name}"


def _precedence_sample_gap(
    override_n: object, confirm_n: object, env_n: object
) -> str:
    """Speak thin/tied when a meter lead would overclaim (display only).

    Empty total stays silent. A single key is compact ``n=1`` (meter ≠ tilt;
    not a mid-band share Δ). Two-plus with no strict lead is ``tied`` (counts
    without a winner). Lead cases stay silent. Soft-allow / LAYA
    ``sample_gap`` parity + xang1234 sample honesty + portfolio AI
    speak-both-sides after precedence share vs Δ. Not a gate.
    """
    override_n, confirm_n, env_n = _precedence_counts(override_n, confirm_n, env_n)
    if _precedence_lead(override_n, confirm_n, env_n):
        return ""
    total = override_n + confirm_n + env_n
    if total <= 0:
        return ""
    if total < 2:
        return "n=1"
    return "tied"


def _precedence_lead_share(
    override_n: object, confirm_n: object, env_n: object
) -> str:
    """Lead row count + ownership % (lead÷total); silent when lead is silent.

    Absolute lead name ≠ how many keys it owns ≠ ownership % (soft-allow /
    sample-lead count≠share + xang1234 / portfolio AI after precedence lead).
    Runner ``vs ok · N`` already names rows; share alone hid the owner's
    count. Speaks ``N · P%`` (sole-bucket still ``N · 100%``).
    """
    override_n, confirm_n, env_n = _precedence_counts(override_n, confirm_n, env_n)
    lead = _precedence_lead(override_n, confirm_n, env_n)
    if not lead:
        return ""
    total = override_n + confirm_n + env_n
    if total <= 0:
        return ""
    buckets = (("win", override_n), ("ok", confirm_n), ("env", env_n))
    top = max(n for _, n in buckets)
    pct = int(round(100.0 * top / total))
    return f"{top} · {pct}%"


# Soft-allow lead margin bands adapted for win/ok/env counts (display only).
PRECEDENCE_LEAD_MARGIN_WIDE = 2
# Ownership spread (lead% − runner%) — same bands as soft-allow share Δ.
PRECEDENCE_LEAD_SHARE_DELTA_WIDE_PP = 20
PRECEDENCE_LEAD_SHARE_DELTA_THIN_PP = 10
# Ops saved-row mtime (RyanJHamby triad + xang1234 seed-age). Display only.
# Fresh <24h · aging <7d · else stale. File exists ≠ recently intended.
PRECEDENCE_FILE_FRESH_HOURS = 24
PRECEDENCE_FILE_AGING_HOURS = 168


def _precedence_lead_margin(
    override_n: object, confirm_n: object, env_n: object
) -> str:
    """Lead−#2 margin when a runner exists; sole-bucket stays silent.

    Ownership % ≠ how far ahead of the next bucket (soft-allow lead margin +
    xang1234 / portfolio AI after precedence lead share). Speaks
    ``ahead wide|thin · +K`` (wide ≥2 · thin =1).
    """
    override_n, confirm_n, env_n = _precedence_counts(override_n, confirm_n, env_n)
    lead = _precedence_lead(override_n, confirm_n, env_n)
    if not lead:
        return ""
    counts = sorted((override_n, confirm_n, env_n), reverse=True)
    top, runner = counts[0], counts[1]
    if runner <= 0:
        return ""
    gap = top - runner
    if gap < 1:
        return ""
    sev = "wide" if gap >= PRECEDENCE_LEAD_MARGIN_WIDE else "thin"
    return f"ahead {sev} · +{gap}"


def _precedence_lead_sides(
    override_n: object, confirm_n: object, env_n: object
) -> str:
    """Name the clear runner after ahead; ahead ≠ who is #2.

    Soft-allow lead sides + xang1234 / portfolio AI speak-both-sides after
    precedence lead margin. Speaks ``vs ok|env|win · N``. Sole-bucket and
    tied runners stay silent.
    """
    override_n, confirm_n, env_n = _precedence_counts(override_n, confirm_n, env_n)
    ahead = _precedence_lead_margin(override_n, confirm_n, env_n)
    if not ahead:
        return ""
    lead = _precedence_lead(override_n, confirm_n, env_n)
    if not lead:
        return ""
    lead_name = lead.rsplit(" ", 1)[-1]
    buckets = (("win", override_n), ("ok", confirm_n), ("env", env_n))
    others = [(name, n) for name, n in buckets if name != lead_name and n > 0]
    if not others:
        return ""
    others.sort(key=lambda item: item[1], reverse=True)
    runner_name, runner_n = others[0]
    if sum(1 for _, n in others if n == runner_n) > 1:
        return ""
    return f"vs {runner_name} · {runner_n}"


def _precedence_lead_sides_share(
    override_n: object, confirm_n: object, env_n: object
) -> str:
    """Runner ownership % when vs already spoke (absolute N ≠ share).

    Soft-allow lead sides share + xang1234 / portfolio AI after precedence
    lead sides. Speaks ``N%`` (runner÷total). Silent when sides is silent.
    """
    override_n, confirm_n, env_n = _precedence_counts(override_n, confirm_n, env_n)
    sides = _precedence_lead_sides(override_n, confirm_n, env_n)
    if not sides:
        return ""
    total = override_n + confirm_n + env_n
    if total <= 0:
        return ""
    # ``vs ok · 2`` → runner count is the last token
    try:
        runner_n = int(sides.rsplit(" · ", 1)[-1])
    except ValueError:
        return ""
    pct = int(round(100.0 * runner_n / total))
    return f"{pct}%"


def _parse_precedence_pct(bit: str) -> int | None:
    """Parse trailing ``N%`` from ``60%`` or ``6 · 60%`` (count≠share)."""
    raw = str(bit or "").strip().rstrip("%")
    if not raw:
        return None
    if " · " in raw:
        raw = raw.rsplit(" · ", 1)[-1]
    try:
        return int(raw)
    except ValueError:
        return None


def _precedence_share_delta_parts(
    override_n: int, confirm_n: int, env_n: int
) -> tuple[str, int] | None:
    """Lean + signed pp for lead% − runner%; None when runner share is silent."""
    lead_pct = _parse_precedence_pct(
        _precedence_lead_share(override_n, confirm_n, env_n)
    )
    runner_pct = _parse_precedence_pct(
        _precedence_lead_sides_share(override_n, confirm_n, env_n)
    )
    if lead_pct is None or runner_pct is None:
        return None
    delta = int(lead_pct) - int(runner_pct)
    mag = abs(delta)
    if mag < 1:
        return None
    if mag >= PRECEDENCE_LEAD_SHARE_DELTA_WIDE_PP:
        sev = "wide"
    elif mag < PRECEDENCE_LEAD_SHARE_DELTA_THIN_PP:
        sev = "thin"
    else:
        sev = "mid"
    return sev, delta


def _precedence_lead_sides_share_delta(
    override_n: int, confirm_n: int, env_n: int
) -> str:
    """Lead% − runner% when both shares already spoke (two % ≠ the spread).

    Soft-allow share Δ + xang1234 / portfolio AI after precedence runner %.
    Speaks ``share Δ wide|thin · ±Npp`` (wide ≥20pp · thin <10pp; mid silent).
    Silent when runner share is silent.
    """
    parts = _precedence_share_delta_parts(override_n, confirm_n, env_n)
    if parts is None:
        return ""
    sev, delta = parts
    if sev == "mid":
        return ""
    sign = f"+{delta}" if delta > 0 else str(delta)
    return f"share Δ {sev} · {sign}pp"


def _precedence_lead_sides_share_delta_line(
    override_n: int, confirm_n: int, env_n: int
) -> str:
    """Compact Δ±Npp for the 96-char Ops line (severity stays on the field)."""
    bit = _precedence_lead_sides_share_delta(override_n, confirm_n, env_n)
    if not bit:
        return ""
    sign = bit.rsplit(" · ", 1)[-1]
    if not sign.endswith("pp"):
        return ""
    return f"Δ{sign}"


def _precedence_ahead_lean(override_n: int, confirm_n: int, env_n: int) -> str:
    """``wide``/``thin`` from ahead, else empty (ahead always leanish when it spoke)."""
    ahead = _precedence_lead_margin(override_n, confirm_n, env_n)
    if not ahead.startswith("ahead "):
        return ""
    sev = ahead.split(" · ", 1)[0].removeprefix("ahead ").strip()
    if sev not in ("wide", "thin"):
        return ""
    return sev


def _precedence_lead_sides_share_vs_delta(
    override_n: int, confirm_n: int, env_n: int
) -> str:
    """Count-ahead lean vs ownership-Δ lean (soft-allow share vs Δ).

    Ahead is always wide/thin when vs spoke. Clash when Δ is mid (exactly one
    lean spoke). Align when both leanish and equal. Different leans stay
    silent — xang1234 + portfolio AI after precedence share Δ. Display only.
    """
    ahead = _precedence_ahead_lean(override_n, confirm_n, env_n)
    if ahead not in ("wide", "thin"):
        return ""
    parts = _precedence_share_delta_parts(override_n, confirm_n, env_n)
    if parts is None:
        return ""
    share, _delta = parts
    if share == "mid":
        return f"share vs Δ clash · ×{ahead} · %mid"
    if share == ahead:
        return f"share vs Δ align · {ahead}"
    return ""


def _precedence_lead_sides_share_vs_delta_line(
    override_n: int, confirm_n: int, env_n: int
) -> str:
    """Compact ``=W``/``=T`` (align) or ``×T/%m`` (clash) for the 96-char line."""
    bit = _precedence_lead_sides_share_vs_delta(override_n, confirm_n, env_n)
    if bit.startswith("share vs Δ clash · ×") and bit.endswith(" · %mid"):
        ahead = bit.removeprefix("share vs Δ clash · ×").split(" · ", 1)[0]
        if ahead in ("wide", "thin"):
            return f"×{ahead[0].upper()}/%m"
        return ""
    if bit.startswith("share vs Δ align · "):
        sev = bit.rsplit(" · ", 1)[-1]
        if sev in ("wide", "thin"):
            return f"={sev[0].upper()}"
    return ""


def _config_age_label(age_sec: float) -> str:
    """Short wall age for Ops file mtime (same steps as scan freshness)."""
    sec = max(0, int(age_sec))
    if sec < 60:
        return "just now"
    if sec < 3600:
        return f"{sec // 60}m ago"
    if sec < 36 * 3600:
        return f"{sec // 3600}h ago"
    return f"{sec // 86400}d ago"


def _ops_file_age(
    path: Path, *, now: datetime | None = None
) -> dict[str, Any]:
    """Fresh/aging/stale for trader_config.json mtime (display only)."""
    empty = {
        "file_age_hours": None,
        "file_freshness": "",
        "file_age_label": "",
        "file_age_bit": "",
        "file_age_line": "",
    }
    try:
        mtime = float(path.stat().st_mtime)
    except OSError:
        return empty
    clock = now or datetime.now(timezone.utc)
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=timezone.utc)
    when = datetime.fromtimestamp(mtime, tz=timezone.utc)
    age_sec = max(0.0, (clock - when).total_seconds())
    hours = age_sec / 3600.0
    if hours < PRECEDENCE_FILE_FRESH_HOURS:
        freshness = "fresh"
    elif hours < PRECEDENCE_FILE_AGING_HOURS:
        freshness = "aging"
    else:
        freshness = "stale"
    label = _config_age_label(age_sec)
    short = "now" if label == "just now" else label.removesuffix(" ago")
    return {
        "file_age_hours": round(hours, 2),
        "file_freshness": freshness,
        "file_age_label": label,
        "file_age_bit": f"saved {label} · {freshness}",
        "file_age_line": f"{short} {freshness}",
    }


def _with_saved_age(line: str, age_bit: str) -> str:
    """Put compact saved-age early so the clip keeps it (before meter)."""
    if not age_bit:
        return line
    for needle in ("file · Ops wins · ", "file · partial · "):
        if line.startswith(needle):
            return f"{needle}{age_bit} · {line[len(needle):]}"
    return line


def _precedence_core(
    override_n: object, confirm_n: object, env_n: object
) -> tuple[str, str]:
    """Meter + optional lead (+ N · P% + ahead + vs + runner % or Δ[+align]).

    When no lead, thin/tied samples speak ``n=1`` / ``tied`` after the meter
    (soft-allow / LAYA sample_gap parity — silent gap hid that counts are
    not a tilt). Lead share speaks ``N · P%`` so runner ``vs ok · N`` ≠
    owner's count alone.
    """
    override_n, confirm_n, env_n = _precedence_counts(override_n, confirm_n, env_n)
    meter = _precedence_meter(override_n, confirm_n, env_n)
    lead = _precedence_lead(override_n, confirm_n, env_n)
    if not lead:
        gap = _precedence_sample_gap(override_n, confirm_n, env_n)
        if gap:
            return meter, f"{meter} · {gap}"
        return meter, meter
    share = _precedence_lead_share(override_n, confirm_n, env_n)
    bit = f"{lead} · {share}" if share else lead
    ahead = _precedence_lead_margin(override_n, confirm_n, env_n)
    if ahead:
        bit = f"{bit} · {ahead}"
        sides = _precedence_lead_sides(override_n, confirm_n, env_n)
        if sides:
            runner_share = _precedence_lead_sides_share(override_n, confirm_n, env_n)
            delta_line = _precedence_lead_sides_share_delta_line(
                override_n, confirm_n, env_n
            )
            vs_delta = _precedence_lead_sides_share_vs_delta_line(
                override_n, confirm_n, env_n
            )
            if delta_line:
                # Spread replaces runner %. Align: Δ+20pp → Δ+20=W (same width).
                if vs_delta.startswith("=") and delta_line.endswith("pp"):
                    bit = f"{bit} · {sides} · {delta_line[:-2]}{vs_delta}"
                elif vs_delta.startswith("="):
                    bit = f"{bit} · {sides} · {delta_line}{vs_delta}"
                else:
                    bit = f"{bit} · {sides} · {delta_line}"
            elif vs_delta.startswith("×"):
                # Clash replaces runner % (mid Δ is silent; count-ahead spoke).
                bit = f"{bit} · {sides} · {vs_delta}"
            elif runner_share:
                bit = f"{bit} · {sides} · {runner_share}"
            else:
                bit = f"{bit} · {sides}"
    return meter, f"{meter} · {bit}"


def config_precedence_status(
    data_dir: Path | str,
    *,
    now: datetime | None = None,
    line_n: object = None,
) -> dict[str, Any]:
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
    A multi-meter (N win · N ok · N env) speaks early so counts survive the
    96-char truncate when key names are long (xang1234 + portfolio AI meter).
    When one meter bucket is strictly largest, speak ``lead win|ok|env``
    right after the meter, then ownership ``N · P%`` (row count then
    lead÷total; sole-bucket still speaks 100%; runner ``vs ok · N`` ≠
    owner's count — sample-lead / soft-allow gap-symbol parity), then
    ``ahead wide|thin · +K`` when a runner-up bucket exists (share ≠
    margin; sole-bucket omits ahead), then ``vs ok|env|win · N`` naming
    the clear runner (ahead ≠ who is #2; tied runners silent), then
    runner ownership ``N%`` (absolute count ≠ share of the meter), then
    ``share Δ wide|thin · ±Npp`` (lead% − runner%; wide ≥20pp · thin
    <10pp; mid silent — two % ≠ the spread), then ``share vs Δ clash ·
    ×sev · %mid`` when Δ is mid (count-ahead spoke, ownership spread did
    not) or ``share vs Δ align · sev`` when both leanish match (mismatch
    stays silent). The Ops line speaks compact ``Δ±N=W``/``=T`` (align,
    same width as ``Δ±Npp``) or ``×T/%m``/``×W/%m`` (clash in place of
    runner %) so the 96-char clip keeps the vs-Δ bit.
    When no lead: 1 key speaks compact ``n=1``; ≥2 with no strict lead
    speaks ``tied`` after the meter (``sample_gap``; lead cases stay silent
    on gap) — soft-allow / LAYA sample honesty parity; silent gap hid that
    the meter is not a tilt.
    When a saved file exists, also speak ``saved {age} · fresh|aging|stale``
    from mtime (RyanJHamby triad + xang1234 seed-age; fresh <24h · aging <7d).
    File exists ≠ recently intended. Age sits before the meter so truncate
    keeps it (compact ``6h fresh`` / ``2d aging`` / ``10d stale`` on the Ops
    line; API keeps the full ``saved {age} · band``). Stale (≥7d) escalates
    ``tone`` to ``warn`` — a long age label on an override line is not a
    warn (RyanJHamby scan-fresh tone + xang1234 seed-age). Aging stays the
    source tone. No file stays silent on age. Line clip is 120 chars so
    age + meter still leave room for lead.
    Unreadable JSON speaks ``Ops file unreadable`` (warn · env lean). A
    parseable non-object (list/string/null) speaks ``Ops file lean`` the
    same way — xang1234 #540 / #498 damaged-section fall-back; do not
    disguise it as a quiet partial Ops row. Empty ``{}`` stays partial.
    """
    path = config_path(data_dir)
    env = _env_defaults()
    n_keys = len(PRECEDENCE_KEYS)
    meter0, core0 = _precedence_core(0, 0, n_keys)
    lead0 = _precedence_lead(0, 0, n_keys)
    share0 = _precedence_lead_share(0, 0, n_keys)
    margin0 = _precedence_lead_margin(0, 0, n_keys)
    sides0 = _precedence_lead_sides(0, 0, n_keys)
    sides_share0 = _precedence_lead_sides_share(0, 0, n_keys)
    sides_delta0 = _precedence_lead_sides_share_delta(0, 0, n_keys)
    sides_vs_delta0 = _precedence_lead_sides_share_vs_delta(0, 0, n_keys)
    gap0 = _precedence_sample_gap(0, 0, n_keys)
    empty = {
        "overrides": [],
        "confirms": [],
        "env_fallbacks": list(PRECEDENCE_KEYS),
        "override_n": 0,
        "confirm_n": 0,
        "env_fallback_n": n_keys,
        "meter": meter0,
        "lead": lead0,
        "lead_share": share0,
        "lead_margin": margin0,
        "lead_sides": sides0,
        "lead_sides_share": sides_share0,
        "lead_sides_share_delta": sides_delta0,
        "lead_sides_share_vs_delta": sides_vs_delta0,
        "sample_gap": gap0,
        "file_age_hours": None,
        "file_freshness": "",
        "file_age_label": "",
        "file_age_bit": "",
        "file_age_line": "",
        "ready": True,
    }
    if not path.is_file():
        return {
            **empty,
            "source": "env",
            "tone": "env",
            "line": f"env · no Ops file · {core0}",
        }

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            **empty,
            "source": "env",
            "tone": "warn",
            "line": f"env · Ops file unreadable · {core0}",
        }

    # xang1234 #540 lean-fallback: non-object sections fall back with a warn —
    # do not pretend a list/string/null is a quiet partial Ops row.
    if not isinstance(raw, dict):
        return {
            **empty,
            "source": "env",
            "tone": "warn",
            "line": f"env · Ops file lean · {core0}",
        }

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

    o_n, c_n, e_n = _precedence_counts(
        len(overrides), len(confirms), len(env_fallbacks)
    )
    meter, core = _precedence_core(o_n, c_n, e_n)
    lead = _precedence_lead(o_n, c_n, e_n)
    lead_share = _precedence_lead_share(o_n, c_n, e_n)
    lead_margin = _precedence_lead_margin(o_n, c_n, e_n)
    lead_sides = _precedence_lead_sides(o_n, c_n, e_n)
    lead_sides_share = _precedence_lead_sides_share(o_n, c_n, e_n)
    lead_sides_share_delta = _precedence_lead_sides_share_delta(o_n, c_n, e_n)
    lead_sides_share_vs_delta = _precedence_lead_sides_share_vs_delta(o_n, c_n, e_n)
    sample_gap = _precedence_sample_gap(o_n, c_n, e_n)
    if overrides:
        bits = _format_key_list(overrides)
        # Meter (+ lead + share + ahead + vs + runner % + Δ + vs-Δ) before names.
        line = f"file · Ops wins · {core} · {bits}"
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
        line = f"file · partial · {core} · env for {bits}"
        if confirms:
            conf = _format_key_list(confirms, limit=2)
            line = f"{line} · confirms {conf}"
        tone = "partial"
    else:
        line = f"file · Ops wins · {core} · matches env"
        tone = "file"

    age = _ops_file_age(path, now=now)
    line = _with_saved_age(line, str(age.get("file_age_line") or ""))
    # True→1 must not invent a one-char strip via line[:True]
    # (ai_model / key-list peers — line truncate was still bare [:119]+…).
    line = _clip_precedence_line(line, line_n)
    # Age spoke ≠ severity: stale saved row is a warn, not a quiet override.
    if age.get("file_freshness") == "stale" and tone != "warn":
        tone = "warn"

    return {
        "source": "file",
        "overrides": overrides,
        "confirms": confirms,
        "env_fallbacks": env_fallbacks,
        "override_n": o_n,
        "confirm_n": c_n,
        "env_fallback_n": e_n,
        "meter": meter,
        "lead": lead,
        "lead_share": lead_share,
        "lead_margin": lead_margin,
        "lead_sides": lead_sides,
        "lead_sides_share": lead_sides_share,
        "lead_sides_share_delta": lead_sides_share_delta,
        "lead_sides_share_vs_delta": lead_sides_share_vs_delta,
        "sample_gap": sample_gap,
        "file_age_hours": age.get("file_age_hours"),
        "file_freshness": age.get("file_freshness") or "",
        "file_age_label": age.get("file_age_label") or "",
        "file_age_bit": age.get("file_age_bit") or "",
        "file_age_line": age.get("file_age_line") or "",
        "tone": tone,
        "line": line,
        "ready": True,
    }


def disk_config_payload(cfg: dict[str, Any]) -> dict[str, Any]:
    """Canonical on-disk shape for ``trader_config.json`` (no secrets)."""
    fee_preset = str(cfg.get("fee_preset") or DEFAULT_FEE_PRESET)
    return {
        "ai_mode": cfg["ai_mode"],
        "ai_model": cfg["ai_model"],
        "ai_multi_role": bool(cfg["ai_multi_role"]),
        "regime_gate": bool(cfg["regime_gate"]),
        "rs_gate": bool(cfg.get("rs_gate", True)),
        "breadth_gate": bool(cfg.get("breadth_gate", True)),
        "fee_preset": fee_preset,
        "commission_rate": float(cfg["commission_rate"]),
        "commission_min_eur": float(cfg["commission_min_eur"]),
        "free_legs_per_month": int(
            cfg.get("free_legs_per_month") or free_legs_for_preset(fee_preset)
        ),
        "max_positions": int(cfg["max_positions"]),
        "min_hold_hours": float(cfg["min_hold_hours"]),
        "promote_experiment_strategy": bool(
            cfg.get("promote_experiment_strategy", False)
        ),
    }


def trader_config_changed_keys(
    data_dir: Path | str, updates: dict[str, Any] | None
) -> list[str]:
    """Sorted disk keys a Save would rewrite (xang1234 #636 impact honesty).

    Missing Ops file returns every payload key (first write materializes the
    whole row). Equal payload returns ``[]`` (no-op / skip path).
    """
    current = load_trader_config(data_dir)
    merged = normalize_config(
        updates if isinstance(updates, dict) else {}, base=current
    )
    new_payload = disk_config_payload(merged)
    if not config_path(data_dir).is_file():
        return sorted(new_payload.keys())
    old_payload = disk_config_payload(current)
    return sorted(
        key
        for key, val in new_payload.items()
        if _values_differ(val, old_payload.get(key))
    )


def config_changed_impact_severity(keys: list[str] | None) -> str:
    """``hot`` when any book/fee/promote knob moved; else ``quiet`` (#636).

    Empty / unknown → ``\"\"``. Hot wins mixed Saves (adverse severity).
    """
    clean = [str(k).strip() for k in (keys or []) if str(k).strip()]
    if not clean:
        return ""
    if any(k in _CHANGE_HOT_KEYS for k in clean):
        return "hot"
    return "quiet"


def config_changed_impact_warn(keys: list[str] | None) -> bool:
    """True when Save impact severity is hot (book/fee/promote)."""
    return config_changed_impact_severity(keys) == "hot"


def config_save_open_cash_venues(
    *, now: datetime | None = None
) -> list[str]:
    """Cash sleeves open right now (US / Xetra) — mid-session Save context.

    xang1234 #636 when-to-run: hot Runs during a live session need a louder
    confirm. Crypto is 24/7 and stays out of this list (book/fee knobs still
    apply, but the mid-session warn is about cash RTH).
    """
    from .market_hours import (
        is_us_cash_session_closed,
        is_xetra_session_closed,
    )

    open_cash: list[str] = []
    if not is_us_cash_session_closed(now=now):
        open_cash.append("US")
    if not is_xetra_session_closed(now=now):
        open_cash.append("Xetra")
    return open_cash


def _config_save_session_shares(
    open_cash: list[str] | None,
) -> tuple[list[str], int, int, str, str, str] | None:
    """Parse open cash into named venues + open/closed severity bands.

    Returns ``(named, n_open, n_closed, share_bit, open_sev, closed_sev)``
    or ``None`` when all cash closed (no mid-session speak).
    """
    clean = [str(v).strip() for v in (open_cash or []) if str(v).strip()]
    if not clean:
        return None
    named = clean[:2]
    n_open = min(len(clean), 2)
    cash_venues = 2
    n_closed = cash_venues - n_open
    if n_open >= 2:
        share = " · all cash"
    elif n_open == 1:
        share = " · half cash"
    else:
        share = ""
    open_share_pct = int(round(100.0 * n_open / cash_venues))
    # Same floors as Hours attention cash share: hot ≥75 · quiet ≤25.
    if open_share_pct >= 75:
        open_sev = "hot"
    elif open_share_pct <= 25:
        open_sev = "quiet"
    else:
        open_sev = "ok"
    closed_share_pct = int(round(100.0 * n_closed / cash_venues))
    # Same floors as Hours attention_open_share: strong ≥75 · thin <50.
    if closed_share_pct >= 75:
        closed_sev = "strong"
    elif closed_share_pct < 50:
        closed_sev = "thin"
    else:
        closed_sev = "ok"
    return named, n_open, n_closed, share, open_sev, closed_sev


def config_save_session_vs_closed_lean(
    open_cash: list[str] | None,
) -> str:
    """Compact ``align · hot|thin`` / ``clash · open hot · closed ok``.

    Hours attn vs open lean parity after mid-session vs-closed sides.
    Extremes only; half cash (both mid) stays silent.
    """
    parsed = _config_save_session_shares(open_cash)
    if parsed is None:
        return ""
    _, _, _, _, open_sev, closed_sev = parsed
    open_lean = open_sev in {"hot", "quiet"}
    closed_lean = closed_sev in {"strong", "thin"}
    if open_lean and closed_lean:
        matched = (
            open_sev == "hot" and closed_sev == "thin"
        ) or (open_sev == "quiet" and closed_sev == "strong")
        if matched:
            return f"align · {open_sev}|{closed_sev}"
        return f"clash · open {open_sev} · closed {closed_sev}"
    if open_lean != closed_lean:
        return f"clash · open {open_sev} · closed {closed_sev}"
    return ""


def config_save_session_vs_closed_warn(
    open_cash: list[str] | None,
) -> bool:
    """True when open vs closed lean is adverse (hot|thin align or clash).

    Favorable quiet|strong align stays calm; half mid stays silent.
    Hours attention_vs_open_warn parity — label ≠ severity.
    """
    lean = config_save_session_vs_closed_lean(open_cash)
    if not lean:
        return False
    if lean.startswith("align · hot|thin"):
        return True
    if lean.startswith("clash ·"):
        parsed = _config_save_session_shares(open_cash)
        if parsed is None:
            return False
        _, _, _, _, open_sev, closed_sev = parsed
        return open_sev == "hot" or closed_sev == "thin"
    return False


def format_config_save_session_bit(open_cash: list[str] | None) -> str:
    """Compact ``mid session · US open · half cash · vs 1 closed · 50%``.

    Empty when all cash closed — quiet nights need no mid-session warn.
    Venue names alone hid partial vs total cash live (Hours attention
    half/all cash parity). Open share alone hid remaining dark sleeves
    (Hours attention vs open + portfolio AI speak-both-sides / count≠share).
    Sides alone hid lean agreement (Hours attn vs open lean). Lean owns
    the relationship on the clip; vs-closed % stays computable from shares.
    Crypto stays out of the cash denom (two sleeves: US + Xetra).
    """
    parsed = _config_save_session_shares(open_cash)
    if parsed is None:
        return ""
    named_list, _n_open, n_closed, share, _open_sev, closed_sev = parsed
    named = " · ".join(named_list)
    lean = config_save_session_vs_closed_lean(open_cash)
    if lean:
        # Lean owns the clip (Hours attn vs open); drop vs-closed %.
        return f"mid session · {named} open{share} · open vs closed {lean}"
    closed_share_pct = int(round(100.0 * n_closed / 2))
    vs_closed = f"vs {n_closed} closed"
    if closed_sev in {"strong", "thin"}:
        vs_closed = f"{vs_closed} · {closed_sev} · {closed_share_pct}%"
    else:
        vs_closed = f"{vs_closed} · {closed_share_pct}%"
    return f"mid session · {named} open{share} · {vs_closed}"


def format_config_save_confirm(
    keys: list[str] | None,
    *,
    open_cash: list[str] | None = None,
) -> str:
    """Browser confirm copy when Save would move hot knobs (xang1234 #636).

    Empty when quiet / no-op — advisory AI/gates save without a prompt.
    Hot book/fee/promote/hold asks once before the mutating PUT.
    When cash RTH is open, also speak mid-session (when-to-run honesty).
    """
    if not config_changed_impact_warn(keys):
        return ""
    bit = format_config_changed_bit(keys)
    if not bit:
        return ""
    session = format_config_save_session_bit(open_cash)
    if session:
        return f"Save moves live paper risk ({bit}) · {session}. Continue?"
    return f"Save moves live paper risk ({bit}). Continue?"


def format_config_changed_bit(
    keys: list[str] | None, *, limit: object = _PRECEDENCE_KEY_LIST_LIMIT
) -> str:
    """Compact ``Δ hot · AI · hold`` / ``Δ quiet · AI`` for Ops glance / toast.

    xang1234 #636: advanced jobs got a red Run — bare knob names hid whether
    the Save moved live book/fee/promote risk vs advisory-only knobs.
    """
    if not keys:
        return ""
    clean = [str(k).strip() for k in keys if str(k).strip()]
    if not clean:
        return ""
    severity = config_changed_impact_severity(clean)
    # Prefer human short labels; fee rate/min/legs collapse under fees when
    # fee_preset already spoke, else keep the specific knob.
    labeled: list[str] = []
    seen_fees = False
    for key in clean:
        if key in {
            "commission_rate",
            "commission_min_eur",
            "free_legs_per_month",
        }:
            if "fee_preset" in clean or seen_fees:
                continue
            labeled.append("fees")
            seen_fees = True
            continue
        labeled.append(_CHANGE_SHORT.get(key, _PRECEDENCE_SHORT.get(key, key)))
    ceiling = _coerce_key_list_limit(limit)
    bits = " · ".join(labeled[:ceiling])
    extra = len(labeled) - min(len(labeled), ceiling)
    if extra > 0:
        bits = f"{bits} +{extra}" if bits else f"+{extra}"
    if not bits:
        return ""
    if severity:
        return f"Δ {severity} · {bits}"
    return f"Δ {bits}"


def trader_config_would_change(
    data_dir: Path | str, updates: dict[str, Any] | None
) -> bool:
    """True when a Save would rewrite knobs (xang1234 #623 refuse-skip-only).

    Missing Ops file always counts as a change (first write materializes the
    saved-row precedence story). Equal payload vs current effective config is
    a no-op — refuse before audit / disk write.
    """
    return bool(trader_config_changed_keys(data_dir, updates))


def save_trader_config(data_dir: Path | str, updates: dict[str, Any]) -> dict[str, Any]:
    """Validate, merge with current, write JSON. Returns the saved config."""
    current = load_trader_config(data_dir)
    merged = normalize_config(updates, base=current)
    path = config_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = disk_config_payload(merged)
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return payload
