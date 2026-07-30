from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialogButtonBox, QMessageBox

from autumn_ledger.backup import BackupManager
from autumn_ledger.models import ApplicationRecord
from autumn_ledger.paths import AppPaths
from autumn_ledger.services import ApplicationService
from autumn_ledger.ui.application_dialog import ApplicationDialog
from autumn_ledger.ui.main_window import MainWindow


def test_main_window_contains_required_controls(
    qtbot,
    service: ApplicationService,
    app_paths: AppPaths,
    database,
) -> None:
    service.create(
        ApplicationRecord(
            company_name="示例科技",
            position_name="Python 开发工程师",
            application_date="2026-07-26",
            status="已投递",
        )
    )
    window = MainWindow(service, BackupManager(database, app_paths), app_paths)
    qtbot.addWidget(window)
    window.show()

    assert window.add_button.text() == "新增公司/岗位"
    assert window.search_edit.placeholderText()
    assert window.status_filter.itemText(0) == "全部状态"
    assert window.table.rowCount() == 1
    assert window.version_label.objectName() == "versionLabel"
    assert window.version_label.text() == "版本v1.0.0"
    assert window.statusBar().isAncestorOf(window.version_label)


def test_application_dialog_can_be_created(qtbot) -> None:
    dialog = ApplicationDialog()
    qtbot.addWidget(dialog)

    assert dialog.windowTitle() == "新增公司/岗位"
    assert dialog.company_edit.objectName() == "company_name"
    assert dialog.position_edit.objectName() == "position_name"


def test_application_dialog_blocks_empty_required_fields(
    qtbot, monkeypatch
) -> None:
    warnings: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda parent, title, message: warnings.append(message),
    )
    dialog = ApplicationDialog()
    qtbot.addWidget(dialog)
    save_button = dialog.findChild(QDialogButtonBox).button(
        QDialogButtonBox.StandardButton.Save
    )

    qtbot.mouseClick(save_button, Qt.MouseButton.LeftButton)

    assert dialog.result() == 0
    assert warnings
    assert "公司名称不能为空" in warnings[0]
