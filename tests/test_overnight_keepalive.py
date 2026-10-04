"""Overnight keep-alive unit files (Linux systemd + install scripts)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_systemd_service_does_not_kill_nohup_children() -> None:
    text = (ROOT / "deploy/systemd/ai-stock-checker-overnight-loops.service").read_text()
    assert "Type=oneshot" in text
    assert "KillMode=process" in text
    assert "After=docker.service" in text
    assert "ensure_overnight_loops.sh" in text
    assert "ASC_CURSOR_IMPROVE=1" in text


def test_systemd_timer_fires_at_boot_and_every_15m() -> None:
    text = (ROOT / "deploy/systemd/ai-stock-checker-overnight-loops.timer").read_text()
    assert "OnBootSec=" in text
    assert "OnUnitActiveSec=15min" in text
    assert "WantedBy=timers.target" in text
    assert "Persistent=true" in text


def test_install_scripts_exist() -> None:
    for name in (
        "install_overnight_keepalive.sh",
        "install_overnight_systemd.sh",
        "install_overnight_launchagent.sh",
        "ensure_overnight_loops.sh",
    ):
        path = ROOT / "scripts" / name
        assert path.is_file()
        assert path.stat().st_mode & 0o111
