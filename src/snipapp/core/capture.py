"""Capture the currently selected text from the active application.

Strategy (in order of preference):
  macOS  — Accessibility API (AX) via pyobjc; fallback to Cmd+C simulation.
  Linux  — PRIMARY X11 selection; fallback to Ctrl+C simulation.
"""

from __future__ import annotations

import logging
import platform
import time

from snipapp.core.clipboard import ClipboardRestoreContext, copy_text, get_text

logger = logging.getLogger(__name__)

_SYSTEM = platform.system()


def capture_selected_text() -> str:
    """Return the text currently selected in the active application, or ''."""
    if _SYSTEM == "Darwin":
        return _capture_macos()
    return _capture_linux()


# ---------------------------------------------------------------------------
# macOS
# ---------------------------------------------------------------------------

def _capture_macos() -> str:
    try:
        return _capture_macos_ax()
    except Exception as exc:
        logger.debug("AX capture failed (%s); falling back to clipboard sim.", exc)
    return _capture_via_clipboard_sim_macos()


def _capture_macos_ax() -> str:
    """Read selected text via the macOS Accessibility API."""
    import AppKit  # type: ignore[import]
    import Quartz  # type: ignore[import]

    focused = AppKit.NSWorkspace.sharedWorkspace().frontmostApplication()
    pid = focused.processIdentifier()
    app_ref = Quartz.AXUIElementCreateApplication(pid)

    focused_elem = Quartz.AXUIElementCopyAttributeValue(
        app_ref, "AXFocusedUIElement", None
    )[1]
    selected = Quartz.AXUIElementCopyAttributeValue(
        focused_elem, "AXSelectedText", None
    )[1]
    return selected or ""


def _capture_via_clipboard_sim_macos() -> str:
    """Simulate Cmd+C, read clipboard, then restore previous contents."""
    from pynput.keyboard import Controller, Key  # type: ignore[import]

    keyboard = Controller()
    with ClipboardRestoreContext(delay_ms=150) as ctx:
        with keyboard.pressed(Key.cmd):
            keyboard.tap("c")
        time.sleep(0.15)
        captured = get_text()
    return captured


# ---------------------------------------------------------------------------
# Linux
# ---------------------------------------------------------------------------

def _capture_linux() -> str:
    try:
        return _capture_x11_primary()
    except Exception as exc:
        logger.debug("X11 PRIMARY capture failed (%s); falling back to Ctrl+C.", exc)
    return _capture_via_clipboard_sim_linux()


def _capture_x11_primary() -> str:
    """Read the X11 PRIMARY selection (auto-updated on text selection)."""
    from PySide6.QtGui import QClipboard
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        raise RuntimeError("No QApplication")
    clipboard = app.clipboard()  # type: ignore[union-attr]
    text = clipboard.text(QClipboard.Mode.Selection)
    return text or ""


def _capture_via_clipboard_sim_linux() -> str:
    """Simulate Ctrl+C, read clipboard, then restore previous contents."""
    from pynput.keyboard import Controller, Key  # type: ignore[import]

    keyboard = Controller()
    with ClipboardRestoreContext(delay_ms=150):
        with keyboard.pressed(Key.ctrl):
            keyboard.tap("c")
        time.sleep(0.15)
        captured = get_text()
    return captured
