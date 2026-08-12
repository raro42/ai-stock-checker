"""Tee process stdout/stderr into a rotating file under DATA_DIR/logs/."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional, TextIO


DEFAULT_MAX_BYTES = 5 * 1024 * 1024  # 5 MiB


class _TeeStream:
    def __init__(self, primary: TextIO, secondary: TextIO) -> None:
        self._primary = primary
        self._secondary = secondary

    def write(self, data: str) -> int:
        n = self._primary.write(data)
        try:
            self._secondary.write(data)
            self._secondary.flush()
        except OSError:
            pass
        return n

    def flush(self) -> None:
        self._primary.flush()
        try:
            self._secondary.flush()
        except OSError:
            pass

    def fileno(self) -> int:
        return self._primary.fileno()

    def isatty(self) -> bool:
        return self._primary.isatty()

    @property
    def encoding(self) -> str:
        return getattr(self._primary, "encoding", "utf-8") or "utf-8"


def logs_dir(data_dir: Path | str | None = None) -> Path:
    root = Path(data_dir or os.getenv("DATA_DIR", "data"))
    return root / "logs"


def _rotate_if_needed(path: Path, max_bytes: int) -> None:
    try:
        if not path.is_file() or path.stat().st_size < max_bytes:
            return
        bak = path.with_suffix(path.suffix + ".1")
        if bak.exists():
            bak.unlink()
        path.rename(bak)
    except OSError:
        pass


def install_runtime_log(
    name: str = "trader",
    *,
    data_dir: Path | str | None = None,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> Optional[Path]:
    """Mirror stdout/stderr to ``{data_dir}/logs/{name}.log``. Returns log path."""
    safe = "".join(c for c in name if c.isalnum() or c in ("-", "_")).strip("._")
    if not safe:
        safe = "trader"
    directory = logs_dir(data_dir)
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None
    path = directory / f"{safe}.log"
    _rotate_if_needed(path, max_bytes)
    try:
        handle = path.open("a", encoding="utf-8", buffering=1)
    except OSError:
        return None
    sys.stdout = _TeeStream(sys.__stdout__, handle)  # type: ignore[assignment]
    sys.stderr = _TeeStream(sys.__stderr__, handle)  # type: ignore[assignment]
    print(f"📝 Runtime log → {path}", flush=True)
    return path
