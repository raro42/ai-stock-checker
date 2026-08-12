"""Offline single-cycle fixture for trader_cycle (B1)."""

from __future__ import annotations

from types import SimpleNamespace

from stock_checker.trader_cycle import run_one_cycle


class _FakePortfolio:
    def __init__(self, holdings=None):
        self.holdings = dict(holdings or {})
        self.cash = 50_000.0
        self.initial_cash = 100_000.0
        self.total_fees_paid = 0.0
        self.transactions = []

    def get_total_value(self):
        return self.cash


class _FakeTrader:
    def __init__(self, *, holdings=None, max_positions=5, opportunities=None, should_scan=False):
        self.portfolio = _FakePortfolio(holdings)
        self.max_positions = max_positions
        self.current_opportunities = list(opportunities or [])
        self._should_scan = should_scan
        self.calls = []

    def apply_runtime_config(self):
        self.calls.append("config")

    def should_scan(self):
        return self._should_scan

    def scan_markets(self):
        self.calls.append("scan")
        self.current_opportunities = [{"symbol": "BTC-USD"}]
        return self.current_opportunities

    def display_position_details(self):
        self.calls.append("display")

    def check_existing_positions(self):
        self.calls.append("exits")

    def evaluate_rebalancing(self):
        self.calls.append("rebalance")
        return False

    def execute_new_trades(self):
        self.calls.append("entries")


def test_cycle_overweight_skips_entries_and_rebalance():
    t = _FakeTrader(
        holdings={"A": 1, "B": 1, "C": 1, "D": 1, "E": 1, "F": 1},
        max_positions=5,
        opportunities=[{"symbol": "BTC-USD"}],
        should_scan=False,
    )
    r = run_one_cycle(t)
    assert r.posture == "overweight"
    assert r.ran_exits is True
    assert r.ran_entries is False
    assert r.ran_rebalance is False
    assert "entries" not in t.calls
    assert "rebalance" not in t.calls


def test_cycle_open_runs_entries_then_rebalance():
    t = _FakeTrader(
        holdings={"A": 1},
        max_positions=5,
        opportunities=[{"symbol": "ETH-USD"}],
        should_scan=False,
    )
    r = run_one_cycle(t)
    assert r.posture == "open"
    assert r.ran_entries and r.ran_rebalance
    assert t.calls.index("entries") < t.calls.index("rebalance")


def test_cycle_at_cap_rebalance_only():
    t = _FakeTrader(
        holdings={"A": 1, "B": 1, "C": 1, "D": 1, "E": 1},
        max_positions=5,
        opportunities=[{"symbol": "SOL-USD"}],
        should_scan=True,
    )
    r = run_one_cycle(t)
    assert r.scanned is True
    assert r.posture == "at_cap"
    assert r.ran_entries is False
    assert r.ran_rebalance is True
    assert "entries" not in t.calls


def test_soft_entry_gates_block_on_regime():
    from stock_checker.entry_gates import soft_entry_gates_ok
    from stock_checker.market_regime import REGIME_OFF

    ok, why = soft_entry_gates_ok(
        is_crypto=False,
        stock_regime=REGIME_OFF,
        crypto_regime="unknown",
        regime_enabled=True,
        rs_check=lambda: (True, "rs ok"),
        breadth_pulse={"crypto_up": 1, "crypto_down": 0, "stock_n": 1, "stock_leaders": 1},
        breadth_enabled=True,
    )
    assert ok is False
    assert "regime" in why
