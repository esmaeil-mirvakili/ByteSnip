"""Picker window: spotlight-style snippet browser (Cmd+Shift+`)."""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, QRect, QSize, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QKeySequence, QPainter, QPainterPath, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QSplitter,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from sqlalchemy.sql import func as sql_func

from snipapp.core.clipboard import copy_text
from snipapp.core.db import get_session
from snipapp.core.models import Folder, Snippet, Tag
from snipapp.core.search import search_snippets
from snipapp.ui.components.snippet_detail import SnippetDetail
from snipapp.ui.components.tag_input import _chip_color

logger = logging.getLogger(__name__)

_SEARCH_DEBOUNCE_MS = 80
_META_ROLE = Qt.ItemDataRole.UserRole + 1  # subtitle string for each list item

_SIDEBAR_LABEL_STYLE = (
    "QLabel { font-size: 10px; font-weight: bold; color: #555555;"
    " text-transform: uppercase; padding: 6px 10px 3px; }"
)
_SIDEBAR_LIST_STYLE = (
    "QListWidget {"
    "  background: transparent; border: none; outline: none;"
    "  font-size: 12px;"
    "}"
    "QListWidget::item { padding: 2px 6px; border-radius: 4px; }"
    "QListWidget::item:selected { background: #1a3a5c; }"
    "QListWidget::item:hover { background: #2a2d2e; }"
)

_SIDEBAR_TREE_STYLE = (
    "QTreeWidget {"
    "  background: transparent; border: none; outline: none; color: #cccccc;"
    "  font-size: 12px;"
    "}"
    "QTreeWidget::item { padding: 4px 4px; border-radius: 4px; color: #cccccc; }"
    "QTreeWidget::item:selected { background: #094771; color: #ffffff; }"
    "QTreeWidget::item:hover { background: #2a2d2e; }"
    # Keep branch background transparent; native Qt style paints the expand triangle
    "QTreeWidget::branch { background: transparent; }"
)


class _FolderTreeDelegate(QStyledItemDelegate):
    """Draws folder tree items with a folder icon prefix and a coloured expand arrow."""

    _ARROW_CLR = QColor("#5a7fa8")
    _LINE_CLR = QColor("#2d3d4d")
    _FOLDER_CLR = QColor("#c8a84b")

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        painter.save()
        r = option.rect
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)

        if selected:
            painter.fillRect(r, QColor("#094771"))
        elif hovered:
            painter.fillRect(r, QColor("#2a2d2e"))

        # Folder icon (small coloured square with ear, drawn as text emoji)
        icon_x = r.x() + 4
        icon_y = r.y()
        f_icon = QFont(option.font)
        f_icon.setPointSizeF(max(9.0, f_icon.pointSizeF() * 0.9))
        painter.setFont(f_icon)
        painter.setPen(self._FOLDER_CLR)
        painter.drawText(
            QRect(icon_x, icon_y, 18, r.height()),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            "📁",
        )

        # Item text
        text = index.data(Qt.ItemDataRole.DisplayRole) or ""
        painter.setFont(option.font)
        painter.setPen(QColor("#ffffff") if selected else QColor("#cccccc"))
        painter.drawText(
            QRect(r.x() + 22, r.y(), r.width() - 26, r.height()),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            text,
        )
        painter.restore()

    def sizeHint(self, _option: QStyleOptionViewItem, _index) -> QSize:
        return QSize(100, 26)


class _TagSidebarDelegate(QStyledItemDelegate):
    """Renders each tag as a coloured pill in the sidebar tag list."""

    _H = 28

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        tag = index.data(Qt.ItemDataRole.DisplayRole) or ""
        bg_hex, fg_hex = _chip_color(tag)

        painter.save()
        r = option.rect

        # Subtle row highlight when selected
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(r, QColor("#1a3a5c"))

        # Pill
        mx, my = 6, 4
        chip_x = float(r.x() + mx)
        chip_y = float(r.y() + my)
        chip_w = float(r.width() - 2 * mx)
        chip_h = float(r.height() - 2 * my)
        path = QPainterPath()
        path.addRoundedRect(chip_x, chip_y, chip_w, chip_h, 9.0, 9.0)
        painter.fillPath(path, QColor(bg_hex))

        f = QFont(option.font)
        f.setPointSizeF(max(8.0, f.pointSizeF() * 0.83))
        painter.setFont(f)
        painter.setPen(QColor(fg_hex))
        from PySide6.QtCore import QRectF
        painter.drawText(
            QRectF(chip_x, chip_y, chip_w, chip_h),
            Qt.AlignmentFlag.AlignCenter,
            tag,
        )
        painter.restore()

    def sizeHint(self, _option: QStyleOptionViewItem, _index) -> QSize:
        return QSize(100, self._H)


