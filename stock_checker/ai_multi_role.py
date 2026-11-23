"""TradingAgents-style multi-role prompts for Ollama validate mode.

One local LLM call simulates bull / bear / risk officers, then a gated consensus.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from stock_checker.technical_indicators import (
    _finite_signed,
    _valid_close,
    _valid_volume,
    coerce_nonneg_int,
    coerce_score,
    daily_pct_change,
)

_DEFAULT_NOTE_CHARS = 160
_DEFAULT_REASONING_CHARS = 2000


def _coerce_clip_chars(value: object, default: int) -> int:
    """Positive note/reasoning char ceiling, or ``default`` when bool/gap/≤0.

    FinRobot + tradermonty #700/#655 + xang1234/portfolio AI: ``True→1`` must
    not invent a one-char bull/bear/risk note (``u…``) or one-char debate dump
    via ``s[:True]``; ``False→0`` must not wipe (LAYA / AI-validate reason clip
    peers — score refuse already covered; note/reasoning ceilings were still
    bare literals).
    """
    n = coerce_nonneg_int(value)
    if n is None or n <= 0:
        return int(default)
    return n


def _clip(
    text: object,
    n: object = _DEFAULT_NOTE_CHARS,
    *,
    default: int = _DEFAULT_NOTE_CHARS,
) -> str:
    limit = _coerce_clip_chars(n, default)
    s = str(text or "")
    if len(s) <= limit:
        return s
    return s[:limit]


def multi_role_enabled() -> bool:
    return os.getenv("AI_MULTI_ROLE", "1").strip().lower() not in {"0", "false", "no", "off"}


def build_multi_role_prompt(stock_data: dict) -> str:
    symbol = stock_data.get("symbol", "Unknown")
    name = stock_data.get("name", symbol)
    price = stock_data.get("current_price")
    prev = stock_data.get("previous_close")
    hi = stock_data.get("52_week_high")
    lo = stock_data.get("52_week_low")
    pe = stock_data.get("pe_ratio")
    volume = stock_data.get("volume")

    # Missing/bool/gap marks → n/a (never invent flat +0.00 / True→$1 / True P/E).
    # Daily% already refused; raw Price/Prev/52w/PE/Volume lines were still open
    # (stock AI + LAYA money bits shipped; FinRobot multi-role debate prompt lagged).
    def _money_bit(raw: object) -> str:
        if not _valid_close(raw):
            return "n/a"
        return f"{float(raw):,.2f}"

    daily = daily_pct_change(price, prev)
    daily_bit = f"{daily:+.2f}" if daily is not None else "n/a"

    lines = [
        "You are three paper-trading officers debating ONE name. Be skeptical of churn.",
        "Roles:",
        "1) BULL — argue for BUY only with clear momentum/value edge",
        "2) BEAR — argue for SELL/avoid if extended, weak, or fee-unfriendly",
        "3) RISK — set ok=false if earnings risk, illiquidity, or chase risk",
        "",
        f"Name: {name} ({symbol})",
        f"Price: {_money_bit(price)}  PrevClose: {_money_bit(prev)}  Daily%: {daily_bit}",
        f"52w High/Low: {_money_bit(hi)} / {_money_bit(lo)}",
    ]
    if _finite_signed(pe):
        lines.append(f"P/E: {float(pe):.2f}")
    if _valid_volume(volume):
        lines.append(f"Volume: {float(volume):,.0f}")
    lines.extend(
        [
            "",
            "Return ONLY one JSON object:",
            "{"
            '"bull":{"bias":"BUY|HOLD","note":"..."},'
            '"bear":{"bias":"SELL|HOLD","note":"..."},'
            '"risk":{"ok":true,"note":"..."},'
            '"action":"BUY|SELL|HOLD",'
            '"confidence":"HIGH|MEDIUM|LOW",'
            '"score":0,'
            '"reasoning":"one sentence consensus"'
            "}",
            "",
            "Hard rules:",
            "- If risk.ok is false → action MUST be HOLD and confidence LOW or MEDIUM.",
            "- If bull.bias is BUY and bear.bias is SELL → action HOLD (disagreement).",
            "- Prefer HOLD over weak BUY. This is paper trading with 0.1% fees/side.",
        ]
    )
    return "\n".join(lines)


def _extract_json(text: str) -> dict | None:
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
    raw = fence.group(1) if fence else None
    if not raw:
        # greedy object with action key
        m = re.search(r"\{[\s\S]*\"action\"[\s\S]*\}", text)
        raw = m.group(0) if m else None
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # try outermost braces trim
        start, end = raw.find("{"), raw.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(raw[start : end + 1])
            except json.JSONDecodeError:
                return None
    return None


def consensus_from_multi_role(payload: dict, symbol: str) -> dict[str, Any]:
    """Apply risk / disagreement gates to multi-role JSON."""
    risk = payload.get("risk") or {}
    bull = payload.get("bull") or {}
    bear = payload.get("bear") or {}
    risk_ok = bool(risk.get("ok", True))
    bull_bias = str(bull.get("bias", "HOLD")).upper()
    bear_bias = str(bear.get("bias", "HOLD")).upper()

    action = str(payload.get("action", "HOLD")).upper()
    if action not in {"BUY", "SELL", "HOLD"}:
        action = "HOLD"
    confidence = str(payload.get("confidence", "LOW")).upper()
    if confidence not in {"HIGH", "MEDIUM", "LOW"}:
        confidence = "LOW"
    # tradermonty #700/#655 + xang1234/portfolio AI: refuse bool/gap invent
    # (True→1); missing/invalid → flat 0 (HOLD-safe).
    sc = coerce_score(payload.get("score"))
    score = int(sc) if sc is not None else 0
    score = max(-100, min(100, score))
    reasoning = str(payload.get("reasoning") or "multi-role consensus")

    gated = False
    if not risk_ok:
        action, confidence, score, gated = "HOLD", "LOW", 0, True
        reasoning = f"Risk veto: {risk.get('note', 'risk.ok=false')}"
    elif bull_bias == "BUY" and bear_bias == "SELL":
        action, confidence, score, gated = "HOLD", "MEDIUM", 0, True
        reasoning = "Bull/bear disagreement → HOLD"

    # FinRobot + tradermonty #700/#655: refuse bool — True→1 / [:True] invents
    # a one-char officer note; False→0 would wipe the debate strip.
    bull_note = _clip(bull.get("note") or bull_bias)
    bear_note = _clip(bear.get("note") or bear_bias)
    risk_note = _clip(risk.get("note") or ("ok" if risk_ok else "blocked"))
    notes = [
        f"Bull: {bull_note}",
        f"Bear: {bear_note}",
        f"Risk: {risk_note}",
        reasoning,
    ]
    return {
        "symbol": symbol,
        "action": action,
        "confidence": confidence,
        "score": score,
        "reasons": notes,
        "ai_reasoning": _clip(
            json.dumps(payload, ensure_ascii=False),
            _DEFAULT_REASONING_CHARS,
            default=_DEFAULT_REASONING_CHARS,
        ),
        "parse_mode": "multi_role",
        "multi_role_gated": gated,
        "bull_bias": bull_bias,
        "bear_bias": bear_bias,
        "risk_ok": risk_ok,
        "bull_note": bull_note,
        "bear_note": bear_note,
        "risk_note": risk_note,
        "reasoning": reasoning,
    }


def parse_multi_role_response(response: str, stock_data: dict) -> dict | None:
    payload = _extract_json(response)
    if not payload or "action" not in payload:
        return None
    if not any(k in payload for k in ("bull", "bear", "risk")):
        return None
    return consensus_from_multi_role(payload, str(stock_data.get("symbol", "Unknown")))
