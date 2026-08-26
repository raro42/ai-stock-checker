# Skill security review — awesome-skills/code-review-skill

**Date:** 2026-08-26  
**Target:** https://github.com/awesome-skills/code-review-skill (`SKILL.md` + `scripts/pr-analyzer.py`)  
**Verdict:** **Not clearly malicious.** Safe enough as **read-only guidance** if pinned and not given blind shell trust. **Do not install as an auto-loaded Cursor skill without pinning + tool limits.**

## What we checked

1. Full `SKILL.md` frontmatter + body (raw GitHub).
2. Sole executable script: `scripts/pr-analyzer.py` (full source).
3. Repo layout via GitHub API (`scripts/`, `.hive/`, `reference/`, `assets/`).
4. Pattern scan for exfil / secret grab / shell abuse (`curl`, `wget`, `requests`, `socket`, `eval`, `exec`, `subprocess`, webhooks, pastebin, SSH keys, prompt-injection phrases).
5. Public context: agent-skill supply chain is risky in general (Snyk / NVIDIA SkillSpector research). That is ecosystem risk, not a specific bomb in this file.

## Malicious indicators

| Check | Result |
|--------|--------|
| Instructs agent to read/send `.env`, keys, SSH, wallets | **No** |
| Hidden network exfil in `pr-analyzer.py` | **No** — stdin/file in, stdout report out; stdlib only |
| `eval` / `exec` / `subprocess` / `os.system` | **No** |
| Prompt injection (“ignore previous rules”, exfil secrets) | **No** in `SKILL.md` |
| Bundled install hook / LaunchAgent / cron | **No** |
| Over-broad “run anything” install script | **No** |

`.env` / `secret` hits in `pr-analyzer.py` are **risk labels** for review (“security-sensitive file”), not credential theft.

## Residual risks (real, not panic)

1. **`allowed-tools` includes `Bash` and `WebFetch`.**  
   That is normal for “run lint/tests / fetch docs,” but a skill that can run shell is always a future supply-chain surface. If upstream edits `SKILL.md` later, wording can change.

2. **Supply-chain mutability.**  
   Today’s `main` looks clean. Tomorrow’s commit might not. Pin a **commit SHA** if you install anything. Re-read after updates.

3. **Scope bloat.**  
   Huge multi-language review encyclopedia. Not malware — but it can pull the agent into React/Java noise and away from our Python/Docker paper desk. Prefer a **thin local rule** for “remove > add / dead code / simplify branches.”

4. **`.hive/` folder.**  
   Repo has `.hive/PROTOCOL.md` + memory/tasks (agent-coordination metadata). Not required for review. Do **not** treat it as trusted automation. Ignore unless you intentionally use that ecosystem.

5. **WebFetch “latest docs”.**  
   Can fetch arbitrary URLs the model chooses. Risk is prompt-driven browsing, not baked-in C2 in this skill. Keep network tools gated.

## Fit for ai-stock-checker

- Useful ideas: reuse-before-add, nested-conditionals, severity labels, security checklist *as reading material*.
- Poor fit as a **default always-on skill**: wrong default stack (React/Vue/etc.), Bash allowance, large token load.
- We already have a user rule: senior developer prefers **removing** over adding. That is **not** yet a committed project rule under `.cursor/rules/` / `AGENTS.md` for this repo.

## Recommendation

1. **Do not** blindly install from `main` with full Bash trust.
2. If you want the review checklists: **vendor a pinned copy** of `SKILL.md` + needed `reference/*.md` into the repo, or write a short local rule (prefer remove / dead code / simplify if-else / no secret exfil).
3. Keep using Cursor’s built-in **review-security** / **review-bugbot** skills for PR review — they are local and known.
4. Never let any skill run commands that print or upload `.env`, `data/`, SSH keys, or API tokens.

## Senior-coder rule status (this repo)

- Present as a **Cursor user rule** (host-level): think twice before adding; seniors remove.
- **Missing** as an explicit always-on project rule in `AGENTS.md` / `.cursor/rules/` for ai-stock-checker (as of this note).
