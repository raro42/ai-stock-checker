"""Book folds screener/AI Group Matrix under details (MonsterDeveloper declutter)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOK = ROOT / "openbb_backend" / "templates" / "desk_book.html"
CSS = ROOT / "openbb_backend" / "static" / "desk.css"

ABOVE_FOLD = (
    ">Slots</span>",
    ">Cash</span>",
    ">Largest</span>",
    ">Mix</span>",
    ">Marks</span>",
    ">Tenure</span>",
    ">Win/Lose</span>",
    ">Size</span>",
    ">Leader</span>",
    ">Venue</span>",
    ">Exit</span>",
    ">Hold</span>",
    ">Scan</span>",
)

INSIDE_DETAILS = (
    ">Session</span>",
    ">Hours</span>",
    ">Rebuy</span>",
    ">Gap</span>",
    ">Post-SL</span>",
    ">Post-TP</span>",
    ">Post-rot</span>",
    ">Post-trim</span>",
    ">Fee</span>",
    ">Buy-c</span>",
    ">Cap</span>",
    ">RR</span>",
    ">List</span>",
    ">Score</span>",
    ">Near</span>",
    ">Move</span>",
    ">Vol</span>",
    ">AI</span>",
    ">Conf</span>",
    ">Roles</span>",
)


def test_book_matrix_honesty_details() -> None:
    text = BOOK.read_text(encoding="utf-8")
    assert 'class="matrix-honesty"' in text
    assert 'id="matrix-honesty"' in text
    open_idx = text.index('class="matrix-honesty"')
    close_idx = text.index("</details>", open_idx)
    above = text[:open_idx]
    body = text[open_idx:close_idx]
    for needle in ABOVE_FOLD:
        assert needle in above, f"{needle} should stay above fold"
        assert needle not in body, f"{needle} must not be inside details"
    for needle in INSIDE_DETAILS:
        assert needle in body, f"{needle} should be inside details"
        assert needle not in above, f"{needle} must not stay above fold"
    assert "Screener &amp; AI marks" in body


def test_book_matrix_honesty_css() -> None:
    css = CSS.read_text(encoding="utf-8")
    assert ".matrix-honesty" in css
    assert ".matrix-honesty > summary" in css
