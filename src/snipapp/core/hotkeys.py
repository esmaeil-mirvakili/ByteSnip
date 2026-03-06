"""Global hotkey registration (macOS + Linux/X11).

Emits Qt signals via a QObject bridge so hotkey callbacks run safely on the
main thread even though pynput fires them from a background thread.
"""

from __future__ import annotations

import logging
import platform
from collections.abc import Callable

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)

_SYSTEM = platform.system()


class HotkeySignals(QObject):
    """Carries cross-thread signals for each registered hotkey."""

    picker_triggered = Signal()
    save_triggered = Signal()


class HotkeyManager:
    """Registers global hotkeys and emits Qt signals when they fire."""

    def __init__(self) -> None:
        self.signals = HotkeySignals()
        self._listener: object | None = None

    def start(
        self,
        picker_combo: str = "<cmd>+<shift>+`",
        save_combo: str = "<ctrl>+<cmd>+c",
    ) -> None:
        """Begin listening for global hotkeys in a background thread."""
        from pynput import keyboard as kb  # type: ignore[import]

        hotkeys = {
            picker_combo: self._on_picker,
            save_combo: self._on_save,
        }
        self._listener = kb.GlobalHotKeys(hotkeys)
        self._listener.start()  # type: ignore[attr-defined]
        logger.info(
            "Hotkeys registered — picker: %s  save: %s", picker_combo, save_combo
        )

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()  # type: ignore[attr-defined]
            self._listener = None

    # pynput callbacks (background thread — only emit Qt signals, no UI work)
    def _on_picker(self) -> None:
        logger.debug("Picker hotkey fired.")
        self.signals.picker_triggered.emit()

    def _on_save(self) -> None:
        logger.debug("Save hotkey fired.")
        self.signals.save_triggered.emit()
