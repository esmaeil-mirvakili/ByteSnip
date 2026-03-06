"""Register ByteSnip as a native application.

macOS  — creates ~/Applications/ByteSnip.app (a minimal .app wrapper so the
          app appears in Spotlight and Launchpad).
Linux  — creates ~/.local/share/applications/bytesnip.desktop so the app
          appears in GNOME Activities, KDE Launcher, etc.

Called automatically on first startup and also exposed as the
``bytesnip-install`` CLI entry point for manual re-registration.
"""

from __future__ import annotations

import logging
import os
import platform
import shutil
import stat
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_APP_NAME = "ByteSnip"
_APP_ID = "com.bytesnip.app"
_APP_VERSION = "0.1.0"
_COMMENT = "Fast keyboard-first code snippet manager"
_CATEGORIES = "Development;Utility;"
_KEYWORDS = "snippet;code;clipboard;developer;"

# Sentinel file written after a successful registration so we don't redo it
# on every launch.
_SENTINEL = Path.home() / ".local" / "share" / "bytesnip" / ".app_registered"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def register_app() -> None:
    """Create the platform application entry for ByteSnip."""
    if platform.system() == "Darwin":
        _macos_register()
    else:
        _linux_register()
    # Write sentinel so we skip next time
    _SENTINEL.parent.mkdir(parents=True, exist_ok=True)
    _SENTINEL.write_text("1")
    logger.info("App registration complete.")


def unregister_app() -> None:
    """Remove the platform application entry for ByteSnip."""
    if platform.system() == "Darwin":
        _macos_unregister()
    else:
        _linux_unregister()
    if _SENTINEL.exists():
        _SENTINEL.unlink()
    logger.info("App unregistration complete.")


def is_registered() -> bool:
    """Return True only if the sentinel exists AND the app entry is still in place."""
    if not _SENTINEL.exists():
        return False
    if platform.system() == "Darwin":
        return _macos_app_path().exists()
    else:
        return _linux_desktop_path().exists()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _executable() -> str:
    """Path to the bytesnip entry-point script (or python -m fallback)."""
    found = shutil.which("bytesnip")
    if found:
        return found
    return f"{sys.executable} -m snipapp.main"


def _icon_path() -> Path | None:
    """Return path to code_color.svg if it exists alongside the package."""
    candidate = Path(__file__).parent.parent.parent.parent / "assets" / "icons" / "code_color.svg"
    return candidate if candidate.exists() else None


# ---------------------------------------------------------------------------
# macOS — minimal .app bundle
# ---------------------------------------------------------------------------

_PLIST = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>ByteSnip</string>
    <key>CFBundleIdentifier</key>
    <string>{app_id}</string>
    <key>CFBundleName</key>
    <string>{app_name}</string>
    <key>CFBundleDisplayName</key>
    <string>{app_name}</string>
    <key>CFBundleVersion</key>
    <string>{version}</string>
    <key>CFBundleShortVersionString</key>
    <string>{version}</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSRequiresAquaSystemAppearance</key>
    <false/>
</dict>
</plist>
"""

_LAUNCHER = """\
#!/bin/bash
exec {exe} "$@"
"""


def _macos_app_path() -> Path:
    return Path.home() / "Applications" / "ByteSnip.app"


def _macos_register() -> None:
    app = _macos_app_path()
    contents = app / "Contents"
    macos_dir = contents / "MacOS"
    macos_dir.mkdir(parents=True, exist_ok=True)

    # Executable shell wrapper
    exe = _executable()
    launcher = macos_dir / "ByteSnip"
    launcher.write_text(_LAUNCHER.format(exe=exe))
    launcher.chmod(launcher.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    # Info.plist
    (contents / "Info.plist").write_text(
        _PLIST.format(app_id=_APP_ID, app_name=_APP_NAME, version=_APP_VERSION)
    )

    # Icon: copy SVG as icns placeholder (Finder will show generic if not .icns,
    # but SVG still works for Quick Look / some contexts)
    icon = _icon_path()
    if icon:
        resources = contents / "Resources"
        resources.mkdir(exist_ok=True)
        shutil.copy(icon, resources / "AppIcon.svg")

    logger.info("macOS .app bundle created at %s", app)

    # Tell Launch Services to re-index so Spotlight picks it up immediately
    try:
        subprocess.run(
            ["/System/Library/Frameworks/CoreServices.framework/Versions/A/"
             "Frameworks/LaunchServices.framework/Versions/A/Support/lsregister",
             "-f", str(app)],
            check=False, capture_output=True,
        )
    except FileNotFoundError:
        pass  # lsregister not available in some environments


def _macos_unregister() -> None:
    app = _macos_app_path()
    if app.exists():
        shutil.rmtree(app)
        logger.info("macOS .app bundle removed: %s", app)


# ---------------------------------------------------------------------------
# Linux — XDG .desktop file
# ---------------------------------------------------------------------------

def _linux_desktop_path() -> Path:
    xdg_data = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return xdg_data / "applications" / "bytesnip.desktop"


def _linux_register() -> None:
    path = _linux_desktop_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    exe = _executable()
    icon_p = _icon_path()
    icon_line = f"Icon={icon_p}" if icon_p else "Icon=utilities-terminal"

    desktop = (
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={_APP_NAME}\n"
        f"Comment={_COMMENT}\n"
        f"Exec={exe}\n"
        f"{icon_line}\n"
        f"Categories={_CATEGORIES}\n"
        f"Keywords={_KEYWORDS}\n"
        "StartupNotify=false\n"
        "Terminal=false\n"
    )
    path.write_text(desktop)
    logger.info("Linux .desktop file created at %s", path)

    # Refresh application database so launchers pick it up
    try:
        subprocess.run(
            ["update-desktop-database", str(path.parent)],
            check=False, capture_output=True,
        )
    except FileNotFoundError:
        pass


def _linux_unregister() -> None:
    path = _linux_desktop_path()
    if path.exists():
        path.unlink()
        logger.info("Linux .desktop file removed: %s", path)
    try:
        subprocess.run(
            ["update-desktop-database", str(path.parent)],
            check=False, capture_output=True,
        )
    except FileNotFoundError:
        pass


# ---------------------------------------------------------------------------
# CLI entry point  (bytesnip-install)
# ---------------------------------------------------------------------------

def cli() -> None:
    """Entry point for ``bytesnip-install`` command."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        register_app()
        print(f"✓  ByteSnip registered as a system application.")
        if platform.system() == "Darwin":
            print("   You can now find it in Spotlight and Launchpad.")
        else:
            print("   You can now find it in your application launcher.")
    except Exception as exc:
        print(f"✗  Registration failed: {exc}", file=sys.stderr)
        sys.exit(1)
