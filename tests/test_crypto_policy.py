"""Live crypto policy: majors only, wider exits, one slot."""

from stock_checker.crypto_policy import (
    CRYPTO_STOP_LOSS_PCT,
    CRYPTO_TAKE_PROFIT_PCT,
    LIVE_CRYPTO_SYMBOLS,
    count_crypto_holdings,
    crypto_buy_block_reason,
    crypto_slot_available,
    is_live_crypto_buy_allowed,
    normalize_live_crypto_symbol,
)
from stock_checker.exit_policy import (
    exit_thresholds_for_asset,
    should_stop_loss,
    should_take_profit,
)


def test_live_crypto_allowlist():
    assert LIVE_CRYPTO_SYMBOLS == frozenset({"BTC-USD", "ETH-USD"})
    assert is_live_crypto_buy_allowed("BTC-USD")
    assert is_live_crypto_buy_allowed("ETHUSDT")
    assert normalize_live_crypto_symbol("BTCUSDT") == "BTC-USD"
    assert not is_live_crypto_buy_allowed("PROM-USD")
    assert not is_live_crypto_buy_allowed("ESP-USD")
    assert crypto_buy_block_reason("PROM-USD")
    assert crypto_buy_block_reason("AAPL") == ""


def test_crypto_slot_cap():
    ok, _ = crypto_slot_available([], max_crypto=1)
    assert ok
    blocked, why = crypto_slot_available(["BTC-USD", "AAPL"], max_crypto=1)
    assert not blocked
    assert "full" in why
    assert count_crypto_holdings(["BTC-USD", "ETH-USD", "AAPL"]) == 2


def test_crypto_exits_wider_than_stocks():
    tp_s, sl_s = exit_thresholds_for_asset(is_crypto=False)
    tp_c, sl_c = exit_thresholds_for_asset(is_crypto=True)
    assert tp_s == 8.0 and sl_s == 5.0
    assert tp_c == CRYPTO_TAKE_PROFIT_PCT == 10.0
    assert sl_c == CRYPTO_STOP_LOSS_PCT == 10.0
    # PROM-style −5.27% must NOT stop crypto majors under new bands
    assert not should_stop_loss(-5.27, threshold=sl_c)
    assert should_stop_loss(-10.0, threshold=sl_c)
    assert not should_take_profit(5.0, threshold=tp_c)
    assert should_take_profit(10.0, threshold=tp_c)
