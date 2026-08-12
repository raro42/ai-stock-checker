"""Tests for shared /data runtime logs and Ops log API helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from openbb_backend.desk_logs import (
    LOG_SOURCES,
    list_log_sources,
    read_log_tail,
    resolve_log_path,
)
from stock_checker.runtime_log import install_runtime_log, logs_dir


def test_resolve_rejects_unknown(tmp_path: Path) -> None:
    with pytest.raises(KeyError):
        resolve_log_path(tmp_path, "nope")


def test_read_tail_and_list(tmp_path: Path) -> None:
    log = tmp_path / "logs" / "trader.log"
    log.parent.mkdir(parents=True)
    log.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")
    snap = read_log_tail(tmp_path, "trader")
    assert snap["exists"] is True
    assert "gamma" in snap["text"]
    rows = list_log_sources(tmp_path)
    trader = next(r for r in rows if r["id"] == "trader")
    assert trader["exists"] is True
    assert trader["size_bytes"] > 0


def test_read_tail_truncates(tmp_path: Path) -> None:
    log = tmp_path / LOG_SOURCES["trader"]
    log.parent.mkdir(parents=True)
    body = ("line-%05d\n" % i for i in range(5000))
    log.write_text("".join(body), encoding="utf-8")
    snap = read_log_tail(tmp_path, "trader", max_bytes=2000)
    assert snap["truncated"] is True
    assert "line-04999" in snap["text"]
    assert "line-00000" not in snap["text"]


def test_install_runtime_log_tees(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import sys

    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    path = install_runtime_log("trader", data_dir=tmp_path)
    assert path is not None
    assert path == logs_dir(tmp_path) / "trader.log"
    print("hello-from-tee", flush=True)
    text = path.read_text(encoding="utf-8")
    assert "hello-from-tee" in text
    # restore stdio for other tests
    sys.stdout = sys.__stdout__
    sys.stderr = sys.__stderr__
