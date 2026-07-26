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

# Adaptive cadence: check ~½ of the average commit gap, clamped.
MIN_CHECK_INTERVAL_SEC = 3 * 3600  # hot repos
MAX_CHECK_INTERVAL_SEC = 7 * 86400  # cold / archived
DEFAULT_CHECK_INTERVAL_SEC = 2 * 86400
MIN_LOOP_SLEEP_SEC = 15 * 60
MAX_LOOP_SLEEP_SEC = 12 * 3600


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _parse_iso(value: str) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def avg_commit_gap_seconds(commits: list[dict[str, Any]]) -> Optional[float]:
    """Mean seconds between consecutive commits (newest-first list)."""
    dates: list[datetime] = []
    for c in commits:
        dt = _parse_iso(str(c.get("date") or ""))
        if dt is not None:
            dates.append(dt)
    if len(dates) < 2:
        return None
    gaps = [(dates[i] - dates[i + 1]).total_seconds() for i in range(len(dates) - 1)]
    gaps = [g for g in gaps if g > 0]
    if not gaps:
        return None
    return sum(gaps) / len(gaps)


def interval_from_cadence(
    avg_gap_sec: Optional[float],
    *,
    archived: bool = False,
    single_commit_age_sec: Optional[float] = None,
) -> int:
    """Map commit cadence → next re-check interval (seconds)."""
    if archived:
        return MAX_CHECK_INTERVAL_SEC
    if avg_gap_sec is not None and avg_gap_sec > 0:
        # Recheck about halfway to the next expected commit.
        raw = avg_gap_sec * 0.5
    elif single_commit_age_sec is not None and single_commit_age_sec > 0:
        # One sample: wait longer if the tip is already old.
        raw = max(single_commit_age_sec * 0.5, DEFAULT_CHECK_INTERVAL_SEC)
    else:
        raw = float(DEFAULT_CHECK_INTERVAL_SEC)
    return int(max(MIN_CHECK_INTERVAL_SEC, min(MAX_CHECK_INTERVAL_SEC, raw)))


def commits_per_day(avg_gap_sec: Optional[float]) -> float:
    if not avg_gap_sec or avg_gap_sec <= 0:
        return 0.0
    return 86400.0 / avg_gap_sec


def is_repo_due(prev: dict[str, Any], now: Optional[datetime] = None) -> bool:
    now = now or _now()
    nxt = _parse_iso(str(prev.get("next_check_at") or ""))
    if nxt is None:
        return True
    return now >= nxt


def next_sleep_seconds(state: dict[str, Any], now: Optional[datetime] = None) -> int:
    """Seconds until the soonest due repo (clamped for the host loop)."""
    now = now or _now()
    soonest: Optional[float] = None
    for prev in (state.get("repos") or {}).values():
        nxt = _parse_iso(str(prev.get("next_check_at") or ""))
        if nxt is None:
            return MIN_LOOP_SLEEP_SEC
        delta = (nxt - now).total_seconds()
        if soonest is None or delta < soonest:
            soonest = delta
    if soonest is None:
        return DEFAULT_CHECK_INTERVAL_SEC
    return int(max(MIN_LOOP_SLEEP_SEC, min(MAX_LOOP_SLEEP_SEC, max(0, soonest))))


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


def fetch_repo_meta(client: GitHubClient, repo: str) -> dict[str, Any]:
    try:
        meta = client.get_json(f"/repos/{repo}") or {}
    except Exception as exc:  # noqa: BLE001
        return {"repo": repo, "error": str(exc)}
    return {
        "repo": repo,
        "url": meta.get("html_url") or f"https://github.com/{repo}",
        "description": (meta.get("description") or "")[:240],
        "stars": int(meta.get("stargazers_count") or 0),
        "pushed_at": meta.get("pushed_at") or "",
        "default_branch": meta.get("default_branch") or "main",
        "archived": bool(meta.get("archived")),
        "error": None,
    }


