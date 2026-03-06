"""SnippetDetail widget: structured metadata + syntax-highlighted code."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import (
    QLabel,
    QLayout,
    QLayoutItem,
    QSizePolicy,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from snipapp.core.highlight import render_html
from snipapp.ui.components.tag_input import _chip_color


# ---------------------------------------------------------------------------
# Flow layout (wraps children like words in a paragraph)
# ---------------------------------------------------------------------------

class _FlowLayout(QLayout):
    def __init__(self, parent: QWidget | None = None, h_gap: int = 5, v_gap: int = 5) -> None:
        super().__init__(parent)
        self._items: list[QLayoutItem] = []
        self._h_gap = h_gap
        self._v_gap = v_gap

    def addItem(self, item: QLayoutItem) -> None:  # noqa: N802
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> QLayoutItem | None:  # noqa: N802
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int) -> QLayoutItem | None:  # noqa: N802
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        return self._layout(QRect(0, 0, width, 0), dry_run=True)

    def setGeometry(self, rect: QRect) -> None:  # noqa: N802
        super().setGeometry(rect)
        self._layout(rect, dry_run=False)

    def sizeHint(self) -> QSize:  # noqa: N802
        return self.minimumSize()

    def minimumSize(self) -> QSize:  # noqa: N802
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        return size + QSize(m.left() + m.right(), m.top() + m.bottom())

    def _layout(self, rect: QRect, dry_run: bool) -> int:
        m = self.contentsMargins()
        x = rect.x() + m.left()
        y = rect.y() + m.top()
        row_h = 0
        right_edge = rect.right() - m.right()

        for item in self._items:
            w = item.sizeHint()
            if x + w.width() > right_edge and x != rect.x() + m.left():
                x = rect.x() + m.left()
                y += row_h + self._v_gap
                row_h = 0
            if not dry_run:
                item.setGeometry(QRect(QPoint(x, y), w))
            x += w.width() + self._h_gap
            row_h = max(row_h, w.height())

        return y + row_h - rect.y() + self.contentsMargins().bottom()


# ---------------------------------------------------------------------------
# Read-only tag chip (no delete button)
# ---------------------------------------------------------------------------

class _Chip(QLabel):
    def __init__(self, tag: str, parent: QWidget | None = None) -> None:
        super().__init__(tag, parent)
        bg, fg = _chip_color(tag)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(
            f"QLabel {{"
            f"  background: {bg}; color: {fg};"
            f"  border-radius: 10px; padding: 3px 10px;"
            f"  font-size: 11px;"
            f"}}"
        )


# ---------------------------------------------------------------------------
# SnippetDetail
# ---------------------------------------------------------------------------

class SnippetDetail(QWidget):
    """Shows snippet metadata (title, desc, tags, lang) + syntax-highlighted code."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def show_snippet(
        self,
        code: str,
        language: str = "text",
        description: str = "",
        title: str = "",
        tags: list[str] | None = None,
    ) -> None:
        self._title_label.setText(title)
        self._title_label.setVisible(bool(title))

        self._desc_label.setText(description)
        self._desc_label.setVisible(bool(description))

        self._set_tags(tags or [], language)
        self._code_view.setHtml(render_html(code, language))

        self._meta_panel.setVisible(bool(title or description or tags or (language and language != "text")))

    def clear_preview(self) -> None:
        self._title_label.setText("")
        self._desc_label.setText("")
        self._set_tags([], "")
        self._code_view.setHtml("")
        self._meta_panel.setVisible(False)

    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Metadata panel ────────────────────────────────────────────
        self._meta_panel = QWidget()
        self._meta_panel.setStyleSheet(
            "background: #1a1a1a; border-bottom: 1px solid #2d2d2d;"
        )
        meta_layout = QVBoxLayout(self._meta_panel)
        meta_layout.setContentsMargins(14, 12, 14, 12)
        meta_layout.setSpacing(6)

        # Title
        self._title_label = QLabel()
        self._title_label.setStyleSheet(
            "QLabel { color: #e2e2e2; font-size: 14px; font-weight: bold;"
            " background: transparent; }"
        )
        self._title_label.setWordWrap(True)
        meta_layout.addWidget(self._title_label)

        # Description
        self._desc_label = QLabel()
        self._desc_label.setStyleSheet(
            "QLabel { color: #888888; font-size: 12px; background: transparent; }"
        )
        self._desc_label.setWordWrap(True)
        meta_layout.addWidget(self._desc_label)

        # Tags row (flow layout)
        self._tags_container = QWidget()
        self._tags_container.setStyleSheet("background: transparent;")
        self._tags_flow = _FlowLayout(self._tags_container, h_gap=5, v_gap=4)
        self._tags_flow.setContentsMargins(0, 0, 0, 0)
        self._tags_container.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        meta_layout.addWidget(self._tags_container)

        # Language badge
        self._lang_badge = QLabel()
        self._lang_badge.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._lang_badge.setStyleSheet(
            "QLabel { background: #3a3a3a; color: #cccccc; border-radius: 4px;"
            " padding: 2px 8px; font-size: 10px; font-family: monospace; }"
        )
        meta_layout.addWidget(self._lang_badge)

        self._meta_panel.setVisible(False)
        root.addWidget(self._meta_panel)

        # ── Code view ─────────────────────────────────────────────────
        self._code_view = QTextBrowser()
        self._code_view.setReadOnly(True)
        self._code_view.setOpenLinks(False)
        self._code_view.setStyleSheet(
            "QTextBrowser { background: #272822; border: none; }"
        )
        root.addWidget(self._code_view, stretch=1)

    def _set_tags(self, tags: list[str], language: str) -> None:
        # Clear existing chips
        while self._tags_flow.count():
            item = self._tags_flow.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        for tag in tags:
            self._tags_flow.addWidget(_Chip(tag, self._tags_container))

        self._tags_container.setVisible(bool(tags))
        self._tags_container.updateGeometry()

        # Language badge
        show_lang = bool(language and language != "text")
        self._lang_badge.setText(language if show_lang else "")
        self._lang_badge.setVisible(show_lang)
