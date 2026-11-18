# Ollama via amvara8 tunnel (2026-11-18)

## Why

The paper desk runs on **amvara3**. That host has no Ollama.
**amvara8** runs Ollama (`gemma4:latest`, `gemma4:12b`, …) on `*:11434`.

Public `178.63.8.217:11434` times out from amvara3 and the Mac (firewall).
amvara3 **can** SSH to amvara8 and curl `127.0.0.1:11434` there.

## Fix

Install a systemd SSH local forward on amvara3:

```bash
sudo ./scripts/install_ollama_tunnel_amvara8.sh
```

That binds `127.0.0.1:11434` → amvara8 `127.0.0.1:11434`.
Compose keeps `OLLAMA_HOST=http://host.docker.internal:11434` (host-gateway).

Then set Ops `ai_mode=validate` (model `gemma4:latest`).

## Checks

```bash
curl -sS -m 5 http://127.0.0.1:11434/api/tags
docker compose exec intelligent-trader \
  sh -c 'curl -sS -m 5 "$OLLAMA_HOST/api/tags" | head -c 200'
systemctl status ai-stock-checker-ollama-amvara8.service
```

## Safety

Do not open amvara8 `:11434` to the public internet.
Prefer the SSH tunnel. Keep AI validate off if the tunnel is down
(fail-open still exists, but prefer an honest Ops setting).
