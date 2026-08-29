"""Post stop-loss buy cooldown (anti revenge refill)."""

import time
from types import SimpleNamespace

from stock_checker.intelligent_trader import IntelligentTrader


def test_post_stop_cooldown_blocks_after_arm(tmp_path):
    t = IntelligentTrader.__new__(IntelligentTrader)
    t.trade_interval = 300
    t._cycle_had_stop_loss = False
    t._buy_block_until = 0.0
    t.persistence = SimpleNamespace(data_dir=tmp_path)
    t.portfolio = SimpleNamespace(initial_cash=100_000.0)
    assert t._entries_blocked_this_cycle() is False

    t._arm_post_stop_cooldown()
    assert t._cycle_had_stop_loss is True
    assert t._buy_block_until > time.time()
    assert t._entries_blocked_this_cycle() is True

    t.begin_trade_cycle()
    assert t._cycle_had_stop_loss is False
    assert t._entries_blocked_this_cycle() is True

    t._buy_block_until = time.time() - 1
    assert t._entries_blocked_this_cycle() is False


def test_post_stop_cooldown_at_least_four_hours():
    t = IntelligentTrader.__new__(IntelligentTrader)
    t.trade_interval = 300
    assert t._post_stop_cooldown_seconds() == 14400.0
    t.trade_interval = 20000
    assert t._post_stop_cooldown_seconds() == 20000.0
