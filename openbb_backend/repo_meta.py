"""Resolve public repo URL + latest commit for the paper desk footer."""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

_BACKEND_DIR = Path(__file__).resolve().parent
DEFAULT_REPO_URL = "https://github.com/raro42/ai-stock-checker"
BUILD_INFO_PATH = _BACKEND_DIR / "build_info.json"


def _parse_git_date(raw: str) -> tuple[str, str]:
    """Return (iso_utc, human display)."""
    raw = (raw or "").strip()
    if not raw:
        return "", ""
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        utc = dt.astimezone(timezone.utc)
        return (
            utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            utc.strftime("%Y-%m-%d %H:%M UTC"),
        )
    except ValueError:
        return raw, raw


def _candidate_git_dirs() -> list[str]:
    candidates = [
        os.getenv("DESK_GIT_DIR", "").strip(),
        "/git",
        str(_BACKEND_DIR.parent / ".git"),
    ]
    out: list[str] = []
    for c in candidates:
        if c and c not in out and Path(c).exists():
            out.append(c)
    return out


def _git_log(git_dir: Optional[str] = None) -> Optional[dict[str, str]]:
    dirs = [git_dir] if git_dir else _candidate_git_dirs()
    if not dirs and git_dir is None:
        # Bare `git` from cwd (host tests)
        dirs = [None]  # type: ignore[list-item]

    for gdir in dirs:
        cmd = ["git"]
        if gdir:
            cmd.extend(["--git-dir", gdir])
        cmd.extend(["log", "-1", "--format=%H%n%h%n%cI%n%s"])
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if proc.returncode != 0 or not proc.stdout.strip():
            continue
        lines = proc.stdout.strip().split("\n")
        if len(lines) < 4:
            continue
        sha, short, date_raw = lines[0], lines[1], lines[2]
        subject = "\n".join(lines[3:]).strip()
        iso, display = _parse_git_date(date_raw)
        return {
            "sha": sha.strip(),
            "short_sha": short.strip(),
            "message": subject,
            "committed_at": iso,
            "committed_at_display": display,
        }
    return None


def _from_build_info() -> Optional[dict[str, str]]:
    if not BUILD_INFO_PATH.exists():
        return None
    try:
        data = json.loads(BUILD_INFO_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    if not data.get("short_sha"):
        return None
    iso = str(data.get("committed_at") or "")
    display = str(data.get("committed_at_display") or "")
    if iso and not display:
        iso, display = _parse_git_date(iso)
    return {
        "sha": str(data.get("sha") or data.get("short_sha") or ""),
        "short_sha": str(data.get("short_sha") or "")[:12],
        "message": str(data.get("message") or ""),
        "committed_at": iso,
        "committed_at_display": display,
    }


def load_repo_meta(
    *,
    repo_url: Optional[str] = None,
    git_probe: Optional[Callable[[], Optional[dict[str, str]]]] = None,
) -> dict[str, Any]:
    """Return footer fields for the public GitHub repo link."""
    url = (repo_url or os.getenv("DESK_REPO_URL") or DEFAULT_REPO_URL).rstrip("/")
    commit: Optional[dict[str, str]]
    if git_probe is not None:
        commit = git_probe()
    else:
        commit = _git_log() or _from_build_info()

    if not commit:
        return {
            "url": url,
            "commit_url": url,
            "short_sha": "",
            "message": "",
            "committed_at": "",
            "committed_at_display": "",
            "available": False,
        }

    sha = commit.get("sha") or commit.get("short_sha") or ""
    short = commit.get("short_sha") or sha[:7]
    return {
        "url": url,
        "commit_url": f"{url}/commit/{sha}" if sha else url,
        "short_sha": short,
        "message": commit.get("message") or "",
        "committed_at": commit.get("committed_at") or "",
        "committed_at_display": commit.get("committed_at_display") or "",
        "available": True,
    }


def write_build_info(path: Path = BUILD_INFO_PATH) -> dict[str, Any]:
    """Snapshot current HEAD into build_info.json (host/CI helper)."""
    root_git = _BACKEND_DIR.parent / ".git"
    meta_commit = _git_log(git_dir=str(root_git) if root_git.exists() else None)
    payload = {
        "repo_url": DEFAULT_REPO_URL,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        **(meta_commit or {}),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return payload
