"""Shared soft-gate logging (fail-open visibility — review A5)."""

from __future__ import annotations


def log_soft_allow(gate: str, reason: str) -> None:
    """Print when a gate allows because data is missing / unknown (fail-open)."""
    r = (reason or "").lower()
    if "unknown" in r or "no bars" in r or "skip_no_bars" in r or "insufficient" in r:
        print(f"   ⚪ Soft-allow [{gate}]: {reason}")
