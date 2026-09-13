"""Docker Python pin honesty (tradermonty drift guard — ops only)."""

from __future__ import annotations

from stock_checker.runtime_pin import (
    EXPECTED_PYTHON,
    format_health_line,
    format_python_pair,
    running_python,
    runtime_pin_ok,
    runtime_pin_status,
)


def test_expected_matches_dockerfile_pin() -> None:
    assert EXPECTED_PYTHON == (3, 11)
    assert format_python_pair(EXPECTED_PYTHON) == "3.11"


def test_runtime_pin_ok_match_and_drift() -> None:
    assert runtime_pin_ok((3, 11)) is True
    assert runtime_pin_ok((3, 12)) is False
    assert runtime_pin_ok((2, 7), expected=(2, 7)) is True


def test_runtime_pin_status_ok() -> None:
    s = runtime_pin_status((3, 11))
    assert s["ok"] is True
    assert s["tone"] == "ok"
    assert s["expected"] == "3.11"
    assert s["running"] == "3.11"
    assert "matches Docker pin" in s["line"]
    assert "drift" not in s["line"]


def test_runtime_pin_status_drift() -> None:
    s = runtime_pin_status((3, 12))
    assert s["ok"] is False
    assert s["tone"] == "warn"
    assert s["running"] == "3.12"
    assert "expected 3.11" in s["line"]
    assert "drift" in s["line"]


def test_format_health_line() -> None:
    assert format_health_line((3, 11)).startswith("OK")
    assert "matches Docker pin" in format_health_line((3, 11))
    fail = format_health_line((3, 10))
    assert fail.startswith("FAIL")
    assert "drift" in fail


def test_running_python_uses_sys_by_default() -> None:
    got = running_python()
    assert got == EXPECTED_PYTHON or isinstance(got[0], int)
    assert len(got) == 2
