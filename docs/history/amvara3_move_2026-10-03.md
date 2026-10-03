# Move the desk to amvara3 (2026-10-03)

Review of `ssh amvara3`, then the first move of the paper desk.

## Host

- Name: `amvara3`. Ubuntu 24.04. CPU: x86_64, 20 cores. RAM: 62 GiB. Disk free: about 139 GiB.
- Docker 28 and Compose v2 are installed. Cursor CLI is installed for root. Ollama is not installed.
- Public HTTP and HTTPS go through the HAProxy container.
- Live host names: `cometa.amvara.de`, `redmine.amvara.de`, `redminetest.amvara.de`.
- TLS files are one certificate per name in `/home/amvara/projects/certs-ssl`. There is no wildcard certificate.
- DNS for `amvara.de` is at Joker. The desk name is `stock.zeitfenster.de` (A record to this host).

## What runs where

- Code: `/home/amvara/projects/ai-stock-checker` (git clone).
- Paper book: `data/` and `.env` copied from the Mac. They stay out of git.
- Containers: `intelligent-trader` and `openbb-backend`.
- Desk bind: `127.0.0.1:7779` only. Open it with an SSH tunnel:

```bash
ssh -L 7779:127.0.0.1:7779 amvara3
```

Then open `http://127.0.0.1:7779/desk`.

- `AI_MODE=off` on the server. The host has no Ollama. Do not turn validate mode on until a model is reachable.
- The Mac containers stop after the server desk answers `/health`, so two loops do not trade the same book.

## Certificate

On 2026-10-03 certbot issued `stock.zeitfenster.de` (standalone HTTP-01, ECDSA). It expires on 2027-01-01. The combined PEM is `/home/amvara/projects/certs-ssl/stock.zeitfenster.de.pem`. The name is in the deploy hook, so the 03:00 renewal job keeps it.

## Public site

HAProxy sends `stock.zeitfenster.de` to `127.0.0.1:7779`. Open the desk at `https://stock.zeitfenster.de/desk`.

The OpenBB widget routes use `OPENBB_BACKEND_API_KEY` when that value is set. The desk pages, including Ops save, do not use that key.
