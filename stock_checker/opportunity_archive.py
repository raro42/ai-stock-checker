"""Opportunity archive readiness pin (keep-newest).

Shared by market_scanner cleanup and desk resolve so hard-readers of
``opportunities_latest`` see the newest publish without waiting for the
next scan prune (xang1234 #682 / #685).

A session-shaped publish is never rewritten; heal/resolve therefore refuse
a malformed JSON artifact and index only usable object publishes
(xang1234 8d447fa / 40a968e market-history refuse-malformed + skip-damaged).
"""

from __future__ import annotations

import json
from pathlib import Path


def opportunity_publish_usable(path: Path) -> bool:
    """True when ``path`` is a parseable JSON object (dict).

    Truncated / wrong-container publishes must not become the readiness pin
    or the keep-newest target — presence alone ≠ usable.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    try:
        doc = json.loads(text)
    except json.JSONDecodeError:
        return False
    return isinstance(doc, dict)


def usable_opportunity_publishes(archive_dir: Path) -> list[Path]:
    """Timestamped opportunity JSON objects, oldest→newest by filename."""
    if not archive_dir.is_dir():
        return []
    return [
        p
        for p in sorted(archive_dir.glob("opportunities_2*.json"))
        if opportunity_publish_usable(p)
    ]


def newest_usable_opportunity_publish(archive_dir: Path) -> Path | None:
    """Newest filename among usable timestamped publishes (or None)."""
    usable = usable_opportunity_publishes(archive_dir)
    return usable[-1] if usable else None


def heal_opportunities_latest_pin(archive_dir: Path) -> bool:
    """Retarget ``*_latest`` to the newest *usable* timestamped publish.

    Filename sort matches desk ``resolve_opportunities_archive`` (not mtime).
    Malformed / wrong-container JSON is skipped so heal never promotes junk
    over a good older publish. Returns True when a pin was created or
    retargeted.
    """
    if not archive_dir.is_dir():
        return False
    newest = newest_usable_opportunity_publish(archive_dir)
    if newest is None:
        return False
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
                if latest_name.endswith(".json") and latest.exists():
                    # Live pin on a damaged artifact must retarget even when
                    # the symlink name already matches a junk path.
                    if not opportunity_publish_usable(latest.resolve()):
                        need = True
                    else:
                        need = latest.resolve() != target.resolve()
                else:
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
