from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


class StatisticCard(QWidget):
    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("card", True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(2)
        title_label = QLabel(title)
        title_label.setStyleSheet("color: #667085; font-size: 13px;")
        self.value_label = QLabel("0")
        self.value_label.setStyleSheet(
            "font-size: 24px; font-weight: 700; color: #274C6B;"
        )
        layout.addWidget(title_label)
        layout.addWidget(self.value_label)

    def set_value(self, value: int) -> None:
        self.value_label.setText(str(value))


class ActionCell(QWidget):
    edit_requested = Signal(int)
    history_requested = Signal(int)
    delete_requested = Signal(int)

    def __init__(self, application_id: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(3, 2, 3, 2)
        layout.setSpacing(4)
        edit_button = QPushButton("编辑")
        history_button = QPushButton("历史")
        delete_button = QPushButton("删除")
        delete_button.setProperty("danger", True)
        for button in (edit_button, history_button, delete_button):
            button.setMinimumWidth(46)
            button.setFocusPolicy(Qt.NoFocus)
            layout.addWidget(button)
        edit_button.clicked.connect(
            lambda: self.edit_requested.emit(application_id)
        )
        history_button.clicked.connect(
            lambda: self.history_requested.emit(application_id)
        )
        delete_button.clicked.connect(
            lambda: self.delete_requested.emit(application_id)
        )
