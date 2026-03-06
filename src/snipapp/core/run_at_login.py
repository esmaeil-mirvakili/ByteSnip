"""Register / unregister ByteSnip as a login item.

macOS  — writes a LaunchAgent plist to ~/Library/LaunchAgents/
Linux  — writes an XDG autostart .desktop file to ~/.config/autostart/
"""

from __future__ import annotations

import logging
import platform
import shutil
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_LABEL = "com.bytesnip.app"
_APP_NAME = "ByteSnip"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def set_run_at_login(enabled: bool) -> None:
    """Enable or disable launch-at-login for ByteSnip."""
    if platform.system() == "Darwin":
        _macos_set(enabled)
    else:
        _linux_set(enabled)


def get_run_at_login() -> bool:
    """Return True if ByteSnip is currently registered as a login item."""
    if platform.system() == "Darwin":
        return _macos_plist_path().exists()
    return _linux_desktop_path().exists()


# ---------------------------------------------------------------------------
# Helpers — executable path
# ---------------------------------------------------------------------------

def _executable() -> str:
    """Best-effort path to the bytesnip entry-point script."""
    found = shutil.which("bytesnip")
    if found:
        return found
    # Fallback: re-invoke via the current interpreter
    return f"{sys.executable} -m snipapp.main"


# ---------------------------------------------------------------------------
# macOS LaunchAgent
# ---------------------------------------------------------------------------

def _macos_plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{_LABEL}.plist"


def _macos_set(enabled: bool) -> None:
    path = _macos_plist_path()
    if enabled:
        path.parent.mkdir(parents=True, exist_ok=True)
        exe = _executable()
        plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{exe}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
</dict>
</plist>
"""
        path.write_text(plist)
        logger.info("LaunchAgent written: %s", path)
    else:
        if path.exists():
            path.unlink()
            logger.info("LaunchAgent removed: %s", path)


# ---------------------------------------------------------------------------
# Linux XDG autostart
# ---------------------------------------------------------------------------

def _linux_desktop_path() -> Path:
    import os
    config = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return config / "autostart" / "bytesnip.desktop"


def _linux_set(enabled: bool) -> None:
    path = _linux_desktop_path()
    if enabled:
        path.parent.mkdir(parents=True, exist_ok=True)
        exe = _executable()
        desktop = (
            "[Desktop Entry]\n"
            "Type=Application\n"
            f"Name={_APP_NAME}\n"
            f"Exec={exe}\n"
            "Hidden=false\n"
            "NoDisplay=false\n"
            "X-GNOME-Autostart-enabled=true\n"
        )
        path.write_text(desktop)
        logger.info("Autostart desktop written: %s", path)
    else:
        if path.exists():
            path.unlink()
            logger.info("Autostart desktop removed: %s", path)
