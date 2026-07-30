from __future__ import annotations

from PySide6.QtWidgets import QSizePolicy

from autumn_ledger.ui.widgets import StatisticCard


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
