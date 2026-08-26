#!/usr/bin/env python3
"""
Local Ollama autoresearch worker — one keep/revert experiment without Cursor tokens.

Edits only stock_checker/experiment_strategy.py, runs Docker harness, updates results.tsv.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from stock_checker.ollama_autoresearch import (  # noqa: E402
    extract_python,
    parse_val_score,
    validate_strategy_source,
)

STRATEGY_PATH = ROOT / "stock_checker" / "experiment_strategy.py"
RESULTS_PATH = ROOT / "autoresearch" / "results.tsv"
RUN_LOG = ROOT / "autoresearch" / "run.log"
EXPERIMENT_SH = ROOT / "scripts" / "run_autoresearch_once.sh"

DEFAULT_MODEL = os.getenv("OLLAMA_AUTOSEARCH_MODEL", "gemma4:latest")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")


def _run(cmd: List[str], *, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, check=check)


def git_short_head() -> str:
    return _run(["git", "rev-parse", "--short", "HEAD"]).stdout.strip()


WF_ERA_MARKER = "walk-forward rebaseline"


def best_keep_score() -> Tuple[float, str]:
    """
    Best keep row in the walk-forward era only.

    Pre-WF inflated scores (e.g. ~9–14) must not block new experiments.
    """
    if not RESULTS_PATH.exists():
        return float("-inf"), ""
    body = RESULTS_PATH.read_text().splitlines()[1:]
    start = 0
    for i, line in enumerate(body):
        if WF_ERA_MARKER in line and "\tkeep\t" in line:
            start = i
    best = float("-inf")
    desc = ""
    for line in body[start:]:
        parts = line.split("\t")
        if len(parts) < 4 or parts[2].strip() != "keep":
            continue
        try:
            score = float(parts[1])
        except ValueError:
            continue
        if score > best:
            best = score
            desc = parts[3].strip()
    return best, desc


def recent_discard_phrases(limit: int = 12) -> List[str]:
    if not RESULTS_PATH.exists():
        return []
    out: List[str] = []
    for line in RESULTS_PATH.read_text().splitlines()[1:]:
        parts = line.split("\t")
        if len(parts) < 4 or parts[2].strip() != "discard":
            continue
        out.append(parts[3].strip()[:80])
    return out[-limit:]


def recent_rows(limit: int = 8) -> str:
    if not RESULTS_PATH.exists():
        return "(none yet)"
    lines = RESULTS_PATH.read_text().splitlines()
    body = lines[1:] if lines else []
    return "\n".join(body[-limit:]) or "(none yet)"


def query_ollama(prompt: str, model: str, timeout: int = 300) -> str:
    url = f"{OLLAMA_HOST}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.7, "num_predict": 4096},
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        result = json.load(resp)
    return result.get("response") or ""


def build_prompt(current: str, best_score: float, best_desc: str) -> str:
    bank_path = ROOT / "autoresearch" / "idea_bank.md"
    if bank_path.exists():
        bank = bank_path.read_text(encoding="utf-8")[:3500]
    else:
        bank = (
            "Try ONE unused idea: loosen/tighten MAX_RETURN_STDEV; toggle REQUIRE_REL_STRENGTH; "
            "change RS_LOOKBACK 10–40; SMA 12/30/90; exit when short < long (slower exit); "
            "volume ratio 1.0–1.5; disable SPY uptrend for one run; RSI entry band 35–65 only."
        )
    banned = recent_discard_phrases()
    banned_txt = "; ".join(banned) if banned else "(none)"
    score_txt = f"{best_score:.4f}" if best_score > float("-inf") else "n/a"
    return f"""You are optimizing a long-only paper trading strategy for an offline walk-forward backtest.

GOAL: Maximize val_score (robust OOS folds). Avoid hyper-churn and fee burn.

