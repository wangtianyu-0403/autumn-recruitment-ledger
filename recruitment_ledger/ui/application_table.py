from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDropEvent
from PySide6.QtWidgets import QAbstractItemView, QTableWidget, QWidget


class ApplicationTableWidget(QTableWidget):
    """A row-draggable table whose reorder signal carries application IDs."""

    rows_reordered = Signal(list)

    def __init__(
        self,
        rows: int = 0,
        columns: int = 0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(rows, columns, parent)
        self._application_ids: list[int] = []
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

    def set_application_ids(self, application_ids: Sequence[int]) -> None:
        self._application_ids = list(application_ids)
        self.setRowCount(len(self._application_ids))

    def apply_row_move(self, source_row: int, destination_row: int) -> bool:
        """Publish a logical move; the signal consumer rebuilds the owned row widgets."""
        row_count = len(self._application_ids)
        if (
            row_count != self.rowCount()
            or not 0 <= source_row < row_count
            or not 0 <= destination_row < row_count
            or source_row == destination_row
        ):
            return False

        application_id = self._application_ids.pop(source_row)
        self._application_ids.insert(destination_row, application_id)
        self.rows_reordered.emit(list(self._application_ids))
        return True

    def dropEvent(self, event: QDropEvent) -> None:
        if (
            event.source() is not self
            or event.proposedAction() == Qt.DropAction.IgnoreAction
            or len(self.selectedIndexes()) == 0
        ):
            event.ignore()
            return

        source_row = self.selectedIndexes()[0].row()
        indicator = self.dropIndicatorPosition()
        target_index = self.indexAt(event.position().toPoint())

        if indicator == QAbstractItemView.DropIndicatorPosition.OnItem:
            destination_row = target_index.row()
        elif indicator == QAbstractItemView.DropIndicatorPosition.OnViewport:
            insertion_row = self.rowCount()
            destination_row = insertion_row - (insertion_row > source_row)
        elif not target_index.isValid():
            event.ignore()
            return
        elif indicator == QAbstractItemView.DropIndicatorPosition.BelowItem:
            insertion_row = target_index.row() + 1
            destination_row = insertion_row - (insertion_row > source_row)
        else:
            insertion_row = target_index.row()
            destination_row = insertion_row - (insertion_row > source_row)

        if self.apply_row_move(source_row, destination_row):
            event.acceptProposedAction()
        else:
            event.ignore()
