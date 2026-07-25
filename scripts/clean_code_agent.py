#!/usr/bin/env python3
"""
Clean-code agent: find and remove slop (safe auto-fixes + report).

Slop = dead ad-hoc scripts, stale duplicate docs, unused imports, empty stubs,
noisy AI leftover comments — not trading emoji logs (product voice).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "docs" / "history"
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
MODEL = os.getenv("OLLAMA_CLEAN_MODEL", os.getenv("AI_MODEL", "gemma4:latest"))

# Root-level one-off scripts that duplicate tests/ or manual demos
ROOT_SLOP_SCRIPTS = (
    "test_ai_logging.py",
    "test_binance.py",
    "test_enhanced_system.py",
    "test_scanner.py",
)

STALE_DOC_REDIRECTS = {
    "ENHANCED_SYSTEM_README.md": (
        "# Deprecated\n\n"
        "This file is historical slop from the 2025 “enhanced system” naming.\n\n"
        "Use **[README.md](README.md)** and **[FRIENDS.md](FRIENDS.md)** instead.\n"
    ),
}


@dataclass
class Finding:
    path: str
    kind: str
    detail: str
    fixed: bool = False


@dataclass
class Report:
    findings: List[Finding] = field(default_factory=list)
    ruff_fixed: int = 0

    def add(self, path: str, kind: str, detail: str, fixed: bool = False) -> None:
        self.findings.append(Finding(path, kind, detail, fixed))


def _run(cmd: List[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)


def move_root_slop_scripts(apply: bool, report: Report) -> None:
    dest = ROOT / "scripts" / "manual"
    for name in ROOT_SLOP_SCRIPTS:
        src = ROOT / name
        if not src.exists():
            continue
        report.add(name, "root_ad_hoc_script", f"move to scripts/manual/{name}", fixed=apply)
        if apply:
            dest.mkdir(parents=True, exist_ok=True)
            target = dest / name
            if target.exists():
                src.unlink()
            else:
                shutil.move(str(src), str(target))
            readme = dest / "README.md"
            if not readme.exists():
                readme.write_text(
                    "# Manual / ad-hoc scripts\n\n"
                    "Not part of pytest. Kept for archaeology; prefer `tests/`.\n"
                )


def redirect_stale_docs(apply: bool, report: Report) -> None:
    for name, body in STALE_DOC_REDIRECTS.items():
        path = ROOT / name
        if not path.exists():
            continue
        current = path.read_text()
        if current.strip().startswith("# Deprecated"):
            continue
        report.add(name, "stale_doc", "replace with redirect to README", fixed=apply)
        if apply:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            archive = ROOT / "docs" / "history" / f"archived_{name}_{stamp}.md"
            archive.parent.mkdir(parents=True, exist_ok=True)
            archive.write_text(current)
            path.write_text(body)


def scan_comment_slop(report: Report) -> None:
    """Flag common AI leftover comments (report-only)."""
    pat = re.compile(
        r"#\s*(NOTE:|IMPORTANT:|This (function|method|class) (is|does)|"
        r"Ensure that|Make sure to|Here we|We (need|want) to)\b",
        re.I,
    )
    for path in (ROOT / "stock_checker").rglob("*.py"):
        if path.name == "experiment_strategy.py":
            continue
        try:
            text = path.read_text()
        except OSError:
            continue
        hits = 0
        for i, line in enumerate(text.splitlines(), 1):
            if pat.search(line):
                hits += 1
                if hits <= 3:
                    report.add(
                        str(path.relative_to(ROOT)),
                        "comment_slop",
                        f"L{i}: {line.strip()[:100]}",
                    )


def _ruff(args: List[str]) -> subprocess.CompletedProcess:
    """Prefer local ruff; fall back to project Docker image."""
    import shutil

    if shutil.which("ruff"):
        return _run(["ruff", *args])
    via_mod = _run([sys.executable, "-m", "ruff", *args])
    if via_mod.returncode in (0, 1) and "No module named" not in (via_mod.stderr or ""):
        return via_mod
    return _run(
        [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{ROOT}:/app",
            "-w",
            "/app",
            "ai-stock-checker",
            "ruff",
            *args,
        ]
    )


def ruff_autofix(apply: bool, report: Report) -> None:
    targets = ["stock_checker", "openbb_backend", "scripts", "tests"]
    select = "F401,F841"
    check = _ruff(["check", *targets, f"--select={select}"])
    out = (check.stdout or "") + (check.stderr or "")
    if "F401" in out or "F841" in out:
        report.add(".", "ruff", f"unused import/var findings:\n{out[:1200]}")
    elif check.returncode == 0:
        report.add(".", "ruff", "no F401/F841 issues", fixed=False)
    else:
        report.add(".", "ruff", f"ruff exit {check.returncode}: {out[-400:]}")
    if apply:
        fix = _ruff(["check", *targets, f"--select={select}", "--fix"])
        fixed_out = (fix.stdout or "") + (fix.stderr or "")
        report.add(".", "ruff_fix", fixed_out[-800:] or "ruff --fix done", fixed=True)


def ollama_review_snippet(paths: List[Path], report: Report) -> Optional[str]:
    """Ask gemma4 for a short review of flagged files (no auto-apply)."""
    chunks = []
    for p in paths[:4]:
        try:
            body = p.read_text()[:4000]
        except OSError:
            continue
        chunks.append(f"### {p}\n```python\n{body}\n```")
    if not chunks:
        return None
    prompt = (
        "You are a strict clean-code reviewer. List ONLY concrete slop to remove "
        "(dead code, useless comments, duplication). No praise. Max 12 bullets.\n\n"
        + "\n\n".join(chunks)
    )
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": 800},
    }
    try:
        req = urllib.request.Request(
            f"{OLLAMA_HOST}/api/generate",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=180) as resp:  # noqa: S310
            text = json.load(resp).get("response") or ""
    except Exception as exc:  # noqa: BLE001
        report.add("ollama", "review_skip", str(exc))
        return None
    return text.strip()


def write_report(report: Report, review: Optional[str], apply: bool) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    day = datetime.now().strftime("%Y-%m-%d")
    path = REPORT_DIR / f"clean_code_{day}.md"
    lines = [
        f"# Clean-code agent report — {day}",
        "",
        f"Mode: `{'apply' if apply else 'dry-run'}` · model review: `{MODEL}`",
        "",
        "## Findings",
        "",
    ]
    if not report.findings:
        lines.append("_No findings._")
    else:
        for f in report.findings:
            mark = "fixed" if f.fixed else "open"
            lines.append(f"- **{f.kind}** (`{mark}`) `{f.path}` — {f.detail}")
    if review:
        lines.extend(["", "## Ollama review (advisory)", "", review, ""])
    lines.extend(
        [
            "",
            "## Next",
            "",
            "- Re-run with `--apply` after dry-run review",
            "- Keep trading log emoji (product voice); do not “sanitize” UX prints",
            "",
        ]
    )
    path.write_text("\n".join(lines))
    return path


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Clean-code agent")
    parser.add_argument("--apply", action="store_true", help="Apply safe fixes")
    parser.add_argument("--no-ollama", action="store_true", help="Skip LLM advisory review")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    report = Report()
    move_root_slop_scripts(args.apply, report)
    redirect_stale_docs(args.apply, report)
    scan_comment_slop(report)
    ruff_autofix(args.apply, report)

    review = None
    if not args.no_ollama:
        samples = [
            ROOT / "stock_checker" / "intelligent_trader.py",
            ROOT / "stock_checker" / "recommender.py",
            ROOT / "openbb_backend" / "main.py",
        ]
        samples = [p for p in samples if p.exists()]
        review = ollama_review_snippet(samples, report)

    out = write_report(report, review, args.apply)
    if not args.quiet:
        print(out.read_text())
        print(f"report: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
