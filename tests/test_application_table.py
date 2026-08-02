from __future__ import annotations

from PySide6.QtCore import QCoreApplication, QEvent, QPointF, Qt
from PySide6.QtWidgets import QAbstractItemView, QPushButton, QTableWidgetItem

from recruitment_ledger.ui.application_table import ApplicationTableWidget


class _DropEvent:
    def __init__(
        self,
        source: object,
        position: QPointF,
        action: Qt.DropAction = Qt.DropAction.MoveAction,
    ) -> None:
        self._source = source
        self._position = position
        self._action = action
        self.accepted = False
        self.ignored = False

    def source(self) -> object:
        return self._source

    def position(self) -> QPointF:
        return self._position

    def proposedAction(self) -> Qt.DropAction:
        return self._action

    def acceptProposedAction(self) -> None:
        self.accepted = True

    def ignore(self) -> None:
        self.ignored = True


def _populated_table(qtbot) -> ApplicationTableWidget:
    table = ApplicationTableWidget(0, 2)
    qtbot.addWidget(table)
    table.set_application_ids([40, 10, 30])
    for row, application_id in enumerate((40, 10, 30)):
        table.setItem(row, 0, QTableWidgetItem(f"公司 {application_id}"))
        table.setCellWidget(row, 1, QPushButton(f"操作 {application_id}"))
    table.resize(400, 260)
    table.show()
    return table


def test_table_is_configured_for_single_row_internal_moves(qtbot) -> None:
    table = ApplicationTableWidget()
    qtbot.addWidget(table)

    assert table.dragDropMode() == QAbstractItemView.DragDropMode.InternalMove
    assert table.selectionBehavior() == QAbstractItemView.SelectionBehavior.SelectRows
    assert table.selectionMode() == QAbstractItemView.SelectionMode.SingleSelection
    assert table.dragEnabled()
    assert table.acceptDrops()
    assert table.showDropIndicator()


def test_apply_row_move_emits_ids_without_reparenting_owned_cell_widgets(
    qtbot, qapp
) -> None:
    table = _populated_table(qtbot)
    source_action = table.cellWidget(0, 1)
    clicks: list[bool] = []
    source_action.clicked.connect(lambda: clicks.append(True))

    with qtbot.waitSignal(table.rows_reordered) as signal:
        assert table.apply_row_move(0, 2)

    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qapp.processEvents()

    assert signal.args == [[10, 30, 40]]
    assert [table.item(row, 0).text() for row in range(3)] == [
        "公司 40",
        "公司 10",
        "公司 30",
    ]
    assert [table.cellWidget(row, 1).text() for row in range(3)] == [
        "操作 40",
        "操作 10",
        "操作 30",
    ]
    assert table.cellWidget(0, 1) is source_action
    source_action.click()
    assert clicks == [True]


def test_apply_row_move_rejects_invalid_or_unchanged_moves_without_signal(qtbot) -> None:
    table = _populated_table(qtbot)
    emissions: list[list[int]] = []
    table.rows_reordered.connect(emissions.append)

    assert not table.apply_row_move(-1, 1)
    assert not table.apply_row_move(0, 3)
    assert not table.apply_row_move(1, 1)

    assert emissions == []
    assert [table.item(row, 0).text() for row in range(3)] == [
        "公司 40",
        "公司 10",
        "公司 30",
    ]


def test_drop_below_a_later_row_adjusts_for_source_removal(qtbot, monkeypatch) -> None:
    table = _populated_table(qtbot)
    table.selectRow(0)
    target = table.visualItemRect(table.item(2, 0)).center()
    monkeypatch.setattr(
        table,
        "dropIndicatorPosition",
        lambda: QAbstractItemView.DropIndicatorPosition.BelowItem,
    )
    event = _DropEvent(table, QPointF(target))

    with qtbot.waitSignal(table.rows_reordered) as signal:
        table.dropEvent(event)

    assert signal.args == [[10, 30, 40]]
    assert event.accepted
    assert not event.ignored


def test_drop_onto_a_later_row_uses_that_final_row(qtbot, monkeypatch) -> None:
    table = _populated_table(qtbot)
    table.selectRow(0)
    target = table.visualItemRect(table.item(2, 0)).center()
    monkeypatch.setattr(
        table,
        "dropIndicatorPosition",
        lambda: QAbstractItemView.DropIndicatorPosition.OnItem,
    )
    event = _DropEvent(table, QPointF(target))

    with qtbot.waitSignal(table.rows_reordered) as signal:
        table.dropEvent(event)

    assert signal.args == [[10, 30, 40]]


def test_drop_on_empty_viewport_moves_row_to_end(qtbot, monkeypatch) -> None:
    table = _populated_table(qtbot)
    table.selectRow(0)
    monkeypatch.setattr(
        table,
        "dropIndicatorPosition",
        lambda: QAbstractItemView.DropIndicatorPosition.OnViewport,
    )
    event = _DropEvent(table, QPointF(-10, -10))

    with qtbot.waitSignal(table.rows_reordered) as signal:
        table.dropEvent(event)

    assert signal.args == [[10, 30, 40]]


def test_cancelled_or_external_drop_keeps_rows_and_does_not_emit(qtbot) -> None:
    table = _populated_table(qtbot)
    table.selectRow(0)
    emissions: list[list[int]] = []
    table.rows_reordered.connect(emissions.append)

    cancelled = _DropEvent(table, QPointF(0, 0), Qt.DropAction.IgnoreAction)
    external = _DropEvent(object(), QPointF(0, 0))
    table.dropEvent(cancelled)
    table.dropEvent(external)

    assert emissions == []
    assert cancelled.ignored
    assert external.ignored
    assert [table.item(row, 0).text() for row in range(3)] == [
        "公司 40",
        "公司 10",
        "公司 30",
    ]
