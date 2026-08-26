#!/usr/bin/env python3
"""
High-volume autoresearch without Ollama.

Mutates one hyperparameter assignment in experiment_strategy.py, scores with the
same harness, keep/revert like the Ollama worker. Use for dense grid search;
do not run alongside the Ollama loop (git race).
"""

from __future__ import annotations

import argparse
import os
import random
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from stock_checker.ollama_autoresearch import parse_val_score  # noqa: E402

STRATEGY_PATH = ROOT / "stock_checker" / "experiment_strategy.py"
RESULTS_PATH = ROOT / "autoresearch" / "results.tsv"
RUN_LOG = ROOT / "autoresearch" / "run.log"
EXPERIMENT_SH = ROOT / "scripts" / "run_autoresearch_once.sh"
HOST_EXPERIMENT = ROOT / "scripts" / "run_experiment.py"

# One name → candidate values. Worker picks one (name, value) not recently tried.
PARAM_GRID: Dict[str, List[Any]] = {
    "SHORT_SMA": [12, 15, 20, 25],
    "SHORT_MOMENTUM_SMA": [3, 5, 8, 10],
    "MED_SMA": [30, 40, 50, 60],
    "LONG_SMA": [40, 50, 60, 90, 100],
    "MIN_VOLUME_RATIO": [1.0, 1.1, 1.2, 1.3, 1.5],
    "MAX_RETURN_STDEV": [0.012, 0.0135, 0.015, 0.018, 0.02],
    "RS_LOOKBACK": [10, 15, 20, 30, 40],
    "REQUIRE_REL_STRENGTH": [True, False],
    "REQUIRE_SPY_UPTREND": [True, False],
    "REQUIRE_VOLUME_CONFIRM": [True, False],
    "MIN_ENTRY_RSI": [30.0, 35.0, 40.0],
    "MAX_ENTRY_RSI": [60.0, 65.0, 70.0],
    "EXIT_PRICE_CONFIRMATION_MULTIPLIER": [0.92, 0.95, 0.98],
}

WF_ERA_MARKER = "walk-forward rebaseline"


def _run(cmd: List[str], *, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, check=check)


def git_short_head() -> str:
    return _run(["git", "rev-parse", "--short", "HEAD"]).stdout.strip()


def best_keep_score() -> float:
    if not RESULTS_PATH.exists():
        return float("-inf")
    body = RESULTS_PATH.read_text().splitlines()[1:]
    start = 0
    for i, line in enumerate(body):
        if WF_ERA_MARKER in line and "\tkeep\t" in line:
            start = i
    best = float("-inf")
    for line in body[start:]:
        parts = line.split("\t")
        if len(parts) < 3 or parts[2].strip() != "keep":
            continue
        try:
            best = max(best, float(parts[1]))
        except ValueError:
            continue
    return best


def recent_param_ideas(limit: int = 80) -> List[str]:
    if not RESULTS_PATH.exists():
        return []
    out: List[str] = []
    for line in RESULTS_PATH.read_text().splitlines()[1:]:
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        desc = parts[3].strip()
        if desc.startswith("param:"):
            out.append(desc)
    return out[-limit:]


def _format_value(value: Any) -> str:
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, float):
        # Keep readable floats
        return repr(float(value))
    return repr(value)


def apply_param(source: str, name: str, value: Any) -> Tuple[str, Optional[str]]:
    """
    Replace a top-level `NAME = ...` assignment (first match).
    Returns (new_source, error_or_none).
    """
    if name not in PARAM_GRID:
        return source, f"unknown param {name}"
    pat = re.compile(rf"^({re.escape(name)}\s*=\s*)([^\n#]+)(.*)$", re.MULTILINE)
    m = pat.search(source)
    if not m:
        return source, f"assignment not found: {name}"
    new_line = f"{m.group(1)}{_format_value(value)}{m.group(3)}"
    new_source, n = pat.subn(new_line, source, count=1)
    if n != 1:
        return source, f"replace failed: {name}"
    idea_line = f"# idea: param: {name}={_format_value(value)}"
    if re.search(r"^# idea:", new_source, re.MULTILINE):
        new_source = re.sub(r"^# idea:.*$", idea_line, new_source, count=1, flags=re.MULTILINE)
    else:
        new_source = idea_line + "\n" + new_source
    return new_source, None


def pick_mutation(rng: random.Random) -> Tuple[str, Any, str]:
    tried = set(recent_param_ideas())
    candidates: List[Tuple[str, Any, str]] = []
    for name, values in PARAM_GRID.items():
        for value in values:
            idea = f"param: {name}={_format_value(value)}"
            if idea not in tried:
                candidates.append((name, value, idea))
    if not candidates:
        # All grid cells seen recently — reshuffle full grid
        for name, values in PARAM_GRID.items():
            for value in values:
                idea = f"param: {name}={_format_value(value)}"
                candidates.append((name, value, idea))
    return rng.choice(candidates)


def append_result(commit: str, score: float, status: str, description: str) -> None:
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not RESULTS_PATH.exists():
        RESULTS_PATH.write_text("commit\tval_score\tstatus\tdescription\n")
    with RESULTS_PATH.open("a") as f:
        f.write(f"{commit}\t{score:.6f}\t{status}\t{description}\n")


def commit_strategy(message: str) -> str:
    _run(["git", "add", str(STRATEGY_PATH)])
    _run(["git", "commit", "-m", message])
    return git_short_head()


def reset_hard(commit: str) -> None:
    _run(["git", "reset", "--hard", commit])


def run_experiment() -> Tuple[int, str]:
    use_host = os.getenv("AUTOSEARCH_HOST_SCORE", "0") == "1"
    if use_host:
        proc = subprocess.run(
            [sys.executable, str(HOST_EXPERIMENT)],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        log = proc.stdout + proc.stderr
        RUN_LOG.write_text(log)
        return proc.returncode, log
    proc = subprocess.run(
        ["bash", str(EXPERIMENT_SH)],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    log = RUN_LOG.read_text() if RUN_LOG.exists() else (proc.stdout + proc.stderr)
    return proc.returncode, log


def one_iteration(*, seed: Optional[int] = None) -> int:
    rng = random.Random(seed)
    keep_commit = git_short_head()
    best = best_keep_score()
    current = STRATEGY_PATH.read_text()
    name, value, idea = pick_mutation(rng)
    new_source, err = apply_param(current, name, value)
    if err:
        print(f"crash: {err}")
        return 2
    if new_source.strip() == current.strip():
        print(f"discard: no change for {idea}")
        append_result(keep_commit, best if best > float("-inf") else -999.0, "discard", idea)
        return 1

    STRATEGY_PATH.write_text(new_source)
    try:
        new_commit = commit_strategy(f"exp: {idea}")
    except subprocess.CalledProcessError as exc:
        print(f"crash: git commit failed: {exc.stderr}")
        STRATEGY_PATH.write_text(current)
        return 2

    print(f"experiment_commit: {new_commit}")
    print(f"idea: {idea}")
    code, log = run_experiment()
    score = parse_val_score(log)
    if code != 0 or score is None:
        print("crash: experiment failed")
        append_result(new_commit, -999.0, "crash", idea)
        reset_hard(keep_commit)
        return 1

    print(f"val_score: {score:.6f} (best keep was {best})")
    if score > best:
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
    parser = argparse.ArgumentParser(description="Param-grid autoresearch (no Ollama)")
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args(argv)
    return one_iteration(seed=args.seed)


if __name__ == "__main__":
    raise SystemExit(main())
