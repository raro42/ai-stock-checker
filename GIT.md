# Git commit & push strategy

**Default for this repo: commit and push as soon as work is verified.**  
Do not wait for the human to say “commit” or “push”.

## When to commit

Commit after any of these (whichever comes first):

1. A coherent feature/fix/docs change is done **and** offline tests pass (`docker run --rm ai-stock-checker pytest -q`)
2. An autoresearch experiment finishes keep/revert (`experiment_strategy.py` + related harness fixes)
3. You are about to switch tasks or end a turn with uncommitted non-secret changes
4. Docs/rules (`AGENTS.md`, `OPENBB.md`, compose) changed

Prefer **small, frequent commits** over large batches.

## Commit message style

- Imperative, scoped, English: `fix earnings blackout weekend path`
- Focus on **why** in one short subject (≤72 chars); optional body for context
- Use a HEREDOC:

```bash
git commit -m "$(cat <<'EOF'
Short imperative summary.

Optional body if needed.
EOF
)"
```

## What never to commit

- `.env`, API keys, tokens, credentials
- `data/` runtime portfolios, `trades.jsonl`, archives
- `autoresearch/results.tsv`, `autoresearch/run.log`
- Host junk (`.DS_Store`, `__pycache__`, `.venv`)

If unsure whether a file is secret → **do not commit**; add to `.gitignore`.

## Branches

| Branch | Purpose |
|--------|---------|
| `main` | Stable product path friends run |
| `autoresearch/<tag>` | Overnight keep/revert experiments (e.g. `autoresearch/jul25`) |

- Product improvements: commit on current working branch; merge/PR to `main` when stable
- Autoresearch: commit every experiment attempt; losers are `git reset --hard` to last keep (see `autoresearch/program.md`)
- Never rewrite published `main` history (`push --force` to `main`/`master` is forbidden)

## When to push

**Push immediately after each successful commit** when `origin` exists:

```bash
git push -u origin HEAD
```

- First push on a new branch: always `-u`
- Prefer non-force pushes only (`git push`). No `--force` / `--force-with-lease` on `main`
- Force-with-lease on feature/`autoresearch/*` branches only if the human explicitly asked

## If there is no remote yet

1. Still **commit locally** immediately
2. Create or link GitHub remote (preferred):

```bash
gh repo create ai-stock-checker --private --source=. --remote=origin --push
```

Or if the repo already exists on GitHub:

```bash
git remote add origin git@github.com:<user>/ai-stock-checker.git
git push -u origin HEAD
```

3. Do not invent a different remote URL; use `gh` / existing GitHub ownership

## Safety (non-negotiable)

- Never update `git config`
- Never skip hooks (`--no-verify`) unless the human explicitly requests it
- Never commit if the only changes are secrets or gitignored runtime data
- After commit+push: `git status` should be clean (except ignored files)

## Agent checklist (every meaningful change)

1. Run offline tests
2. `git status` / `git diff` / recent `git log` for style
3. Stage relevant files (not secrets)
4. Commit with HEREDOC message
5. `git push -u origin HEAD` (or create remote then push); merge to `main` when product-facing
6. Restart Docker services / overnight loops when the change requires a reload; confirm healthy
7. Confirm with `git status -sb` — never leave shippable work unpushed overnight (CEST)
