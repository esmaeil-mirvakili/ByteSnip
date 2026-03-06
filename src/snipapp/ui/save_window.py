"""Save-snippet window: pre-filled form with preview (Ctrl+Cmd+C)."""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from snipapp.core.db import get_session
from snipapp.core.highlight import detect_language
from snipapp.core.models import Folder, Snippet, Tag
from snipapp.ui.components.code_preview import CodePreview
from snipapp.ui.components.folder_tree import FolderTree
from snipapp.ui.components.tag_input import TagInput

logger = logging.getLogger(__name__)

_COMMON_LANGUAGES = [
    "text", "python", "javascript", "typescript", "rust", "go", "java",
    "c", "cpp", "csharp", "swift", "kotlin", "ruby", "php", "bash",
    "sql", "html", "css", "json", "yaml", "toml", "markdown",
]

_DARK_STYLE = """
    QDialog {
        background: #1e1e1e;
    }
    QLabel {
        color: #cccccc;
    }
    QLineEdit, QComboBox {
        background: #2d2d2d;
        border: 1px solid #555555;
        border-radius: 4px;
        padding: 5px 8px;
        color: #e8e8e8;
        selection-background-color: #094771;
    }
    QLineEdit:focus, QComboBox:focus {
        border: 1px solid #007acc;
    }
    QPlainTextEdit {
        background: #252526;
        border: 1px solid #3c3c3c;
        border-radius: 4px;
        color: #d4d4d4;
        font-family: "Menlo", "Consolas", monospace;
        font-size: 13px;
        selection-background-color: #094771;
    }
    QPlainTextEdit:focus {
        border: 1px solid #007acc;
    }
    QComboBox::drop-down {
        border: none;
        padding-right: 6px;
    }
    QTreeView {
        background: #252526;
        border: 1px solid #3c3c3c;
        color: #cccccc;
    }
    QTreeView::item:selected {
        background: #094771;
        color: #ffffff;
    }
    QTreeView::item:hover {
        background: #2a2d2e;
    }
    QPushButton {
        background: #0e639c;
        color: #ffffff;
        border: none;
        border-radius: 4px;
        padding: 6px 16px;
        min-width: 80px;
    }
    QPushButton:hover {
        background: #1177bb;
    }
    QPushButton:pressed {
        background: #094771;
    }
"""


