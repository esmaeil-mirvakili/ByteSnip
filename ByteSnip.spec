# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for ByteSnip.

Build:
  macOS : pyinstaller ByteSnip.spec --clean
  Linux : pyinstaller ByteSnip.spec --clean

Output:
  macOS : dist/ByteSnip.app   → drag to /Applications
  Linux : dist/ByteSnip/      → run dist/ByteSnip/ByteSnip
"""

import platform
import sys
from pathlib import Path

IS_MACOS = platform.system() == "Darwin"

# ── Analysis ──────────────────────────────────────────────────────────────────

a = Analysis(
    ["src/snipapp/main.py"],
    pathex=["src"],
    binaries=[],
    datas=[
        ("assets/icons", "assets/icons"),
    ],
    hiddenimports=[
        "sqlalchemy.dialects.sqlite",
        "sqlalchemy.sql.default_comparator",
        "sqlalchemy.orm.events",
        *(["pynput.keyboard._darwin", "pynput.mouse._darwin"] if IS_MACOS else
          ["pynput.keyboard._xorg", "pynput.mouse._xorg"]),
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "unittest"],
    noarchive=False,
)

pyz = PYZ(a.pure)

# ── Executable ────────────────────────────────────────────────────────────────

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ByteSnip",
    debug=False,
    strip=False,
    upx=False,
    console=False,          # no terminal window
    argv_emulation=IS_MACOS,
)

# ── Collect ───────────────────────────────────────────────────────────────────

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="ByteSnip",
)

# ── macOS .app bundle ─────────────────────────────────────────────────────────

if IS_MACOS:
    app = BUNDLE(
        coll,
        name="ByteSnip.app",
        icon="assets/icons/ByteSnip.icns",
        bundle_identifier="com.bytesnip.app",
        info_plist={
            "CFBundleName": "ByteSnip",
            "CFBundleDisplayName": "ByteSnip",
            "CFBundleVersion": "0.1.0",
            "CFBundleShortVersionString": "0.1.0",
            "CFBundlePackageType": "APPL",
            "NSHighResolutionCapable": True,
            "NSRequiresAquaSystemAppearance": False,
            # LSUIElement = 1 hides the Dock icon; the app lives in the menu bar.
            "LSUIElement": True,
            "NSAccessibilityUsageDescription":
                "ByteSnip needs Accessibility access for global hotkeys and text capture.",
            "NSInputMonitoringUsageDescription":
                "ByteSnip needs Input Monitoring access to listen for global hotkeys.",
        },
    )
