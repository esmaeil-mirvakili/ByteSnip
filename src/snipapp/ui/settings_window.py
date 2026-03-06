"""Settings dialog."""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, Signal

logger = logging.getLogger(__name__)
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from snipapp.core.settings import Settings

_STYLE = """
QDialog {
    background: #1e1e1e;
    color: #cccccc;
}
QTabWidget::pane {
    border: 1px solid #3c3c3c;
    background: #252526;
    border-radius: 0 4px 4px 4px;
}
QTabBar::tab {
    background: #2d2d2d;
    color: #9d9d9d;
    padding: 6px 18px;
    border: none;
    margin-right: 2px;
}
QTabBar::tab:selected {
    background: #252526;
    color: #ffffff;
    border-top: 2px solid #007acc;
}
QTabBar::tab:hover:!selected {
    background: #333333;
    color: #cccccc;
}
QGroupBox {
    color: #777777;
    border: 1px solid #3c3c3c;
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 8px;
    font-size: 11px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
}
QLabel { color: #cccccc; }
QCheckBox {
    color: #cccccc;
    spacing: 8px;
}
QCheckBox::indicator {
    width: 15px;
    height: 15px;
    border: 1px solid #555555;
    border-radius: 3px;
    background: #2d2d2d;
}
QCheckBox::indicator:checked {
    background: #007acc;
    border-color: #007acc;
    image: none;
}
QCheckBox::indicator:hover { border-color: #007acc; }
QLineEdit {
    background: #2d2d2d;
    border: 1px solid #555555;
    border-radius: 4px;
    color: #e8e8e8;
    padding: 5px 8px;
    font-family: monospace;
    font-size: 12px;
}
QLineEdit:focus { border-color: #007acc; }
"""

_BTN_SAVE = """
QPushButton {
    background: #2d5a8e; color: #e8e8e8;
    border: none; border-radius: 4px;
    padding: 6px 20px; font-size: 12px;
}
QPushButton:hover { background: #3a70b0; }
QPushButton:pressed { background: #1e4a7a; }
"""
_BTN_CANCEL = """
QPushButton {
    background: transparent; color: #9d9d9d;
    border: 1px solid #444444; border-radius: 4px;
    padding: 6px 20px; font-size: 12px;
}
QPushButton:hover { background: #2a2d2e; color: #cccccc; }
"""


class SettingsWindow(QDialog):
    """Modal settings dialog."""

    #: Emitted when hotkey strings change — caller should restart HotkeyManager.
    hotkeys_changed = Signal(str, str)  # (picker_combo, save_combo)

    def __init__(self, settings: Settings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self.setWindowTitle("ByteSnip — Settings")
        self.setModal(True)
        self.setMinimumWidth(500)
        self.setStyleSheet(_STYLE)
        self._setup_ui()
        self._load_values()

    # ------------------------------------------------------------------
    # Build UI
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 16)
        root.setSpacing(16)

        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_general_tab(), "General")
        self._tabs.addTab(self._build_hotkeys_tab(), "Hotkeys")
        root.addWidget(self._tabs, stretch=1)

        # Footer
        footer = QHBoxLayout()
        footer.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(_BTN_CANCEL)
        cancel_btn.clicked.connect(self.reject)
        footer.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.setStyleSheet(_BTN_SAVE)
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._save)
        footer.addWidget(save_btn)
        root.addLayout(footer)

    def _build_general_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 8)
        layout.setSpacing(14)

        # Search group
        search_grp = QGroupBox("Search")
        sg = QVBoxLayout(search_grp)
        sg.setContentsMargins(12, 8, 12, 12)
        self._search_body_cb = QCheckBox("Search inside snippet bodies")
        sg.addWidget(self._search_body_cb)
        layout.addWidget(search_grp)

        # Startup group
        startup_grp = QGroupBox("Startup")
        su = QVBoxLayout(startup_grp)
        su.setContentsMargins(12, 8, 12, 12)
        self._run_at_login_cb = QCheckBox("Run at login")
        su.addWidget(self._run_at_login_cb)
        layout.addWidget(startup_grp)

        layout.addStretch()
        return page

    def _build_hotkeys_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 8)
        layout.setSpacing(12)

        hint = QLabel(
            "Use pynput modifier names: <cmd>  <ctrl>  <shift>  <alt>\n"
            "followed by a regular key character.\n\n"
            "Examples:  <cmd>+<shift>+`     <ctrl>+<cmd>+c"
        )
        hint.setStyleSheet("color: #666666; font-size: 11px; padding: 4px 0;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        grp = QGroupBox("Shortcuts")
        form_layout = QFormLayout(grp)
        form_layout.setContentsMargins(12, 12, 12, 12)
        form_layout.setSpacing(10)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._picker_hotkey = QLineEdit()
        self._picker_hotkey.setPlaceholderText("<cmd>+<shift>+`")
        form_layout.addRow("Snippet Picker:", self._picker_hotkey)

        self._save_hotkey = QLineEdit()
        self._save_hotkey.setPlaceholderText("<ctrl>+<cmd>+c")
        form_layout.addRow("Save Snippet:", self._save_hotkey)

        layout.addWidget(grp)
        layout.addStretch()
        return page

    # ------------------------------------------------------------------
    # Load / Save
    # ------------------------------------------------------------------

    def _load_values(self) -> None:
        self._search_body_cb.setChecked(self._settings.get("search_in_body", True))
        self._run_at_login_cb.setChecked(self._settings.get("run_at_login", False))
        self._picker_hotkey.setText(
            self._settings.get("hotkeys.picker", "<cmd>+<shift>+`")
        )
        self._save_hotkey.setText(
            self._settings.get("hotkeys.save", "<ctrl>+<cmd>+c")
        )

    def _save(self) -> None:
        old_picker = self._settings.get("hotkeys.picker", "")
        old_save = self._settings.get("hotkeys.save", "")

        run_at_login = self._run_at_login_cb.isChecked()
        self._settings.set("search_in_body", self._search_body_cb.isChecked())
        self._settings.set("run_at_login", run_at_login)

        new_picker = self._picker_hotkey.text().strip() or "<cmd>+<shift>+`"
        new_save = self._save_hotkey.text().strip() or "<ctrl>+<cmd>+c"
        self._settings.set("hotkeys.picker", new_picker)
        self._settings.set("hotkeys.save", new_save)
        self._settings.save()

        try:
            from snipapp.core.run_at_login import set_run_at_login
            set_run_at_login(run_at_login)
        except Exception as exc:
            logger.warning("Could not update run-at-login: %s", exc)

        if new_picker != old_picker or new_save != old_save:
            self.hotkeys_changed.emit(new_picker, new_save)

        self.accept()
