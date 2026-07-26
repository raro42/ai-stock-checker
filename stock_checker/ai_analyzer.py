#!/usr/bin/env python3
"""Local Ollama or OpenAI-compatible cloud LLMs for paper-trade gates."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Optional


def _env_truthy(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _generic_stock_prompt(stock_data: dict) -> str:
    symbol = stock_data.get("symbol", "Unknown")
    name = stock_data.get("name", "Unknown")
    price = stock_data.get("current_price", "N/A")
    prev_close = stock_data.get("previous_close", "N/A")
    market_cap = stock_data.get("market_cap", "N/A")
    pe_ratio = stock_data.get("pe_ratio", "N/A")
    return f"""Analyze the following stock information and provide insights:

Stock: {name} ({symbol})
Current Price: ${price}
Previous Close: ${prev_close}
Market Cap: ${market_cap}
P/E Ratio: {pe_ratio}

Please provide:
1. Brief assessment of current valuation
2. Key observations from the data
3. Potential considerations for investors

Keep the analysis concise and factual based on the provided data."""


class OllamaAnalyzer:
    """Analyze stock data using Ollama AI models."""

    def __init__(
        self, base_url: str = "http://localhost:11434", model: str = "gemma4:latest"
    ):
        self.backend = "ollama"
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.generate_url = f"{self.base_url}/api/generate"

    def analyze_stock(self, stock_data: dict) -> str:
        return self._query_ollama(_generic_stock_prompt(stock_data))

    def _build_prompt(self, stock_data: dict) -> str:
        return _generic_stock_prompt(stock_data)

    def _query_ollama(self, prompt: str) -> str:
        """Send prompt to Ollama and get response."""
        payload = {"model": self.model, "prompt": prompt, "stream": False}

        try:
            data = json.dumps(payload).encode("utf-8")
            request = urllib.request.Request(
                self.generate_url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310
                result = json.load(response)
                return result.get("response", "No response from model")

        except urllib.error.URLError as e:
            return (
                f"Error connecting to Ollama: {str(e)}\n"
                f"Make sure Ollama is running at {self.base_url} "
                f"(or set LLM_BACKEND=openai for a cloud API)."
            )
        except Exception as e:
            return f"Error analyzing stock: {str(e)}"


class OpenAICompatibleAnalyzer:
    """Chat Completions API — Groq, OpenRouter, DeepSeek, OpenAI, etc."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_s: float = 60.0,
    ):
        self.backend = "openai"
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_s = timeout_s
        self.chat_url = f"{self.base_url}/chat/completions"

    def analyze_stock(self, stock_data: dict) -> str:
        return self._query_ollama(_generic_stock_prompt(stock_data))

    def _query_ollama(self, prompt: str) -> str:
        """Same call site as OllamaAnalyzer — chat completions under the hood."""
        if not self.api_key:
            return (
                "Error: OPENAI_API_KEY (or LLM_API_KEY) is empty. "
                "Set a free/cheap provider key, or use LLM_BACKEND=ollama / AI_MODE=off."
            )
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a careful paper-trading assistant. "
                        "Be concise and follow the user's output format exactly."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }
        try:
            data = json.dumps(payload).encode("utf-8")
            request = urllib.request.Request(
                self.chat_url,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                },
                method="POST",
            )
            with urllib.request.urlopen(  # noqa: S310
                request, timeout=self.timeout_s
            ) as response:
                result = json.load(response)
            choices = result.get("choices") or []
            if not choices:
                return "No response from model"
            msg = choices[0].get("message") or {}
            content = msg.get("content")
            if isinstance(content, list):
                # Some providers return content parts
                parts = [
                    p.get("text", "") for p in content if isinstance(p, dict)
                ]
                return "\n".join(parts).strip() or "No response from model"
            return str(content or "No response from model")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:400]
            return f"Error from cloud LLM HTTP {e.code}: {body}"
        except urllib.error.URLError as e:
            return f"Error connecting to cloud LLM at {self.base_url}: {e}"
        except Exception as e:
            return f"Error analyzing stock: {str(e)}"


def resolve_llm_backend() -> str:
    """ollama | openai — openai also selected when OPENAI_BASE_URL is set."""
    explicit = (os.getenv("LLM_BACKEND") or "").strip().lower()
    if explicit in {"openai", "openai_compatible", "cloud", "groq", "openrouter"}:
        return "openai"
    if explicit in {"ollama", "local"}:
        return "ollama"
    if os.getenv("OPENAI_BASE_URL") or os.getenv("OPENAI_API_KEY") or os.getenv(
        "LLM_API_KEY"
    ):
        # Prefer cloud when keys are present and backend unset
        if not os.getenv("OLLAMA_HOST") and (
            os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY")
        ):
            return "openai"
        if os.getenv("OPENAI_BASE_URL"):
            return "openai"
    return "ollama"


def make_analyzer(model: Optional[str] = None):
    """Factory: local Ollama or OpenAI-compatible cloud."""
    backend = resolve_llm_backend()
    model_name = (
        model
        or os.getenv("AI_MODEL")
        or ("llama-3.1-8b-instant" if backend == "openai" else "gemma4:latest")
    )
    if backend == "openai":
        base = (
            os.getenv("OPENAI_BASE_URL")
            or os.getenv("LLM_BASE_URL")
            or "https://api.groq.com/openai/v1"
        )
        key = (
            os.getenv("OPENAI_API_KEY")
            or os.getenv("LLM_API_KEY")
            or os.getenv("GROQ_API_KEY")
            or ""
        ).strip()
        return OpenAICompatibleAnalyzer(
            base_url=base, api_key=key, model=model_name
        )
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    return OllamaAnalyzer(base_url=host, model=model_name)
