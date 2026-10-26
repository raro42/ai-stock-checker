"""Opportunity archive readiness pin (keep-newest).

Shared by market_scanner cleanup and desk resolve so hard-readers of
``opportunities_latest`` see the newest publish without waiting for the
next scan prune (xang1234 #682 / #685).
"""

from __future__ import annotations

from pathlib import Path


def heal_opportunities_latest_pin(archive_dir: Path) -> bool:
    """Retarget ``*_latest`` to the newest timestamped publish when behind.

    Filename sort matches desk ``resolve_opportunities_archive`` (not mtime).
    Returns True when a pin was created or retargeted.
    """
    if not archive_dir.is_dir():
        return False
    candidates = sorted(archive_dir.glob("opportunities_2*.json"))
    if not candidates:
        return False
    newest = candidates[-1]
    healed = False
    for latest_name, target in (
        ("opportunities_latest.json", newest),
        (
            "opportunities_latest.txt",
            newest.with_suffix(".txt")
            if newest.with_suffix(".txt").exists()
            else None,
        ),
    ):
        if target is None or not target.exists():
            continue
        latest = archive_dir / latest_name
        need = True
        if latest.is_symlink() or latest.is_file():
            try:
                need = (not latest.exists()) or (
                    latest.resolve() != target.resolve()
                )
            except OSError:
                need = True
        if not need:
            continue
        try:
            if latest.exists() or latest.is_symlink():
                latest.unlink()
            latest.symlink_to(target.name)
            healed = True
        except OSError as exc:
            print(f"⚠️  Could not heal {latest_name}: {exc}")
    if healed:
        print(f"📌 Healed opportunities_latest → {newest.name}")
    return healed
