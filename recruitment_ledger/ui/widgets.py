from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class StatisticCard(QWidget):
    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("card", True)
        self.setFixedHeight(90)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)
        title_label = QLabel(title)
        title_label.setStyleSheet("color: #667085; font-size: 13px;")
        self.value_label = QLabel("0")
        self.value_label.setStyleSheet(
            "font-size: 24px; font-weight: 700; color: #274C6B;"
        )
        layout.addWidget(title_label)
        layout.addWidget(self.value_label)
        layout.addStretch(1)

    def set_value(self, value: int) -> None:
        self.value_label.setText(str(value))


class ActionCell(QWidget):
    edit_requested = Signal(int)
    history_requested = Signal(int)
    delete_requested = Signal(int)
    pin_requested = Signal(int, bool)

    def __init__(
        self,
        application_id: int,
        is_pinned: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(3, 2, 3, 2)
        layout.setSpacing(4)
        self.pin_button = QPushButton("取消置顶" if is_pinned else "置顶")
        self.edit_button = QPushButton("编辑")
        self.history_button = QPushButton("历史")
        self.delete_button = QPushButton("删除")
        self.delete_button.setProperty("danger", True)
        for button in (
            self.pin_button,
            self.edit_button,
            self.history_button,
            self.delete_button,
        ):
            button.setMinimumWidth(46)
            button.setFocusPolicy(Qt.NoFocus)
            layout.addWidget(button)
        self.pin_button.setMinimumWidth(62)
        self.pin_button.clicked.connect(
            lambda: self.pin_requested.emit(application_id, not is_pinned)
        )
        self.edit_button.clicked.connect(
            lambda: self.edit_requested.emit(application_id)
        )
        self.history_button.clicked.connect(
            lambda: self.history_requested.emit(application_id)
        )
        self.delete_button.clicked.connect(
            lambda: self.delete_requested.emit(application_id)
        )
