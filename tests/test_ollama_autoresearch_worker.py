"""Unit tests for Ollama autoresearch helpers (no network)."""

from stock_checker.ollama_autoresearch import (
    extract_python,
    parse_val_score,
    validate_strategy_source,
)


def test_extract_python_fence():
    raw = "Sure.\n```python\ndef generate_signals(a,b,c):\n    return {}\n```\n"
    src = extract_python(raw)
    assert "def generate_signals" in src
    assert validate_strategy_source(src) is None


def test_extract_strips_think_tags():
    raw = "<think>plan</think>\n```python\ndef generate_signals(a, b, c):\n    return {}\n```\n"
    assert "<think>" not in extract_python(raw)


def test_validate_rejects_network():
    bad = "import urllib\ndef generate_signals(a,b,c):\n    return {}\n"
    assert validate_strategy_source(bad) is not None


def test_parse_val_score():
    log = "---\nval_score:            9.600080\ntotal_trades: 3\n"
    assert parse_val_score(log) == 9.600080
