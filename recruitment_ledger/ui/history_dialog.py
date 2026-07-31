from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..models import ApplicationRecord, StatusHistoryRecord


class HistoryDialog(QDialog):
    def __init__(
        self,
        application: ApplicationRecord,
        history: list[StatusHistoryRecord],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"状态历史 - {application.company_name} / {application.position_name}")
        self.resize(700, 430)
        layout = QVBoxLayout(self)
        if not history:
            layout.addWidget(QLabel("该岗位暂无状态历史记录。"))
        else:
            table = QTableWidget(len(history), 4)
            table.setHorizontalHeaderLabels(["修改时间", "原状态", "新状态", "备注"])
            table.setEditTriggers(QTableWidget.NoEditTriggers)
            table.setSelectionBehavior(QTableWidget.SelectRows)
            table.setAlternatingRowColors(True)
            for row_index, item in enumerate(history):
                values = (
                    item.changed_at,
                    item.old_status or "初始创建",
                    item.new_status,
                    item.notes,
                )
                for column, value in enumerate(values):
                    cell = QTableWidgetItem(value)
                    cell.setFlags(cell.flags() & ~Qt.ItemIsEditable)
                    table.setItem(row_index, column, cell)
            table.resizeColumnsToContents()
            table.horizontalHeader().setStretchLastSection(True)
            layout.addWidget(table)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.button(QDialogButtonBox.Close).setText("关闭")
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

