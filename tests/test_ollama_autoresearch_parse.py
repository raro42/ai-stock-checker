"""Tests for autoresearch log parsers."""

from stock_checker.ollama_autoresearch import parse_beats_spy_walkforward, parse_val_score


def test_parse_val_score():
    assert parse_val_score("val_score: 12.5\n") == 12.5
    assert parse_val_score("nope") is None


def test_parse_beats_spy():
    assert parse_beats_spy_walkforward("beats_buy_hold_spy_walkforward: true\n") is True
    assert parse_beats_spy_walkforward("beats_buy_hold_spy_walkforward: false\n") is False
    assert parse_beats_spy_walkforward("val_score: 1\n") is None


def test_idea_family():
    from stock_checker.ollama_autoresearch import idea_family

    assert idea_family("param: SHORT_SMA=15") == "param:short_sma"
    assert idea_family("Tightening RSI band") == "rsi"
    assert idea_family("fails SPY WF gate | foo") == "spy_gate"
    assert idea_family("random tweak") == "other"