class SaveWindow(QDialog):
    """Modal dialog for saving a new snippet, or editing an existing one."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._selected_folder_id: int | None = None
        self._editing_id: int | None = None  # None → create, int → edit
        self._setup_window()
        self._setup_ui()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def open_with_text(self, text: str) -> None:
        """Pre-fill the editor with *text* and auto-detect its language."""
        self._reset_mode()
        language = detect_language(text)
        self._editor.setPlainText(text)
        self._title_input.setText(_default_title(text))

        idx = self._lang_combo.findText(language)
        self._lang_combo.setCurrentIndex(idx if idx >= 0 else 0)

        self._desc_input.clear()
        self._tag_input.set_tags([])
        self._warning_label.hide()
        self._refresh_preview()
        self._load_folders_and_tags()
        self.show()
        self.raise_()
        self.activateWindow()
        self._title_input.setFocus()

    def edit_snippet(self, snippet_id: int) -> None:
        """Open the window pre-filled with an existing snippet for editing."""
        with get_session() as session:
            snippet = session.get(Snippet, snippet_id)
            if snippet is None:
                return
            body = snippet.body
            title = snippet.title
            language = snippet.language or "text"
            description = snippet.description or ""
            folder_id = snippet.folder_id
            tag_names = [t.name for t in snippet.tags]

        self._editing_id = snippet_id
        self.setWindowTitle("Edit Snippet — ByteSnip")

        self._editor.setPlainText(body)
        self._title_input.setText(title)
        idx = self._lang_combo.findText(language)
        if idx < 0:
            self._lang_combo.addItem(language)
            idx = self._lang_combo.findText(language)
        self._lang_combo.setCurrentIndex(idx)
        self._desc_input.setText(description)
        self._tag_input.set_tags(tag_names)
        self._warning_label.hide()
        self._refresh_preview()
        self._load_folders_and_tags()
        self._folder_tree.select_folder_by_id(folder_id)
        self.show()
        self.raise_()
        self.activateWindow()
        self._title_input.setFocus()

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _setup_window(self) -> None:
        self.setWindowTitle("Save Snippet — ByteSnip")
        self.resize(900, 600)
        self.setStyleSheet(_DARK_STYLE)
        self._center_on_screen()

    def _setup_ui(self) -> None:
        _SPLITTER_STYLE = "QSplitter::handle { background: #3c3c3c; }"
        _SECTION_LABEL_STYLE = "font-size: 11px; color: #888888; text-transform: uppercase;"

        root = QVBoxLayout(self)
        root.setSpacing(8)

        # ── Outer vertical splitter (top section | bottom section) ────────
        outer = QSplitter(Qt.Orientation.Vertical)
        outer.setHandleWidth(1)
        outer.setStyleSheet(_SPLITTER_STYLE)
        root.addWidget(outer, stretch=1)

        # ── TOP: form fields (left) | folder tree (right) ─────────────────
        top_split = QSplitter(Qt.Orientation.Horizontal)
        top_split.setHandleWidth(1)
        top_split.setStyleSheet(_SPLITTER_STYLE)

        # Left — form fields
        form_widget = QWidget()
        form_layout = QVBoxLayout(form_widget)
        form_layout.setContentsMargins(0, 0, 8, 0)
        form_layout.setSpacing(6)

        fields = QFormLayout()
        fields.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        fields.setSpacing(8)
        fields.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        self._title_input = QLineEdit()
        self._title_input.setPlaceholderText("Snippet title…")
        fields.addRow("Title", self._title_input)

        self._lang_combo = QComboBox()
        self._lang_combo.addItems(_COMMON_LANGUAGES)
        self._lang_combo.currentTextChanged.connect(self._refresh_preview)
        fields.addRow("Language", self._lang_combo)

        self._desc_input = QLineEdit()
        self._desc_input.setPlaceholderText("Short description (searchable)…")
        fields.addRow("Description", self._desc_input)

        self._tag_input = TagInput()
        fields.addRow("Tags", self._tag_input)

        form_layout.addLayout(fields)
        form_layout.addStretch()
        top_split.addWidget(form_widget)

        # Right — folder tree
        folder_widget = QWidget()
        folder_layout = QVBoxLayout(folder_widget)
        folder_layout.setContentsMargins(8, 0, 0, 0)
        folder_layout.setSpacing(4)

        folder_label = QLabel("Folder")
        folder_label.setStyleSheet(_SECTION_LABEL_STYLE)
        folder_layout.addWidget(folder_label)

        self._folder_tree = FolderTree()
        self._folder_tree.folder_selected.connect(self._on_folder_selected)
        folder_layout.addWidget(self._folder_tree, stretch=1)

        top_split.addWidget(folder_widget)
        top_split.setSizes([480, 320])
        outer.addWidget(top_split)

        # ── BOTTOM: code editor (left) | preview (right) ──────────────────
        bottom_split = QSplitter(Qt.Orientation.Horizontal)
        bottom_split.setHandleWidth(1)
        bottom_split.setStyleSheet(_SPLITTER_STYLE)

        # Left — editor
        editor_widget = QWidget()
        editor_layout = QVBoxLayout(editor_widget)
        editor_layout.setContentsMargins(0, 0, 8, 0)
        editor_layout.setSpacing(4)

        code_label = QLabel("Code")
        code_label.setStyleSheet(_SECTION_LABEL_STYLE)
        editor_layout.addWidget(code_label)

        self._editor = QPlainTextEdit()
        self._editor.setPlaceholderText("Paste or type code here…")
        self._editor.textChanged.connect(self._on_editor_changed)
        editor_layout.addWidget(self._editor, stretch=1)

        bottom_split.addWidget(editor_widget)

        # Right — preview
        preview_widget = QWidget()
        preview_layout = QVBoxLayout(preview_widget)
        preview_layout.setContentsMargins(8, 0, 0, 0)
        preview_layout.setSpacing(4)

        preview_label = QLabel("Preview")
        preview_label.setStyleSheet(_SECTION_LABEL_STYLE)
        preview_layout.addWidget(preview_label)

        self._preview = CodePreview()
        preview_layout.addWidget(self._preview, stretch=1)

        bottom_split.addWidget(preview_widget)
        bottom_split.setSizes([400, 400])
        outer.addWidget(bottom_split)

        outer.setSizes([220, 340])

        # ── Validation warning ─────────────────────────────────────────────
        self._warning_label = QLabel("")
        self._warning_label.setStyleSheet("color: #f44747; font-size: 12px; padding: 2px 0;")
        self._warning_label.hide()
        root.addWidget(self._warning_label)

        # ── Buttons ────────────────────────────────────────────────────────
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        save_btn = buttons.button(QDialogButtonBox.StandardButton.Save)
        if save_btn:
            save_btn.setText("Save  ⌘↩")
        cancel_btn = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_btn:
            cancel_btn.setStyleSheet(
                "background: #3c3c3c; color: #cccccc; border: 1px solid #555555;"
            )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_folder_selected(self, folder_id: int) -> None:
        self._selected_folder_id = folder_id if folder_id != -1 else None

    def _on_editor_changed(self) -> None:
        if not self._warning_label.isHidden():
            self._warning_label.hide()
        self._refresh_preview()

    def _refresh_preview(self) -> None:
        code = self._editor.toPlainText()
        lang = self._lang_combo.currentText()
        self._preview.show_snippet(code, lang)

    def _load_folders_and_tags(self) -> None:
        with get_session() as session:
            folders = session.query(Folder).order_by(Folder.name).all()
            all_tags = [t.name for t in session.query(Tag).order_by(Tag.name).all()]
        self._folder_tree.load_folders(folders)
        self._tag_input.set_suggestions(all_tags)

    def _save(self) -> None:
        title = self._title_input.text().strip() or "Untitled"
        body = self._editor.toPlainText()
        language = self._lang_combo.currentText()
        description = self._desc_input.text().strip()
        tag_names = self._tag_input.get_tags()

        if not body.strip():
            self._warning_label.setText("⚠  Code body cannot be empty.")
            self._warning_label.show()
            self._editor.setFocus()
            return

        with get_session() as session:
            if self._editing_id is not None:
                snippet = session.get(Snippet, self._editing_id)
                if snippet is None:
                    logger.warning("Edit target snippet %d not found.", self._editing_id)
                    self._reset_mode()
                    self.reject()
                    return
                snippet.title = title
                snippet.body = body
                snippet.language = language
                snippet.description = description
                snippet.folder_id = self._selected_folder_id
                snippet.tags.clear()
                for name in tag_names:
                    tag = session.query(Tag).filter_by(name=name).first()
                    if tag is None:
                        tag = Tag(name=name)
                        session.add(tag)
                    snippet.tags.append(tag)
                session.commit()
                logger.info("Updated snippet '%s' (id=%d).", snippet.title, snippet.id)
            else:
                snippet = Snippet(
                    title=title,
                    body=body,
                    language=language,
                    description=description,
                    folder_id=self._selected_folder_id,
                )
                for name in tag_names:
                    tag = session.query(Tag).filter_by(name=name).first()
                    if tag is None:
                        tag = Tag(name=name)
                        session.add(tag)
                    snippet.tags.append(tag)
                session.add(snippet)
                session.commit()
                logger.info("Saved snippet '%s' (id=%d).", snippet.title, snippet.id)

        self._reset_mode()
        self.accept()

    def reject(self) -> None:
        self._reset_mode()
        super().reject()

    # ------------------------------------------------------------------
    # Keyboard shortcuts
    # ------------------------------------------------------------------

    def keyPressEvent(self, event: object) -> None:
        from PySide6.QtGui import QKeyEvent

        e: QKeyEvent = event  # type: ignore[assignment]
        mods = e.modifiers()
        key = e.key()
        if (
            key in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
            and mods & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier)
        ):
            self._save()
        else:
            super().keyPressEvent(e)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _reset_mode(self) -> None:
        """Switch back to create-new-snippet mode."""
        self._editing_id = None
        self.setWindowTitle("Save Snippet — ByteSnip")

    def _center_on_screen(self) -> None:
        from PySide6.QtGui import QGuiApplication

        screen = QGuiApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            self.move(
                geo.center().x() - self.width() // 2,
                geo.center().y() - self.height() // 2,
            )


def _default_title(text: str) -> str:
    first_line = text.strip().splitlines()[0] if text.strip() else ""
    return first_line[:80] or "Untitled"
