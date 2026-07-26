#!/usr/bin/env python3
"""Watch curated GitHub repos for new commits and releases.

Writes:
  data/github_watch/state.json   — last-seen SHAs / tags (local)
  data/github_watch/latest.json  — machine digest for desk / scripts
  data/github_watch/latest.md    — human digest
  docs/history/github_watch_YYYY-MM-DD.md — dated copy when --archive

Uses `gh api` when available, else HTTPS + optional GITHUB_TOKEN.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WATCHLIST = ROOT / "config" / "github_watchlist.json"
DEFAULT_STATE_DIR = ROOT / "data" / "github_watch"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def load_watchlist(path: Path) -> list[dict[str, str]]:
    data = json.loads(path.read_text())
    repos = data.get("repos") or []
    out = []
    for row in repos:
        repo = (row.get("repo") or "").strip()
        if not repo or "/" not in repo:
            continue
        out.append({"repo": repo, "why": (row.get("why") or "").strip()})
    return out


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"repos": {}}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {"repos": {}}


def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")


class GitHubClient:
    """Thin client: prefer `gh api`, fall back to urllib."""

    def __init__(self, token: Optional[str] = None, use_gh: bool = True):
        self.token = (token or os.getenv("GITHUB_TOKEN") or "").strip() or None
        self.use_gh = use_gh and shutil.which("gh") is not None

    def get_json(self, path: str) -> Any:
        """path like /repos/owner/name/commits?per_page=5"""
        if self.use_gh:
            try:
                proc = subprocess.run(
                    ["gh", "api", path.lstrip("/")],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=60,
                )
                if proc.returncode == 0 and proc.stdout.strip():
                    return json.loads(proc.stdout)
                # fall through on auth/rate errors
            except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
                pass

        url = f"https://api.github.com{path if path.startswith('/') else '/' + path}"
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "ai-stock-checker-github-watch",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            body = exc.read().decode(errors="replace")[:300]
            raise RuntimeError(f"GitHub HTTP {exc.code} for {path}: {body}") from exc


def _short_sha(sha: str) -> str:
    return (sha or "")[:7]


def fetch_repo_activity(
    client: GitHubClient, repo: str, *, commits: int = 8, releases: int = 3
) -> dict[str, Any]:
    meta: dict[str, Any] = {}
    try:
        meta = client.get_json(f"/repos/{repo}") or {}
    except Exception as exc:  # noqa: BLE001 — surface per-repo errors
        return {"repo": repo, "error": str(exc), "commits": [], "releases": []}

    commit_rows: list[dict[str, Any]] = []
    try:
        raw = client.get_json(f"/repos/{repo}/commits?per_page={commits}") or []
        if isinstance(raw, list):
            for c in raw:
                commit = c.get("commit") or {}
                author = commit.get("author") or {}
                commit_rows.append(
                    {
                        "sha": c.get("sha") or "",
                        "short": _short_sha(c.get("sha") or ""),
                        "message": (commit.get("message") or "").split("\n", 1)[0][:160],
                        "date": author.get("date") or "",
                        "url": c.get("html_url") or f"https://github.com/{repo}/commit/{c.get('sha')}",
                    }
                )
    except Exception as exc:  # noqa: BLE001
        commit_rows = []
        meta["_commits_error"] = str(exc)

    release_rows: list[dict[str, Any]] = []
    try:
        raw = client.get_json(f"/repos/{repo}/releases?per_page={releases}") or []
        if isinstance(raw, list):
            for r in raw:
                release_rows.append(
                    {
                        "tag": r.get("tag_name") or "",
                        "name": r.get("name") or r.get("tag_name") or "",
                        "published_at": r.get("published_at") or "",
                        "url": r.get("html_url") or "",
                        "prerelease": bool(r.get("prerelease")),
                    }
                )
    except Exception as exc:  # noqa: BLE001
        meta["_releases_error"] = str(exc)

    return {
        "repo": repo,
        "url": meta.get("html_url") or f"https://github.com/{repo}",
        "description": (meta.get("description") or "")[:240],
        "stars": int(meta.get("stargazers_count") or 0),
        "pushed_at": meta.get("pushed_at") or "",
        "default_branch": meta.get("default_branch") or "main",
        "archived": bool(meta.get("archived")),
        "commits": commit_rows,
        "releases": release_rows,
        "error": None,
    }


def diff_against_state(
    activity: dict[str, Any], prev: dict[str, Any]
) -> dict[str, Any]:
    """Return new commits/releases since last run (or all if first seen)."""
    prev = prev or {}
    last_sha = prev.get("last_commit_sha") or ""
    last_tag = prev.get("last_release_tag") or ""
    commits = activity.get("commits") or []
    releases = activity.get("releases") or []

    new_commits: list[dict] = []
    for c in commits:
        if last_sha and c.get("sha") == last_sha:
            break
        new_commits.append(c)
    # On first run, only highlight the tip (avoid dumping history as "new")
    first_seen = not last_sha
    if first_seen:
        new_commits = commits[:3]

    new_releases: list[dict] = []
    for r in releases:
        if last_tag and r.get("tag") == last_tag:
            break
        new_releases.append(r)
    if not last_tag and releases:
        new_releases = releases[:1]

    tip_sha = commits[0]["sha"] if commits else last_sha
    tip_tag = releases[0]["tag"] if releases else last_tag

    return {
        "first_seen": first_seen,
        "new_commits": new_commits,
        "new_releases": new_releases,
        "has_updates": bool(new_commits or new_releases) and not first_seen,
        "baseline": first_seen,
        "tip_sha": tip_sha,
        "tip_tag": tip_tag,
        "tip_message": commits[0]["message"] if commits else "",
    }


def build_digest(
    watchlist: list[dict[str, str]],
    activities: list[dict[str, Any]],
    diffs: list[dict[str, Any]],
) -> dict[str, Any]:
    why = {w["repo"]: w.get("why") or "" for w in watchlist}
    rows = []
    updates = 0
    for act, diff in zip(activities, diffs):
        repo = act["repo"]
        row = {
            **act,
            "why": why.get(repo, ""),
            **{k: diff[k] for k in (
                "first_seen",
                "new_commits",
                "new_releases",
                "has_updates",
                "baseline",
                "tip_sha",
                "tip_tag",
                "tip_message",
            )},
        }
        if row.get("has_updates"):
            updates += 1
        rows.append(row)

    ideas: list[str] = []
    for row in rows:
        if row.get("error"):
            continue
        label = row["repo"]
        if row.get("has_updates"):
            for c in row.get("new_commits") or []:
                ideas.append(f"{label}: commit {_short_sha(c['sha'])} — {c['message']}")
            for r in row.get("new_releases") or []:
                ideas.append(f"{label}: release {r['tag']} — {r.get('name') or r['tag']}")
        elif row.get("baseline") and row.get("tip_message"):
            ideas.append(f"{label} (baseline): {row['tip_message']}")

    return {
        "generated_at": _now_iso(),
        "repo_count": len(rows),
        "update_count": updates,
        "idea_bullets": ideas[:40],
        "repos": rows,
    }


def render_markdown(digest: dict[str, Any]) -> str:
    lines = [
        f"# GitHub idea watch — {digest.get('generated_at', '')}",
        "",
        "Curated external repos. Steal **one** transferable idea at a time; re-benchmark before adopting.",
        "",
        f"- Repos watched: **{digest.get('repo_count', 0)}**",
        f"- Repos with new activity since last run: **{digest.get('update_count', 0)}**",
        "",
    ]
    bullets = digest.get("idea_bullets") or []
    if bullets:
        lines.append("## Highlights")
        lines.append("")
        for b in bullets:
            lines.append(f"- {b}")
        lines.append("")
    else:
        lines.append("_No new commits/releases since last check._")
        lines.append("")

    lines.append("## Per repo")
    lines.append("")
    for row in digest.get("repos") or []:
        name = row.get("repo")
        lines.append(f"### [{name}]({row.get('url')})")
        if row.get("error"):
            lines.append(f"- **Error:** `{row['error']}`")
            lines.append("")
            continue
        why = row.get("why") or ""
        if why:
            lines.append(f"- Watch reason: {why}")
        desc = row.get("description") or ""
        if desc:
            lines.append(f"- {desc}")
        lines.append(
            f"- Stars: {row.get('stars', 0)} · pushed: {row.get('pushed_at') or '—'} · "
            f"branch: `{row.get('default_branch')}`"
            + (" · **archived**" if row.get("archived") else "")
        )
        if row.get("baseline"):
            lines.append("- Status: **baseline recorded** (first watch)")
        elif row.get("has_updates"):
            lines.append("- Status: **updates since last run**")
        else:
            lines.append("- Status: quiet")

        new_c = row.get("new_commits") or []
        if new_c:
            lines.append("- Commits:")
            for c in new_c[:8]:
                lines.append(
                    f"  - [`{c['short']}`]({c['url']}) {c['date'][:10]} — {c['message']}"
                )
        new_r = row.get("new_releases") or []
        if new_r:
            lines.append("- Releases:")
            for r in new_r[:5]:
                lines.append(
                    f"  - [{r['tag']}]({r['url']}) {str(r.get('published_at') or '')[:10]} — {r.get('name')}"
                )
        lines.append("")

    lines.append("## How to use")
    lines.append("")
    lines.append("1. Skim highlights for UX, risk, or research patterns we lack.")
    lines.append("2. Open one PR/commit; note a single idea in IMPROVEMENT.md Phase C.")
    lines.append("3. Implement a minimal slice; never promote without walk-forward / paper evidence.")
    lines.append("")
    return "\n".join(lines)


def update_state(state: dict[str, Any], diffs: list[dict[str, Any]], activities: list[dict]) -> dict[str, Any]:
    repos_state = state.setdefault("repos", {})
    for act, diff in zip(activities, diffs):
        repo = act["repo"]
        prev = repos_state.get(repo) or {}
        repos_state[repo] = {
            "last_commit_sha": diff.get("tip_sha") or prev.get("last_commit_sha") or "",
            "last_release_tag": diff.get("tip_tag") or prev.get("last_release_tag") or "",
            "last_checked": _now_iso(),
            "url": act.get("url"),
            "stars": act.get("stars"),
        }
    state["updated_at"] = _now_iso()
    return state


def run_watch(
    *,
    watchlist_path: Path,
    state_dir: Path,
    client: Optional[GitHubClient] = None,
    archive: bool = True,
    commit_count: int = 8,
) -> dict[str, Any]:
    watchlist = load_watchlist(watchlist_path)
    if not watchlist:
        raise SystemExit(f"No repos in {watchlist_path}")

    state_path = state_dir / "state.json"
    state = load_state(state_path)
    client = client or GitHubClient()

    activities: list[dict[str, Any]] = []
    diffs: list[dict[str, Any]] = []
    for item in watchlist:
        repo = item["repo"]
        act = fetch_repo_activity(client, repo, commits=commit_count)
        prev = (state.get("repos") or {}).get(repo) or {}
        diff = diff_against_state(act, prev)
        activities.append(act)
        diffs.append(diff)

    digest = build_digest(watchlist, activities, diffs)
    state = update_state(state, diffs, activities)

    save_json(state_path, state)
    save_json(state_dir / "latest.json", digest)
    md = render_markdown(digest)
    (state_dir / "latest.md").write_text(md)

    if archive:
        hist = ROOT / "docs" / "history"
        hist.mkdir(parents=True, exist_ok=True)
        dated = hist / f"github_watch_{_today()}.md"
        dated.write_text(md)
        (hist / "github_watch_latest.md").write_text(md)

    return digest


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--watchlist",
        type=Path,
        default=DEFAULT_WATCHLIST,
        help="Path to github_watchlist.json",
    )
    p.add_argument(
        "--state-dir",
        type=Path,
        default=DEFAULT_STATE_DIR,
        help="Directory for state + latest digest",
    )
    p.add_argument(
        "--no-archive",
        action="store_true",
        help="Skip writing docs/history copies",
    )
    p.add_argument("--commits", type=int, default=8, help="Commits to fetch per repo")
    p.add_argument(
        "--no-gh",
        action="store_true",
        help="Force HTTPS API instead of `gh api`",
    )
    args = p.parse_args(argv)

    client = GitHubClient(use_gh=not args.no_gh)
    digest = run_watch(
        watchlist_path=args.watchlist,
        state_dir=args.state_dir,
        client=client,
        archive=not args.no_archive,
        commit_count=args.commits,
    )
    print(
        f"github_watch: {digest['repo_count']} repos, "
        f"{digest['update_count']} with updates → {args.state_dir / 'latest.md'}"
    )
    for bullet in (digest.get("idea_bullets") or [])[:12]:
        print(f"  • {bullet}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