def fetch_repo_activity(
    client: GitHubClient, repo: str, *, commits: int = 8, releases: int = 3
) -> dict[str, Any]:
    meta = fetch_repo_meta(client, repo)
    if meta.get("error"):
        return {**meta, "commits": [], "releases": []}

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
                        "url": c.get("html_url")
                        or f"https://github.com/{repo}/commit/{c.get('sha')}",
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
        **meta,
        "commits": commit_rows,
        "releases": release_rows,
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
    *,
    checked_count: int = 0,
    skipped_count: int = 0,
    next_sleep_sec: int = DEFAULT_CHECK_INTERVAL_SEC,
) -> dict[str, Any]:
    why = {w["repo"]: w.get("why") or "" for w in watchlist}
    rows = []
    updates = 0
    for act, diff in zip(activities, diffs):
        repo = act["repo"]
        row = {
            **act,
            "why": why.get(repo, ""),
            **{
                k: diff[k]
                for k in (
                    "first_seen",
                    "new_commits",
                    "new_releases",
                    "has_updates",
                    "baseline",
                    "tip_sha",
                    "tip_tag",
                    "tip_message",
                )
            },
        }
        if row.get("has_updates"):
            updates += 1
        rows.append(row)

    ideas: list[str] = []
    for row in rows:
        if row.get("error") or row.get("skipped"):
            continue
        label = row["repo"]
        if row.get("has_updates"):
            for c in row.get("new_commits") or []:
                ideas.append(
                    f"{label}: commit {_short_sha(c['sha'])} — {c['message']}"
                )
            for r in row.get("new_releases") or []:
                ideas.append(
                    f"{label}: release {r['tag']} — {r.get('name') or r['tag']}"
                )
        elif row.get("baseline") and row.get("tip_message"):
            ideas.append(f"{label} (baseline): {row['tip_message']}")

    return {
        "generated_at": _now_iso(),
        "repo_count": len(rows),
        "checked_count": checked_count,
        "skipped_count": skipped_count,
        "update_count": updates,
        "next_sleep_sec": next_sleep_sec,
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
        f"- Checked this run: **{digest.get('checked_count', 0)}** · skipped (not due): **{digest.get('skipped_count', 0)}**",
        f"- Repos with new activity: **{digest.get('update_count', 0)}**",
        f"- Next loop sleep: **{digest.get('next_sleep_sec', 0)}s** (cadence-aware)",
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
        if row.get("avg_commit_gap_hours") is not None:
            lines.append(
                f"- Cadence: ~{row.get('commits_per_day', 0):.2f} commits/day "
                f"(avg gap {row['avg_commit_gap_hours']:.1f}h) · "
                f"recheck every {int((row.get('check_interval_sec') or 0) / 3600)}h · "
                f"next {row.get('next_check_at') or '—'}"
            )
        if row.get("skipped"):
            lines.append("- Status: **skipped** (not due yet)")
        elif row.get("unchanged_push"):
            lines.append("- Status: due but `pushed_at` unchanged — no deep fetch")
        elif row.get("baseline"):
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


def _schedule_fields(
    *,
    avg_gap: Optional[float],
    interval: int,
    now: datetime,
) -> dict[str, Any]:
    next_at = now.timestamp() + interval
    next_iso = datetime.fromtimestamp(next_at, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    return {
        "avg_commit_gap_sec": avg_gap,
        "avg_commit_gap_hours": round(avg_gap / 3600.0, 2) if avg_gap else None,
        "commits_per_day": round(commits_per_day(avg_gap), 3),
        "check_interval_sec": interval,
        "next_check_at": next_iso,
    }


def update_repo_state(
    prev: dict[str, Any],
    *,
    tip_sha: str,
    tip_tag: str,
    url: Any,
    stars: Any,
    pushed_at: str,
    schedule: dict[str, Any],
) -> dict[str, Any]:
    return {
        "last_commit_sha": tip_sha or prev.get("last_commit_sha") or "",
        "last_release_tag": tip_tag or prev.get("last_release_tag") or "",
        "last_checked": _now_iso(),
        "url": url,
        "stars": stars,
        "pushed_at": pushed_at,
        **schedule,
    }


def run_watch(
    *,
    watchlist_path: Path,
    state_dir: Path,
    client: Optional[GitHubClient] = None,
    archive: bool = True,
    commit_count: int = 8,
    force: bool = False,
) -> dict[str, Any]:
    watchlist = load_watchlist(watchlist_path)
    if not watchlist:
        raise SystemExit(f"No repos in {watchlist_path}")

    state_path = state_dir / "state.json"
    state = load_state(state_path)
    client = client or GitHubClient()
    now = _now()
    prev_digest = _load_json(state_dir / "latest.json", {})
    prev_by_repo = {
        r.get("repo"): r for r in (prev_digest.get("repos") or []) if r.get("repo")
    }

    activities: list[dict[str, Any]] = []
    diffs: list[dict[str, Any]] = []
    checked = 0
    skipped = 0
    repos_state = state.setdefault("repos", {})

    for item in watchlist:
        repo = item["repo"]
        prev = repos_state.get(repo) or {}
        due = force or is_repo_due(prev, now)

        if not due:
            skipped += 1
            cached = prev_by_repo.get(repo) or {
                "repo": repo,
                "url": prev.get("url") or f"https://github.com/{repo}",
                "commits": [],
                "releases": [],
            }
            act = {
                **cached,
                "skipped": True,
                "check_interval_sec": prev.get("check_interval_sec"),
                "next_check_at": prev.get("next_check_at"),
                "avg_commit_gap_hours": prev.get("avg_commit_gap_hours"),
                "commits_per_day": prev.get("commits_per_day") or 0,
            }
            diff = {
                "first_seen": False,
                "new_commits": [],
                "new_releases": [],
                "has_updates": False,
                "baseline": False,
                "tip_sha": prev.get("last_commit_sha") or "",
                "tip_tag": prev.get("last_release_tag") or "",
                "tip_message": "",
            }
            activities.append(act)
            diffs.append(diff)
            continue

        checked += 1
        meta = fetch_repo_meta(client, repo)
        if meta.get("error"):
            act = {**meta, "commits": [], "releases": [], "skipped": False}
            interval = int(prev.get("check_interval_sec") or DEFAULT_CHECK_INTERVAL_SEC)
            schedule = _schedule_fields(avg_gap=prev.get("avg_commit_gap_sec"), interval=interval, now=now)
            repos_state[repo] = update_repo_state(
                prev,
                tip_sha=prev.get("last_commit_sha") or "",
                tip_tag=prev.get("last_release_tag") or "",
                url=meta.get("url"),
                stars=prev.get("stars"),
                pushed_at=prev.get("pushed_at") or "",
                schedule=schedule,
            )
            activities.append(act)
            diffs.append(
                {
                    "first_seen": False,
                    "new_commits": [],
                    "new_releases": [],
                    "has_updates": False,
                    "baseline": False,
                    "tip_sha": prev.get("last_commit_sha") or "",
                    "tip_tag": prev.get("last_release_tag") or "",
                    "tip_message": "",
                }
            )
            continue

        pushed_at = meta.get("pushed_at") or ""
        unchanged = bool(
            prev.get("last_commit_sha")
            and prev.get("pushed_at")
            and prev.get("pushed_at") == pushed_at
        )

        if unchanged and not force:
            # Repo due by clock, but GitHub says no new push — cheap skip of commits API.
            avg_gap = prev.get("avg_commit_gap_sec")
            interval = interval_from_cadence(
                avg_gap if isinstance(avg_gap, (int, float)) else None,
                archived=bool(meta.get("archived")),
            )
            schedule = _schedule_fields(avg_gap=avg_gap if isinstance(avg_gap, (int, float)) else None, interval=interval, now=now)
            repos_state[repo] = update_repo_state(
                prev,
                tip_sha=prev.get("last_commit_sha") or "",
                tip_tag=prev.get("last_release_tag") or "",
                url=meta.get("url"),
                stars=meta.get("stars"),
                pushed_at=pushed_at,
                schedule=schedule,
            )
            cached = prev_by_repo.get(repo) or {}
            act = {
                **meta,
                "commits": cached.get("commits") or [],
                "releases": cached.get("releases") or [],
                "unchanged_push": True,
                "skipped": False,
                **{
                    k: schedule[k]
                    for k in (
                        "avg_commit_gap_hours",
                        "commits_per_day",
                        "check_interval_sec",
                        "next_check_at",
                    )
                },
            }
            activities.append(act)
            diffs.append(
                {
                    "first_seen": False,
                    "new_commits": [],
                    "new_releases": [],
                    "has_updates": False,
                    "baseline": False,
                    "tip_sha": prev.get("last_commit_sha") or "",
                    "tip_tag": prev.get("last_release_tag") or "",
                    "tip_message": "",
                }
            )
            continue

        act = fetch_repo_activity(client, repo, commits=commit_count)
        act["skipped"] = False
        act["unchanged_push"] = False
        diff = diff_against_state(act, prev)
        avg_gap = avg_commit_gap_seconds(act.get("commits") or [])
        age = None
        commits = act.get("commits") or []
        if avg_gap is None and commits:
            tip_dt = _parse_iso(str(commits[0].get("date") or ""))
            if tip_dt is not None:
                age = (now - tip_dt).total_seconds()
        interval = interval_from_cadence(
            avg_gap, archived=bool(act.get("archived")), single_commit_age_sec=age
        )
        schedule = _schedule_fields(avg_gap=avg_gap, interval=interval, now=now)
        act.update(
            {
                "avg_commit_gap_hours": schedule["avg_commit_gap_hours"],
                "commits_per_day": schedule["commits_per_day"],
                "check_interval_sec": schedule["check_interval_sec"],
                "next_check_at": schedule["next_check_at"],
            }
        )
        repos_state[repo] = update_repo_state(
            prev,
            tip_sha=diff.get("tip_sha") or "",
            tip_tag=diff.get("tip_tag") or "",
            url=act.get("url"),
            stars=act.get("stars"),
            pushed_at=act.get("pushed_at") or "",
            schedule=schedule,
        )
        activities.append(act)
        diffs.append(diff)

    state["updated_at"] = _now_iso()
    sleep_sec = next_sleep_seconds(state, now)
    state["next_sleep_sec"] = sleep_sec
    digest = build_digest(
        watchlist,
        activities,
        diffs,
        checked_count=checked,
        skipped_count=skipped,
        next_sleep_sec=sleep_sec,
    )

    save_json(state_path, state)
    save_json(state_dir / "latest.json", digest)
    (state_dir / "next_sleep_sec").write_text(str(sleep_sec) + "\n")
    md = render_markdown(digest)
    (state_dir / "latest.md").write_text(md)

    if archive and (digest.get("update_count") or checked > 0):
        hist = ROOT / "docs" / "history"
        hist.mkdir(parents=True, exist_ok=True)
        dated = hist / f"github_watch_{_today()}.md"
        dated.write_text(md)
        (hist / "github_watch_latest.md").write_text(md)

    return digest


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return default


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
        "--force",
        action="store_true",
        help="Ignore next_check_at and re-fetch all repos",
    )
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
        force=args.force,
    )
    print(
        f"github_watch: checked={digest.get('checked_count', 0)} "
        f"skipped={digest.get('skipped_count', 0)} "
        f"updates={digest.get('update_count', 0)} "
        f"next_sleep={digest.get('next_sleep_sec')}s → {args.state_dir / 'latest.md'}"
    )
    for bullet in (digest.get("idea_bullets") or [])[:12]:
        print(f"  • {bullet}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
