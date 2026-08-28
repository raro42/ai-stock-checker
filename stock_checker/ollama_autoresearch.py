"""Helpers for local Ollama autoresearch (token-free overnight experiments)."""

from __future__ import annotations

import ast
import re
from typing import Optional


def extract_python(text: str) -> str:
    """Pull Python source from model output (fences / think tags)."""
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"<thinking>.*?</thinking>", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
    fence = re.search(r"```(?:python)?\s*\n(.*?)```", cleaned, flags=re.DOTALL | re.IGNORECASE)
    if fence:
        return fence.group(1).strip() + "\n"
    for marker in ("#!/usr/bin/env python", "from __future__", "def generate_signals"):
        idx = cleaned.find(marker)
        if idx >= 0:
            if marker == "def generate_signals":
                start = cleaned.rfind("#!/usr/bin/env python", 0, idx)
                if start < 0:
                    start = cleaned.rfind("from __future__", 0, idx)
                if start < 0:
                    start = 0
                return cleaned[start:].strip() + "\n"
            return cleaned[idx:].strip() + "\n"
    return cleaned.strip() + "\n"


def validate_strategy_source(source: str) -> Optional[str]:
    """Return error message or None if OK."""
    if "def generate_signals" not in source:
        return "missing def generate_signals"
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return f"syntax error: {exc}"
    names = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    if "generate_signals" not in names:
        return "generate_signals not a function"
    forbidden = ("subprocess", "os.system", "urllib", "requests", "socket", "eval(", "exec(")
    lower = source.lower()
    for token in forbidden:
        if token in lower:
            return f"forbidden token: {token}"
    return None


def parse_val_score(log_text: str) -> Optional[float]:
    m = re.search(r"^val_score:\s*([-+0-9.eE]+)", log_text, re.MULTILINE)
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def parse_beats_spy_walkforward(log_text: str) -> Optional[bool]:
    m = re.search(
        r"^beats_buy_hold_spy_walkforward:\s*(true|false)",
        log_text,
        re.MULTILINE | re.IGNORECASE,
    )
    if not m:
        return None
    return m.group(1).lower() == "true"


def idea_family(description: str) -> str:
    """Coarse idea family for morning stall review."""
    low = (description or "").lower()
    if low.startswith("param:") or "param: " in low:
        name = low.split("param:", 1)[-1].strip().split("=")[0].strip()
        if name:
            return f"param:{name}"
        return "param"
    if "fails spy wf" in low:
        return "spy_gate"
    if "rsi" in low:
        return "rsi"
    if "volume" in low or "min_volume" in low:
        return "volume"
    if "rel_strength" in low or "relative strength" in low or "rs_lookback" in low:
        return "rs"
    if "spy" in low and "uptrend" in low:
        return "spy_filter"
    if "stdev" in low or "volatil" in low or "true range" in low:
        return "vol"
    if "exit" in low or "sma" in low:
        return "sma_exit"
    return "other"
