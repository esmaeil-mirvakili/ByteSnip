"""ByteSnip entry point: bootstraps Qt app, tray icon, and hotkeys."""

from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path

# Icons live in <repo-root>/assets/icons/ (source) or alongside the bundle (frozen).
if getattr(sys, "frozen", False):
    _ICONS_DIR = Path(sys._MEIPASS) / "assets" / "icons"  # type: ignore[attr-defined]
else:
    _ICONS_DIR = Path(__file__).parent.parent.parent / "assets" / "icons"


def _setup_logging() -> None:
    log_dir = Path.home() / "Library" / "Logs" / "ByteSnip"
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        log_dir / "bytesnip.log", maxBytes=2 * 1024 * 1024, backupCount=3
    )
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        handlers=[handler, logging.StreamHandler()],
    )


def _tray_icon() -> "QIcon":  # noqa: F821
    """Return the tray icon appropriate for the current palette (dark vs light)."""
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    is_dark = QApplication.palette().window().color().lightness() < 128
    name = "code_dark.svg" if is_dark else "code_light.svg"
    path = _ICONS_DIR / name
    if path.exists():
        return QIcon(str(path))
    return QIcon.fromTheme("edit-paste")  # fallback


def main() -> None:
    _setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("ByteSnip starting up.")

    from PySide6.QtGui import QIcon, QAction
    from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

    app = QApplication(sys.argv)
    app.setApplicationName("ByteSnip")
    app.setQuitOnLastWindowClosed(False)

    # App icon (dock / taskbar / About dialog)
    app_icon_path = _ICONS_DIR / "code_color.svg"
    if app_icon_path.exists():
        app.setWindowIcon(QIcon(str(app_icon_path)))

    # Initialise database
    from snipapp.core.db import init_engine
    init_engine()

    # Load settings
    from snipapp.core.settings import Settings
    settings = Settings()

    # Create windows (lazy — shown on demand)
    from snipapp.ui.picker_window import PickerWindow
    from snipapp.ui.save_window import SaveWindow
    from snipapp.ui.settings_window import SettingsWindow

    picker = PickerWindow()
    save_win = SaveWindow()
    settings_win = SettingsWindow(settings)

    # Hotkeys
    from snipapp.core.hotkeys import HotkeyManager
    hotkeys = HotkeyManager()
    hotkeys.signals.picker_triggered.connect(picker.show_and_focus)
    hotkeys.signals.save_triggered.connect(_open_save_window(save_win))
    picker.edit_requested.connect(save_win.edit_snippet)
    hotkeys.start(
        picker_combo=settings.get("hotkeys.picker", "<cmd>+<shift>+`"),
        save_combo=settings.get("hotkeys.save", "<ctrl>+<cmd>+c"),
    )

    def _restart_hotkeys(picker_combo: str, save_combo: str) -> None:
        hotkeys.stop()
        hotkeys.start(picker_combo=picker_combo, save_combo=save_combo)
        logger.info("Hotkeys restarted: picker=%s save=%s", picker_combo, save_combo)

    settings_win.hotkeys_changed.connect(_restart_hotkeys)

    # ── System tray ──────────────────────────────────────────────────────
    tray = QSystemTrayIcon(app)
    tray.setIcon(_tray_icon())
    tray.setToolTip("ByteSnip")

    # Re-apply correct icon whenever the OS switches dark ↔ light mode
    app.paletteChanged.connect(lambda _: tray.setIcon(_tray_icon()))

    tray_menu = QMenu()

    open_action = QAction("Open ByteSnip", app)
    open_action.triggered.connect(picker.show_and_focus)
    tray_menu.addAction(open_action)

    tray_menu.addSeparator()

    settings_action = QAction("Settings", app)
    settings_action.triggered.connect(settings_win.show)
    tray_menu.addAction(settings_action)

    tray_menu.addSeparator()

    quit_action = QAction("Quit ByteSnip", app)
    quit_action.triggered.connect(app.quit)
    tray_menu.addAction(quit_action)

    tray.setContextMenu(tray_menu)

    # Left-click / activate → open picker
    def _on_tray_activated(reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            picker.show_and_focus()

    tray.activated.connect(_on_tray_activated)
    tray.show()

    logger.info("ByteSnip ready.")
    exit_code = app.exec()
    hotkeys.stop()
    sys.exit(exit_code)


def _open_save_window(save_win: object) -> object:
    """Return a slot that captures selected text and opens the save window."""
    def _slot() -> None:
        from snipapp.core.capture import capture_selected_text
        text = capture_selected_text()
        save_win.open_with_text(text)  # type: ignore[attr-defined]

    return _slot


if __name__ == "__main__":
    main()
