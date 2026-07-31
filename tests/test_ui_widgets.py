from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QSizePolicy

from recruitment_ledger.styles import APP_STYLESHEET
from recruitment_ledger.ui.widgets import StatisticCard


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
