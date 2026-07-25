"""TradingAgents-style multi-role prompts for Ollama validate mode.

One local LLM call simulates bull / bear / risk officers, then a gated consensus.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any


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

    daily = 0.0
    if price and prev:
        try:
            daily = ((float(price) - float(prev)) / float(prev)) * 100.0
        except (TypeError, ValueError, ZeroDivisionError):
            daily = 0.0

    lines = [
        "You are three paper-trading officers debating ONE name. Be skeptical of churn.",
        "Roles:",
        "1) BULL — argue for BUY only with clear momentum/value edge",
        "2) BEAR — argue for SELL/avoid if extended, weak, or fee-unfriendly",
        "3) RISK — set ok=false if earnings risk, illiquidity, or chase risk",
        "",
        f"Name: {name} ({symbol})",
        f"Price: {price}  PrevClose: {prev}  Daily%: {daily:+.2f}",
        f"52w High/Low: {hi} / {lo}",
    ]
    if pe is not None:
        lines.append(f"P/E: {pe}")
    if volume is not None:
        lines.append(f"Volume: {volume}")
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
    try:
        score = int(float(payload.get("score", 0)))
    except (TypeError, ValueError):
        score = 0
    score = max(-100, min(100, score))
    reasoning = str(payload.get("reasoning") or "multi-role consensus")

    gated = False
    if not risk_ok:
        action, confidence, score, gated = "HOLD", "LOW", 0, True
        reasoning = f"Risk veto: {risk.get('note', 'risk.ok=false')}"
    elif bull_bias == "BUY" and bear_bias == "SELL":
        action, confidence, score, gated = "HOLD", "MEDIUM", 0, True
        reasoning = "Bull/bear disagreement → HOLD"

    notes = [
        f"Bull: {bull.get('note', bull_bias)}",
        f"Bear: {bear.get('note', bear_bias)}",
        f"Risk: {risk.get('note', risk_ok)}",
        reasoning,
    ]
    return {
        "symbol": symbol,
        "action": action,
        "confidence": confidence,
        "score": score,
        "reasons": notes,
        "ai_reasoning": json.dumps(payload, ensure_ascii=False)[:2000],
        "parse_mode": "multi_role",
        "multi_role_gated": gated,
        "bull_bias": bull_bias,
        "bear_bias": bear_bias,
        "risk_ok": risk_ok,
    }


def parse_multi_role_response(response: str, stock_data: dict) -> dict | None:
    payload = _extract_json(response)
    if not payload or "action" not in payload:
        return None
    if not any(k in payload for k in ("bull", "bear", "risk")):
        return None
    return consensus_from_multi_role(payload, str(stock_data.get("symbol", "Unknown")))
