"""Allowlisted runtime logs under DATA_DIR for the Ops desk viewer."""

from __future__ import annotations

import asyncio
import math
from pathlib import Path
from typing import AsyncIterator, Dict, List

from stock_checker.secret_redact import redact_secrets
from stock_checker.technical_indicators import coerce_nonneg_int


# Relative to DATA_DIR. Only these names are exposed to the browser.
LOG_SOURCES: Dict[str, str] = {
    "trader": "logs/trader.log",
    "watchdog": "run_watchdog_loop.log",
    "watchdog_detail": "watchdog/watchdog.log",
    "ollama": "run_ollama_autoresearch_loop.log",
    "improve": "run_improve_loop.log",
    "github_watch": "run_github_watch_loop.log",
}

DEFAULT_TAIL_MAX_BYTES = 64_000
DEFAULT_FOLLOW_TAIL_BYTES = 48_000
DEFAULT_FOLLOW_CHUNK = 16_000
DEFAULT_POLL_SEC = 1.0


def _coerce_tail_max_bytes(
    value: object, default: int = DEFAULT_TAIL_MAX_BYTES
) -> int:
    """Positive Ops tail ceiling, or ``default`` when bool/gap/≤0.

    tradermonty #700/#655 + xang1234/portfolio AI: ``True→1`` must not invent
    a one-byte Ops strip; ``False→0`` must not look like a quiet empty log.
    Parity with ``runtime_log._coerce_max_bytes`` (tee rotate already refused).
    """
    n = coerce_nonneg_int(value)
    if n is None or n <= 0:
        return int(default)
    return n


def _coerce_follow_chunk(
    value: object, default: int = DEFAULT_FOLLOW_CHUNK
) -> int:
    """Positive SSE read chunk, or ``default`` when bool/gap/≤0.

    ``True→1`` must not invent one-byte SSE spam; ``False→0`` must not stall
    ``read(0)`` forever while the file grows.
    """
    n = coerce_nonneg_int(value)
    if n is None or n <= 0:
        return int(default)
    return n


def _coerce_poll_sec(
    value: object, default: float = DEFAULT_POLL_SEC
) -> float:
    """Positive SSE poll interval, or ``default`` when bool/gap/≤0.

    ``False→0`` / ``True→1`` must not invent a busy ``sleep(0)`` spin or a
    thin 1s-only band from a damaged knob (``asyncio.sleep(False)`` spins).
    """
    if isinstance(value, bool) or value is None:
        return float(default)
    if not isinstance(value, (int, float)):
        return float(default)
    sec = float(value)
    if not math.isfinite(sec) or sec <= 0:
        return float(default)
    return sec


def _coerce_size_offset(value: object) -> int:
    """Non-neg follow offset from a snap size; bool/gap → 0 (never ``True→1``)."""
    n = coerce_nonneg_int(value)
    return 0 if n is None else n


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
    max_bytes: object = DEFAULT_TAIL_MAX_BYTES,
) -> dict:
    ceiling = _coerce_tail_max_bytes(max_bytes)
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
    truncated = size > ceiling
    with path.open("rb") as fh:
        if truncated:
            fh.seek(-ceiling, 2)
            raw = fh.read()
            nl = raw.find(b"\n")
            if nl >= 0 and nl + 1 < len(raw):
                raw = raw[nl + 1 :]
        else:
            raw = fh.read()
    # tradermonty #556: never echo raw/URL-encoded provider keys to Ops tails.
    text = redact_secrets(raw.decode("utf-8", errors="replace"))
    return {
        "source": source,
        "path": LOG_SOURCES[source],
        "exists": True,
        "text": text,
        "size_bytes": size,
        "truncated": truncated,
    }


async def follow_log(
    data_dir: Path,
    source: str,
    *,
    poll_sec: object = DEFAULT_POLL_SEC,
    max_chunk: object = DEFAULT_FOLLOW_CHUNK,
) -> AsyncIterator[str]:
    """Yield new text appended to the log (for SSE)."""
    path = resolve_log_path(data_dir, source)
    poll = _coerce_poll_sec(poll_sec)
    chunk_cap = _coerce_follow_chunk(max_chunk)
    snap = read_log_tail(
        data_dir, source, max_bytes=DEFAULT_FOLLOW_TAIL_BYTES
    )
    if snap["text"]:
        yield str(snap["text"])
    offset = _coerce_size_offset(snap.get("size_bytes"))

    while True:
        await asyncio.sleep(poll)
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
                chunk = fh.read(chunk_cap)
                offset = fh.tell()
        except OSError:
            continue
        if chunk:
            yield redact_secrets(chunk.decode("utf-8", errors="replace"))
