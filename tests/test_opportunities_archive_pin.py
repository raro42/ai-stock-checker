"""Opportunity archive latest-pin honesty (xang1234 #682 readiness)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from openbb_backend.desk import build_scan_freshness, resolve_opportunities_archive


def test_resolve_prefers_latest_symlink(tmp_path: Path) -> None:
    arch = tmp_path / "archive"
    arch.mkdir()
    target = arch / "opportunities_20260101_120000.json"
    target.write_text("{}")
    (arch / "opportunities_latest.json").symlink_to(target.name)

    res = resolve_opportunities_archive(tmp_path)
    assert res["pin"] == "latest"
    assert res["fallback"] is False
    assert res["warn"] is False
    assert res["bit"] == ""
    assert Path(res["path"]).resolve() == target.resolve()


def test_resolve_falls_back_when_latest_missing(tmp_path: Path) -> None:
    arch = tmp_path / "archive"
    arch.mkdir()
    older = arch / "opportunities_20260101_120000.json"
    older.write_text("{}")
    newer = arch / "opportunities_20260201_120000.json"
    newer.write_text('{"n": 1}')

    res = resolve_opportunities_archive(tmp_path)
    assert res["pin"] == "missing"
    assert res["fallback"] is True
    assert res["warn"] is True
    assert res["bit"] == "latest missing · fallback"
    assert Path(res["path"]) == newer


def test_resolve_falls_back_when_latest_dangling(tmp_path: Path) -> None:
    arch = tmp_path / "archive"
    arch.mkdir()
    (arch / "opportunities_latest.json").symlink_to("opportunities_gone.json")
    kept = arch / "opportunities_20260301_000000.json"
    kept.write_text("{}")

    res = resolve_opportunities_archive(tmp_path)
    assert res["pin"] == "dangling"
    assert res["fallback"] is True
    assert res["warn"] is True
    assert res["bit"] == "latest dangling · fallback"
    assert Path(res["path"]) == kept


def test_resolve_falls_back_when_latest_stale(tmp_path: Path) -> None:
    """Live latest behind a newer timestamped publish → keep-newest (#685)."""
    arch = tmp_path / "archive"
    arch.mkdir()
    pinned = arch / "opportunities_20260101_120000.json"
    pinned.write_text('{"old": true}')
    newer = arch / "opportunities_20260201_120000.json"
    newer.write_text('{"new": true}')
    (arch / "opportunities_latest.json").symlink_to(pinned.name)

    res = resolve_opportunities_archive(tmp_path)
    assert res["pin"] == "stale"
    assert res["fallback"] is True
    assert res["warn"] is True
    assert res["behind"] == 1
    assert res["behind_share_pct"] == 50
    assert res["behind_share_severity"] == "hot"
    assert res["pin_side"] == 1
    assert res["pin_share_pct"] == 50
    assert res["pin_share_severity"] == ""
    # 50/50: behind hot · pin mid → clash (Screener junk vs ok lean parity).
    assert res["behind_vs_pin"] == "clash · behind hot · pin ok"
    assert res["behind_vs_pin_warn"] is True
    assert res["behind_vs_pin_delta_pp"] == 0
    assert res["behind_vs_pin_delta_severity"] == "thin"
    assert res["behind_vs_pin_lean_vs_delta"] == "align · thin"
    assert res["behind_vs_pin_lean_vs_delta_warn"] is False
    assert res["pin_lag_label"] == "lag 31d · stale"
    assert res["pin_lag_severity"] == "stale"
    assert res["pin_lag_sec"] == 31 * 86400
    # stale↔hot crossed (soft-allow last/share extremes).
    assert res["pin_lag_vs_share"] == "clash · stale · hot"
    assert res["pin_lag_vs_share_warn"] is True
    # lag/share clash + lean clash → both-clash (Screener lean vs Δ moods).
    assert res["pin_lag_share_vs_lean"] == "align · both clash"
    assert res["pin_lag_share_vs_lean_warn"] is True
    # both-clash meta-align vs lean↔Δ align → calm both-align (verbs match).
    assert res["pin_lag_share_lean_vs_delta"] == "align · both align"
    assert res["pin_lag_share_lean_vs_delta_warn"] is False
    assert res["bit"] == (
        "latest stale · 1 behind · hot · 50% · vs 1 pin · 50% · "
        "behind vs pin clash · behind hot · pin ok · Δ thin · 0pp · "
        "lean vs Δ align · thin · lag 31d · stale · "
        "lag/share clash · stale · hot · "
        "lag/share vs lean align · both clash · "
        "lag/share↔lean vs lean↔Δ align · both align · fallback"
    )
    assert res["bit_core"] == (
        "latest stale · 1 behind · hot · 50% · vs 1 pin · 50% · "
        "lag 31d · stale · fallback"
    )
    assert res["pin_lean"] == (
        "behind vs pin clash · behind hot · pin ok · Δ thin · 0pp · "
        "lean vs Δ align · thin · lag/share clash · stale · hot · "
        "lag/share vs lean align · both clash · "
        "lag/share↔lean vs lean↔Δ align · both align"
    )
    assert res["pin_lean_warn"] is True
    assert Path(res["path"]) == newer


def test_resolve_stale_speaks_behind_count(tmp_path: Path) -> None:
    """Bare stale hid how many publishes sit ahead (portfolio AI count≠share)."""
    arch = tmp_path / "archive"
    arch.mkdir()
    pinned = arch / "opportunities_20260101_120000.json"
    pinned.write_text('{"old": true}')
    mid = arch / "opportunities_20260115_120000.json"
    mid.write_text('{"mid": true}')
    newest = arch / "opportunities_20260201_120000.json"
    newest.write_text('{"new": true}')
    (arch / "opportunities_latest.json").symlink_to(pinned.name)

    res = resolve_opportunities_archive(tmp_path)
    assert res["pin"] == "stale"
    assert res["behind"] == 2
    assert res["behind_share_pct"] == 67
    assert res["behind_share_severity"] == "hot"
    assert res["pin_side"] == 1
    assert res["pin_share_pct"] == 33
    assert res["pin_share_severity"] == "thin"
    assert res["behind_vs_pin"] == "align · hot|thin"
    assert res["behind_vs_pin_warn"] is False
    assert res["behind_vs_pin_delta_pp"] == 34
    assert res["behind_vs_pin_delta_severity"] == "wide"
    assert res["behind_vs_pin_lean_vs_delta"] == "align · wide"
    # Adverse align · hot|thin + Δ wide (Screener junk vs ok lean/Δ).
    assert res["behind_vs_pin_lean_vs_delta_warn"] is True
    assert res["pin_lag_label"] == "lag 31d · stale"
    assert res["pin_lag_severity"] == "stale"
    assert res["pin_lag_vs_share"] == "clash · stale · hot"
    assert res["pin_lag_vs_share_warn"] is True
    # lag/share clash vs lean align → crossed warn.
    assert res["pin_lag_share_vs_lean"] == (
        "clash · lag/share clash · lean align"
    )
    assert res["pin_lag_share_vs_lean_warn"] is True
    # meta-clash vs lean↔Δ align → crossed warn.
    assert res["pin_lag_share_lean_vs_delta"] == (
        "clash · lag/share↔lean clash · lean↔Δ align"
    )
    assert res["pin_lag_share_lean_vs_delta_warn"] is True
    assert res["bit"] == (
        "latest stale · 2 behind · hot · 67% · vs 1 pin · thin · 33% · "
        "behind vs pin align · hot|thin · Δ wide · +34pp · "
        "lean vs Δ align · wide · lag 31d · stale · "
        "lag/share clash · stale · hot · "
        "lag/share vs lean clash · lag/share clash · lean align · "
        "lag/share↔lean vs lean↔Δ clash · lag/share↔lean clash · "
        "lean↔Δ align · fallback"
    )
    assert res["bit_core"] == (
        "latest stale · 2 behind · hot · 67% · vs 1 pin · thin · 33% · "
        "lag 31d · stale · fallback"
    )
    assert res["pin_lean"] == (
        "behind vs pin align · hot|thin · Δ wide · +34pp · "
        "lean vs Δ align · wide · lag/share clash · stale · hot · "
        "lag/share vs lean clash · lag/share clash · lean align · "
        "lag/share↔lean vs lean↔Δ clash · lag/share↔lean clash · "
        "lean↔Δ align"
    )
    assert res["pin_lean_warn"] is True
    assert Path(res["path"]) == newest


def test_resolve_stale_behind_share_quiet(tmp_path: Path) -> None:
    """Absolute N behind alone hid a sliver lag vs a majority miss."""
    arch = tmp_path / "archive"
    arch.mkdir()
    # 4 older + pin + 1 newer → behind=1 of 6 → 17% quiet · vs 5 pin strong
    for i, name in enumerate(
        (
            "opportunities_20260101_120000.json",
            "opportunities_20260102_120000.json",
            "opportunities_20260103_120000.json",
            "opportunities_20260104_120000.json",
            "opportunities_20260105_120000.json",
            "opportunities_20260106_120000.json",
        )
    ):
        (arch / name).write_text(f'{{"i": {i}}}')
    (arch / "opportunities_latest.json").symlink_to(
        "opportunities_20260105_120000.json"
    )

    res = resolve_opportunities_archive(tmp_path)
    assert res["pin"] == "stale"
    assert res["behind"] == 1
    assert res["behind_share_pct"] == 17
    assert res["behind_share_severity"] == "quiet"
    assert res["pin_side"] == 5
    assert res["pin_share_pct"] == 83
    assert res["pin_share_severity"] == "strong"
    assert res["behind_vs_pin"] == "align · quiet|strong"
    assert res["behind_vs_pin_warn"] is False
    assert res["behind_vs_pin_delta_pp"] == -66
    assert res["behind_vs_pin_delta_severity"] == "wide"
    assert res["behind_vs_pin_lean_vs_delta"] == "align · wide"
    # Favorable quiet|strong stays calm on lean vs Δ even when Δ is wide.
    assert res["behind_vs_pin_lean_vs_delta_warn"] is False
    assert res["pin_lag_label"] == "lag 24h · aging"
    assert res["pin_lag_severity"] == "aging"
    # aging lag stays silent on lag/share (extremes only) → vs lean silent
    # → meta vs lean↔Δ silent (missing lag/share↔lean).
    assert res["pin_lag_vs_share"] == ""
    assert res["pin_lag_vs_share_warn"] is False
    assert res["pin_lag_share_vs_lean"] == ""
    assert res["pin_lag_share_vs_lean_warn"] is False
    assert res["pin_lag_share_lean_vs_delta"] == ""
    assert res["pin_lag_share_lean_vs_delta_warn"] is False
    assert res["bit"] == (
        "latest stale · 1 behind · quiet · 17% · "
        "vs 5 pin · strong · 83% · behind vs pin align · quiet|strong · "
        "Δ wide · -66pp · lean vs Δ align · wide · lag 24h · aging · fallback"
    )
    assert res["bit_core"] == (
        "latest stale · 1 behind · quiet · 17% · "
        "vs 5 pin · strong · 83% · lag 24h · aging · fallback"
    )
    assert res["pin_lean"] == (
        "behind vs pin align · quiet|strong · Δ wide · -66pp · "
        "lean vs Δ align · wide"
    )
    assert res["pin_lean_warn"] is False
    assert Path(res["path"]).name == "opportunities_20260106_120000.json"


def test_resolve_stale_speaks_pin_lag_hours(tmp_path: Path) -> None:
    """Count+% alone hid whether the pin is hours or weeks behind newest."""
    arch = tmp_path / "archive"
    arch.mkdir()
    pinned = arch / "opportunities_20260101_100000.json"
    pinned.write_text('{"old": true}')
    newer = arch / "opportunities_20260101_160000.json"
    newer.write_text('{"new": true}')
    (arch / "opportunities_latest.json").symlink_to(pinned.name)

    res = resolve_opportunities_archive(tmp_path)
    assert res["pin"] == "stale"
    assert res["behind"] == 1
    assert res["behind_vs_pin"] == "clash · behind hot · pin ok"
    assert res["behind_vs_pin_delta_pp"] == 0
    assert res["behind_vs_pin_delta_severity"] == "thin"
    assert res["behind_vs_pin_lean_vs_delta"] == "align · thin"
    assert res["pin_lag_label"] == "lag 6h · aging"
    assert res["pin_lag_severity"] == "aging"
    assert res["pin_lag_sec"] == 6 * 3600
    assert res["pin_lag_vs_share"] == ""
    assert res["pin_lag_vs_share_warn"] is False
    assert res["pin_lag_share_vs_lean"] == ""
    assert res["pin_lag_share_vs_lean_warn"] is False
    assert res["pin_lag_share_lean_vs_delta"] == ""
    assert res["pin_lag_share_lean_vs_delta_warn"] is False
    assert res["bit"] == (
        "latest stale · 1 behind · hot · 50% · vs 1 pin · 50% · "
        "behind vs pin clash · behind hot · pin ok · Δ thin · 0pp · "
        "lean vs Δ align · thin · lag 6h · aging · fallback"
    )
    assert Path(res["path"]) == newer


def test_resolve_stale_speaks_pin_lag_fresh(tmp_path: Path) -> None:
    """Bare lag duration hid same-session race vs multi-day miss (FinRobot)."""
    arch = tmp_path / "archive"
    arch.mkdir()
    pinned = arch / "opportunities_20260101_120000.json"
    pinned.write_text('{"old": true}')
    newer = arch / "opportunities_20260101_130000.json"
    newer.write_text('{"new": true}')
    (arch / "opportunities_latest.json").symlink_to(pinned.name)

    res = resolve_opportunities_archive(tmp_path)
    assert res["pin"] == "stale"
    assert res["pin_lag_sec"] == 3600
    assert res["pin_lag_severity"] == "fresh"
    assert res["pin_lag_label"] == "lag 1h · fresh"
    # fresh↔hot align (soft-allow last/share + FinRobot age).
    assert res["pin_lag_vs_share"] == "align · fresh · hot"
    assert res["pin_lag_vs_share_warn"] is False
    # lag/share align vs lean clash → crossed warn.
    assert res["pin_lag_share_vs_lean"] == (
        "clash · lag/share align · lean clash"
    )
    assert res["pin_lag_share_vs_lean_warn"] is True
    # meta-clash vs lean↔Δ align → crossed warn.
    assert res["pin_lag_share_lean_vs_delta"] == (
        "clash · lag/share↔lean clash · lean↔Δ align"
    )
    assert res["pin_lag_share_lean_vs_delta_warn"] is True
    assert (
        "lag 1h · fresh · lag/share align · fresh · hot · "
        "lag/share vs lean clash · lag/share align · lean clash · "
        "lag/share↔lean vs lean↔Δ clash · lag/share↔lean clash · "
        "lean↔Δ align · fallback"
    ) in res["bit"]


def test_resolve_missing_archive_speaks_pin() -> None:
    res = resolve_opportunities_archive("/tmp/asc-no-such-desk-data")
    assert res["pin"] == "missing"
    assert res["warn"] is True
    assert res["bit"] == "latest missing"
    assert res["fallback"] is False


def test_scan_freshness_speaks_archive_pin_bit() -> None:
    now = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)
    when = (now - timedelta(minutes=10)).isoformat()
    g = build_scan_freshness(
        when,
        now=now,
        archive_pin="missing",
        archive_pin_bit="latest missing · fallback",
        archive_pin_warn=True,
    )
    assert g["ready"] is True
    assert g["archive_pin"] == "missing"
    assert g["archive_pin_bit"] == "latest missing · fallback"
    assert g["archive_pin_warn"] is True
    assert "latest missing · fallback" in g["line"]
    # Age band on the line stays fresh; display tone escalates for CSS.
    assert " · fresh · " in g["line"]
    assert g["tone"] == "aging"


