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
# tradermonty #437: soft-allows older than this are expired diagnostics.
SOFT_ALLOW_FRESH_HOURS = 24.0
# xang1234 / RyanJHamby scan-age triad: aging before expired (display only).
SOFT_ALLOW_AGING_HOURS = 12.0
_SOFT_MARKERS = (
    "unknown",
    "no bars",
    "skip_no_bars",
    "insufficient",
    "empty yahoo",
    "empty earnings",
    "malformed yahoo",
)


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


def parse_soft_allow_at(raw: Any) -> datetime | None:
    """Parse a soft-allow ``at`` stamp (UTC). Unknown shapes → None."""
    if raw is None:
        return None
    if isinstance(raw, datetime):
        if raw.tzinfo is None:
            return raw.replace(tzinfo=timezone.utc)
        return raw.astimezone(timezone.utc)
    text = str(raw).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        stamp = datetime.fromisoformat(text)
    except ValueError:
        return None
    if stamp.tzinfo is None:
        return stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone(timezone.utc)


def soft_allow_age_hours(
    at: Any,
    *,
    now: datetime | None = None,
) -> float | None:
    """Hours since ``at``, or None when the stamp is missing/unparseable."""
    stamp = parse_soft_allow_at(at)
    if stamp is None:
        return None
    clock = now if now is not None else datetime.now(timezone.utc)
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=timezone.utc)
    else:
        clock = clock.astimezone(timezone.utc)
    return max(0.0, (clock - stamp).total_seconds() / 3600.0)


def soft_allow_is_expired(
    at: Any,
    *,
    now: datetime | None = None,
    fresh_hours: float = SOFT_ALLOW_FRESH_HOURS,
) -> bool:
    """True when age is known and older than ``fresh_hours``.

    Missing/unparseable ``at`` stays fresh (fail-open — do not hide the row).
    """
    age = soft_allow_age_hours(at, now=now)
    if age is None:
        return False
    return age > float(fresh_hours)


def soft_allow_freshness(
    at: Any,
    *,
    now: datetime | None = None,
    aging_hours: float = SOFT_ALLOW_AGING_HOURS,
    fresh_hours: float = SOFT_ALLOW_FRESH_HOURS,
) -> str:
    """fresh / aging / expired / unknown — scan-age triad for fail-open rows.

    Missing stamp → ``unknown`` (speak, do not hide). Not an entry gate.
    """
    age = soft_allow_age_hours(at, now=now)
    if age is None:
        return "unknown"
    aging = float(aging_hours)
    expire = float(fresh_hours)
    if expire < aging:
        expire = aging
    if age > expire:
        return "expired"
    if age > aging:
        return "aging"
    return "fresh"


def enrich_soft_allows(
    events: list[dict[str, Any]] | None,
    *,
    now: datetime | None = None,
    fresh_hours: float = SOFT_ALLOW_FRESH_HOURS,
    aging_hours: float = SOFT_ALLOW_AGING_HOURS,
) -> list[dict[str, Any]]:
    """Copy rows with freshness + ``expired`` + ``age_hours`` (display only)."""
    out: list[dict[str, Any]] = []
    for row in events or []:
        if not isinstance(row, dict):
            continue
        copy = dict(row)
        age = soft_allow_age_hours(copy.get("at"), now=now)
        copy["age_hours"] = None if age is None else round(age, 2)
        band = soft_allow_freshness(
            copy.get("at"),
            now=now,
            aging_hours=aging_hours,
            fresh_hours=fresh_hours,
        )
        copy["freshness"] = band
        copy["expired"] = band == "expired"
        out.append(copy)
    return out


