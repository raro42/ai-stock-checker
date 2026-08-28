"""Post stop-loss buy cooldown (anti revenge refill)."""

import time

from stock_checker.intelligent_trader import IntelligentTrader


def test_post_stop_cooldown_blocks_after_arm(tmp_path):
    t = IntelligentTrader.__new__(IntelligentTrader)
    t.trade_interval = 300
    t._cycle_had_stop_loss = False
    t._buy_block_until = 0.0
    assert t._entries_blocked_this_cycle() is False

    t._arm_post_stop_cooldown()
    assert t._cycle_had_stop_loss is True
    assert t._buy_block_until > time.time()
    # Same-cycle flag alone
    assert t._entries_blocked_this_cycle() is True

    # After cycle reset, durable timestamp still blocks
    t.begin_trade_cycle()
    assert t._cycle_had_stop_loss is False
    assert t._entries_blocked_this_cycle() is True

    # Expired cooldown allows entries
    t._buy_block_until = time.time() - 1
    assert t._entries_blocked_this_cycle() is False


def test_post_stop_cooldown_at_least_one_hour():
    t = IntelligentTrader.__new__(IntelligentTrader)
    t.trade_interval = 300
    assert t._post_stop_cooldown_seconds() == 3600.0
    t.trade_interval = 7200
    assert t._post_stop_cooldown_seconds() == 7200.0