class _SnippetDelegate(QStyledItemDelegate):
    """Renders snippet list items with title on top and language/tags below."""

    _H = 52

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        painter.save()
        r = option.rect
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)

        if selected:
            painter.fillRect(r, QColor("#094771"))
        elif hovered:
            painter.fillRect(r, QColor("#2a2d2e"))
        else:
            painter.fillRect(r, QColor("#1e1e1e"))

        px = 12
        aw = r.width() - 2 * px

        painter.setPen(QColor("#e0e0e0") if selected else QColor("#cccccc"))
        painter.setFont(option.font)
        painter.drawText(
            QRect(r.x() + px, r.y() + 8, aw, 20),
            Qt.TextFlag.TextSingleLine | Qt.AlignmentFlag.AlignVCenter,
            index.data(Qt.ItemDataRole.DisplayRole) or "",
        )

        meta = index.data(_META_ROLE) or ""
        if meta:
            mf = QFont(option.font)
            mf.setPointSizeF(max(8.0, mf.pointSizeF() * 0.83))
            painter.setFont(mf)
            painter.setPen(QColor("#9a9a9a") if selected else QColor("#606060"))
            painter.drawText(
                QRect(r.x() + px, r.y() + 31, aw, 15),
                Qt.TextFlag.TextSingleLine | Qt.AlignmentFlag.AlignVCenter,
                meta,
            )

        painter.restore()

    def sizeHint(self, _option: QStyleOptionViewItem, _index) -> QSize:
        return QSize(100, self._H)


