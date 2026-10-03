# Move the desk to amvara3 (2026-10-03)

Review of `ssh amvara3`, then the first move of the paper desk.

## Host

- Name: `amvara3`. Ubuntu 24.04. CPU: x86_64, 20 cores. RAM: 62 GiB. Disk free: about 139 GiB.
- Docker 28 and Compose v2 are installed. Cursor CLI is installed for root. Ollama is not installed.
- Public HTTP and HTTPS go through the HAProxy container.
- Live host names: `cometa.amvara.de`, `redmine.amvara.de`, `redminetest.amvara.de`.
- TLS files are one certificate per name in `/home/amvara/projects/certs-ssl`. There is no wildcard certificate.
- DNS for `amvara.de` is at Joker. `stock.amvara.de` has no A record yet.

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

## Public site (not done)

Do not add the desk to HAProxy until all of these are true:

1. Add an A record for `stock.amvara.de` to the amvara3 address.
2. Issue a certificate with certbot. Put the PEM in `/home/amvara/projects/certs-ssl`.
3. Set `OPENBB_BACKEND_API_KEY` in the server `.env`. The Ops config route can change the trader when the key is empty.
4. Add a HAProxy host ACL and a backend to `127.0.0.1:7779`. Reload HAProxy only after a config check. A bad reload breaks Cometa and Redmine.
