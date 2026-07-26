# Local Ollama *or* cheap cloud LLMs

AI is **optional**. Rules-only paper trading (`AI_MODE=off`) needs no LLM at all.

## Paths by budget

| Budget | Setup | Notes |
|--------|--------|--------|
| **€0 + no GPU** | `AI_MODE=off` | Scanner + paper desk only — recommended default for friends without Ollama |
| **€0 free tier** | `LLM_BACKEND=openai` + Groq / OpenRouter free key | Fast cloud chat; rate limits apply |
| **Cents / day** | DeepSeek / cheap OpenRouter models | OpenAI-compatible |
| **Local privacy** | Ollama + `gemma4:latest` | House default when you have a machine |

## Cloud (OpenAI-compatible)

Works with **Groq**, **OpenRouter**, **DeepSeek**, Fireworks, Together, etc.

```bash
# .env
AI_MODE=validate
LLM_BACKEND=openai
OPENAI_API_KEY=gsk_...          # or LLM_API_KEY / GROQ_API_KEY
OPENAI_BASE_URL=https://api.groq.com/openai/v1
AI_MODEL=llama-3.1-8b-instant   # pick a free/cheap chat model on that host
```

OpenRouter example:

```bash
LLM_BACKEND=openai
OPENAI_BASE_URL=https://openrouter.ai/api/v1
OPENAI_API_KEY=sk-or-...
AI_MODEL=meta-llama/llama-3.1-8b-instruct:free
```

DeepSeek example:

```bash
LLM_BACKEND=openai
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_API_KEY=sk-...
AI_MODEL=deepseek-chat
```

Compose picks up `AI_MODE` / `AI_MODEL` from `.env`. Restart:

```bash
docker compose up -d --build intelligent-trader
```

## Local Ollama (house preference)

```bash
LLM_BACKEND=ollama   # or omit
OLLAMA_HOST=http://host.docker.internal:11434
AI_MODEL=gemma4:latest
OLLAMA_AUTOSEARCH_MODEL=gemma4:latest
```

### Picks (Ollama)

| Job | Default | Notes |
|-----|---------|--------|
| Paper-trader AI (`validate` / `full`) | **`gemma4:latest`** | Instruct / JSON trade gates |
| Autoresearch | **`gemma4:latest`** | Fallback: `qwen2.5-coder:latest` |
| Avoid for trading | coder-only / tiny granite | Wrong skill or too weak |

### Smoke test (strategy code validity)

| Model | Time | Valid? |
|-------|------|--------|
| `qwen2.5-coder:latest` | ~4s | yes |
| `gemma4:latest` | ~9s | yes ← **selected** |
| `qwen3:latest` | ~13s | yes |
| `qwen3.5:9b` | ~18–30s | no (empty response) |

Restart the Ollama autoresearch loop after changing `OLLAMA_AUTOSEARCH_MODEL`.
