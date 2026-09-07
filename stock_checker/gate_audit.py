"""Shared soft-gate logging (fail-open visibility — review A5).

Prints soft-allows and keeps a short desk-readable ring buffer under data/.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SOFT_ALLOW_FILE = "gate_soft_allows.json"
SOFT_ALLOW_CAP = 40
_SOFT_MARKERS = ("unknown", "no bars", "skip_no_bars", "insufficient")


def _default_data_dir() -> Path:
    return Path(os.getenv("DATA_DIR", "data"))


def soft_allow_path(data_dir: Path | str) -> Path:
    return Path(data_dir) / SOFT_ALLOW_FILE


def is_soft_allow_reason(reason: str) -> bool:
    r = (reason or "").lower()
    return any(m in r for m in _SOFT_MARKERS)


def load_soft_allows(data_dir: Path | str) -> list[dict[str, Any]]:
    path = soft_allow_path(data_dir)
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


def recent_soft_allows(
    data_dir: Path | str, *, limit: int = 12
) -> list[dict[str, Any]]:
    """Newest-first soft-allows for Ops (display only)."""
    lim = max(0, int(limit))
    events = load_soft_allows(data_dir)
    return list(reversed(events[-lim:])) if lim else []


def record_soft_allow(
    data_dir: Path | str,
    gate: str,
    reason: str,
    *,
    cap: int = SOFT_ALLOW_CAP,
) -> None:
    """Append one soft-allow; keep the newest ``cap`` rows."""
    if not is_soft_allow_reason(reason):
        return
    path = soft_allow_path(data_dir)
    events = load_soft_allows(data_dir)
    events.append(
        {
            "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "gate": str(gate or "").strip() or "?",
            "reason": str(reason or "").strip()[:240],
        }
    )
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


def log_soft_allow(
    gate: str,
    reason: str,
    data_dir: Path | str | None = None,
) -> None:
    """Print + persist when a gate allows because data is missing / unknown."""
    if not is_soft_allow_reason(reason):
        return
    print(f"   ⚪ Soft-allow [{gate}]: {reason}")
    record_soft_allow(data_dir or _default_data_dir(), gate, reason)
