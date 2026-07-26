"""Offline tests for LLM backend factory + OpenAI-compatible client."""

from __future__ import annotations

import json
from pathlib import Path
import urllib.error

import pytest

from stock_checker import ai_analyzer as aa


def test_resolve_backend_explicit(monkeypatch):
    monkeypatch.setenv("LLM_BACKEND", "openai")
    assert aa.resolve_llm_backend() == "openai"
    monkeypatch.setenv("LLM_BACKEND", "ollama")
    assert aa.resolve_llm_backend() == "ollama"


def test_make_analyzer_openai(monkeypatch):
    monkeypatch.setenv("LLM_BACKEND", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.groq.com/openai/v1")
    monkeypatch.setenv("AI_MODEL", "llama-3.1-8b-instant")
    analyzer = aa.make_analyzer()
    assert isinstance(analyzer, aa.OpenAICompatibleAnalyzer)
    assert analyzer.model == "llama-3.1-8b-instant"
    assert "groq" in analyzer.base_url


def test_openai_compatible_parses_chat(monkeypatch):
    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps(
                {"choices": [{"message": {"content": '{"action":"HOLD"}'}}]}
            ).encode()

    def fake_urlopen(req, timeout=60):
        assert "Authorization" in req.headers
        assert "Bearer test-key" in req.headers["Authorization"]
        return _Resp()

    monkeypatch.setattr(aa.urllib.request, "urlopen", fake_urlopen)
    client = aa.OpenAICompatibleAnalyzer(
        base_url="https://example.test/v1",
        api_key="test-key",
        model="tiny",
    )
    out = client._query_ollama("hello")
    assert "HOLD" in out


def test_openai_missing_key_message():
    client = aa.OpenAICompatibleAnalyzer(
        base_url="https://example.test/v1", api_key="", model="tiny"
    )
    out = client._query_ollama("hi")
    assert "OPENAI_API_KEY" in out or "LLM_API_KEY" in out
