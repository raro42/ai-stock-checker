# Local Ollama model choices

Do **not** use one model for everything. Defaults below were checked on this machine (2026-07-25).

## Picks

| Job | Best default | Why |
|-----|--------------|-----|
| Paper-trader AI (`validate` / `full`) | **`gemma4:latest`** | Instruct model for JSON trade gates — not a coder model |
| Autoresearch (`experiment_strategy.py`) | **`qwen2.5-coder:latest`** | Fast + reliably emits valid Python in smoke test; already proven in overnight loop |
| Cursor local chat / light coding (optional) | **`qwen2.5-coder:latest`** | Same as autoresearch; keep overnight **Cursor agent** on cloud unless A/B proves otherwise |
| General Q&A (non-code) | **`gemma4:latest`** or **`qwen3:latest`** | Fine for chat; not preferred for strategy file rewrites |
| OCR / images | LightOnOCR / `qwen3-vl:8b` | Not for trading or strategy code |

## Smoke test (strategy code validity)

Prompt: emit a minimal `generate_signals` module.

| Model | Time | Valid? |
|-------|------|--------|
| `qwen2.5-coder:latest` | ~4s | yes |
| `gemma4:latest` | ~9s | yes |
| `qwen3:latest` | ~13s | yes |
| `qwen3.5:9b` | ~18–30s | **no** (empty `/api/generate` response here) |

So: **Qwen is not automatically best** — `qwen3.5:9b` looked strongest on paper (largest) but failed this API path tonight. Prefer **`qwen2.5-coder:latest`** for code generation until that is fixed/retested.

## Env

```bash
# trading
AI_MODEL=gemma4:latest

# autoresearch worker
OLLAMA_AUTOSEARCH_MODEL=qwen2.5-coder:latest
```

Restart the Ollama autoresearch loop after changing `OLLAMA_AUTOSEARCH_MODEL`.