def soft_allow_band_tally(
    events: list[dict[str, Any]] | None,
    *,
    band: str,
) -> list[tuple[str, int]]:
    """Gate counts for one freshness band — sorted by count desc, then gate.

    ``band`` is ``fresh`` / ``aging`` / ``expired``. Expired also matches the
    legacy ``expired`` bool when ``freshness`` is missing. Fresh also matches
    ``unknown`` stamps (fail-open — same as glance ``fresh_count``).
    """
    want = str(band or "").strip().casefold()
    counts: dict[str, int] = {}
    for row in events or []:
        if not isinstance(row, dict):
            continue
        freshness = str(row.get("freshness") or "").strip().casefold()
        if not freshness and want == "expired" and row.get("expired"):
            freshness = "expired"
        if want == "fresh":
            if freshness not in ("fresh", "unknown"):
                continue
        elif freshness != want:
            continue
        gate = str(row.get("gate") or "?").strip() or "?"
        counts[gate] = counts.get(gate, 0) + 1
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))


def format_soft_allow_band_tally(
    events: list[dict[str, Any]] | None,
    *,
    band: str,
) -> str:
    """Compact ``regime×2 · rs×1`` for one freshness band."""
    parts = [
        f"{gate}×{n}" for gate, n in soft_allow_band_tally(events, band=band)
    ]
    return " · ".join(parts)


def expired_soft_allow_tally(
    events: list[dict[str, Any]] | None,
) -> list[tuple[str, int]]:
    """Gate counts for expired rows only (tradermonty #437)."""
    return soft_allow_band_tally(events, band="expired")


def format_expired_soft_allow_tally(
    events: list[dict[str, Any]] | None,
) -> str:
    """Compact ``regime×2 · rs×1`` for expired soft-allows (tradermonty #437)."""
    return format_soft_allow_band_tally(events, band="expired")


def aging_soft_allow_tally(
    events: list[dict[str, Any]] | None,
) -> list[tuple[str, int]]:
    """Gate counts for aging rows only — speak-both-sides with expired tally."""
    return soft_allow_band_tally(events, band="aging")


def format_aging_soft_allow_tally(
    events: list[dict[str, Any]] | None,
) -> str:
    """Compact ``breadth×1 · rs×1`` for aging soft-allows (portfolio AI + xang1234)."""
    return format_soft_allow_band_tally(events, band="aging")


def fresh_soft_allow_tally(
    events: list[dict[str, Any]] | None,
) -> list[tuple[str, int]]:
    """Gate counts for fresh (+ unknown) rows — speak-both-sides with aging/expired."""
    return soft_allow_band_tally(events, band="fresh")


def format_fresh_soft_allow_tally(
    events: list[dict[str, Any]] | None,
) -> str:
    """Compact ``rs×1 · regime×1`` for fresh soft-allows (portfolio AI + xang1234)."""
    return format_soft_allow_band_tally(events, band="fresh")


def soft_allow_event_key(gate: str, reason: str) -> tuple[str, str]:
    """Identity for one soft-allow row (gate + reason, case-folded).

    tradermonty #447 rejects duplicate hypothesis ids in multi-asset replay —
    same idea here: one live fail-open key, refresh stamp instead of flooding.
    """
    g = str(gate or "").strip() or "?"
    r = str(reason or "").strip()[:240]
    return (g.casefold(), r.casefold())


def record_soft_allow(
    data_dir: Path | str,
    gate: str,
    reason: str,
    *,
    cap: int = SOFT_ALLOW_CAP,
) -> None:
    """Append one soft-allow; keep the newest ``cap`` rows.

    Replacing a prior row with the same gate+reason refreshes ``at`` and
    drops the duplicate (tradermonty #447). Distinct reasons still accumulate.
    """
    if not is_soft_allow_reason(reason):
        return
    path = soft_allow_path(data_dir)
    gate_s = str(gate or "").strip() or "?"
    reason_s = str(reason or "").strip()[:240]
    key = soft_allow_event_key(gate_s, reason_s)
    events = [
        e
        for e in load_soft_allows(data_dir)
        if soft_allow_event_key(
            str(e.get("gate") or ""), str(e.get("reason") or "")
        )
        != key
    ]
    events.append(
        {
            "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "gate": gate_s,
            "reason": reason_s,
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
