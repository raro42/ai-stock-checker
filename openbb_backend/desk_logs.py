"""Allowlisted runtime logs under DATA_DIR for the Ops desk viewer."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import AsyncIterator, Dict, List


# Relative to DATA_DIR. Only these names are exposed to the browser.
LOG_SOURCES: Dict[str, str] = {
    "trader": "logs/trader.log",
    "watchdog": "run_watchdog_loop.log",
    "watchdog_detail": "watchdog/watchdog.log",
    "ollama": "run_ollama_autoresearch_loop.log",
    "improve": "run_improve_loop.log",
    "github_watch": "run_github_watch_loop.log",
}


def resolve_log_path(data_dir: Path, source: str) -> Path:
    rel = LOG_SOURCES.get(source)
    if not rel:
        raise KeyError(f"unknown log source: {source}")
    root = data_dir.resolve()
    path = (data_dir / rel).resolve()
    if path != root and root not in path.parents:
        raise PermissionError("log path escapes data dir")
    return path


def list_log_sources(data_dir: Path) -> List[dict]:
    rows: List[dict] = []
    for name, rel in LOG_SOURCES.items():
        path = data_dir / rel
        exists = path.is_file()
        size = int(path.stat().st_size) if exists else 0
        mtime = path.stat().st_mtime if exists else None
        rows.append(
            {
                "id": name,
                "path": rel,
                "exists": exists,
                "size_bytes": size,
                "mtime": mtime,
            }
        )
    return rows


def read_log_tail(
    data_dir: Path,
    source: str,
    *,
    max_bytes: int = 64_000,
) -> dict:
    path = resolve_log_path(data_dir, source)
    if not path.is_file():
        return {
            "source": source,
            "path": LOG_SOURCES[source],
            "exists": False,
            "text": "",
            "size_bytes": 0,
            "truncated": False,
        }
    size = path.stat().st_size
    truncated = size > max_bytes
    with path.open("rb") as fh:
        if truncated:
            fh.seek(-max_bytes, 2)
            raw = fh.read()
            nl = raw.find(b"\n")
            if nl >= 0 and nl + 1 < len(raw):
                raw = raw[nl + 1 :]
        else:
            raw = fh.read()
    return {
        "source": source,
        "path": LOG_SOURCES[source],
        "exists": True,
        "text": raw.decode("utf-8", errors="replace"),
        "size_bytes": size,
        "truncated": truncated,
    }


async def follow_log(
    data_dir: Path,
    source: str,
    *,
    poll_sec: float = 1.0,
    max_chunk: int = 16_000,
) -> AsyncIterator[str]:
    """Yield new text appended to the log (for SSE)."""
    path = resolve_log_path(data_dir, source)
    snap = read_log_tail(data_dir, source, max_bytes=48_000)
    if snap["text"]:
        yield str(snap["text"])
    offset = int(snap["size_bytes"] or 0)

    while True:
        await asyncio.sleep(poll_sec)
        if not path.is_file():
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if size < offset:
            offset = 0
        if size == offset:
            continue
        try:
            with path.open("rb") as fh:
                fh.seek(offset)
                chunk = fh.read(max_chunk)
                offset = fh.tell()
        except OSError:
            continue
        if chunk:
            yield chunk.decode("utf-8", errors="replace")
