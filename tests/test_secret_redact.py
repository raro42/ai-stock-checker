"""tradermonty #556: raw + URL-encoded key echoes never reach Ops surfaces."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote, quote_plus

from openbb_backend.desk_logs import read_log_tail
from stock_checker.ops_audit import audited_ops_action, load_ops_actions
from stock_checker.secret_redact import (
    _DEFAULT_EXC_CHARS,
    _coerce_exc_clip_chars,
    redact_secrets,
    safe_exc_text,
)


def test_redact_query_param_token_and_apikey():
    raw = (
        "GET https://finnhub.io/api/v1/quote?symbol=AAPL&token=sekritVALUE99 "
        "and https://x.example/v3?apikey=OTHERKEY1234&foo=1"
    )
    out = redact_secrets(raw)
    assert "sekritVALUE99" not in out
    assert "OTHERKEY1234" not in out
    assert "token=REDACTED" in out
    assert "apikey=REDACTED" in out
    assert "symbol=AAPL" in out


def test_redact_url_encoded_env_secret(monkeypatch):
    secret = "Ab/Cd+Ef=Gh99"  # pragma: allowlist secret
    monkeypatch.setenv("FINNHUB_API_KEY", secret)
    raw = (
        f"fail url=https://api.example/q?token={quote(secret, safe='')}"
        f" plus={quote_plus(secret, safe='')}"
        f" bare={secret}"
    )
    out = redact_secrets(raw)
    assert secret not in out
    assert quote(secret, safe="") not in out
    assert quote_plus(secret, safe="") not in out
    assert out.count("REDACTED") >= 2


def test_redact_bearer_header():
    out = redact_secrets("Authorization: Bearer sk-live-ABCDEFGH1234")
    assert "sk-live-ABCDEFGH1234" not in out
    assert "Bearer REDACTED" in out


def test_safe_exc_text_redacts_token_in_request_exception():
    """tradermonty #778: console diagnostics must not echo token= URLs."""
    secret = "finnhubExcLeak99"  # pragma: allowlist secret
    exc = ConnectionError(
        f"HTTPSConnectionPool(host='finnhub.io', port=443): "
        f"Max retries exceeded with url: /api/v1/quote?symbol=AAPL&token={secret}"
    )
    out = safe_exc_text(exc, limit=200)
    assert secret not in out
    assert "ConnectionError" in out
    assert "token=REDACTED" in out
    assert "AAPL" in out


def test_safe_exc_text_class_only_when_message_empty():
    class EmptyMsg(Exception):
        def __str__(self) -> str:
            return ""

    assert safe_exc_text(EmptyMsg()) == "EmptyMsg"


def test_coerce_exc_clip_chars_refuses_bool():
    """True→1 must not invent a one-char console strip; False must not wipe."""
    assert _coerce_exc_clip_chars(True) == _DEFAULT_EXC_CHARS
    assert _coerce_exc_clip_chars(False) == _DEFAULT_EXC_CHARS
    assert _coerce_exc_clip_chars(0) == _DEFAULT_EXC_CHARS
    assert _coerce_exc_clip_chars(None) == _DEFAULT_EXC_CHARS
    assert _coerce_exc_clip_chars(40) == 40


def test_safe_exc_text_refuses_bool_clip_ceiling():
    """True→1 must not invent ``V…`` via msg[:True]; False must not wipe."""
    exc = ValueError(
        "HTTPSConnectionPool url=/api/v1/quote?symbol=AAPL&token=sekritVALUE99"
    )
    full = safe_exc_text(exc, limit=True)
    assert "ValueError:" in full
    assert "HTTPSConnectionPool" in full
    assert "token=REDACTED" in full
    assert "sekritVALUE99" not in full
    # Without refuse, msg[:True] → one char after the class prefix.
    assert full != "ValueError: H"

    wiped = safe_exc_text(exc, limit=False)
    assert "HTTPSConnectionPool" in wiped
    assert wiped == full

    short = safe_exc_text(exc, limit=8)
    assert short == "ValueError: HTTPSCon"


def test_safe_detail_redacts_encoded_key_in_note(tmp_path: Path, monkeypatch):
    secret = "finnhubLeakKey99"  # pragma: allowlist secret
    monkeypatch.setenv("FINNHUB_API_KEY", secret)
    _, meta = audited_ops_action(
        tmp_path,
        kind="config",
        detail={
            "ai_mode": "off",
            "note": f"debug https://finnhub.io/api/v1/quote?token={secret}",
        },
        act=lambda: True,
    )
    assert meta["blocked"] is False
    detail = (load_ops_actions(tmp_path)[0].get("detail") or {})
    assert detail.get("ai_mode") == "off"
    assert secret not in str(detail.get("note"))
    assert "REDACTED" in str(detail.get("note"))


def test_read_log_tail_redacts_token(tmp_path: Path, monkeypatch):
    secret = "liveTailSecret99"  # pragma: allowlist secret
    monkeypatch.setenv("FINNHUB_API_KEY", secret)
    log = tmp_path / "logs" / "trader.log"
    log.parent.mkdir(parents=True)
    log.write_text(
        f"Failed Finnhub: https://finnhub.io/api/v1/quote?symbol=MSFT&token={secret}\n",
        encoding="utf-8",
    )
    snap = read_log_tail(tmp_path, "trader")
    assert snap["exists"] is True
    assert secret not in snap["text"]
    assert "token=REDACTED" in snap["text"]
    assert "MSFT" in snap["text"]
