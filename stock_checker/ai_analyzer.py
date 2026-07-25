#!/usr/bin/env python3

import json
import urllib.error
import urllib.request


class OllamaAnalyzer:
    """Analyze stock data using Ollama AI models."""

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "gemma4:latest"):
        self.base_url = base_url
        self.model = model
        self.generate_url = f"{base_url}/api/generate"

    def analyze_stock(self, stock_data: dict) -> str:
        """
        Analyze stock data and provide AI-powered insights.

        Args:
            stock_data: Dictionary containing stock information

        Returns:
            Analysis text from the AI model
        """
        prompt = self._build_prompt(stock_data)
        return self._query_ollama(prompt)

    def _build_prompt(self, stock_data: dict) -> str:
        """Build analysis prompt from stock data."""
        symbol = stock_data.get("symbol", "Unknown")
        name = stock_data.get("name", "Unknown")
        price = stock_data.get("current_price", "N/A")
        prev_close = stock_data.get("previous_close", "N/A")
        market_cap = stock_data.get("market_cap", "N/A")
        pe_ratio = stock_data.get("pe_ratio", "N/A")

        prompt = f"""Analyze the following stock information and provide insights:

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

        return prompt

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
            return f"Error connecting to Ollama: {str(e)}\nMake sure Ollama is running at {self.base_url}"
        except Exception as e:
            return f"Error analyzing stock: {str(e)}"
