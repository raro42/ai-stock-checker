"""Docker / host Python pin honesty (tradermonty OS drift guard — display/ops only).

Dockerfile pins ``FROM python:3.11``. Friends and healthcheck can see when the
running interpreter drifts from that pin. Not an entry gate.
"""

from __future__ import annotations

import sys
from typing import Any

# Keep in sync with Dockerfile ``FROM python:X.Y``.
EXPECTED_PYTHON: tuple[int, int] = (3, 11)


def running_python(
    version_info: tuple[int, ...] | None = None,
) -> tuple[int, int]:
    """Return ``(major, minor)`` for the active interpreter."""
    info = version_info if version_info is not None else sys.version_info
    return (int(info[0]), int(info[1]))


def format_python_pair(pair: tuple[int, int]) -> str:
    return f"{pair[0]}.{pair[1]}"


def runtime_pin_ok(
    running: tuple[int, int] | None = None,
    *,
    expected: tuple[int, int] = EXPECTED_PYTHON,
) -> bool:
    """True when major.minor matches the Docker pin."""
    got = running if running is not None else running_python()
    return got == expected


def runtime_pin_status(
    running: tuple[int, int] | None = None,
    *,
    expected: tuple[int, int] = EXPECTED_PYTHON,
) -> dict[str, Any]:
    """Ops / health snapshot: expected vs running, no secrets."""
    got = running if running is not None else running_python()
    ok = got == expected
    expected_s = format_python_pair(expected)
    running_s = format_python_pair(got)
    if ok:
        line = f"Python {running_s} · matches Docker pin"
        tone = "ok"
    else:
        line = f"Python {running_s} · expected {expected_s} (drift)"
        tone = "warn"
    return {
        "ok": ok,
        "tone": tone,
        "line": line,
        "expected": expected_s,
        "running": running_s,
        "expected_tuple": expected,
        "running_tuple": got,
    }


def format_health_line(
    running: tuple[int, int] | None = None,
    *,
    expected: tuple[int, int] = EXPECTED_PYTHON,
) -> str:
    """One-line healthcheck output: ``OK …`` or ``FAIL …``."""
    status = runtime_pin_status(running, expected=expected)
    prefix = "OK" if status["ok"] else "FAIL"
    return f"{prefix}  runtime pin · {status['line']}"