def test_scan_freshness_pin_only_when_no_scan_time() -> None:
    g = build_scan_freshness(
        None,
        archive_pin="dangling",
        archive_pin_bit="latest dangling",
        archive_pin_warn=True,
    )
    assert g["ready"] is True
    assert g["tone"] == "stale"
    assert g["line"] == "latest dangling"


def test_scan_freshness_speaks_stale_pin_bit() -> None:
    now = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)
    when = (now - timedelta(minutes=10)).isoformat()
    full_bit = (
        "latest stale · 2 behind · hot · 67% · "
        "vs 1 pin · thin · 33% · behind vs pin align · hot|thin · "
        "Δ wide · +34pp · lean vs Δ align · wide · lag 31d · stale · fallback"
    )
    bit_core = (
        "latest stale · 2 behind · hot · 67% · "
        "vs 1 pin · thin · 33% · lag 31d · stale · fallback"
    )
    pin_lean = (
        "behind vs pin align · hot|thin · Δ wide · +34pp · "
        "lean vs Δ align · wide"
    )
    g = build_scan_freshness(
        when,
        now=now,
        archive_pin="stale",
        archive_pin_bit=full_bit,
        archive_pin_bit_core=bit_core,
        archive_pin_lean=pin_lean,
        archive_pin_lean_warn=True,
        archive_pin_warn=True,
    )
    assert full_bit in g["line"]
    assert " · fresh · " in g["line"]
    assert g["tone"] == "aging"
    assert g["archive_pin"] == "stale"
    assert g["archive_pin_bit_core"] == bit_core
    assert g["archive_pin_lean"] == pin_lean
    assert g["archive_pin_lean_warn"] is True