CONSTRAINTS:
- Output ONE complete Python module only (no prose before/after).
- Prefer a ```python fenced block.
- Must define generate_signals(bars_by_symbol, index, portfolio) -> dict[symbol, 'BUY'|'SELL'].
- Keep stdlib only (typing ok). No network, no subprocess, no file I/O.
- Change ONE clear NEW idea vs the current file.
- Do NOT repeat these recent failed ideas: {banned_txt}
- First line after the module docstring should be a short comment: # idea: <your unique idea>

CURRENT BEST KEEP (walk-forward era only): val_score={score_txt} ({best_desc or 'n/a'})

RECENT RESULTS (commit, score, status, description):
{recent_rows()}

IDEA BANK (pick ONE unused testable idea):
{bank}

CURRENT FILE stock_checker/experiment_strategy.py:
```python
{current}
```

Rewrite the full file with one improvement that might beat val_score {score_txt}.
"""


def append_result(commit: str, score: float, status: str, description: str) -> None:
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not RESULTS_PATH.exists():
        RESULTS_PATH.write_text("commit\tval_score\tstatus\tdescription\n")
    with RESULTS_PATH.open("a") as fh:
        fh.write(f"{commit}\t{score:.6f}\t{status}\t{description}\n")


def commit_strategy(message: str) -> str:
    _run(["git", "add", str(STRATEGY_PATH.relative_to(ROOT))])
    _run(["git", "commit", "-m", message])
    return git_short_head()


def reset_hard(commit: str) -> None:
    _run(["git", "reset", "--hard", commit])


def run_experiment() -> Tuple[int, str]:
    proc = subprocess.run(
        ["bash", str(EXPERIMENT_SH)],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    log = RUN_LOG.read_text() if RUN_LOG.exists() else (proc.stdout + proc.stderr)
    return proc.returncode, log


def one_iteration(
    *,
    model: str,
    description_hint: str = "",
    dry_run: bool = False,
) -> int:
    keep_commit = git_short_head()
    best_score, best_desc = best_keep_score()
    current = STRATEGY_PATH.read_text()
    prompt = build_prompt(current, best_score, best_desc)

    print(f"ollama_model: {model}")
    print(f"keep_commit:  {keep_commit}")
    print(f"best_keep:    {best_score}")

    try:
        raw = query_ollama(prompt, model=model)
    except urllib.error.URLError as exc:
        print(f"crash: ollama unreachable ({exc})")
        return 2
    except Exception as exc:  # noqa: BLE001
        print(f"crash: ollama error ({exc})")
        return 2

    source = extract_python(raw)
    err = validate_strategy_source(source)
    if err:
        print(f"discard: invalid proposal ({err})")
        preview = raw[:400].replace("\n", " ")
        print(f"raw_preview: {preview}")
        append_result(
            keep_commit,
            best_score if best_score > float("-inf") else -999.0,
            "crash",
            f"invalid proposal: {err}",
        )
        return 1

    if source.strip() == current.strip():
        print("discard: model returned identical file")
        append_result(
            keep_commit,
            best_score if best_score > float("-inf") else -999.0,
            "discard",
            "identical proposal",
        )
        return 1

    if dry_run:
        print("--- dry-run proposed source (first 40 lines) ---")
        print("\n".join(source.splitlines()[:40]))
        return 0

    STRATEGY_PATH.write_text(source)
    idea = description_hint or "ollama local proposal"
    # Prefer "# idea: ..." then other comments; never shebang / hyperparam headers.
    skip_prefixes = ("#!", "# -*-", "# coding")
    for line in source.splitlines()[:40]:
        s = line.strip()
        if not s.startswith("#"):
            continue
        if any(s.startswith(p) for p in skip_prefixes):
            continue
        if "EDITABLE" in s or "Harness:" in s or "Export " in s:
            continue
        body = s.lstrip("# ").strip()
        if body.lower().startswith("idea:"):
            idea = body[5:].strip()[:80]
            break
        if body.lower().startswith("hyperparameters") or "agent may tune" in body.lower():
            continue
        if body.lower().startswith("require short"):
            continue
        if len(body) > 8 and idea == (description_hint or "ollama local proposal"):
            idea = body[:80]

    try:
        new_commit = commit_strategy(f"exp: {idea}")
    except subprocess.CalledProcessError as exc:
        print(f"crash: git commit failed: {exc.stderr}")
        STRATEGY_PATH.write_text(current)
        return 2

    print(f"experiment_commit: {new_commit}")
    code, log = run_experiment()
    score = parse_val_score(log)
    if code != 0 or score is None:
        print("crash: experiment failed")
        print(log[-1500:] if log else "(empty log)")
        append_result(new_commit, -999.0, "crash", idea)
        reset_hard(keep_commit)
        print(f"reverted: {keep_commit}")
        return 1

    print(f"val_score: {score:.6f} (best keep was {best_score})")
    if score > best_score:
        append_result(new_commit, score, "keep", idea)
        print("status: keep")
        if os.getenv("OLLAMA_AUTOSEARCH_PUSH", "0") == "1":
            push = _run(["git", "push", "origin", "HEAD"], check=False)
            print("push:", "ok" if push.returncode == 0 else push.stderr.strip())
        return 0

    append_result(new_commit, score, "discard", idea)
    reset_hard(keep_commit)
    print(f"status: discard; reverted to {keep_commit}")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Ollama-powered autoresearch one-shot")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Ollama model name")
    parser.add_argument("--dry-run", action="store_true", help="Propose only; no write/commit")
    parser.add_argument("--hint", default="", help="Short description hint for results.tsv")
    args = parser.parse_args(argv)
    return one_iteration(model=args.model, description_hint=args.hint, dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
