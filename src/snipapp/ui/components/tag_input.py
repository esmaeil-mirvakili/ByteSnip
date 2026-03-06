"""TagInput widget: horizontal chip-style tag editor with per-tag colours."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QStringListModel, Qt, Signal
from PySide6.QtWidgets import (
    QCompleter,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QWidget,
)

# ---------------------------------------------------------------------------
# Colour palette — (background, foreground) pairs, dark-theme friendly
# The same tag name always maps to the same colour (hash-based).
# ---------------------------------------------------------------------------
_PALETTE: list[tuple[str, str]] = [
    ("#1e3a8a", "#93c5fd"),  # blue
    ("#831843", "#f9a8d4"),  # pink
    ("#134e4a", "#5eead4"),  # teal
    ("#4c1d95", "#c4b5fd"),  # purple
    ("#7c2d12", "#fdba74"),  # orange
    ("#14532d", "#86efac"),  # green
    ("#7f1d1d", "#fca5a5"),  # red
    ("#713f12", "#fde68a"),  # amber
]

_ADD_MARKER = "\x00add\x00"  # invisible sentinel — never appears in real tag names


def _chip_color(tag: str) -> tuple[str, str]:
    """Return a (bg, fg) pair that is stable for a given tag name."""
    return _PALETTE[hash(tag) % len(_PALETTE)]


# ---------------------------------------------------------------------------
# Tag chip
# ---------------------------------------------------------------------------

class _TagChip(QWidget):
    """A coloured pill showing a tag name and an × remove button."""

    removed = Signal(str)

    def __init__(self, tag: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tag = tag
        bg, fg = _chip_color(tag)
        self.setObjectName("chip")
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(
            f"QWidget#chip {{ background: {bg}; border-radius: 10px; }}"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 3, 6, 3)
        layout.setSpacing(4)

        label = QLabel(tag)
        label.setStyleSheet(
            f"QLabel {{ color: {fg}; font-size: 11px; background: transparent; }}"
        )
        layout.addWidget(label)

        btn = QPushButton("×")
        btn.setStyleSheet(
            f"QPushButton {{ color: {fg}; background: transparent; border: none;"
            f"  font-size: 13px; padding: 0; min-width: 0; }}"
            f"QPushButton:hover {{ color: #ff6b6b; }}"
        )
        btn.setFixedSize(15, 15)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda: self.removed.emit(self._tag))
        layout.addWidget(btn)


# ---------------------------------------------------------------------------
# TagInput
# ---------------------------------------------------------------------------

class TagInput(QWidget):
    """Horizontal tag editor: [input field] [chip1 ×] [chip2 ×] …"""

    tags_changed = Signal(list)  # emits list[str]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tags: list[str] = []
        self._base_suggestions: list[str] = []
        self._typed_text: str = ""  # tracks raw user input, unaffected by completer navigation
        self._completion_map: dict[str, str] = {}  # display text → real sentinel value
        self._setup_ui()

    def _setup_ui(self) -> None:
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(6)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Add tag…")
        self._input.setFixedWidth(130)
        self._input.installEventFilter(self)   # ← consume Enter before QDialog sees it
        self._input.textEdited.connect(self._on_text_edited)
        self._layout.addWidget(self._input)

        # Completer backed by a mutable model.
        # UnfilteredPopupCompletion: we fully control what goes in the model,
        # Qt shows exactly those items without applying its own filter.
        self._completer_model = QStringListModel(self)
        self._completer = QCompleter(self._completer_model, self)
        self._completer.setCompletionMode(
            QCompleter.CompletionMode.UnfilteredPopupCompletion
        )
        self._completer.activated.connect(self._on_completer_activated)
        self._input.setCompleter(self._completer)

        add_btn = QPushButton("Add")
        add_btn.setFixedHeight(self._input.sizeHint().height())
        add_btn.setStyleSheet(
            "QPushButton { background: #2d5a8e; color: #e8e8e8; border: none;"
            "  border-radius: 4px; padding: 0 10px; font-size: 11px; }"
            "QPushButton:hover { background: #3a70b0; }"
            "QPushButton:pressed { background: #1e4a7a; }"
        )
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.clicked.connect(self._commit_tag)
        self._layout.addWidget(add_btn)

        self._layout.addStretch()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_suggestions(self, suggestions: list[str]) -> None:
        self._base_suggestions = list(suggestions)
        self._update_completer()

    def set_tags(self, tags: list[str]) -> None:
        self._tags = list(tags)
        self._rebuild()

    def get_tags(self) -> list[str]:
        return list(self._tags)

    # ------------------------------------------------------------------
    # Event filter — consume Enter/Return so QDialog doesn't intercept it
    # ------------------------------------------------------------------

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if obj is self._input and event.type() == QEvent.Type.KeyPress:
            from PySide6.QtGui import QKeyEvent
            key_event: QKeyEvent = event  # type: ignore[assignment]
            if key_event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                # Hide the popup first so _commit_tag reads _typed_text, not the
                # highlighted completion item that the completer has pushed into the field.
                self._completer.popup().hide()
                self._input.setText(self._typed_text)
                self._commit_tag()
                return True  # consume — never let QDialog see Enter
        return super().eventFilter(obj, event)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_text_edited(self, typed: str) -> None:
        """Called only when the user actually types (not when completer writes to the field)."""
        self._typed_text = typed.strip().lower()
        self._update_completer()

    def _update_completer(self) -> None:
        """Rebuild the completer model using _typed_text as the filter."""
        typed = self._typed_text
        already = {t.lower() for t in self._tags}
        matches = [
            s for s in self._base_suggestions
            if typed in s.lower() and s.lower() not in already
        ]

        # _completion_map: display string shown in popup → real tag value
        self._completion_map = {}
        display_items: list[str] = []

        exact_lower = {s.lower() for s in self._base_suggestions}
        if typed and typed not in exact_lower:
            display = f'+ Add "{typed}"'
            self._completion_map[display] = typed
            display_items.append(display)

        display_items.extend(matches)
        self._completer_model.setStringList(display_items)

    def _on_completer_activated(self, text: str) -> None:
        """Called when the user clicks a completer item (not keyboard Enter)."""
        tag = self._completion_map.get(text, text)
        self._typed_text = tag.strip().lower()
        # Defer so the completer finishes its own field update before we clear it.
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, self._commit_tag)

    def _commit_tag(self) -> None:
        text = self._typed_text or self._input.text().strip().lower()
        if text and text not in self._tags:
            self._tags.append(text)
            self._rebuild()
            self.tags_changed.emit(self._tags)
        self._typed_text = ""
        self._input.clear()

    def _remove_tag(self, tag: str) -> None:
        if tag in self._tags:
            self._tags.remove(tag)
            self._rebuild()
            self.tags_changed.emit(self._tags)

    def _rebuild(self) -> None:
        # Remove everything after the input (index 0)
        while self._layout.count() > 1:
            item = self._layout.takeAt(1)
            if item and item.widget():
                item.widget().deleteLater()

        for tag in self._tags:
            chip = _TagChip(tag)
            chip.removed.connect(self._remove_tag)
            self._layout.addWidget(chip)

        self._layout.addStretch()