def test_opportunities_markdown_prefers_latest(tmp_path: Path) -> None:
    from openbb_backend.main import _opportunities_markdown_body

    arch = tmp_path / "archive"
    arch.mkdir()
    target = arch / "opportunities_20260101_120000.json"
    target.write_text(
        '{"recommendations":[{"symbol":"AAPL","asset_class":"stock",'
        '"score":40,"reasoning":"ok"}]}'
    )
    (arch / "opportunities_latest.json").symlink_to(target.name)

    body = _opportunities_markdown_body(tmp_path)
    assert "AAPL" in body
    assert "Archive pin" not in body


def test_opportunities_markdown_falls_back_when_latest_stale(tmp_path: Path) -> None:
    """Widget hard-read of opportunities_latest hid keep-newest (#682/#685)."""
    from openbb_backend.main import _opportunities_markdown_body

    arch = tmp_path / "archive"
    arch.mkdir()
    pinned = arch / "opportunities_20260101_120000.json"
    pinned.write_text(
        '{"recommendations":[{"symbol":"OLD","asset_class":"stock",'
        '"score":1,"reasoning":"stale pin"}]}'
    )
    newer = arch / "opportunities_20260201_120000.json"
    newer.write_text(
        '{"recommendations":[{"symbol":"NEW","asset_class":"stock",'
        '"score":99,"reasoning":"keep newest"}]}'
    )
    (arch / "opportunities_latest.json").symlink_to(pinned.name)

    body = _opportunities_markdown_body(tmp_path)
    assert "NEW" in body
    assert "OLD" not in body
    assert (
        "latest stale · 1 behind · hot · 50% · vs 1 pin · 50% · "
        "behind vs pin clash · behind hot · pin ok · Δ thin · 0pp · "
        "lean vs Δ align · thin · lag 31d · stale · "
        "lag/share clash · stale · hot · "
        "lag/share vs lean align · both clash · "
        "lag/share↔lean vs lean↔Δ align · both align · fallback"
    ) in body


def test_opportunities_markdown_prefers_txt_twin_of_resolved(tmp_path: Path) -> None:
    from openbb_backend.main import _opportunities_markdown_body

    arch = tmp_path / "archive"
    arch.mkdir()
    newer = arch / "opportunities_20260201_120000.json"
    newer.write_text('{"recommendations":[]}')
    (arch / "opportunities_20260201_120000.txt").write_text("# From twin txt\nKEEP")
    pinned = arch / "opportunities_20260101_120000.json"
    pinned.write_text("{}")
    (arch / "opportunities_latest.json").symlink_to(pinned.name)
    (arch / "opportunities_latest.txt").write_text("# Stale twin\nOLD")

    body = _opportunities_markdown_body(tmp_path)
    assert "KEEP" in body
    assert "OLD" not in body
    assert (
        "latest stale · 1 behind · hot · 50% · vs 1 pin · 50% · "
        "behind vs pin clash · behind hot · pin ok · Δ thin · 0pp · "
        "lean vs Δ align · thin · lag 31d · stale · "
        "lag/share clash · stale · hot · "
        "lag/share vs lean align · both clash · "
        "lag/share↔lean vs lean↔Δ align · both align · fallback"
    ) in body
