#!/usr/bin/env python3

import json
import os
import re
import sys
from typing import Dict

from stock_checker.ai_analyzer import make_analyzer
from stock_checker.secret_redact import redact_secrets, safe_exc_text
from stock_checker.technical_indicators import (
    _finite_signed,
    _valid_close,
    _valid_volume,
    coerce_score,
    daily_pct_change,
)


def _ai_verbose() -> bool:
    return os.getenv("AI_VERBOSE", "0").strip().lower() in {"1", "true", "yes", "on"}


def ai_backend_unavailable(response: str | None) -> bool:
    """True when the LLM transport failed (not a real model answer)."""
    text = (response or "").strip().lower()
    if not text:
        return True
    needles = (
        "error connecting to ollama",
        "error connecting to cloud llm",
        "error from cloud llm http",
        "error analyzing stock:",
        "make sure ollama is running",
        "couldn't connect to server",
        "connection refused",
    )
    return any(n in text for n in needles)


class AIRecommender:
    """AI-driven recommendation engine (Ollama or OpenAI-compatible cloud)."""

    def __init__(self, model: str = "gemma4:latest"):
        self.analyzer = make_analyzer(model)

    def _log_block(self, title: str, body: str) -> None:
        if not _ai_verbose():
            return
        print(f"\n{'='*80}", flush=True)
        print(title, flush=True)
        print(f"{'='*80}", flush=True)
        print(body, flush=True)
        print(f"{'='*80}\n", flush=True)
        sys.stdout.flush()

    def get_ai_recommendation(self, stock_data: dict) -> Dict:
        """
        Get AI-driven buy/sell/hold recommendation.

        Returns dict with action, confidence, reasoning.
        """
        from stock_checker.ai_multi_role import (
            build_multi_role_prompt,
            multi_role_enabled,
            parse_multi_role_response,
        )

        symbol = stock_data.get("symbol", "Unknown")
        use_multi = multi_role_enabled()
        prompt = (
            build_multi_role_prompt(stock_data)
            if use_multi
            else self._build_trading_prompt(stock_data)
        )

        self._log_block(f"🤖 AI PROMPT for {symbol}", prompt)

        try:
            response = self.analyzer._query_ollama(prompt)
            self._log_block(f"🤖 AI RESPONSE for {symbol}", response)

            if ai_backend_unavailable(response):
                out = {
                    "symbol": symbol,
                    "action": "HOLD",
                    "confidence": "LOW",
                    "score": 0,
                    "reasons": [
                        "AI backend unreachable — fail-open (scanner rules keep)"
                    ],
                    "ai_reasoning": response,
                    "current_price": stock_data.get("current_price"),
                    "parse_mode": "unavailable",
                }
                if not _ai_verbose():
                    print(
                        f"🤖 AI {symbol}: unavailable "
                        f"(backend down — fail-open)",
                        flush=True,
                    )
                return out

            parsed = None
            if use_multi:
                multi = parse_multi_role_response(response, stock_data)
                if multi:
                    multi["current_price"] = stock_data.get("current_price")
                    parsed = multi
            if parsed is None:
                parsed = self._parse_ai_response(response, stock_data)

            if not _ai_verbose():
                print(
                    f"🤖 AI {symbol}: {parsed.get('action')} "
                    f"conf={parsed.get('confidence')} score={parsed.get('score')} "
                    f"mode={parsed.get('parse_mode')}",
                    flush=True,
                )
            return parsed
        except Exception as e:
            print(f"⚠️  AI Error for {symbol}: {safe_exc_text(e)}", flush=True)
            sys.stdout.flush()
            if _ai_verbose():
                import traceback

                print(redact_secrets(traceback.format_exc()), flush=True)
                sys.stdout.flush()
            return {
                "symbol": symbol,
                "action": "HOLD",
                "confidence": "LOW",
                "score": 0,
                "reasons": [f"AI error: {safe_exc_text(e)} — fail-open"],
                "ai_reasoning": None,
                "current_price": stock_data.get("current_price"),
                "parse_mode": "unavailable",
            }

    def _build_trading_prompt(self, stock_data: dict) -> str:
        """Build a focused trading prompt for the AI."""
        symbol = stock_data.get("symbol", "Unknown")
        name = stock_data.get("name", "Unknown")
        current_price = stock_data.get("current_price")
        prev_close = stock_data.get("previous_close")
        week_52_high = stock_data.get("52_week_high")
        week_52_low = stock_data.get("52_week_low")
        pe_ratio = stock_data.get("pe_ratio")
        volume = stock_data.get("volume")

        # Missing/bool/gap marks → n/a (never invent flat +0.00 / True→$1).
        # Stock lines used to print raw `$True`; BTC prompt already used money bits.
        def _money_bit(raw: object) -> str:
            if not _valid_close(raw):
                return "n/a"
            return f"${float(raw):,.2f}"

        daily = daily_pct_change(current_price, prev_close)
        daily_bit = f"{daily:+.2f}%" if daily is not None else "n/a"

        range_bit = "n/a"
        if (
            _valid_close(current_price)
            and _valid_close(week_52_high)
            and _valid_close(week_52_low)
        ):
            span = float(week_52_high) - float(week_52_low)
            if span > 0:
                range_bit = (
                    f"{((float(current_price) - float(week_52_low)) / span) * 100.0:.1f}%"
                    f" of range"
                )

        # Build prompt with conditional fields
        prompt_lines = [
            "You are a trading advisor. Analyze this stock and provide a recommendation.",
            "",
            f"Stock: {name} ({symbol})",
            f"Current Price: {_money_bit(current_price)}",
            f"Previous Close: {_money_bit(prev_close)}",
            f"Daily Change: {daily_bit}",
            f"52-Week High: {_money_bit(week_52_high)}",
            f"52-Week Low: {_money_bit(week_52_low)}",
            f"52-Week Position: {range_bit}",
        ]

        # Bool/gap P/E or volume must not invent 1.00 / 1-share prints (True→1).
        if _finite_signed(pe_ratio):
            prompt_lines.append(f"P/E Ratio: {float(pe_ratio):.2f}")

        if _valid_volume(volume):
            vol_n = float(volume)
            if vol_n >= 1_000_000:
                prompt_lines.append(f"Volume: {vol_n:,.0f}")
            else:
                prompt_lines.append(f"Volume: {vol_n}")

        prompt_lines.extend([
            "",
            "Based on this data, provide a trading recommendation.",
            "Prefer a single JSON object:",
            '{"action":"BUY|SELL|HOLD","confidence":"HIGH|MEDIUM|LOW","score":0,"reasoning":"..."}',
            "",
            "Or use this EXACT text format:",
            "",
            "ACTION: [BUY/SELL/HOLD]",
            "CONFIDENCE: [HIGH/MEDIUM/LOW]",
            "SCORE: [number between -100 and +100, negative for sell, positive for buy]",
            "REASONING: [1-2 sentences explaining your decision]",
            "",
            "Focus on:",
            "1. Price momentum (daily change)",
            "2. Valuation position (52-week range)",
        ])

        if _finite_signed(pe_ratio):
            prompt_lines.append("3. P/E ratio (valuation)")
            prompt_lines.append("4. Overall risk/reward")
        else:
            prompt_lines.append("3. Overall risk/reward")

        prompt_lines.extend([
            "",
            "Be direct and concise. Do not add extra commentary outside the format."
        ])

        prompt = "\n".join(prompt_lines)

        return prompt

    def _parse_ai_response(self, response: str, stock_data: dict) -> Dict:
        """Parse AI response into structured recommendation (JSON preferred)."""
        symbol = stock_data.get("symbol", "Unknown")

        # Prefer JSON object if the model returned one
        json_blob = None
        fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response, re.DOTALL | re.IGNORECASE)
        if fence:
            json_blob = fence.group(1)
        else:
            brace = re.search(r"\{[^{}]*\"action\"[^{}]*\}", response, re.IGNORECASE | re.DOTALL)
            if brace:
                json_blob = brace.group(0)

        if json_blob:
            try:
                payload = json.loads(json_blob)
                action = str(payload.get("action", "HOLD")).upper()
                if action not in {"BUY", "SELL", "HOLD"}:
                    action = "HOLD"
                confidence = str(payload.get("confidence", "LOW")).upper()
                if confidence not in {"HIGH", "MEDIUM", "LOW"}:
                    confidence = "LOW"
                # tradermonty #700/#655 + xang1234/portfolio AI: refuse bool/gap
                # invent (True→1); missing/invalid → flat 0 (HOLD-safe).
                sc = coerce_score(payload.get("score"))
                score = int(sc) if sc is not None else 0
                score = max(-100, min(100, score))
                reasoning = str(payload.get("reasoning") or payload.get("reason") or "No reasoning")
                mark = stock_data.get("current_price")
                return {
                    "symbol": symbol,
                    "action": action,
                    "confidence": confidence,
                    "score": score,
                    "reasons": [reasoning],
                    "ai_reasoning": response,
                    # Refuse bool/gap — True→$1 must not leave parse as a usable mark.
                    "current_price": float(mark) if _valid_close(mark) else None,
                    "parse_mode": "json",
                }
            except json.JSONDecodeError:
                pass

        # Extract action
        action_match = re.search(r"ACTION:\s*(BUY|SELL|HOLD)", response, re.IGNORECASE)
        action = action_match.group(1).upper() if action_match else "HOLD"

        # Extract confidence
        conf_match = re.search(r"CONFIDENCE:\s*(HIGH|MEDIUM|LOW)", response, re.IGNORECASE)
        confidence = conf_match.group(1).upper() if conf_match else "LOW"

        # Extract score
        score_match = re.search(r"SCORE:\s*([+-]?\d+)", response)
        score = int(score_match.group(1)) if score_match else 0
        score = max(-100, min(100, score))

        mark = stock_data.get("current_price")
        mark_out = float(mark) if _valid_close(mark) else None

        # If required fields missing, force HOLD LOW (reject free-form garbage)
        if not action_match or not conf_match:
            return {
                "symbol": symbol,
                "action": "HOLD",
                "confidence": "LOW",
                "score": 0,
                "reasons": ["AI response missing structured ACTION/CONFIDENCE; defaulting to HOLD"],
                "ai_reasoning": response,
                "current_price": mark_out,
                "parse_mode": "rejected",
            }

        # Extract reasoning
        reason_match = re.search(r"REASONING:\s*(.+?)(?:\n|$)", response, re.IGNORECASE | re.DOTALL)
        reasoning = reason_match.group(1).strip() if reason_match else "No specific reasoning provided"

        return {
            "symbol": symbol,
            "action": action,
            "confidence": confidence,
            "score": score,
            "reasons": [reasoning],
            "ai_reasoning": response,
            "current_price": mark_out,
            "parse_mode": "text",
        }

    def validate_recommendation(
        self, rule_based_rec: Dict, stock_data: dict
    ) -> Dict:
        """
        Hybrid mode: AI validates rule-based recommendation.

        Returns enhanced recommendation with AI validation.
        """
        # Only validate HIGH confidence signals
        if rule_based_rec["confidence"] != "HIGH":
            return rule_based_rec

        # Get AI opinion
        ai_rec = self.get_ai_recommendation(stock_data)

        # AI agrees with rule-based signal
        if ai_rec["action"] == rule_based_rec["action"]:
            return {
                **rule_based_rec,
                "confidence": "HIGH",
                "ai_validated": True,
                "ai_reasoning": ai_rec.get("ai_reasoning"),
                "reasons": rule_based_rec["reasons"] + [f"AI confirms: {ai_rec['reasons'][0]}"],
            }

        # AI suggests HOLD when rules say BUY/SELL
        elif ai_rec["action"] == "HOLD":
            return {
                **rule_based_rec,
                "confidence": "MEDIUM",
                "ai_validated": False,
                "ai_reasoning": ai_rec.get("ai_reasoning"),
                "reasons": rule_based_rec["reasons"] + [f"AI suggests caution: {ai_rec['reasons'][0]}"],
            }

        # AI disagrees (opposite action)
        else:
            return {
                **rule_based_rec,
                "action": "HOLD",
                "confidence": "LOW",
                "ai_validated": False,
                "ai_reasoning": ai_rec.get("ai_reasoning"),
                "reasons": [f"Rules suggest {rule_based_rec['action']}, but AI recommends {ai_rec['action']}. Defaulting to HOLD."],
            }

    def get_bitcoin_ai_recommendation(self, btc_data: dict) -> Dict:
        """Get AI recommendation specifically for Bitcoin."""
        prompt = self._build_bitcoin_prompt(btc_data)
        self._log_block("🤖 AI PROMPT for BTC-USD", prompt)

        try:
            response = self.analyzer._query_ollama(prompt)
            self._log_block("🤖 AI RESPONSE for BTC-USD", response)

            btc_data_with_symbol = {**btc_data, "symbol": "BTC-USD"}
            parsed = self._parse_ai_response(response, btc_data_with_symbol)
            if not _ai_verbose():
                print(
                    f"🤖 AI BTC-USD: {parsed.get('action')} "
                    f"conf={parsed.get('confidence')} score={parsed.get('score')}",
                    flush=True,
                )
            return parsed
        except Exception as e:
            print(f"⚠️  AI Error for BTC-USD: {safe_exc_text(e)}", flush=True)
            sys.stdout.flush()
            if _ai_verbose():
                import traceback

                print(redact_secrets(traceback.format_exc()), flush=True)
                sys.stdout.flush()
            return {
                "symbol": "BTC-USD",
                "action": "HOLD",
                "confidence": "LOW",
                "score": 0,
                "reasons": [f"AI error: {safe_exc_text(e)}"],
                "ai_reasoning": None,
            }

    def _build_bitcoin_prompt(self, btc_data: dict) -> str:
        """Build Bitcoin-specific trading prompt."""
        current_price = btc_data.get("current_price")
        week_52_high = btc_data.get("52_week_high")
        week_52_low = btc_data.get("52_week_low")

        # Missing/bool/gap → n/a (never invent flat +0.00 / True→$1 / 0% vol).
        def _pct_bit(raw: object) -> str:
            if not _finite_signed(raw):
                return "n/a"
            return f"{float(raw):+.2f}%"

        def _money_bit(raw: object) -> str:
            if not _valid_close(raw):
                return "n/a"
            return f"${float(raw):,.2f}"

        def _vol_bit(raw: object) -> str:
            if not _finite_signed(raw):
                return "n/a"
            return f"{float(raw):.2f}%"

        range_bit = "n/a"
        if (
            _valid_close(current_price)
            and _valid_close(week_52_high)
            and _valid_close(week_52_low)
        ):
            span = float(week_52_high) - float(week_52_low)
            if span > 0:
                range_bit = (
                    f"{((float(current_price) - float(week_52_low)) / span) * 100.0:.1f}%"
                    f" of range"
                )

        prompt = f"""You are a cryptocurrency trading advisor. Analyze Bitcoin and provide a recommendation.

Bitcoin (BTC-USD)
Current Price: {_money_bit(current_price)}
1-Day Change: {_pct_bit(btc_data.get("change_1d"))}
7-Day Change: {_pct_bit(btc_data.get("change_7d"))}
30-Day Change: {_pct_bit(btc_data.get("change_30d"))}
30-Day Volatility: {_vol_bit(btc_data.get("volatility_30d"))}
52-Week High: {_money_bit(week_52_high)}
52-Week Low: {_money_bit(week_52_low)}
52-Week Position: {range_bit}

Based on this data, provide a trading recommendation following this EXACT format:

ACTION: [BUY/SELL/HOLD]
CONFIDENCE: [HIGH/MEDIUM/LOW]
SCORE: [number between -100 and +100, negative for sell, positive for buy]
REASONING: [1-2 sentences explaining your decision]

Focus on:
1. Multi-timeframe momentum (1d, 7d, 30d trends)
2. Volatility level (risk assessment)
3. Position in yearly range
4. Overall trend direction

Be direct and concise. Do not add extra commentary outside the format."""

        return prompt
