from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QSizePolicy

from recruitment_ledger.styles import APP_STYLESHEET
from recruitment_ledger.ui.widgets import ActionCell, StatisticCard


def test_action_cell_emits_pin_request_for_the_opposite_state(qtbot) -> None:
    cell = ActionCell(application_id=7, is_pinned=False)
    qtbot.addWidget(cell)

    with qtbot.waitSignal(cell.pin_requested) as signal:
        qtbot.mouseClick(cell.pin_button, Qt.MouseButton.LeftButton)

    assert signal.args == [7, True]
    assert cell.pin_button.text() == "置顶"


def test_pinned_action_cell_requests_unpin_and_keeps_existing_actions(qtbot) -> None:
    cell = ActionCell(application_id=7, is_pinned=True)
    qtbot.addWidget(cell)
    edit_requests: list[int] = []
    history_requests: list[int] = []
    delete_requests: list[int] = []
    cell.edit_requested.connect(edit_requests.append)
    cell.history_requested.connect(history_requests.append)
    cell.delete_requested.connect(delete_requests.append)

    with qtbot.waitSignal(cell.pin_requested) as signal:
        qtbot.mouseClick(cell.pin_button, Qt.MouseButton.LeftButton)
    for button in (cell.edit_button, cell.history_button, cell.delete_button):
        qtbot.mouseClick(button, Qt.MouseButton.LeftButton)

    assert signal.args == [7, False]
    assert cell.pin_button.text() == "取消置顶"
    assert edit_requests == [7]
    assert history_requests == [7]
    assert delete_requests == [7]


def test_statistic_card_uses_compact_fixed_geometry(qtbot) -> None:
    card = StatisticCard("全部岗位")
    qtbot.addWidget(card)

    margins = card.layout().contentsMargins()
    assert card.minimumHeight() == 90
    assert card.maximumHeight() == 90
    assert card.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Expanding
    assert card.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Fixed
    assert (margins.left(), margins.top(), margins.right(), margins.bottom()) == (
        16,
        12,
        16,
        12,
    )
    assert card.layout().spacing() == 4
    assert card.layout().stretch(card.layout().count() - 1) == 1


def test_application_stylesheet_renders_white_statistic_card(qtbot, qapp) -> None:
    previous_stylesheet = qapp.styleSheet()
    try:
        qapp.setStyleSheet(APP_STYLESHEET)
        card = StatisticCard("全部岗位")
        card.resize(240, 90)
        qtbot.addWidget(card)
        card.show()
        qapp.processEvents()

        image = card.grab().toImage()
        assert image.pixelColor(8, card.height() - 8) == QColor("#FFFFFF")
    finally:
        qapp.setStyleSheet(previous_stylesheet)
