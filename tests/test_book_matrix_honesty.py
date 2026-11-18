"""Book folds screener/AI Group Matrix under details (MonsterDeveloper declutter)."""

from __future__ import annotations

from pathlib import Path

from openbb_backend.desk import book_matrix_fold_meta

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
    ">Buy-s</span>",
    ">Strat</span>",
    ">Buy-%</span>",
    ">Src</span>",
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


def test_book_matrix_fold_meta_spoken_inventory() -> None:
    assert book_matrix_fold_meta(None) == ("quiet", False)
    assert book_matrix_fold_meta({}) == ("quiet", False)
    meta, warn = book_matrix_fold_meta(
        {
            "entry_session_marks_ready": True,
            "live_rr_marks_ready": True,
            "live_rr_thin_lots": 0,
            "live_rr_hit_lots": 0,
            "ai_debate_marks_ready": True,
        }
    )
    assert meta == "quiet · 3 folds · Session · RR · AI"
    assert warn is False


def test_book_matrix_fold_meta_rr_thin_hit_warn() -> None:
    meta, warn = book_matrix_fold_meta(
        {
            "live_rr_marks_ready": True,
            "live_rr_thin_lots": 2,
            "live_rr_hit_lots": 0,
        }
    )
    assert meta == "warn · 1 hot of 1 · RR thin · quiet · 0 folds"
    assert warn is True
    meta, warn = book_matrix_fold_meta(
        {
            "live_rr_marks_ready": True,
            "entry_hours_marks_ready": True,
            "live_rr_thin_lots": 1,
            "live_rr_hit_lots": 1,
        }
    )
    assert meta == "warn · 1 hot of 2 · RR hit · quiet · 1 fold · Hours"
    assert warn is True


def test_book_matrix_fold_meta_refuses_bool_rr_lots() -> None:
    """tradermonty #700/#655: True→1 thin/hit must not invent RR warn."""
    meta, warn = book_matrix_fold_meta(
        {
            "live_rr_marks_ready": True,
            "live_rr_thin_lots": True,
            "live_rr_hit_lots": True,
        }
    )
    assert meta == "quiet · 1 fold · RR"
    assert warn is False
    meta2, warn2 = book_matrix_fold_meta(
        {
            "live_rr_marks_ready": True,
            "live_rr_thin_lots": False,
            "live_rr_hit_lots": False,
        }
    )
    assert meta2 == "quiet · 1 fold · RR"
    assert warn2 is False


def test_book_matrix_fold_meta_clips_storm_and_keeps_rr_hit() -> None:
    ready = {key: True for key, _label in (
        ("entry_session_marks_ready", "Session"),
        ("entry_hours_marks_ready", "Hours"),
        ("entry_rebuy_marks_ready", "Rebuy"),
        ("entry_rebuy_gap_marks_ready", "Gap"),
        ("entry_post_sl_marks_ready", "Post-SL"),
        ("entry_buy_fee_marks_ready", "Fee"),
        ("live_rr_marks_ready", "RR"),
    )}
    ready["live_rr_hit_lots"] = 1
    meta, warn = book_matrix_fold_meta(ready)
    assert warn is True
    assert meta.startswith("warn · 1 hot of 7 · RR hit · quiet · 6 folds · ")
    assert "Session · Hours · Rebuy · Gap · +2" in meta
    assert "Post-SL" not in meta
    assert "Fee" not in meta


def test_book_matrix_honesty_details() -> None:
    text = BOOK.read_text(encoding="utf-8")
    assert "matrix-honesty" in text
    assert 'id="matrix-honesty"' in text
    assert "matrix_meta" in text
    assert "matrix_warn" in text
    open_idx = text.index("matrix-honesty")
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
    # Static full inventory hid thin subsets — meta chip speaks ready only.
    assert (
        "Session · Hours · Rebuy · Gap · Post-SL · Post-TP · Post-rot · "
        "Post-trim · Fee · Buy-c · Buy-s · Strat · Buy-% · Src · Cap · RR · "
        "List · Score · Near · Move · Vol · AI · Conf · Roles"
    ) not in body


def test_book_matrix_honesty_css() -> None:
    css = CSS.read_text(encoding="utf-8")
    assert ".matrix-honesty" in css
    assert ".matrix-honesty > summary" in css
    assert ".matrix-honesty.warn" in css
