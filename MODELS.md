# Local Ollama model choices

**House preference: `gemma4:latest`** for trading AI and autoresearch (human choice, 2026-07-25). It passed the strategy-code smoke test (~9s).

## Picks

| Job | Default | Notes |
|-----|---------|--------|
| Paper-trader AI (`validate` / `full`) | **`gemma4:latest`** | Instruct / JSON trade gates |
| Autoresearch (`experiment_strategy.py`) | **`gemma4:latest`** | Preferred; slightly slower than `qwen2.5-coder` but valid |
| Fallback if gemma4 busy/weak on code | `qwen2.5-coder:latest` | Fastest valid code emitter in smoke test |
| OCR / images | LightOnOCR / `qwen3-vl:8b` | Not for trading |
| Avoid for trading | coder-only / tiny granite | Wrong skill or too weak |
| Avoid until retested | `qwen3.5:9b` | Empty `/api/generate` responses observed |

## Smoke test (strategy code validity)

| Model | Time | Valid? |
|-------|------|--------|
| `qwen2.5-coder:latest` | ~4s | yes |
| `gemma4:latest` | ~9s | yes ← **selected** |
| `qwen3:latest` | ~13s | yes |
| `qwen3.5:9b` | ~18–30s | no (empty response) |

## Env

```bash
AI_MODEL=gemma4:latest
OLLAMA_AUTOSEARCH_MODEL=gemma4:latest
```

Restart the Ollama autoresearch loop after changing `OLLAMA_AUTOSEARCH_MODEL`.
