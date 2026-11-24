"""OpenBB /opportunities_markdown strip ceilings refuse bool invent."""

from __future__ import annotations

import json
from pathlib import Path

from openbb_backend.main import (
    OPPORTUNITY_MARKDOWN_BODY_CHARS,
    OPPORTUNITY_MARKDOWN_RECS_STRIP,
    _opportunities_markdown_body,
)
from openbb_backend.desk import _coerce_opportunity_strip_limit


def test_opportunity_markdown_strip_defaults() -> None:
    assert OPPORTUNITY_MARKDOWN_RECS_STRIP == 15
    assert OPPORTUNITY_MARKDOWN_BODY_CHARS == 12000


def test_opportunity_markdown_strip_refuses_bool() -> None:
    assert (
        _coerce_opportunity_strip_limit(
            True, default=OPPORTUNITY_MARKDOWN_RECS_STRIP
        )
        == OPPORTUNITY_MARKDOWN_RECS_STRIP
    )
    assert (
        _coerce_opportunity_strip_limit(
            False, default=OPPORTUNITY_MARKDOWN_RECS_STRIP
        )
        == OPPORTUNITY_MARKDOWN_RECS_STRIP
    )
    assert (
        _coerce_opportunity_strip_limit(
            0, default=OPPORTUNITY_MARKDOWN_BODY_CHARS
        )
        == OPPORTUNITY_MARKDOWN_BODY_CHARS
    )
    assert (
        _coerce_opportunity_strip_limit(
            7, default=OPPORTUNITY_MARKDOWN_RECS_STRIP
        )
        == 7
    )


def test_opportunities_markdown_refuses_bool_recs_strip(tmp_path: Path) -> None:
    """True→1 must not invent a one-name Workspace strip via recs[:True]."""
    arch = tmp_path / "archive"
    arch.mkdir()
    recs = [
        {
            "symbol": f"S{i}",
            "asset_class": "stock",
            "score": 40 + i,
            "reasoning": f"r{i}",
        }
        for i in range(20)
    ]
    (arch / "opportunities_latest.json").write_text(
        json.dumps({"recommendations": recs})
    )

    # Bool ceilings keep the full default strip (20 > 15 → capped at 15).
    body_true = _opportunities_markdown_body(tmp_path, recs_n=True)
    assert body_true.count("- **S") == OPPORTUNITY_MARKDOWN_RECS_STRIP
    assert "S0" in body_true
    assert "S14" in body_true
    assert "S15" not in body_true

    body_false = _opportunities_markdown_body(tmp_path, recs_n=False)
    assert body_false.count("- **S") == OPPORTUNITY_MARKDOWN_RECS_STRIP

    body_thin = _opportunities_markdown_body(tmp_path, recs_n=3)
    assert body_thin.count("- **S") == 3
    assert "S2" in body_thin
    assert "S3" not in body_thin


def test_opportunities_markdown_refuses_bool_body_chars(tmp_path: Path) -> None:
    """True→1 must not invent a one-char txt strip via body[:True]."""
    arch = tmp_path / "archive"
    arch.mkdir()
    twin = "# Twin body\n" + ("KEEPME " * 40)
    (arch / "opportunities_latest.txt").write_text(twin)
    (arch / "opportunities_latest.json").write_text("{}")

    body_true = _opportunities_markdown_body(tmp_path, body_n=True)
    assert body_true.startswith("# Twin body")
    assert "KEEPME" in body_true
    assert len(body_true) == len(twin)  # under default 12000 → full twin

    body_clip = _opportunities_markdown_body(tmp_path, body_n=20)
    assert body_clip == twin[:20]
    assert len(body_clip) == 20
