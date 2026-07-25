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
