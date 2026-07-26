from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..services import ApplicationService


class RecycleBinDialog(QDialog):
    changed = Signal()

    def __init__(
        self,
        service: ApplicationService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.setWindowTitle("回收站")
        self.resize(760, 470)
        layout = QVBoxLayout(self)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["公司名称", "岗位名称", "当前进度", "最后更新", "操作"]
        )
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.button(QDialogButtonBox.Close).setText("关闭")
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.refresh()

    def refresh(self) -> None:
        records = self.service.list_deleted()
        self.table.setRowCount(len(records))
        for row, record in enumerate(records):
            for column, value in enumerate(
                (record.company_name, record.position_name, record.status, record.updated_at)
            ):
                self.table.setItem(row, column, QTableWidgetItem(value))
            actions = QWidget()
            action_layout = QHBoxLayout(actions)
            action_layout.setContentsMargins(2, 2, 2, 2)
            restore_button = QPushButton("恢复")
            delete_button = QPushButton("永久删除")
            delete_button.setProperty("danger", True)
            action_layout.addWidget(restore_button)
            action_layout.addWidget(delete_button)
            if record.id is not None:
                restore_button.clicked.connect(
                    lambda checked=False, application_id=record.id: self._restore(
                        application_id
                    )
                )
                delete_button.clicked.connect(
                    lambda checked=False, application_id=record.id: self._delete(
                        application_id
                    )
                )
            self.table.setCellWidget(row, 4, actions)
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setStretchLastSection(True)

    def _restore(self, application_id: int) -> None:
        try:
            self.service.restore(application_id)
        except RuntimeError as exc:
            QMessageBox.critical(self, "恢复失败", str(exc))
            return
        self.changed.emit()
        self.refresh()

    def _delete(self, application_id: int) -> None:
        answer = QMessageBox.warning(
            self,
            "确认永久删除",
            "永久删除后无法恢复,且对应状态历史会一并删除。是否继续?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        try:
            self.service.permanently_delete(application_id)
        except RuntimeError as exc:
            QMessageBox.critical(self, "永久删除失败", str(exc))
            return
        self.changed.emit()
        self.refresh()

