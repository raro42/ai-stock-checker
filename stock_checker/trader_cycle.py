"""One trade-check cycle — phases carved out of the intelligent_trader god-loop.

Offline tests can drive a fake trader through ``run_one_cycle`` without network.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Protocol

from .exit_policy import book_action_mode


class CycleTrader(Protocol):
    """Minimal surface used by ``run_one_cycle``."""

    portfolio: Any
    max_positions: int
    current_opportunities: List

    def apply_runtime_config(self) -> None: ...
    def should_scan(self) -> bool: ...
    def scan_markets(self) -> List: ...
    def display_position_details(self) -> None: ...
    def check_existing_positions(self) -> None: ...
    def evaluate_rebalancing(self) -> bool: ...
    def execute_new_trades(self) -> None: ...


@dataclass
class CycleResult:
    scanned: bool = False
    posture: str = "open"
    ran_exits: bool = False
    ran_entries: bool = False
    ran_rebalance: bool = False
    phases: List[str] = field(default_factory=list)


def run_one_cycle(trader: CycleTrader, *, force_scan: bool = False) -> CycleResult:
    """
    Single iteration: config → optional scan → exits → posture-gated entries/rebalance.

    Does not sleep. Caller owns the outer loop interval.
    """
    result = CycleResult()
    trader.apply_runtime_config()
    result.phases.append("config")
    if hasattr(trader, "begin_trade_cycle"):
        trader.begin_trade_cycle()
        result.phases.append("cycle_reset")

    if force_scan or trader.should_scan():
        trader.scan_markets()
        result.scanned = True
        result.phases.append("scan")

    if trader.portfolio.holdings:
        trader.display_position_details()
        result.phases.append("display")
        trader.check_existing_positions()
        result.ran_exits = True
        result.phases.append("exits")

    posture = book_action_mode(len(trader.portfolio.holdings), trader.max_positions)
    result.posture = posture
    result.phases.append(f"posture:{posture}")

    if posture == "overweight":
        # Exits only — no buys / scan rotation.
        return result

    if posture == "at_cap":
        if trader.current_opportunities:
            trader.evaluate_rebalancing()
            result.ran_rebalance = True
            result.phases.append("rebalance")
        return result

    # open book — room for new entries
    if trader.current_opportunities:
        trader.execute_new_trades()
        result.ran_entries = True
        result.phases.append("entries")
        trader.evaluate_rebalancing()
        result.ran_rebalance = True
        result.phases.append("rebalance")
    return result
