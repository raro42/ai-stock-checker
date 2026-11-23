"""Tests for shared /data runtime logs and Ops log API helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from openbb_backend.desk_logs import (
    DEFAULT_FOLLOW_CHUNK,
    DEFAULT_POLL_SEC,
    DEFAULT_TAIL_MAX_BYTES,
    LOG_SOURCES,
    _coerce_follow_chunk,
    _coerce_poll_sec,
    _coerce_size_offset,
    _coerce_tail_max_bytes,
    list_log_sources,
    read_log_tail,
    resolve_log_path,
)
from stock_checker.runtime_log import (
    DEFAULT_MAX_BYTES,
    _coerce_max_bytes,
    _rotate_if_needed,
    install_runtime_log,
    logs_dir,
)


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


def test_coerce_max_bytes_refuses_bool() -> None:
    assert _coerce_max_bytes(True) == DEFAULT_MAX_BYTES
    assert _coerce_max_bytes(False) == DEFAULT_MAX_BYTES
    assert _coerce_max_bytes(0) == DEFAULT_MAX_BYTES
    assert _coerce_max_bytes(None) == DEFAULT_MAX_BYTES
    assert _coerce_max_bytes(4096) == 4096


def test_rotate_refuses_bool_ceiling(tmp_path: Path) -> None:
    log = tmp_path / "trader.log"
    log.write_bytes(b"x" * 100)
    # True→1 must not invent a one-byte rotate of a 100-byte file.
    _rotate_if_needed(log, True)
    assert log.is_file()
    assert log.stat().st_size == 100
    _rotate_if_needed(log, 50)
    assert not log.is_file()
    assert (tmp_path / "trader.log.1").is_file()


def test_desk_tail_knobs_refuse_bool() -> None:
    # tradermonty #700/#655: True→1 must not invent a one-byte Ops strip;
    # False→0 must not invent a quiet empty tail or busy SSE spin.
    assert _coerce_tail_max_bytes(True) == DEFAULT_TAIL_MAX_BYTES
    assert _coerce_tail_max_bytes(False) == DEFAULT_TAIL_MAX_BYTES
    assert _coerce_tail_max_bytes(0) == DEFAULT_TAIL_MAX_BYTES
    assert _coerce_tail_max_bytes(2000) == 2000
    assert _coerce_follow_chunk(True) == DEFAULT_FOLLOW_CHUNK
    assert _coerce_follow_chunk(False) == DEFAULT_FOLLOW_CHUNK
    assert _coerce_follow_chunk(512) == 512
    assert _coerce_poll_sec(True) == DEFAULT_POLL_SEC
    assert _coerce_poll_sec(False) == DEFAULT_POLL_SEC
    assert _coerce_poll_sec(0) == DEFAULT_POLL_SEC
    assert _coerce_poll_sec(2.5) == 2.5
    assert _coerce_size_offset(True) == 0
    assert _coerce_size_offset(False) == 0
    assert _coerce_size_offset(None) == 0
    assert _coerce_size_offset(48_000) == 48_000


def test_read_tail_bool_max_bytes_keeps_full_strip(tmp_path: Path) -> None:
    log = tmp_path / LOG_SOURCES["trader"]
    log.parent.mkdir(parents=True)
    body = "alpha\nbeta\ngamma\n" * 200
    log.write_text(body, encoding="utf-8")
    # True→1 must not invent a one-byte truncated Ops glance.
    snap = read_log_tail(tmp_path, "trader", max_bytes=True)
    assert snap["exists"] is True
    assert snap["truncated"] is False
    assert "gamma" in snap["text"]
    assert len(snap["text"]) > 10
