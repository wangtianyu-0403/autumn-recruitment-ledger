from __future__ import annotations


APP_STYLESHEET = """
QMainWindow, QDialog, QWidget {
    background: #F7F8FA;
    color: #263238;
}
QToolBar {
    background: #FFFFFF;
    border: none;
    border-bottom: 1px solid #E1E5EA;
    spacing: 6px;
    padding: 8px;
}
QPushButton, QToolButton {
    background: #FFFFFF;
    border: 1px solid #C9D1D9;
    border-radius: 5px;
    padding: 6px 12px;
    min-height: 22px;
}
QPushButton:hover, QToolButton:hover {
    border-color: #4E7AA8;
    background: #F0F6FC;
}
QPushButton:disabled, QToolButton:disabled {
    color: #9AA4AF;
    background: #F1F3F5;
}
QPushButton[primary="true"], QToolButton[primary="true"] {
    color: #FFFFFF;
    background: #3D6F9E;
    border-color: #3D6F9E;
}
QPushButton[primary="true"]:hover, QToolButton[primary="true"]:hover {
    background: #315E87;
}
QPushButton[danger="true"] {
    color: #9F2D2D;
    border-color: #D9A1A1;
    background: #FFF7F7;
}
QLineEdit, QComboBox, QDateEdit, QPlainTextEdit {
    background: #FFFFFF;
    border: 1px solid #C9D1D9;
    border-radius: 5px;
    padding: 5px 7px;
    selection-background-color: #6B93B8;
}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QPlainTextEdit:focus {
    border: 1px solid #3D6F9E;
}
QTableWidget {
    background: #FFFFFF;
    alternate-background-color: #F8FAFC;
    border: 1px solid #DEE3E8;
    border-radius: 6px;
    gridline-color: #E9EDF1;
}
QHeaderView::section {
    background: #EEF2F6;
    color: #354052;
    border: none;
    border-right: 1px solid #DDE3E9;
    border-bottom: 1px solid #D4DBE2;
    padding: 7px;
    font-weight: 600;
}
QTableWidget::item:selected {
    background: #DDEAF6;
    color: #1F2933;
}
QLabel[card="true"] {
    background: #FFFFFF;
    border: 1px solid #E0E5EA;
    border-radius: 8px;
    padding: 12px;
}
QStatusBar {
    background: #FFFFFF;
    border-top: 1px solid #E1E5EA;
}
"""

