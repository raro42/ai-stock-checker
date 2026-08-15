"""Local night window for Ollama autoresearch (no daytime GPU/CPU burn).

Default window: 23:00 ≤ t < 08:00 in the **machine local** timezone
(detected from the OS / `$TZ` / `$ASC_LOCAL_TZ`). Falls back to Europe/Berlin
only if detection fails.

Override with OLLAMA_AUTOSEARCH_NIGHT_START / _NIGHT_END / _TZ (or ASC_LOCAL_TZ),
or force daytime runs with OLLAMA_AUTOSEARCH_FORCE=1.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


def default_local_tz_name() -> str:
    """
    IANA timezone for this host.

    Order: ASC_LOCAL_TZ → OLLAMA_AUTOSEARCH_TZ → TZ → /etc/localtime →
    datetime tz key → Europe/Berlin fallback.
    """
    for key in ("ASC_LOCAL_TZ", "OLLAMA_AUTOSEARCH_TZ", "TZ"):
        raw = (os.getenv(key) or "").strip()
        if raw and not raw.startswith(":"):
            return raw
    try:
        link = Path("/etc/localtime").resolve()
        parts = link.parts
        if "zoneinfo" in parts:
            i = parts.index("zoneinfo")
            cand = "/".join(parts[i + 1 :])
            if cand:
                ZoneInfo(cand)  # validate
                return cand
    except Exception:
        pass
    try:
        info = datetime.now().astimezone().tzinfo
        key = getattr(info, "key", None)
        if key:
            return str(key)
    except Exception:
        pass
    return "Europe/Berlin"


def night_window_bounds() -> tuple[int, int, str]:
    start = _env_int("OLLAMA_AUTOSEARCH_NIGHT_START", 23)
    end = _env_int("OLLAMA_AUTOSEARCH_NIGHT_END", 8)
    # Explicit OLLAMA_AUTOSEARCH_TZ wins; else ASC_LOCAL_TZ / system local.
    tz_name = (os.getenv("OLLAMA_AUTOSEARCH_TZ") or "").strip() or default_local_tz_name()
    if not (0 <= start <= 23 and 0 <= end <= 23):
        raise ValueError(f"night hours must be 0-23, got start={start} end={end}")
    if start == end:
        raise ValueError("night start and end must differ")
    return start, end, tz_name


def force_bypass() -> bool:
    return os.getenv("OLLAMA_AUTOSEARCH_FORCE", "0").strip() == "1"


def _now(tz_name: str, now: Optional[datetime] = None) -> datetime:
    tz = ZoneInfo(tz_name)
    if now is None:
        return datetime.now(tz)
    if now.tzinfo is None:
        return now.replace(tzinfo=tz)
    return now.astimezone(tz)


def in_night_window(now: Optional[datetime] = None) -> bool:
    """True during [start, end) wrapping midnight, or when FORCE=1."""
    if force_bypass():
        return True
    start, end, tz_name = night_window_bounds()
    local = _now(tz_name, now)
    h = local.hour + local.minute / 60.0 + local.second / 3600.0
    # Compare on fractional hour so 08:00:00 is outside [23, 8).
    if start > end:
        return h >= start or h < end
    return start <= h < end


def seconds_until_night_window(now: Optional[datetime] = None) -> int:
    """Seconds until next window open. 0 if already inside (or FORCE=1)."""
    if force_bypass() or in_night_window(now):
        return 0
    start, _end, tz_name = night_window_bounds()
    local = _now(tz_name, now)
    target = local.replace(hour=start, minute=0, second=0, microsecond=0)
    if local >= target:
        target += timedelta(days=1)
    return max(1, int((target - local).total_seconds()))


def seconds_until_local_hour(hour: int = 8, now: Optional[datetime] = None) -> int:
    """Seconds until next ``hour:00`` in the configured local TZ (morning briefing)."""
    _start, _end, tz_name = night_window_bounds()
    local = _now(tz_name, now)
    target = local.replace(hour=int(hour) % 24, minute=0, second=0, microsecond=0)
    if local >= target:
        target += timedelta(days=1)
    return max(60, int((target - local).total_seconds()))


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help"):
        print(
            "usage: python3 -m stock_checker.autoresearch_schedule "
            "{in_window|seconds_until_open|seconds_until_morning|status}",
            file=sys.stderr,
        )
        return 2
    cmd = args[0]
    start, end, tz_name = night_window_bounds()
    if cmd == "in_window":
        print("1" if in_night_window() else "0")
        return 0
    if cmd == "seconds_until_open":
        print(seconds_until_night_window())
        return 0
    if cmd == "seconds_until_morning":
        hour = int(args[1]) if len(args) > 1 else 8
        print(seconds_until_local_hour(hour))
        return 0
    if cmd == "status":
        inside = in_night_window()
        wait = seconds_until_night_window()
        print(
            f"tz={tz_name} window={start:02d}:00-{end:02d}:00 "
            f"in_window={int(inside)} force={int(force_bypass())} "
            f"seconds_until_open={wait}"
        )
        return 0
    print(f"unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
