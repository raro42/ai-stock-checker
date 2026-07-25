#!/usr/bin/env python3

import json
import re
from typing import Dict, Optional

from stock_checker.ai_analyzer import OllamaAnalyzer


class AIRecommender:
    """AI-driven recommendation engine using Ollama."""

    def __init__(self, model: str = "gemma4:latest"):
        import os
        ollama_host = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
        self.analyzer = OllamaAnalyzer(base_url=ollama_host, model=model)

    def get_ai_recommendation(self, stock_data: dict) -> Dict:
        """
        Get AI-driven buy/sell/hold recommendation.

        Returns dict with action, confidence, reasoning.
        """
        import sys

        prompt = self._build_trading_prompt(stock_data)

        print(f"\n{'='*80}", flush=True)
        print(f"🤖 AI PROMPT for {stock_data.get('symbol', 'Unknown')}", flush=True)
        print(f"{'='*80}", flush=True)
        print(prompt, flush=True)
        print(f"{'='*80}\n", flush=True)
        sys.stdout.flush()

        try:
            response = self.analyzer._query_ollama(prompt)

            print(f"\n{'='*80}", flush=True)
            print(f"🤖 AI RESPONSE for {stock_data.get('symbol', 'Unknown')}", flush=True)
            print(f"{'='*80}", flush=True)
            print(response, flush=True)
            print(f"{'='*80}\n", flush=True)
            sys.stdout.flush()

            return self._parse_ai_response(response, stock_data)
        except Exception as e:
            print(f"⚠️  AI Error for {stock_data.get('symbol', 'Unknown')}: {str(e)}", flush=True)
            sys.stdout.flush()
            import traceback
            traceback.print_exc()
            sys.stdout.flush()
            return {
                "action": "HOLD",
                "confidence": "LOW",
                "score": 0,
                "reasons": [f"AI error: {str(e)}"],
                "ai_reasoning": None,
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

        # Calculate daily change
        daily_change = 0
        if current_price and prev_close:
            daily_change = ((current_price - prev_close) / prev_close) * 100

        # Calculate 52-week position
        range_position = 0
        if current_price and week_52_high and week_52_low:
            range_position = ((current_price - week_52_low) / (week_52_high - week_52_low)) * 100

        # Build prompt with conditional fields
        prompt_lines = [
            "You are a trading advisor. Analyze this stock and provide a recommendation.",
            "",
            f"Stock: {name} ({symbol})",
            f"Current Price: ${current_price}",
            f"Previous Close: ${prev_close}",
            f"Daily Change: {daily_change:+.2f}%",
            f"52-Week High: ${week_52_high}",
            f"52-Week Low: ${week_52_low}",
            f"52-Week Position: {range_position:.1f}% of range",
        ]

        # Only include P/E ratio if it has a meaningful value
        if pe_ratio is not None:
            prompt_lines.append(f"P/E Ratio: {pe_ratio:.2f}")

        # Only include volume if available
        if volume is not None:
            if volume >= 1_000_000:
                prompt_lines.append(f"Volume: {volume:,.0f}")
            else:
                prompt_lines.append(f"Volume: {volume}")

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

        if pe_ratio is not None:
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
                try:
                    score = int(float(payload.get("score", 0)))
                except (TypeError, ValueError):
                    score = 0
                score = max(-100, min(100, score))
                reasoning = str(payload.get("reasoning") or payload.get("reason") or "No reasoning")
                return {
                    "symbol": symbol,
                    "action": action,
                    "confidence": confidence,
                    "score": score,
                    "reasons": [reasoning],
                    "ai_reasoning": response,
                    "current_price": stock_data.get("current_price"),
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

        # If required fields missing, force HOLD LOW (reject free-form garbage)
        if not action_match or not conf_match:
            return {
                "symbol": symbol,
                "action": "HOLD",
                "confidence": "LOW",
                "score": 0,
                "reasons": ["AI response missing structured ACTION/CONFIDENCE; defaulting to HOLD"],
                "ai_reasoning": response,
                "current_price": stock_data.get("current_price"),
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
            "current_price": stock_data.get("current_price"),
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
        import sys

        prompt = self._build_bitcoin_prompt(btc_data)

        print(f"\n{'='*80}", flush=True)
        print(f"🤖 AI PROMPT for BTC-USD", flush=True)
        print(f"{'='*80}", flush=True)
        print(prompt, flush=True)
        print(f"{'='*80}\n", flush=True)
        sys.stdout.flush()

        try:
            response = self.analyzer._query_ollama(prompt)

            print(f"\n{'='*80}", flush=True)
            print(f"🤖 AI RESPONSE for BTC-USD", flush=True)
            print(f"{'='*80}", flush=True)
            print(response, flush=True)
            print(f"{'='*80}\n", flush=True)
            sys.stdout.flush()

            btc_data_with_symbol = {**btc_data, "symbol": "BTC-USD"}
            return self._parse_ai_response(response, btc_data_with_symbol)
        except Exception as e:
            print(f"⚠️  AI Error for BTC-USD: {str(e)}", flush=True)
            sys.stdout.flush()
            import traceback
            traceback.print_exc()
            sys.stdout.flush()
            return {
                "symbol": "BTC-USD",
                "action": "HOLD",
                "confidence": "LOW",
                "score": 0,
                "reasons": [f"AI error: {str(e)}"],
                "ai_reasoning": None,
            }

    def _build_bitcoin_prompt(self, btc_data: dict) -> str:
        """Build Bitcoin-specific trading prompt."""
        current_price = btc_data.get("current_price")
        change_1d = btc_data.get("change_1d", 0)
        change_7d = btc_data.get("change_7d", 0)
        change_30d = btc_data.get("change_30d", 0)
        volatility = btc_data.get("volatility_30d", 0)
        week_52_high = btc_data.get("52_week_high")
        week_52_low = btc_data.get("52_week_low")

        # Calculate position
        range_position = 0
        if current_price and week_52_high and week_52_low:
            range_position = ((current_price - week_52_low) / (week_52_high - week_52_low)) * 100

        prompt = f"""You are a cryptocurrency trading advisor. Analyze Bitcoin and provide a recommendation.

Bitcoin (BTC-USD)
Current Price: ${current_price:,.2f}
1-Day Change: {change_1d:+.2f}%
7-Day Change: {change_7d:+.2f}%
30-Day Change: {change_30d:+.2f}%
30-Day Volatility: {volatility:.2f}%
52-Week High: ${week_52_high:,.2f}
52-Week Low: ${week_52_low:,.2f}
52-Week Position: {range_position:.1f}% of range

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
