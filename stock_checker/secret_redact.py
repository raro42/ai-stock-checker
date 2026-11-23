"""Mask API-key echoes (raw + URL-encoded) in desk/ops diagnostics.

Adapted from tradermonty/claude-trading-skills #556 (redact encoded keys through
a shared fragment) and #778 (never print raw request exceptions that embed
``token=`` URLs): Ops live tails, audit detail, and trader console must not
carry provider tokens. Display/ops honesty only — not a trading gate.
"""

from __future__ import annotations

import os
import re
from urllib.parse import quote, quote_plus

# Query-param prefixes that often carry provider secrets (Finnhub uses token=).
_QUERY_KEY_RE = re.compile(
    r"([?&](?:apikey|api_key|api-key|token|access_token|key)=)[^&\s\"']+",
    re.IGNORECASE,
)
_BEARER_RE = re.compile(r"(Bearer\s+)\S+", re.IGNORECASE)

_ENV_SECRET_NAMES = (
    "FINNHUB_API_KEY",
    "OPENAI_API_KEY",
    "LAYA_API_KEY",
    "OPENBB_BACKEND_API_KEY",
    "CMC_API_KEY",
    "COINMARKETCAP_API_KEY",
)

_MARKER = "REDACTED"
_MIN_SECRET_LEN = 8


def env_secret_values() -> list[str]:
    """Collect non-placeholder secrets from the process environment."""
    out: list[str] = []
    seen: set[str] = set()
    for name in _ENV_SECRET_NAMES:
        raw = (os.getenv(name) or "").strip()
        if len(raw) < _MIN_SECRET_LEN:
            continue
        # Skip .env.example-style placeholders.
        low = raw.lower()
        if "your_" in low or low.endswith("_here") or low in {"changeme", "xxx"}:
            continue
        if raw in seen:
            continue
        seen.add(raw)
        out.append(raw)
    return out


def _encoded_patterns(secret: str) -> list[str]:
    """Regex fragments matching raw + percent-encoded forms of ``secret``."""
    patterns = [re.escape(secret)]
    for encoded in (quote(secret, safe=""), quote_plus(secret, safe="")):
        if encoded == secret:
            continue
        # Percent triplets are case-insensitive; other chars stay literal.
        parts = re.split(r"(%[0-9A-Fa-f]{2})", encoded)
        frag = "".join(
            "(?i:" + re.escape(part) + ")"
            if re.fullmatch(r"%[0-9A-Fa-f]{2}", part)
            else re.escape(part)
            for part in parts
            if part
        )
        if frag:
            patterns.append(frag)
    return patterns


def redact_secrets(text: str, *, extra: list[str] | None = None) -> str:
    """Mask query-param keys, Bearer tokens, and known env secret echoes."""
    if not isinstance(text, str) or not text:
        return text if isinstance(text, str) else ""
    out = _QUERY_KEY_RE.sub(r"\1" + _MARKER, text)
    out = _BEARER_RE.sub(r"\1" + _MARKER, out)
    secrets = list(extra or [])
    secrets.extend(env_secret_values())
    # Longest first so a short key cannot match inside a longer replacement.
    patterns: list[str] = []
    seen: set[str] = set()
    for secret in sorted({s for s in secrets if isinstance(s, str)}, key=len, reverse=True):
        if len(secret) < _MIN_SECRET_LEN:
            continue
        for frag in _encoded_patterns(secret):
            if frag in seen:
                continue
            seen.add(frag)
            patterns.append(frag)
    if patterns:
        out = re.sub("|".join(patterns), _MARKER, out)
    return out


_DEFAULT_EXC_CHARS = 120


def _coerce_exc_clip_chars(
    value: object, default: int = _DEFAULT_EXC_CHARS
) -> int:
    """Positive console exception message ceiling, or ``default`` when bool/gap/≤0.

    tradermonty #778/#700/#655 + xang1234/portfolio AI: ``True→1`` must not
    invent a one-char console strip via ``msg[:True]``; ``False→0`` must not
    wipe the redacted message (LAYA/AI-validate reason clip peer — token
    redact already covered; char ceilings were still open).
    """
    from stock_checker.technical_indicators import coerce_nonneg_int

    n = coerce_nonneg_int(value)
    if n is None or n <= 0:
        return int(default)
    return n


def safe_exc_text(exc: BaseException, *, limit: object = _DEFAULT_EXC_CHARS) -> str:
    """Class name + redacted message for console/log diagnostics.

    tradermonty #778: ``requests`` exceptions often embed the full URL (including
    ``token=`` / ``apikey=``) in ``str(e)``. Prefer this helper (or class-only)
    over raw ``str(e)`` / ``{e}`` on provider failure paths.
    """
    name = type(exc).__name__
    msg = redact_secrets(str(exc) or "").strip()
    if not msg or msg == name:
        return name
    ceiling = _coerce_exc_clip_chars(limit)
    if ceiling > 0:
        msg = msg[:ceiling]
    return f"{name}: {msg}"