class PickerWindow(QWidget):
    """Frameless, always-on-top picker window."""

    edit_requested = Signal(int)  # emits snippet_id

    def __init__(self) -> None:
        super().__init__()
        self._current_folder_id: int | None = None
        self._current_tag_filter: str | None = None
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self._run_search)
        self._close_timer = QTimer(self)
        self._close_timer.setSingleShot(True)
        self._close_timer.timeout.connect(self.hide)
        self._setup_window()
        self._setup_ui()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show_and_focus(self) -> None:
        self._search_box.clear()
        self._current_folder_id = None
        self._current_tag_filter = None
        self._status_label.setText("")
        self._load_sidebar()
        self._run_search()
        self.show()
        self.raise_()
        self.activateWindow()
        self._search_box.setFocus()

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _setup_window(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(1000, 580)
        self._center_on_screen()

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)

        container = QFrame()
        container.setObjectName("pickerContainer")
        container.setStyleSheet(
            "QFrame#pickerContainer {"
            "  background: #1e1e1e;"
            "  border: 1px solid #3c3c3c;"
            "  border-radius: 12px;"
            "}"
        )
        outer.addWidget(container)

        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        # ── Content row (sidebar | divider | middle+right) ─────────────
        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        sidebar = self._build_sidebar()
        content_layout.addWidget(sidebar)

        div = QFrame()
        div.setFrameShape(QFrame.Shape.VLine)
        div.setStyleSheet("color: #2d2d2d;")
        content_layout.addWidget(div)

        split = QSplitter(Qt.Orientation.Horizontal)
        split.setHandleWidth(1)
        split.setStyleSheet(
            "QSplitter::handle { background: #2d2d2d; }"
            "QSplitter { background: transparent; }"
        )
        middle = self._build_middle()
        split.addWidget(middle)

        self._preview = SnippetDetail()
        split.addWidget(self._preview)
        split.setSizes([280, 520])

        content_layout.addWidget(split, stretch=1)
        vbox.addWidget(content, stretch=1)

        # ── Footer ────────────────────────────────────────────────────
        footer_widget = QWidget()
        footer_widget.setStyleSheet(
            "background: #181818;"
            "border-bottom-left-radius: 12px;"
            "border-bottom-right-radius: 12px;"
        )
        footer = QHBoxLayout(footer_widget)
        footer.setContentsMargins(12, 4, 12, 6)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: #4ec9b0; font-size: 11px;")
        footer.addWidget(self._status_label)
        footer.addStretch()

        hint_label = QLabel("↑↓  navigate    ↩  copy    ⌘E  edit    Del  delete    Esc  close")
        hint_label.setStyleSheet("color: #444444; font-size: 11px;")
        footer.addWidget(hint_label)
        vbox.addWidget(footer_widget)

        # Cmd+E shortcut
        edit_shortcut = QShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_E), self)
        edit_shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        edit_shortcut.activated.connect(self._open_edit)

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setFixedWidth(170)
        sidebar.setStyleSheet("background: #1a1a1a;")
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(0)

        # Folders section
        folder_label = QLabel("Folders")
        folder_label.setStyleSheet(_SIDEBAR_LABEL_STYLE)
        layout.addWidget(folder_label)

        self._folder_tree = QTreeWidget()
        self._folder_tree.setHeaderHidden(True)
        self._folder_tree.setStyleSheet(_SIDEBAR_TREE_STYLE)
        self._folder_tree.setIndentation(16)
        self._folder_tree.setRootIsDecorated(True)
        self._folder_tree.setItemDelegate(_FolderTreeDelegate(self._folder_tree))
        self._folder_tree.itemClicked.connect(self._on_folder_clicked)
        layout.addWidget(self._folder_tree, stretch=3)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #2d2d2d; margin: 4px 0;")
        layout.addWidget(sep)

        # Tags section
        tag_label = QLabel("Tags")
        tag_label.setStyleSheet(_SIDEBAR_LABEL_STYLE)
        layout.addWidget(tag_label)

        self._tag_list = QListWidget()
        self._tag_list.setStyleSheet(_SIDEBAR_LIST_STYLE)
        self._tag_list.setItemDelegate(_TagSidebarDelegate(self._tag_list))
        self._tag_list.itemClicked.connect(self._on_tag_clicked)
        layout.addWidget(self._tag_list, stretch=2)

        return sidebar

    def _build_middle(self) -> QWidget:
        middle = QWidget()
        layout = QVBoxLayout(middle)
        layout.setContentsMargins(10, 10, 6, 10)
        layout.setSpacing(8)

        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText("Search snippets…")
        self._search_box.setStyleSheet(
            "QLineEdit {"
            "  background: #2d2d2d; border: 1px solid #555555; border-radius: 6px;"
            "  padding: 7px 12px; color: #e8e8e8; font-size: 13px;"
            "  selection-background-color: #094771;"
            "}"
            "QLineEdit:focus { border: 1px solid #007acc; }"
        )
        self._search_box.textChanged.connect(self._on_search_text_changed)
        layout.addWidget(self._search_box)

        self._list = QListWidget()
        self._list.setItemDelegate(_SnippetDelegate(self._list))
        self._list.setMouseTracking(True)
        self._list.viewport().setMouseTracking(True)
        self._list.setStyleSheet(
            "QListWidget { background: transparent; border: none; outline: none; }"
            "QListWidget::item { border-bottom: 1px solid #252525; }"
        )
        self._list.currentItemChanged.connect(self._on_selection_changed)
        layout.addWidget(self._list, stretch=1)

        return middle

    # ------------------------------------------------------------------
    # Sidebar loading
    # ------------------------------------------------------------------

    def _load_sidebar(self) -> None:
        with get_session() as session:
            folders = session.query(Folder).order_by(Folder.name).all()
            folder_data = [(f.id, f.parent_id, f.name) for f in folders]
            tag_names = [t.name for t in session.query(Tag).order_by(Tag.name).all()]

        # ── Folder tree ───────────────────────────────────────────────
        self._folder_tree.clear()

        root_item = QTreeWidgetItem(["Root"])
        root_item.setData(0, Qt.ItemDataRole.UserRole, None)
        self._folder_tree.addTopLevelItem(root_item)

        id_to_item: dict[int, QTreeWidgetItem] = {}
        for fid, _parent_id, name in folder_data:
            item = QTreeWidgetItem([name])
            item.setData(0, Qt.ItemDataRole.UserRole, fid)
            id_to_item[fid] = item

        for fid, parent_id, _name in folder_data:
            item = id_to_item[fid]
            if parent_id and parent_id in id_to_item:
                id_to_item[parent_id].addChild(item)
            else:
                self._folder_tree.addTopLevelItem(item)

        self._folder_tree.expandAll()
        self._folder_tree.setCurrentItem(root_item)

        # ── Tags list ─────────────────────────────────────────────────
        self._tag_list.clear()
        for name in tag_names:
            self._tag_list.addItem(name)

    # ------------------------------------------------------------------
    # Search & navigation
    # ------------------------------------------------------------------

    def _on_search_text_changed(self, _text: str) -> None:
        self._debounce.start(_SEARCH_DEBOUNCE_MS)

    def _on_folder_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        self._current_folder_id = item.data(0, Qt.ItemDataRole.UserRole)
        self._run_search()

    def _on_tag_clicked(self, item: QListWidgetItem) -> None:
        tag_name = item.text()
        if self._current_tag_filter == tag_name:
            self._current_tag_filter = None
            self._tag_list.clearSelection()
        else:
            self._current_tag_filter = tag_name
        self._run_search()

    def _run_search(self) -> None:
        query = self._search_box.text()
        with get_session() as session:
            results = search_snippets(
                session, query, self._current_folder_id, self._current_tag_filter
            )
            items = [
                (r.snippet.id, r.snippet.title, r.snippet.language or "text", len(r.snippet.tags))
                for r in results
            ]

        self._list.clear()
        if not items:
            placeholder = QListWidgetItem("  No snippets found")
            placeholder.setForeground(QColor("#555555"))
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            self._list.addItem(placeholder)
            self._preview.clear_preview()
            return

        for snippet_id, title, language, tags_count in items:
            item = QListWidgetItem(title)
            item.setData(Qt.ItemDataRole.UserRole, snippet_id)
            meta_parts = [language]
            if tags_count:
                meta_parts.append(f"{tags_count} tag{'s' if tags_count != 1 else ''}")
            item.setData(_META_ROLE, "  ·  ".join(meta_parts))
            self._list.addItem(item)

        self._list.setCurrentRow(0)

    def _on_selection_changed(self, current: QListWidgetItem | None, _previous: object) -> None:
        if current is None:
            self._preview.clear_preview()
            return
        snippet_id = current.data(Qt.ItemDataRole.UserRole)
        if snippet_id is None:
            self._preview.clear_preview()
            return
        with get_session() as session:
            snippet = session.get(Snippet, snippet_id)
            if snippet is None:
                self._preview.clear_preview()
                return
            body = snippet.body
            language = snippet.language or "text"
            description = snippet.description or ""
            title = snippet.title
            tags = [t.name for t in snippet.tags]
        self._preview.show_snippet(body, language, description, title=title, tags=tags)

    # ------------------------------------------------------------------
    # Key handling
    # ------------------------------------------------------------------

    def keyPressEvent(self, event: object) -> None:
        from PySide6.QtGui import QKeyEvent

        e: QKeyEvent = event  # type: ignore[assignment]
        key = e.key()

        if key == Qt.Key.Key_Escape:
            self.hide()
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._copy_selected()
        elif key == Qt.Key.Key_Down:
            self._move_list(1)
        elif key == Qt.Key.Key_Up:
            self._move_list(-1)
        elif key == Qt.Key.Key_Delete:
            self._delete_selected()
        else:
            super().keyPressEvent(e)

    def _copy_selected(self) -> None:
        item = self._list.currentItem()
        if item is None:
            return
        snippet_id = item.data(Qt.ItemDataRole.UserRole)
        if snippet_id is None:
            return
        with get_session() as session:
            snippet = session.get(Snippet, snippet_id)
            if snippet:
                copy_text(snippet.body)
                snippet.use_count += 1
                snippet.last_used_at = sql_func.now()
                session.commit()
        logger.debug("Copied snippet %d to clipboard.", snippet_id)
        self._status_label.setText("✓  Copied!")
        self._close_timer.start(450)

    def _delete_selected(self) -> None:
        item = self._list.currentItem()
        if item is None:
            return
        snippet_id = item.data(Qt.ItemDataRole.UserRole)
        if snippet_id is None:
            return
        title = item.data(Qt.ItemDataRole.DisplayRole) or "this snippet"

        box = QMessageBox(self)
        box.setWindowTitle("Delete Snippet")
        box.setText(f"Delete <b>{title}</b>?")
        box.setInformativeText("This cannot be undone.")
        box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel
        )
        box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        box.setIcon(QMessageBox.Icon.Warning)
        if box.exec() != QMessageBox.StandardButton.Yes:
            return

        with get_session() as session:
            snippet = session.get(Snippet, snippet_id)
            if snippet:
                session.delete(snippet)
                session.commit()

        logger.debug("Deleted snippet %d.", snippet_id)
        self._preview.clear_preview()
        self._run_search()

    def _open_edit(self) -> None:
        item = self._list.currentItem()
        if item is None:
            return
        snippet_id = item.data(Qt.ItemDataRole.UserRole)
        if snippet_id is None:
            return
        self.hide()
        self.edit_requested.emit(snippet_id)

    def _move_list(self, delta: int) -> None:
        count = self._list.count()
        if count == 0:
            return
        row = self._list.currentRow() + delta
        row = max(0, min(row, count - 1))
        self._list.setCurrentRow(row)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _center_on_screen(self) -> None:
        from PySide6.QtGui import QGuiApplication

        screen = QGuiApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            self.move(
                geo.center().x() - self.width() // 2,
                geo.center().y() - self.height() // 2,
            )
