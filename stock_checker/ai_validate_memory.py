"""Ring buffer of recent AI validate debates (FinRobot / TradingAgents style).

Persists bull/bear/risk notes from multi-role validate so Ideas can show a
transcript. Display only — not an entry gate. Lives under data/ (gitignored).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VALIDATE_MEMORY_FILE = "ai_validate_memory.json"
VALIDATE_MEMORY_CAP = 24
IDEAS_LIMIT = 8


def _default_data_dir() -> Path:
    return Path(os.getenv("DATA_DIR", "data"))


def validate_memory_path(data_dir: Path | str) -> Path:
    return Path(data_dir) / VALIDATE_MEMORY_FILE


def _clip(text: Any, n: int = 160) -> str:
    s = str(text or "").strip()
    if len(s) <= n:
        return s
    return s[: n - 1] + "…"


def _score(raw: Any) -> int:
    try:
        return max(-100, min(100, int(float(raw or 0))))
    except (TypeError, ValueError):
        return 0


def load_ai_validate_memory(data_dir: Path | str) -> list[dict[str, Any]]:
    path = validate_memory_path(data_dir)
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return []
    events = raw.get("events") if isinstance(raw, dict) else None
    if not isinstance(events, list):
        return []
    return [e for e in events if isinstance(e, dict)]


def recent_ai_debates(
    data_dir: Path | str, *, limit: int = IDEAS_LIMIT
) -> list[dict[str, Any]]:
    """Newest-first debates for Ideas (display only)."""
    lim = max(0, int(limit))
    events = load_ai_validate_memory(data_dir)
    return list(reversed(events[-lim:])) if lim else []


def record_ai_validate(
    data_dir: Path | str,
    ai_result: dict[str, Any] | None,
    *,
    symbol: str | None = None,
    kept: bool | None = None,
    cap: int = VALIDATE_MEMORY_CAP,
) -> None:
    """Append one validate debate; keep the newest ``cap`` rows."""
    if not isinstance(ai_result, dict) or not ai_result:
        return
    sym = str(symbol or ai_result.get("symbol") or "").strip().upper()
    if not sym:
        return
    action = str(ai_result.get("action") or "HOLD").upper()
    if action not in {"BUY", "SELL", "HOLD"}:
        action = "HOLD"
    confidence = str(ai_result.get("confidence") or "").upper()
    if confidence not in {"HIGH", "MEDIUM", "LOW"}:
        confidence = ""
    reasons = ai_result.get("reasons") if isinstance(ai_result.get("reasons"), list) else []
    consensus = _clip(ai_result.get("reasoning") or "")
    if not consensus and reasons:
        # Multi-role packs consensus last; single-role uses first reason.
        consensus = _clip(reasons[-1] if len(reasons) > 1 else reasons[0])
    event = {
        "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "symbol": sym,
        "action": action,
        "confidence": confidence,
        "score": _score(ai_result.get("score")),
        "parse_mode": str(ai_result.get("parse_mode") or ""),
        "multi_role_gated": bool(ai_result.get("multi_role_gated")),
        "bull_bias": str(ai_result.get("bull_bias") or "").upper(),
        "bear_bias": str(ai_result.get("bear_bias") or "").upper(),
        "risk_ok": ai_result.get("risk_ok"),
        "bull_note": _clip(ai_result.get("bull_note") or ""),
        "bear_note": _clip(ai_result.get("bear_note") or ""),
        "risk_note": _clip(ai_result.get("risk_note") or ""),
        "consensus": consensus,
        "kept": None if kept is None else bool(kept),
    }
    # Recover notes from reasons when multi-role fields missing (older payloads).
    if not event["bull_note"] and reasons:
        for line in reasons:
            s = str(line or "")
            if s.lower().startswith("bull:"):
                event["bull_note"] = _clip(s.split(":", 1)[-1])
            elif s.lower().startswith("bear:"):
                event["bear_note"] = _clip(s.split(":", 1)[-1])
            elif s.lower().startswith("risk:"):
                event["risk_note"] = _clip(s.split(":", 1)[-1])
    path = validate_memory_path(data_dir)
    events = load_ai_validate_memory(data_dir)
    events.append(event)
    keep = max(1, int(cap))
    events = events[-keep:]
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"updated_at": events[-1]["at"], "events": events}, indent=2)
            + "\n"
        )
    except OSError:
        pass
