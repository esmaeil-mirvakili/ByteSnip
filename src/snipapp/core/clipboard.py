"""Clipboard helpers: copy to clipboard and safe clipboard restore."""

from __future__ import annotations

import logging
import time

from PySide6.QtGui import QClipboard
from PySide6.QtWidgets import QApplication

logger = logging.getLogger(__name__)


def copy_text(text: str) -> None:
    """Copy *text* to the system clipboard via Qt."""
    clipboard = _get_clipboard()
    clipboard.setText(text, QClipboard.Mode.Clipboard)
    logger.debug("Copied %d chars to clipboard.", len(text))


def get_text() -> str:
    """Return the current clipboard text contents."""
    return _get_clipboard().text(QClipboard.Mode.Clipboard)


class ClipboardRestoreContext:
    """Context manager that saves the current clipboard and restores it on exit.

    Usage::

        with ClipboardRestoreContext():
            # simulate Cmd+C / Ctrl+C here
            captured = get_text()
    """

    def __init__(self, delay_ms: int = 100) -> None:
        self._delay_ms = delay_ms
        self._saved: str = ""

    def __enter__(self) -> "ClipboardRestoreContext":
        self._saved = get_text()
        return self

    def __exit__(self, *_: object) -> None:
        time.sleep(self._delay_ms / 1000)
        copy_text(self._saved)
        logger.debug("Restored previous clipboard contents.")


def _get_clipboard() -> QClipboard:
    app = QApplication.instance()
    if app is None:
        raise RuntimeError("QApplication must be created before using clipboard helpers.")
    return app.clipboard()  # type: ignore[union-attr]
