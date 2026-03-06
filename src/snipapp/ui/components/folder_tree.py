"""FolderTree widget: a tree view of Folder hierarchy backed by the DB."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QMessageBox,
    QPushButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from snipapp.core.db import get_session
from snipapp.core.models import Folder

_ROOT_ID = -1  # sentinel for "no folder"


class FolderTree(QWidget):
    """Folder hierarchy selector with a 'New Folder' button and a Root entry."""

    folder_selected = Signal(int)  # folder id, or -1 for root/no folder

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._model = QStandardItemModel()
        self._model.setHorizontalHeaderLabels(["Folder"])

        self._view = QTreeView()
        self._view.setModel(self._model)
        self._view.setHeaderHidden(True)
        self._view.selectionModel().currentChanged.connect(self._on_selection_changed)

        self._new_btn = QPushButton("+ New Folder")
        self._new_btn.setFixedHeight(24)
        self._new_btn.clicked.connect(self._on_new_folder)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self._view, stretch=1)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(self._new_btn)
        layout.addLayout(btn_row)

        self._selected_parent_id: int | None = None  # for new-folder creation

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def load_folders(self, folders: list[Folder]) -> None:
        """Populate the tree from a flat list of Folder ORM objects."""
        self._model.clear()
        root_item = self._model.invisibleRootItem()

        # Sentinel "Root (no folder)" entry at the top
        root_sentinel = QStandardItem("Root (no folder)")
        root_sentinel.setData(_ROOT_ID, Qt.ItemDataRole.UserRole)
        root_sentinel.setEditable(False)
        root_item.appendRow(root_sentinel)

        id_to_item: dict[int, QStandardItem] = {}
        for folder in sorted(folders, key=lambda f: f.id):
            item = QStandardItem(folder.name)
            item.setData(folder.id, Qt.ItemDataRole.UserRole)
            item.setEditable(False)
            id_to_item[folder.id] = item

        for folder in folders:
            item = id_to_item[folder.id]
            if folder.parent_id and folder.parent_id in id_to_item:
                id_to_item[folder.parent_id].appendRow(item)
            else:
                root_item.appendRow(item)

        self._view.expandAll()

        # Default selection: Root
        self._view.setCurrentIndex(self._model.indexFromItem(root_sentinel))

    def select_folder_by_id(self, folder_id: int | None) -> None:
        """Select the item matching *folder_id* (None → Root sentinel)."""
        target_id = _ROOT_ID if folder_id is None else folder_id

        def _search(parent_item: QStandardItem) -> bool:
            for row in range(parent_item.rowCount()):
                child = parent_item.child(row)
                if child is None:
                    continue
                if child.data(Qt.ItemDataRole.UserRole) == target_id:
                    self._view.setCurrentIndex(self._model.indexFromItem(child))
                    return True
                if _search(child):
                    return True
            return False

        _search(self._model.invisibleRootItem())

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_selection_changed(self, current: object, _previous: object) -> None:
        item = self._model.itemFromIndex(current)  # type: ignore[arg-type]
        if item is not None:
            folder_id = item.data(Qt.ItemDataRole.UserRole)
            # Track selected parent for new-folder creation
            self._selected_parent_id = None if folder_id == _ROOT_ID else folder_id
            self.folder_selected.emit(folder_id if folder_id is not None else _ROOT_ID)

    def _on_new_folder(self) -> None:
        """Prompt for a name and create a new folder under the current selection."""
        name, ok = QInputDialog.getText(self, "New Folder", "Folder name:")
        if not ok or not name.strip():
            return

        name = name.strip()
        parent_id = self._selected_parent_id  # None → top-level, int → sub-folder

        try:
            with get_session() as session:
                folder = Folder(name=name, parent_id=parent_id)
                session.add(folder)
                session.commit()
                folders = session.query(Folder).all()
                # Detach from session before reload
                session.expunge_all()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Error", f"Could not create folder: {exc}")
            return

        self.load_folders(folders)
        self._select_folder_by_name(name, parent_id)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _select_folder_by_name(self, name: str, parent_id: int | None) -> None:
        """Select the newly created folder in the tree."""
        def _search(parent_item: QStandardItem) -> bool:
            for row in range(parent_item.rowCount()):
                child = parent_item.child(row)
                if child is None:
                    continue
                fid = child.data(Qt.ItemDataRole.UserRole)
                if child.text() == name and (
                    (parent_id is None and fid != _ROOT_ID)
                    or parent_id is not None
                ):
                    self._view.setCurrentIndex(self._model.indexFromItem(child))
                    return True
                if _search(child):
                    return True
            return False

        _search(self._model.invisibleRootItem())
